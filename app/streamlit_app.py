from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
import streamlit as st
from dessert_ad_studio.banner_overlay import (
    BannerCopy,
    create_banner_overlay,
)
from dessert_ad_studio.demo_samples import DEMO_SAMPLES, DemoSample
from dessert_ad_studio.schemas import GenerationRequest
from pydantic import ValidationError

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
LAST_GENERATION_KEY = "last_successful_generation"
GENERATION_JOBS_KEY = "generation_jobs"
AGENTIC_RAG_RUNS_KEY = "agentic_rag_runs"
MAX_GENERATION_JOBS = 5
DOWNLOAD_IGNORE_MIN_VERSION = (1, 43, 0)
IMAGE_STRETCH_MIN_VERSION = (1, 58, 0)
PENDING_JOB_STATUSES = {"queued", "running"}
JOB_STATUS_LABELS = {
    "queued": "대기",
    "running": "생성 중",
    "succeeded": "완료",
    "failed": "실패",
}
AGENTIC_RAG_RUN_STATUS_LABELS = {
    "needs_approval": "승인 대기",
    "approved": "승인됨",
    "rejected": "거절됨",
    "completed": "완료",
    "failed": "실패",
}

PURPOSE_OPTIONS = {
    "신메뉴 출시": "new_menu",
    "시즌 이벤트": "seasonal_event",
    "할인/프로모션": "discount",
    "브랜드 인지도": "brand_awareness",
}

TONE_OPTIONS = {
    "따뜻한": "warm",
    "프리미엄": "premium",
    "발랄한": "playful",
    "깔끔한": "clean",
}

TEMPLATE_OPTIONS = {
    "코지 카페": "cozy_cafe",
    "미니멀 프리미엄": "minimal_premium",
    "귀여운 디저트": "cute_dessert",
    "시즌 이벤트": "seasonal_event",
}

REVISION_PRESETS = {
    "없음": "",
    "더 프리미엄하게": "더 프리미엄하고 고급스럽게 수정",
    "할인 강조": "할인 혜택을 더 앞에 보이게 수정",
    "문구 짧게": "문구를 더 짧고 스캔하기 쉽게 수정",
    "더 따뜻하게": "더 따뜻하고 매장 방문을 유도하는 톤으로 수정",
}

PURPOSE_LABELS_BY_VALUE = {value: label for label, value in PURPOSE_OPTIONS.items()}
TONE_LABELS_BY_VALUE = {value: label for label, value in TONE_OPTIONS.items()}
TEMPLATE_LABELS_BY_VALUE = {value: label for label, value in TEMPLATE_OPTIONS.items()}
CUSTOM_SAMPLE_LABEL = "직접 입력"
SAMPLE_OPTIONS = (CUSTOM_SAMPLE_LABEL, *(sample.label for sample in DEMO_SAMPLES))


def _sample_by_label(label: str) -> DemoSample | None:
    for sample in DEMO_SAMPLES:
        if sample.label == label:
            return sample
    return None


def _encode_uploaded_file(uploaded_file) -> str | None:
    if uploaded_file is None:
        return None
    return base64.b64encode(uploaded_file.getvalue()).decode("ascii")


def _parse_version_prefix(version: str) -> tuple[int, int, int]:
    parts: list[int] = []
    for raw_part in version.split(".")[:3]:
        digits = ""
        for character in raw_part:
            if not character.isdigit():
                break
            digits += character
        parts.append(int(digits) if digits else 0)

    while len(parts) < 3:
        parts.append(0)

    return tuple(parts[:3])


def _download_button_rerun_kwargs() -> dict[str, str]:
    if _parse_version_prefix(st.__version__) >= DOWNLOAD_IGNORE_MIN_VERSION:
        return {"on_click": "ignore"}
    return {}


def _stretch_image_kwargs() -> dict[str, bool | str]:
    if _parse_version_prefix(st.__version__) >= IMAGE_STRETCH_MIN_VERSION:
        return {"width": "stretch"}
    return {"use_column_width": True}


def _save_generation(
    request: GenerationRequest,
    result: dict,
) -> dict:
    saved_generation = {
        "request": request.model_dump(),
        "result": result,
        "analysis": result.get("product_analysis", {}),
    }
    st.session_state[LAST_GENERATION_KEY] = saved_generation
    return saved_generation


def _api_url(path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    return f"{API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def _generation_job_status_label(status: str) -> str:
    return JOB_STATUS_LABELS.get(status, status)


def _is_generation_job_pending(job: dict) -> bool:
    return job.get("status") in PENDING_JOB_STATUSES


def _merge_generation_job_status(job: dict, status: dict) -> dict:
    updated = dict(job)
    for key in (
        "status",
        "queue_backend",
        "queue_job_id",
        "request_summary",
        "response_summary",
        "error_detail",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
    ):
        if key in status:
            updated[key] = status[key]
    updated.pop("poll_error", None)
    return updated


def _agentic_rag_run_status_label(status: str) -> str:
    return AGENTIC_RAG_RUN_STATUS_LABELS.get(status, status)


def _build_agentic_rag_approval_payload(
    *,
    decision: str,
    reviewer_id: str,
    comment: str,
) -> dict[str, str]:
    payload = {"decision": decision}
    if reviewer_id.strip():
        payload["reviewer_id"] = reviewer_id.strip()
    if comment.strip():
        payload["comment"] = comment.strip()
    return payload


def _merge_agentic_rag_approval_decision(run: dict, approval: dict) -> dict:
    updated = dict(run)
    updated["status"] = approval.get("status", run.get("status", "unknown"))
    updated["next_action"] = approval.get("next_action", run.get("next_action"))
    updated["decision"] = {
        "status": approval.get("status"),
        "decision": approval.get("decision"),
        "next_action": approval.get("next_action"),
        "reviewer_id_sha256": approval.get("reviewer_id_sha256"),
        "comment_sha256": approval.get("comment_sha256"),
        "audit_persisted": approval.get("audit_persisted", False),
        "raw_inputs_committed": approval.get("raw_inputs_committed", False),
    }
    updated.pop("approval_error", None)
    return updated


def _submit_agentic_rag_approval(
    run: dict,
    *,
    decision: str,
    reviewer_id: str,
    comment: str,
) -> dict:
    run_id = str(run["run_id"])
    payload = _build_agentic_rag_approval_payload(
        decision=decision,
        reviewer_id=reviewer_id,
        comment=comment,
    )
    try:
        response = httpx.post(
            _api_url(f"/agentic-rag/runs/{run_id}/approval"),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail")
        except Exception:
            detail = None
        updated = dict(run)
        updated["approval_error"] = detail or str(exc)
        return updated
    except Exception as exc:
        updated = dict(run)
        updated["approval_error"] = str(exc)
        return updated
    return _merge_agentic_rag_approval_decision(run, response.json())


def _upsert_generation_job(
    jobs: list[dict],
    request: GenerationRequest,
    accepted: dict,
) -> list[dict]:
    job = {
        "job_id": accepted["job_id"],
        "status": accepted.get("status", "queued"),
        "status_url": accepted["status_url"],
        "queue_backend": accepted.get("queue_backend", "unknown"),
        "request": request.model_dump(),
    }
    remaining = [existing for existing in jobs if existing.get("job_id") != job["job_id"]]
    return [job, *remaining][:MAX_GENERATION_JOBS]


def _refresh_generation_job(job: dict) -> dict:
    try:
        response = httpx.get(_api_url(str(job["status_url"])), timeout=10)
        response.raise_for_status()
    except Exception as exc:
        updated = dict(job)
        updated["poll_error"] = str(exc)
        return updated
    return _merge_generation_job_status(job, response.json())


def _refresh_pending_generation_jobs(jobs: list[dict]) -> list[dict]:
    refreshed: list[dict] = []
    for job in jobs:
        if _is_generation_job_pending(job):
            refreshed.append(_refresh_generation_job(job))
        else:
            refreshed.append(job)
    return refreshed


def _render_generation_job_history(jobs: list[dict]) -> None:
    if not jobs:
        return

    st.subheader("생성 작업")
    st.button("작업 상태 새로고침", use_container_width=True)
    for job in jobs:
        status = str(job.get("status", "unknown"))
        label = _generation_job_status_label(status)
        with st.container(border=True):
            st.markdown(f"**{label}**")
            st.caption(
                f"{job.get('job_id', 'unknown')} · queue={job.get('queue_backend', 'unknown')}"
            )
            if job.get("poll_error"):
                st.warning(f"상태 조회 실패: {job['poll_error']}")
            if status == "succeeded":
                summary = job.get("response_summary") or {}
                st.success(
                    "생성 완료 · "
                    f"문구 {summary.get('copy_options_count', 'unknown')}개 · "
                    f"scorer={summary.get('template_scorer', 'unknown')}"
                )
            elif status == "failed":
                st.error(job.get("error_detail") or "생성 작업이 실패했습니다.")
            elif status == "running":
                st.info("생성 중")
            else:
                st.info("대기 중")


def _render_agentic_rag_approval_queue(runs: list[dict]) -> list[dict]:
    if not runs:
        return runs

    st.subheader("Agentic RAG 승인")
    updated_runs = list(runs)
    for index, run in enumerate(runs):
        status = str(run.get("status", "unknown"))
        with st.container(border=True):
            st.markdown(f"**{_agentic_rag_run_status_label(status)}**")
            st.caption(f"{run.get('run_id', 'unknown')} · next={run.get('next_action', 'unknown')}")
            reasons = run.get("approval_reasons") or []
            if reasons:
                st.write("승인 사유: " + ", ".join(str(reason) for reason in reasons))
            if run.get("approval_error"):
                st.error(f"승인 요청 실패: {run['approval_error']}")
            if run.get("decision"):
                decision = run["decision"]
                st.success(
                    "결정 기록: "
                    f"{decision.get('decision', decision.get('status', 'unknown'))} · "
                    f"next={decision.get('next_action', 'unknown')}"
                )
                st.caption(
                    "reviewer_hash="
                    f"{decision.get('reviewer_id_sha256') or 'none'} · "
                    f"comment_hash={decision.get('comment_sha256') or 'none'}"
                )
                continue
            if status != "needs_approval":
                st.info("승인 대기 상태가 아닙니다.")
                continue

            reviewer_id = st.text_input(
                "리뷰어 ID",
                key=f"agentic_rag_reviewer_{run.get('run_id', index)}",
            )
            comment = st.text_area(
                "승인 메모",
                key=f"agentic_rag_comment_{run.get('run_id', index)}",
            )
            approve_col, reject_col = st.columns(2)
            if approve_col.button(
                "승인",
                key=f"agentic_rag_approve_{run.get('run_id', index)}",
                use_container_width=True,
            ):
                updated_runs[index] = _submit_agentic_rag_approval(
                    run,
                    decision="approved",
                    reviewer_id=reviewer_id,
                    comment=comment,
                )
            if reject_col.button(
                "거절",
                key=f"agentic_rag_reject_{run.get('run_id', index)}",
                use_container_width=True,
            ):
                updated_runs[index] = _submit_agentic_rag_approval(
                    run,
                    decision="rejected",
                    reviewer_id=reviewer_id,
                    comment=comment,
                )
    return updated_runs


def _render_saved_generation(saved_generation: dict) -> None:
    try:
        request = GenerationRequest(**saved_generation["request"])
        result = saved_generation["result"]
        analysis = saved_generation.get("analysis") or result.get("product_analysis", {})
    except (KeyError, TypeError, ValidationError) as exc:
        st.session_state.pop(LAST_GENERATION_KEY, None)
        st.warning(f"저장된 생성 결과를 다시 표시할 수 없습니다: {exc}")
        return

    _render_result(result, request, analysis)


def _render_result(result: dict, request: GenerationRequest, analysis: dict[str, str]) -> None:
    if not analysis:
        st.warning("제품 분석 결과가 API 응답에 포함되지 않았습니다.")
        return

    st.subheader(analysis.get("label", "Product analysis"))
    with st.container(border=True):
        st.markdown(f"**{analysis.get('product_context', '제품 분석 정보 없음')}**")
        st.write(analysis.get("ad_goal", "광고 목표 정보 없음"))
        st.write(analysis.get("visual_strategy", "비주얼 전략 정보 없음"))
        st.write(analysis.get("photo_strategy", "사진 활용 전략 정보 없음"))
        st.write(analysis.get("copy_focus", "문구 전략 정보 없음"))
        st.caption(analysis.get("rendering_strategy", "렌더링 전략 정보 없음"))

    copy_options = result.get("copy_options", [])
    image_path_value = result.get("image_path")
    image_path = Path(str(image_path_value)) if image_path_value else None
    image_exists = image_path is not None and image_path.exists()

    st.subheader("대표 완성 배너")
    if request.revision_request:
        st.caption(f"수정 요청 반영: {request.revision_request}")
    if image_path is None:
        st.warning("생성 이미지 경로가 응답에 포함되지 않았습니다.")
    elif not image_exists:
        st.warning(f"이미지 파일을 찾지 못했습니다: {image_path}")
    else:
        overlay_path = None
        if copy_options:
            primary = copy_options[0]
            primary_copy = BannerCopy(
                headline=primary["headline"],
                body=primary["body"],
                call_to_action=primary["call_to_action"],
            )
            try:
                overlay_path = create_banner_overlay(
                    image_path=image_path,
                    copy=primary_copy,
                    price_text=request.price_text,
                )
            except Exception as exc:
                st.warning(
                    f"배너 오버레이 생성 중 문제가 발생했습니다. 원본 이미지를 표시합니다: {exc}"
                )
        else:
            st.warning("배너 오버레이에 사용할 광고 문구를 찾지 못했습니다.")

        if overlay_path is not None and overlay_path.exists():
            st.image(str(overlay_path), caption="대표 완성 배너", **_stretch_image_kwargs())
            st.download_button(
                "오버레이 배너 다운로드",
                data=overlay_path.read_bytes(),
                file_name=overlay_path.name,
                mime="image/png",
                **_download_button_rerun_kwargs(),
            )
        else:
            st.image(str(image_path), caption="원본 생성 이미지", **_stretch_image_kwargs())

    st.subheader("추천 광고 문구")
    if copy_options:
        for index, option in enumerate(copy_options, start=1):
            with st.container(border=True):
                st.markdown(f"**{index}. {option['headline']}**")
                st.write(option["body"])
                st.caption(option["call_to_action"])
    else:
        st.warning("추천 광고 문구가 응답에 포함되지 않았습니다.")

    if image_exists and image_path is not None:
        with st.expander("원본 생성 이미지"):
            st.image(
                str(image_path),
                caption=f"backend={result.get('image_backend', 'unknown')}",
                **_stretch_image_kwargs(),
            )

    with st.expander("기술 정보"):
        used_reference = "예" if result.get("used_reference") else "아니요"
        st.write(f"문구 백엔드: {result.get('copy_backend', 'unknown')}")
        st.write(f"이미지 백엔드: {result.get('image_backend', 'unknown')}")
        st.write(f"참고 이미지 반영: {used_reference}")
        st.write(f"소요 시간(ms): {result.get('elapsed_ms', 'unknown')}")
        st.json(result.get("selected_template", {}))

    with st.expander("프롬프트 요약"):
        st.code(result.get("prompt_summary", ""))


st.set_page_config(page_title="Dessert Ad Studio", layout="wide")
st.title("Dessert Ad Studio")
st.caption("카페와 디저트 소상공인을 위한 SNS 광고 이미지와 문구 생성 스튜디오")

left_column, right_column = st.columns([0.38, 0.62], gap="large")

with left_column:
    st.subheader("Upload Studio")
    sample_label = st.selectbox("데모 샘플", SAMPLE_OPTIONS)
    selected_sample = _sample_by_label(sample_label)
    if selected_sample is not None:
        st.caption(f"{selected_sample.business_type} · {selected_sample.platform}")

    uploaded = st.file_uploader(
        "제품 이미지",
        type=["png", "jpg", "jpeg", "webp"],
        help="업로드하면 사진을 바탕으로 광고 이미지를 생성합니다.",
    )
    if uploaded is not None:
        st.image(uploaded, caption=uploaded.name, **_stretch_image_kwargs())
    else:
        st.info("제품 사진을 업로드하면 생성 결과와 오버레이 배너를 함께 확인할 수 있습니다.")

    default_product_name = selected_sample.product_name if selected_sample else "딸기 크림 크루아상"
    default_campaign_label = (
        PURPOSE_LABELS_BY_VALUE[selected_sample.campaign_purpose]
        if selected_sample
        else "신메뉴 출시"
    )
    default_tone_label = TONE_LABELS_BY_VALUE[selected_sample.tone] if selected_sample else "따뜻한"
    default_template_label = (
        TEMPLATE_LABELS_BY_VALUE[selected_sample.template_hint] if selected_sample else "코지 카페"
    )
    default_price_text = selected_sample.price_text if selected_sample else "6,800원"
    default_user_constraints = (
        selected_sample.user_constraints
        if selected_sample
        else "봄 시즌 한정 느낌, 따뜻한 카페 조명"
    )

    with st.form("generation_form"):
        product_name = st.text_input("상품명", value=default_product_name)
        campaign_label = st.selectbox(
            "캠페인 목적",
            list(PURPOSE_OPTIONS),
            index=list(PURPOSE_OPTIONS).index(default_campaign_label),
        )
        tone_label = st.selectbox(
            "톤",
            list(TONE_OPTIONS),
            index=list(TONE_OPTIONS).index(default_tone_label),
        )
        template_label = st.selectbox(
            "시각 템플릿",
            list(TEMPLATE_OPTIONS),
            index=list(TEMPLATE_OPTIONS).index(default_template_label),
        )
        price_text = st.text_input("가격/혜택", value=default_price_text)
        user_constraints = st.text_area(
            "추가 요청",
            value=default_user_constraints,
        )
        revision_preset_label = st.selectbox("수정 방향", list(REVISION_PRESETS))
        custom_revision_request = st.text_input(
            "수정 요청",
            placeholder="예: 더 프리미엄하게, 할인 강조, 문구 짧게",
        )
        submitted = st.form_submit_button("광고 생성")

    api_path = "/generate" if uploaded is not None else "/generation-jobs"
    st.caption(f"API: POST {API_BASE_URL}{api_path}")

with right_column:
    saved_generation = st.session_state.get(LAST_GENERATION_KEY)
    generation_jobs = st.session_state.get(GENERATION_JOBS_KEY, [])
    agentic_rag_runs = st.session_state.get(AGENTIC_RAG_RUNS_KEY, [])
    if generation_jobs:
        generation_jobs = _refresh_pending_generation_jobs(generation_jobs)
        st.session_state[GENERATION_JOBS_KEY] = generation_jobs
    if agentic_rag_runs:
        agentic_rag_runs = _render_agentic_rag_approval_queue(agentic_rag_runs)
        st.session_state[AGENTIC_RAG_RUNS_KEY] = agentic_rag_runs

    if not submitted and saved_generation is None and not generation_jobs and not agentic_rag_runs:
        st.info(
            "광고 생성 후 이 영역에서 데모 제품 분석, 대표 완성 배너, 추천 문구, "
            "오버레이 배너 다운로드, 원본 이미지와 기술 정보를 확인할 수 있습니다."
        )
    elif not submitted:
        if saved_generation is not None:
            _render_saved_generation(saved_generation)
        _render_generation_job_history(generation_jobs)
    else:
        try:
            request = GenerationRequest(
                campaign_purpose=PURPOSE_OPTIONS[campaign_label],
                product_name=product_name,
                tone=TONE_OPTIONS[tone_label],
                template_hint=TEMPLATE_OPTIONS[template_label],
                price_text=price_text,
                user_constraints=user_constraints,
                revision_request=custom_revision_request.strip()
                or REVISION_PRESETS[revision_preset_label],
                reference_image_b64=_encode_uploaded_file(uploaded),
                reference_image_name=uploaded.name if uploaded else None,
            )
        except ValidationError as exc:
            st.error("입력값을 확인해 주세요.")
            st.json(exc.errors())
        else:
            if request.reference_image_b64:
                spinner_text = (
                    "광고 문구와 이미지를 생성하는 중입니다... "
                    "(이미지 생성은 수십 초 걸릴 수 있어요)"
                )
                with st.spinner(spinner_text):
                    try:
                        response = httpx.post(
                            f"{API_BASE_URL}/generate",
                            json=request.model_dump(),
                            timeout=120,
                        )
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        try:
                            detail = exc.response.json().get("detail")
                        except Exception:
                            detail = None
                        st.error(detail or f"생성 요청 실패: {exc}")
                    except Exception as exc:
                        st.error(f"생성 요청 실패: {exc}")
                    else:
                        result = response.json()
                        saved_generation = _save_generation(request, result)
                        _render_saved_generation(saved_generation)
                        _render_generation_job_history(generation_jobs)
            else:
                with st.spinner("생성 작업을 등록하는 중입니다..."):
                    try:
                        response = httpx.post(
                            f"{API_BASE_URL}/generation-jobs",
                            json=request.model_dump(),
                            timeout=20,
                        )
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        try:
                            detail = exc.response.json().get("detail")
                        except Exception:
                            detail = None
                        st.error(detail or f"작업 등록 실패: {exc}")
                    except Exception as exc:
                        st.error(f"작업 등록 실패: {exc}")
                    else:
                        accepted = response.json()
                        generation_jobs = _upsert_generation_job(
                            generation_jobs,
                            request,
                            accepted,
                        )
                        generation_jobs = _refresh_pending_generation_jobs(generation_jobs)
                        st.session_state[GENERATION_JOBS_KEY] = generation_jobs
                        _render_generation_job_history(generation_jobs)

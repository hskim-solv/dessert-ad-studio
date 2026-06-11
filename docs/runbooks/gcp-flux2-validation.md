# Runbook: GCP L4에서 FLUX.2 검증 데모 재실행

검증 완료: 2026-06-11 (브랜치 `feature/flux2-gcp-validation`). 실측 1회 실행 비용 ~$0.3
(g2-standard-4 ~$0.85/h × 약 20분 — 모델이 HF 캐시 볼륨에 남아 있으면 재실행은 더 짧다).
**정지 중에도 부트 디스크(100GB pd-balanced) 보관 비용 ~$10/월이 발생** — 재실행 계획이
없으면 부록 B로 완전 철거할 것.

## 사전 조건

- gcloud CLI 인증 (times21c@gmail.com), 프로젝트 `dessert-ad-flux2-hskim`
- GPU 쿼터: `GPUS_ALL_REGIONS >= 1`, 해당 리전 `NVIDIA_L4_GPUS >= 1`
  (2026-06-11 기준 둘 다 1 확보됨. 전역 쿼터가 0으로 리셋된 경우 CLI로 증설 요청 가능:
  `gcloud alpha quotas preferences create --service=compute.googleapis.com
  --quota-id=GPUS-ALL-REGIONS-per-project --preferred-value=1
  --project=dessert-ad-flux2-hskim --email=times21c@gmail.com` — 검증 당시 수 분 내 자동 승인)
- macOS에서 `~/.ssh/config`에 `UseKeychain`이 있으면 gcloud가 부르는 ssh가 거부할 수 있다
  → 모든 `gcloud compute ssh`/`scp`에 `--ssh-flag="-F/dev/null"`/`--scp-flag="-F/dev/null"`을
  붙여 사용자 config를 우회한다 (아래 명령들에 이미 반영).

```bash
ZONE=us-central1-c   # 검증에 실제 사용한 존 (a/b는 당시 L4 STOCKOUT)
```

## 1. VM 기동 (이미 만들어 둔 VM 재사용)

```bash
gcloud compute instances start flux2-l4 --zone="$ZONE"
```

처음부터 만들 때는 부록 A의 create 명령 사용.

## 2. 코드 갱신 + 컨테이너 기동

```bash
# 코드 전송 (git bundle — VM에 GitHub 인증 불필요)
git bundle create /tmp/dessert-ad-studio.bundle feature/flux2-gcp-validation
gcloud compute scp /tmp/dessert-ad-studio.bundle flux2-l4:~ --zone="$ZONE" --quiet --scp-flag="-F/dev/null"
gcloud compute ssh flux2-l4 --zone="$ZONE" --quiet --ssh-flag="-F/dev/null" \
  --command="rm -rf ~/dessert-ad-studio && git clone -b feature/flux2-gcp-validation ~/dessert-ad-studio.bundle ~/dessert-ad-studio"

# 컨테이너 빌드·기동 (--no-deps가 triton 이미지 ~10GB 다운로드를 건너뜀; 실측 7분 20초)
gcloud compute ssh flux2-l4 --zone="$ZONE" --quiet --ssh-flag="-F/dev/null" \
  --command="cd ~/dessert-ad-studio && sudo docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d --no-deps api"
```

## 3. 검증

```bash
# (1) 컨테이너 내부 CUDA — 기대 출력: True NVIDIA L4
gcloud compute ssh flux2-l4 --zone="$ZONE" --quiet --ssh-flag="-F/dev/null" \
  --command="cd ~/dessert-ad-studio && sudo docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api \
  python -c 'import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))'"

# (2) 스모크 — 최초 실행은 모델 다운로드(17파일, 실측 1분 38초) 포함. 기대 출력(실측):
# {'model': 'black-forest-labs/FLUX.2-klein-4B', 'total_ms': ..., 'image_path': 'outputs/..._flux2_ad.png',
#  'usage': {'generation_seconds': ~5.3, 'num_inference_steps': 4, 'vram_peak_gb': ~17.3}}
gcloud compute ssh flux2-l4 --zone="$ZONE" --quiet --ssh-flag="-F/dev/null" \
  --command="cd ~/dessert-ad-studio && sudo docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec api \
  python scripts/flux2_smoke.py"

# (3) API 경유 — 기대: HTTP 200, "image_backend":"flux2", scorer local-template-scorer(REQUIRE_TRITON=0 폴백)
cat > /tmp/flux2_req.json <<'EOF'
{
  "campaign_purpose": "new_menu",
  "product_name": "딸기 크림 크루아상",
  "tone": "warm",
  "template_hint": "cozy_cafe",
  "price_text": "6,800원",
  "user_constraints": "봄 시즌 한정 느낌"
}
EOF
gcloud compute scp /tmp/flux2_req.json flux2-l4:/tmp/ --zone="$ZONE" --quiet --scp-flag="-F/dev/null"
gcloud compute ssh flux2-l4 --zone="$ZONE" --quiet --ssh-flag="-F/dev/null" \
  --command="curl -s -X POST http://localhost:8080/generate -H 'Content-Type: application/json' -d @/tmp/flux2_req.json -w '\nHTTP %{http_code}\n'"

# (4) 텔레메트리 JSONL — image_usage에 generation_seconds / num_inference_steps / vram_peak_gb
gcloud compute ssh flux2-l4 --zone="$ZONE" --quiet --ssh-flag="-F/dev/null" \
  --command="tail -n 1 ~/dessert-ad-studio/logs/generations.jsonl"

# (5) 증빙 회수 (outputs/는 gitignored — 로컬 보관용)
mkdir -p outputs/gcp-validation
gcloud compute scp 'flux2-l4:~/dessert-ad-studio/outputs/*_flux2_ad.png' outputs/gcp-validation/ --zone="$ZONE" --quiet --scp-flag="-F/dev/null"
```

## 4. 정지 (필수)

```bash
gcloud compute ssh flux2-l4 --zone="$ZONE" --quiet --ssh-flag="-F/dev/null" \
  --command="cd ~/dessert-ad-studio && sudo docker compose -f docker-compose.yml -f docker-compose.gpu.yml down"
gcloud compute instances stop flux2-l4 --zone="$ZONE"
gcloud compute instances describe flux2-l4 --zone="$ZONE" --format="value(status)"  # TERMINATED
```

## 실측 기준선 (2026-06-11, klein-4B, 4 steps, 1024x1024, L4 24GB)

| 지표 | 값 |
|---|---|
| generation_seconds (스모크 / API 경유) | 5.26 / 4.85 |
| vram_peak_gb | 17.32 |
| API 첫 요청 elapsed_ms (파이프라인 로드 포함) | 63,186 |
| 컨테이너 빌드 시간 (torch CUDA wheel 포함) | 7분 20초 |
| 모델 다운로드 시간/구성 | 1분 38초 / 17파일 (~8GB, hf-cache 볼륨에 캐시) |
| 드라이버 / CUDA | 580.159.03 / 13.0 (이미지 패밀리 `ubuntu-accelerator-2204-amd64-with-nvidia-580`) |

관찰: 생성 이미지의 한글 오버레이 텍스트는 비문으로 렌더링됨(확산 모델의 한글 한계).
텍스트가 필요한 실서비스 산출물은 후처리 오버레이를 권장.

## 부록 A: VM 신규 생성

```bash
# 이미지 패밀리 실재 확인 (nvidia-550은 단종됨 — 2026-06-11 기준 570/580 제공)
gcloud compute images list --project=ubuntu-os-accelerator-images \
  --filter="family~ubuntu-accelerator-2204-amd64" --format="value(family)" | sort -u

gcloud compute instances create flux2-l4 \
  --zone="$ZONE" \
  --machine-type=g2-standard-4 \
  --image-family=ubuntu-accelerator-2204-amd64-with-nvidia-580 \
  --image-project=ubuntu-os-accelerator-images \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-balanced \
  --maintenance-policy=TERMINATE
# ZONE_RESOURCE_POOL_EXHAUSTED(STOCKOUT)면 같은 리전의 다른 존 → 쿼터 보유 타 리전 순으로 재시도

# Docker + NVIDIA Container Toolkit 설치 (컨테이너 nvidia-smi까지 자동 검증, 실측 ~2분)
gcloud compute ssh flux2-l4 --zone="$ZONE" --quiet --ssh-flag="-F/dev/null" \
  --command="bash ~/dessert-ad-studio/scripts/gcp/setup_vm.sh"
```

## 부록 B: 완전 철거

```bash
gcloud compute instances delete flux2-l4 --zone="$ZONE"   # 디스크 과금 종료
```

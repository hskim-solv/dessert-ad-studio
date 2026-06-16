CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS marketing_guide_embeddings (
    doc_id text PRIMARY KEY,
    category text NOT NULL,
    content text NOT NULL,
    keywords text[] NOT NULL DEFAULT ARRAY[]::text[],
    embedding vector(32) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS marketing_guide_embeddings_category_idx
    ON marketing_guide_embeddings (category);

CREATE INDEX IF NOT EXISTS marketing_guide_embeddings_embedding_hnsw_idx
    ON marketing_guide_embeddings
    USING hnsw (embedding vector_cosine_ops);

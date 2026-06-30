-- Run once in Neon SQL editor (or: psql $DATABASE_URL -f schema.sql)

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY,
    source_filename TEXT,
    global_idx INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS session_blobs (
    session_id UUID NOT NULL REFERENCES user_sessions(id) ON DELETE CASCADE,
    blob_key TEXT NOT NULL,
    data BYTEA NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, blob_key)
);

CREATE INDEX IF NOT EXISTS idx_session_blobs_session_id ON session_blobs(session_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_updated ON user_sessions(updated_at DESC);

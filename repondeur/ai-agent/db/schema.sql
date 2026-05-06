-- Schema DEPANMAGIC AI Agent
-- Stocke l'historique des appels passés par l'agent vocal pour :
--   1. fournir le contexte d'un appel récurrent au prochain appel du même numéro
--   2. permettre une revue qualité hors-ligne par les conseillers humains
--   3. extraire les patterns récurrents pour enrichir la knowledge base

CREATE TABLE IF NOT EXISTS calls (
    id              BIGSERIAL PRIMARY KEY,
    asterisk_uid    TEXT UNIQUE NOT NULL,
    caller_number   TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    outcome         TEXT,                          -- 'urgence_transfer' | 'devis' | 'suivi' | 'info' | 'hangup' | 'error'
    summary         TEXT,                          -- résumé généré en fin d'appel
    handoff_to      TEXT                           -- 'astreinte' | 'conseiller' | NULL
);

CREATE INDEX IF NOT EXISTS calls_caller_idx ON calls(caller_number);
CREATE INDEX IF NOT EXISTS calls_started_idx ON calls(started_at DESC);

CREATE TABLE IF NOT EXISTS call_turns (
    id          BIGSERIAL PRIMARY KEY,
    call_id     BIGINT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    turn_index  INTEGER NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stt_confidence REAL,                           -- confiance STT (0-1)
    latency_ms  INTEGER,                           -- latence du tour (record→play)
    UNIQUE (call_id, turn_index)
);

CREATE INDEX IF NOT EXISTS call_turns_call_idx ON call_turns(call_id, turn_index);

-- Table extraite : "ce qu'on a appris" de chaque appel.
-- Le conseiller humain peut valider une note et la reverser dans la knowledge base.
CREATE TABLE IF NOT EXISTS extracted_facts (
    id          BIGSERIAL PRIMARY KEY,
    call_id     BIGINT REFERENCES calls(id) ON DELETE SET NULL,
    fact        TEXT NOT NULL,
    category    TEXT,                              -- 'tarif' | 'zone' | 'service' | 'horaire' | 'autre'
    validated   BOOLEAN NOT NULL DEFAULT FALSE,
    validated_at TIMESTAMPTZ,
    validated_by TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS extracted_facts_pending_idx
    ON extracted_facts(validated, created_at DESC)
    WHERE validated = FALSE;

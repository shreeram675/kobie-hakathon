"""SQLite persistence for Kobie runs and evidence records."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from core.schemas import Claim, NormalizedObjectPacket, ProgramIdentity, RawDocument, now_iso


DEFAULT_DB_PATH = Path("kobie.sqlite3")
_WRITE_LOCK = threading.Lock()


DDL = (
    """
    CREATE TABLE IF NOT EXISTS run_snapshots (
        program_name_normalized TEXT PRIMARY KEY,
        program_name TEXT NOT NULL,
        brand TEXT,
        country_or_region TEXT,
        program_state_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        mode TEXT NOT NULL,
        user_input TEXT NOT NULL,
        program_name TEXT,
        domain TEXT,
        status TEXT NOT NULL,
        data_quality REAL NOT NULL DEFAULT 0,
        run_state_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS program_identities (
        identity_id TEXT PRIMARY KEY,
        raw_input TEXT NOT NULL,
        program_name TEXT NOT NULL,
        brand TEXT NOT NULL,
        domain TEXT NOT NULL,
        country_or_region TEXT,
        confidence REAL NOT NULL,
        status TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sources (
        source_id TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        canonical_url TEXT,
        domain TEXT,
        source_type TEXT,
        authority_score REAL,
        fetched_at TEXT,
        content_date TEXT,
        http_status INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pages (
        page_id TEXT PRIMARY KEY,
        source_id TEXT,
        content_hash TEXT,
        title TEXT,
        cleaned_text TEXT NOT NULL,
        token_count INTEGER NOT NULL,
        sanitizer_flags TEXT,
        FOREIGN KEY(source_id) REFERENCES sources(source_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY,
        page_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        text TEXT NOT NULL,
        token_count INTEGER NOT NULL,
        embedding_hash TEXT,
        FOREIGN KEY(page_id) REFERENCES pages(page_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claims (
        claim_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        field_path TEXT NOT NULL,
        value_json TEXT,
        status TEXT NOT NULL,
        source_url TEXT,
        access_date TEXT,
        quote TEXT,
        confidence REAL NOT NULL,
        volatility TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conflicts (
        conflict_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        field_path TEXT NOT NULL,
        claim_ids_json TEXT NOT NULL,
        score_gap REAL NOT NULL,
        resolution_status TEXT NOT NULL,
        judge_reason TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS briefs (
        brief_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        brief_json TEXT NOT NULL,
        brief_html TEXT,
        word_count INTEGER NOT NULL,
        entailment_passed INTEGER NOT NULL,
        unsupported_sentences_json TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        message_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        role TEXT NOT NULL,
        question TEXT,
        answer_json TEXT,
        cited_claim_ids_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_documents (
        url_hash TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        content TEXT NOT NULL,
        word_count INTEGER NOT NULL,
        query_id TEXT,
        entity_name TEXT,
        domain TEXT,
        retrieved_at TEXT NOT NULL,
        source_authority REAL,
        metadata_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS normalized_packets (
        identity_hash TEXT NOT NULL,
        object_type TEXT NOT NULL,
        source_url TEXT NOT NULL,
        chunk_id TEXT NOT NULL,
        packet_json TEXT NOT NULL,
        normalized_at TEXT NOT NULL,
        PRIMARY KEY(identity_hash, source_url, chunk_id)
    )
    """,
)


def connect(path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    # check_same_thread=True (the default) on purpose: a sqlite3.Connection is
    # not safe for concurrent use from multiple threads. Cross-thread callers
    # (FastAPI threadpool + pipeline threads) must go through
    # ThreadLocalConnection, which hands each thread its own connection; WAL
    # mode makes multi-connection access to the same file safe.
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


class ThreadLocalConnection:
    """Connection facade that lazily opens one real connection per thread.

    Drop-in for the module's helper functions: any attribute access
    (execute, executemany, commit, …) is delegated to the calling thread's
    own sqlite3.Connection. Writes are still serialized by _WRITE_LOCK in
    the helpers, matching SQLite's single-writer model.
    """

    def __init__(self, path: Path | str = DEFAULT_DB_PATH) -> None:
        self._path = path
        self._local = threading.local()

    def _connection(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = connect(self._path)
            self._local.conn = conn
        return conn

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection(), name)


# Accepted by every helper below: a raw connection (tests, single-threaded
# scripts) or the thread-local facade (server).
DBConnection = sqlite3.Connection | ThreadLocalConnection


def checkpoint(conn: DBConnection) -> None:
    """Merge the WAL into the main DB file so data survives loss of -wal/-shm."""
    with _WRITE_LOCK:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def migrate(conn: DBConnection) -> None:
    with _WRITE_LOCK:
        # Migrate run_snapshots if it exists with the old schema (keyed by run_id, not program_name_normalized)
        snapshot_cols = {row[1] for row in conn.execute("PRAGMA table_info(run_snapshots)").fetchall()}
        if snapshot_cols and "program_name_normalized" not in snapshot_cols:
            conn.execute("ALTER TABLE run_snapshots RENAME TO run_snapshots_v1")

        for statement in DDL:
            conn.execute(statement)

        existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(runs)").fetchall()
        }
        if "run_state_json" not in existing_cols:
            conn.execute("ALTER TABLE runs ADD COLUMN run_state_json TEXT")
        conn.commit()


def upsert_run(
    conn: DBConnection,
    state: dict[str, Any],
    status: str = "initialized",
    run_state_json: str | None = None,
) -> None:
    with _WRITE_LOCK:
        conn.execute(
            """
            INSERT INTO runs (run_id, mode, user_input, program_name, domain, status, data_quality, run_state_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                program_name=excluded.program_name,
                domain=excluded.domain,
                status=excluded.status,
                data_quality=excluded.data_quality,
                run_state_json=excluded.run_state_json,
                updated_at=excluded.updated_at
            """,
            (
                state["run_id"],
                state["mode"],
                state["user_input"],
                state.get("program_name"),
                str(state.get("domain")) if state.get("domain") else None,
                status,
                state.get("data_quality", 0.0),
                run_state_json,
                state["created_at"],
                now_iso(),
            ),
        )
        conn.commit()
        try:
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass


def list_runs(conn: DBConnection, limit: int = 200) -> list[dict]:
    """Return persisted run summaries ordered by most recent first.

    Deliberately excludes run_state_json: full states can reach tens of MB
    each and this list backs a polled history endpoint. Use find_run() for
    a single run's full state.
    """
    rows = conn.execute(
        "SELECT run_id, mode, user_input, program_name, status, data_quality, created_at, updated_at "
        "FROM runs ORDER BY created_at DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    return [dict(r) for r in rows]


def find_run(conn: DBConnection, run_id: str) -> dict | None:
    """Return a persisted run row by id, including any serialized state payload."""
    row = conn.execute(
        "SELECT run_id, mode, user_input, program_name, status, data_quality, run_state_json, created_at, updated_at "
        "FROM runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    return dict(row) if row else None


def upsert_identity(conn: DBConnection, identity: ProgramIdentity) -> None:
    data = identity.model_dump()
    with _WRITE_LOCK:
        conn.execute(
            """
            INSERT INTO program_identities
                (identity_id, raw_input, program_name, brand, domain, country_or_region, confidence, status)
            VALUES
                (:identity_id, :raw_input, :program_name, :brand, :domain, :country_or_region, :confidence, :status)
            ON CONFLICT(identity_id) DO UPDATE SET
                raw_input=excluded.raw_input,
                program_name=excluded.program_name,
                brand=excluded.brand,
                domain=excluded.domain,
                country_or_region=excluded.country_or_region,
                confidence=excluded.confidence,
                status=excluded.status
            """,
            data,
        )
        conn.commit()


def insert_claims(conn: DBConnection, claims: list[Claim]) -> None:
    rows = [
        {
            **claim.model_dump(),
            "value_json": json.dumps(claim.value_json, ensure_ascii=True),
        }
        for claim in claims
    ]
    with _WRITE_LOCK:
        conn.executemany(
            """
            INSERT INTO claims
                (claim_id, run_id, field_path, value_json, status, source_url, access_date, quote, confidence, volatility)
            VALUES
                (:claim_id, :run_id, :field_path, :value_json, :status, :source_url, :access_date, :quote, :confidence, :volatility)
            ON CONFLICT(claim_id) DO NOTHING
            """,
            rows,
        )
        conn.commit()


def upsert_raw_documents(conn: DBConnection, documents: list[RawDocument]) -> None:
    """Persist raw Firecrawl documents idempotently by URL hash."""

    rows = [
        {
            **document.model_dump(),
            "metadata_json": json.dumps(document.metadata, ensure_ascii=True),
        }
        for document in documents
    ]
    with _WRITE_LOCK:
        conn.executemany(
            """
            INSERT INTO raw_documents
                (url_hash, url, content, word_count, query_id, entity_name, domain, retrieved_at, source_authority, metadata_json)
            VALUES
                (:url_hash, :url, :content, :word_count, :query_id, :entity_name, :domain, :retrieved_at, :source_authority, :metadata_json)
            ON CONFLICT(url_hash) DO UPDATE SET
                url=excluded.url,
                content=excluded.content,
                word_count=excluded.word_count,
                query_id=excluded.query_id,
                entity_name=excluded.entity_name,
                domain=excluded.domain,
                retrieved_at=excluded.retrieved_at,
                source_authority=excluded.source_authority,
                metadata_json=excluded.metadata_json
            """,
            rows,
        )
        conn.commit()


def save_program_snapshot(
    conn: DBConnection,
    program_name: str,
    brand: str | None,
    country_or_region: str | None,
    program_state_json: str,
    created_at: str | None = None,
) -> None:
    """Upsert a completed program-analysis snapshot keyed by normalised program name."""
    if created_at is None:
        created_at = now_iso()
    normalized = program_name.lower().strip()
    with _WRITE_LOCK:
        conn.execute(
            """
            INSERT INTO run_snapshots
                (program_name_normalized, program_name, brand, country_or_region, program_state_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(program_name_normalized) DO UPDATE SET
                program_name=excluded.program_name,
                brand=excluded.brand,
                country_or_region=excluded.country_or_region,
                program_state_json=excluded.program_state_json,
                created_at=excluded.created_at
            """,
            (normalized, program_name, brand, country_or_region, program_state_json, created_at),
        )
        conn.commit()
        try:
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass


def find_program_snapshot(conn: DBConnection, query: str) -> dict | None:
    """Return the most-recent snapshot row for a program query, or None.

    Matching order: exact normalised name → stored name contains query → query words all appear in stored name.
    """
    normalized = query.lower().strip()

    row = conn.execute(
        "SELECT * FROM run_snapshots WHERE program_name_normalized = ?",
        (normalized,),
    ).fetchone()
    if row:
        return dict(row)

    row = conn.execute(
        "SELECT * FROM run_snapshots WHERE program_name_normalized LIKE ? ORDER BY created_at DESC LIMIT 1",
        (f"%{normalized}%",),
    ).fetchone()
    if row:
        return dict(row)

    words = [w for w in normalized.split() if len(w) > 2]
    if words:
        like_clause = " AND ".join("program_name_normalized LIKE ?" for _ in words)
        row = conn.execute(
            f"SELECT * FROM run_snapshots WHERE {like_clause} ORDER BY created_at DESC LIMIT 1",
            [f"%{w}%" for w in words],
        ).fetchone()
        if row:
            return dict(row)

    return None


def list_program_snapshots(conn: DBConnection, limit: int = 100) -> list[dict]:
    """Return all stored snapshots ordered by most recent first."""
    rows = conn.execute(
        "SELECT program_name, brand, country_or_region, program_state_json, created_at "
        "FROM run_snapshots ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_program_snapshot_summaries(conn: DBConnection, limit: int = 100) -> list[dict]:
    """Return snapshot metadata for the history list without loading the state blobs.

    Extracts the handful of summary fields in SQL (json_extract) so listing
    100 snapshots reads a few KB instead of parsing tens of MB of JSON in
    Python on every history poll.
    """
    rows = conn.execute(
        """
        SELECT program_name, brand, created_at,
               json_extract(program_state_json, '$.run_id')       AS run_id,
               json_extract(program_state_json, '$.user_input')   AS user_input,
               json_extract(program_state_json, '$.mode')         AS mode,
               json_extract(program_state_json, '$.data_quality') AS data_quality,
               json_extract(program_state_json, '$.status')       AS status
        FROM run_snapshots ORDER BY created_at DESC LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    return [dict(r) for r in rows]


def find_program_snapshot_by_run_id(conn: DBConnection, run_id: str) -> dict | None:
    """Return a stored program snapshot containing the requested run id."""
    rows = conn.execute(
        "SELECT * FROM run_snapshots WHERE program_state_json LIKE ? ORDER BY created_at DESC",
        (f'%"run_id": "{run_id}"%',),
    ).fetchall()
    for row in rows:
        data = dict(row)
        try:
            state = json.loads(data["program_state_json"])
        except Exception:
            continue
        if state.get("run_id") == run_id:
            return data
    return None


def delete_run(conn: DBConnection, run_id: str) -> bool:
    """Delete a run and its associated claims, conflicts, briefs, and conversations. Returns True if deleted."""
    with _WRITE_LOCK:
        conn.execute("DELETE FROM claims WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM conflicts WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM briefs WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM conversations WHERE run_id = ?", (run_id,))
        cursor = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        conn.commit()
    return cursor.rowcount > 0


def delete_run_snapshot(conn: DBConnection, program_name_normalized: str) -> bool:
    """Delete a run_snapshot by normalized program name. Returns True if deleted."""
    with _WRITE_LOCK:
        cursor = conn.execute(
            "DELETE FROM run_snapshots WHERE program_name_normalized = ?",
            (program_name_normalized,),
        )
        conn.commit()
    return cursor.rowcount > 0


def list_program_snapshots_by_run_id(conn: DBConnection, run_id: str) -> list[dict]:
    """Return all stored snapshots whose serialized state references the given run id."""
    rows = conn.execute(
        "SELECT * FROM run_snapshots WHERE program_state_json LIKE ? ORDER BY created_at ASC",
        (f'%"run_id": "{run_id}"%',),
    ).fetchall()
    result: list[dict] = []
    for row in rows:
        data = dict(row)
        try:
            state = json.loads(data["program_state_json"])
        except Exception:
            continue
        if state.get("run_id") == run_id:
            result.append(data)
    return result


def upsert_normalized_packets(conn: DBConnection, packets: list[NormalizedObjectPacket]) -> None:
    """Persist normalized extraction packets idempotently."""

    rows = [
        {
            "identity_hash": packet.identity_hash,
            "object_type": packet.object_type,
            "source_url": packet.source_url,
            "chunk_id": packet.chunk_id,
            "packet_json": packet.model_dump_json(),
            "normalized_at": packet.normalized_at,
        }
        for packet in packets
    ]
    with _WRITE_LOCK:
        conn.executemany(
            """
            INSERT INTO normalized_packets
                (identity_hash, object_type, source_url, chunk_id, packet_json, normalized_at)
            VALUES
                (:identity_hash, :object_type, :source_url, :chunk_id, :packet_json, :normalized_at)
            ON CONFLICT(identity_hash, source_url, chunk_id) DO UPDATE SET
                object_type=excluded.object_type,
                packet_json=excluded.packet_json,
                normalized_at=excluded.normalized_at
            """,
            rows,
        )
        conn.commit()

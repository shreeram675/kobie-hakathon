import json
import threading

from core.schemas import build_initial_state
from core.db import (
    ThreadLocalConnection,
    connect,
    list_program_snapshot_summaries,
    list_runs,
    migrate,
    save_program_snapshot,
    upsert_run,
)


def test_sqlite_migration_and_run_upsert(tmp_path):
    conn = connect(tmp_path / "kobie.sqlite3")
    migrate(conn)
    state = build_initial_state("Air India")
    upsert_run(conn, state)

    row = conn.execute("SELECT run_id, user_input FROM runs").fetchone()
    assert row["run_id"] == state["run_id"]
    assert row["user_input"] == "Air India"


def test_thread_local_connection_concurrent_writes_and_reads(tmp_path):
    """Many threads reading and writing through one facade must not corrupt
    the DB or trip sqlite's same-thread check (each thread gets its own
    underlying connection)."""
    db_path = tmp_path / "kobie.sqlite3"
    conn = ThreadLocalConnection(db_path)
    migrate(conn)

    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            state = build_initial_state(f"Program {i}")
            upsert_run(conn, state)
            rows = list_runs(conn, limit=50)
            assert any(r["user_input"] == f"Program {i}" for r in rows)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert count == 8
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_list_runs_excludes_state_blob(tmp_path):
    conn = connect(tmp_path / "kobie.sqlite3")
    migrate(conn)
    state = build_initial_state("Air India")
    upsert_run(conn, state, status="done", run_state_json=json.dumps({"big": "x" * 1000}))

    rows = list_runs(conn)
    assert len(rows) == 1
    assert "run_state_json" not in rows[0]
    assert rows[0]["status"] == "done"


def test_list_program_snapshot_summaries_extracts_metadata_without_blob(tmp_path):
    conn = connect(tmp_path / "kobie.sqlite3")
    migrate(conn)
    program_state = {
        "run_id": "run_abc",
        "user_input": "delta skymiles",
        "mode": "single",
        "data_quality": 0.87,
        "status": "done",
        "scraped_blocks": [{"content": "x" * 5000}],
    }
    save_program_snapshot(
        conn, "Delta SkyMiles", "Delta", "US", json.dumps(program_state), "2026-07-01T00:00:00Z"
    )

    rows = list_program_snapshot_summaries(conn)
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == "run_abc"
    assert row["user_input"] == "delta skymiles"
    assert row["mode"] == "single"
    assert row["data_quality"] == 0.87
    assert row["status"] == "done"
    assert row["program_name"] == "Delta SkyMiles"
    assert "program_state_json" not in row

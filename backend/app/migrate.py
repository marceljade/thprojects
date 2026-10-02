"""Schema-Abgleich beim Start: neue Tabellen und neue Spalten werden in einer bestehenden
Datenbank ergänzt (ALTER TABLE ADD COLUMN). Vorhandene Daten bleiben unangetastet.
Spalten werden nie gelöscht oder umbenannt – das wäre ein manueller Schritt."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .database import Base


def _sql_type(col) -> str:
    try:
        return col.type.compile(dialect=__import__("sqlalchemy.dialects.sqlite", fromlist=["dialect"]).dialect())
    except Exception:  # noqa: BLE001
        return "TEXT"


def migrate(engine: Engine) -> list[str]:
    """Liefert die Liste der ergänzten Spalten (für das Startprotokoll)."""
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    added: list[str] = []
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                default = ""
                if col.default is not None and getattr(col.default, "arg", None) is not None and not callable(col.default.arg):
                    arg = col.default.arg
                    if isinstance(arg, bool):
                        default = f" DEFAULT {1 if arg else 0}"
                    elif isinstance(arg, (int, float)):
                        default = f" DEFAULT {arg}"
                    elif isinstance(arg, str):
                        default = " DEFAULT '" + arg.replace("'", "''") + "'"
                    elif hasattr(arg, "value"):
                        default = f" DEFAULT '{arg.value}'"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {_sql_type(col)}{default}'))
                added.append(f"{table.name}.{col.name}")
        added += backfill_rounds(conn)
    return added


def backfill_rounds(conn) -> list[str]:
    """Jedes Projekt ohne Runde bekommt Runde 1 aus seinen heutigen Feldern, Aufgaben ohne Runde
    gehören zur aktuellen Runde ihres Projekts. Läuft bei jedem Start, ändert nur, was fehlt."""
    out: list[str] = []
    missing = conn.execute(text(
        "SELECT p.id, p.status, p.request_date, p.offer_date, p.order_date, p.offered_weeks, p.target_deadline, p.completed_at, p.created_at "
        "FROM projects p WHERE NOT EXISTS (SELECT 1 FROM project_rounds r WHERE r.project_id = p.id)")).all()
    for row in missing:
        conn.execute(text(
            "INSERT INTO project_rounds (project_id, number, title, status, request_date, offer_date, order_date, offered_weeks, "
            "target_deadline, closed_at, created_at) VALUES (:pid, 1, 'Erstauftrag', :status, :rq, :of, :od, :ow, :td, :closed, :created)"),
            {"pid": row[0], "status": row[1], "rq": row[2], "of": row[3], "od": row[4], "ow": row[5], "td": row[6],
             "closed": row[7] if row[1] == "abgeschlossen" else None, "created": row[8] or datetime.now().isoformat(sep=" ")})
    if missing:
        out.append(f"project_rounds: Runde 1 für {len(missing)} Projekte")
    n = conn.execute(text(
        "UPDATE tasks SET round_id = (SELECT r.id FROM project_rounds r WHERE r.project_id = tasks.project_id "
        "ORDER BY r.number DESC LIMIT 1) WHERE round_id IS NULL")).rowcount
    if n:
        out.append(f"tasks.round_id: {n} Aufgaben der aktuellen Runde zugeordnet")
    return out

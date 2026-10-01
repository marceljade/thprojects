"""Schema-Abgleich beim Start: neue Tabellen und neue Spalten werden in einer bestehenden
Datenbank ergänzt (ALTER TABLE ADD COLUMN). Vorhandene Daten bleiben unangetastet.
Spalten werden nie gelöscht oder umbenannt – das wäre ein manueller Schritt."""
from __future__ import annotations

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
    return added

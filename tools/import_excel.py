"""Einmaliger Import der laufenden Projekte aus import/Laufende_Projekte_Uebernahme.xlsx in die laufende App.

Schreibt nur über die HTTP-API (POST /api/projects, /api/tasks, /api/notes), nie in die Datenbankdatei.
Legt auf dem NAS nichts an. Vor dem ersten Schreibzugriff eine Sicherung über POST /api/backups.
Vorhandene Projektnummern werden übersprungen, das Skript kann gefahrlos mehrfach laufen.

  python tools/import_excel.py            Trockenlauf, zeigt nur, was angelegt würde
  python tools/import_excel.py --apply    schreibt wirklich
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

import openpyxl

BASE = "http://localhost:8765"
XLSX = Path(__file__).resolve().parent.parent / "import" / "Laufende_Projekte_Uebernahme.xlsx"
APPLY = "--apply" in sys.argv


# ------------------------------------------------------------------ HTTP --
def api(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"{method} {path} -> HTTP {e.code}: {detail}")


# ----------------------------------------------------------------- Excel --
def iso(v) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    raise SystemExit(f"Kein Datum: {v!r}")


def s(v) -> str:
    return str(v).strip() if v is not None else ""


def rows(ws) -> list[dict]:
    it = ws.iter_rows(values_only=True)
    header = [s(h) for h in next(it)]
    out = []
    for r in it:
        if not any(c not in (None, "") for c in r):
            continue
        out.append(dict(zip(header, r)))
    return out


def load():
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    return rows(wb["Projekte"]), rows(wb["Aufgaben"])


def build(projects: list[dict], tasks: list[dict], users: dict[str, int]) -> list[dict]:
    """Je Projekt ein Plan: Projekt-Payload, Soll-Status, Notiz, Aufgaben-Payloads."""
    by_nr: dict[str, list[dict]] = {}
    for t in tasks:
        by_nr.setdefault(s(t["Projektnr."]), []).append(t)
    plans = []
    for p in projects:
        nr = s(p["Projektnr."])
        codes = [c.strip().upper() for c in s(p["Bearbeiter"]).replace(",", "/").split("/") if c.strip()]
        assignee = codes[0] if codes else ""
        if assignee and assignee not in users:
            raise SystemExit(f"{nr}: Bearbeiter {assignee} gibt es in der App nicht.")
        others = codes[1:]
        note = s(p["Notiz zum Projekt"])
        if others:
            note = f"Beteiligt: {', '.join(others)}. {note}".strip()
        if s(p["Folgeauftrag?"]).lower() == "ja":
            note = f"Folgeauftrag: {note}".strip()
        status = s(p["Status"]) or "anfrage"
        weeks = p["Angebotene Wochen"]
        payload = {
            "project_number": nr, "name": s(p["Projektname"]), "category": s(p["Kategorie"]) or "gutachten",
            "client": s(p["Auftraggeber"]), "status": status,
            "assignee_id": users.get(assignee), "participants": "/".join(others),
            "request_date": iso(p["Anfrage am"]), "offer_date": iso(p["Angebot am"]), "order_date": iso(p["Auftrag am"]),
            "offered_weeks": float(weeks) if weeks not in (None, "") else None,
            "target_deadline": iso(p["Ziel-Frist"]),
            "template_id": None, "compute_due_dates": False, "create_folder": False,
        }
        tlist = []
        for t in sorted(by_nr.get(nr, []), key=lambda t: float(t["Nr."] or 0)):
            tstatus = s(t["Status"]) or "nicht_begonnen"
            tp = {"title": s(t["Aufgabe"]), "status": tstatus, "priority": s(t["Priorität"]) or "normal",
                  "due_date": iso(t["Frist"])}
            if tstatus == "wartet":
                tp["waiting_on"] = s(t["Wartet auf (wer)"])
                tp["waiting_since"] = date.today().isoformat()
            tlist.append(tp)
        plans.append({"nr": nr, "status": status, "project": payload, "note": note, "tasks": tlist})
    return plans


# ------------------------------------------------------------------ Main --
def main() -> None:
    meta = api("GET", "/api/meta")
    users = {u["code"].upper(): u["id"] for u in meta["users"]}
    code_of = {i: c for c, i in users.items()}
    existing = {p["project_number"] for p in api("GET", "/api/projects")}
    projects, tasks = load()
    plans = build(projects, tasks, users)

    mode = "SCHREIBEN" if APPLY else "TROCKENLAUF"
    print(f"== {mode}: {len(plans)} Projekte, {sum(len(p['tasks']) for p in plans)} Aufgaben in der Excel")
    todo = [p for p in plans if p["nr"] not in existing]
    skipped = [p for p in plans if p["nr"] in existing]
    for p in skipped:
        print(f"  übersprungen (schon vorhanden): {p['nr']} {p['project']['name']}")
    for p in todo:
        pr = p["project"]
        parts = [pr["category"], f"Bearbeiter {code_of.get(pr['assignee_id'], '-')}"]
        if pr["participants"]:
            parts.append(f"beteiligt {pr['participants']}")
        if pr["client"]:
            parts.append(f"AG {pr['client']}")
        for label, key in (("Anfrage", "request_date"), ("Angebot", "offer_date"), ("Auftrag", "order_date"), ("Ziel", "target_deadline")):
            if pr[key]:
                parts.append(f"{label} {pr[key]}")
        if pr["offered_weeks"]:
            parts.append(f"{pr['offered_weeks']:g} Wo")
        print(f"\n+ {p['nr']} {pr['name']} [{p['status']}] " + " · ".join(parts))
        note = p["note"]
        print(f"    Notiz: {note[:110]}{'...' if len(note) > 110 else ''}")
        for i, t in enumerate(p["tasks"], 1):
            w = f" wartet auf {t['waiting_on']}" if t.get("waiting_on") else ""
            d = f" Frist {t['due_date']}" if t["due_date"] else ""
            pri = f" [{t['priority']}]" if t["priority"] != "normal" else ""
            print(f"    {i}. {t['title']} ({t['status']}){pri}{d}{w}")
    print(f"\n== Anzulegen: {len(todo)} Projekte, {sum(len(p['tasks']) for p in todo)} Aufgaben, {len(skipped)} übersprungen")
    if not APPLY:
        print("Trockenlauf, nichts geschrieben. Zum Schreiben: --apply")
        return
    if not todo:
        print("Nichts zu tun.")
        return

    b = api("POST", "/api/backups")
    print(f"Sicherung angelegt: {b['file']} ({b['size_bytes']} Bytes)")

    n_p = n_t = 0
    no_folder = []
    for p in todo:
        created = api("POST", "/api/projects", p["project"])
        pid = created["id"]
        n_p += 1
        if created["status"] != p["status"]:
            api("PUT", f"/api/projects/{pid}", {"status": p["status"]})
            print(f"  {p['nr']}: Status von {created['status']} auf {p['status']} gesetzt")
        if p["note"]:
            api("POST", "/api/notes", {"project_id": pid, "content": p["note"]})
        for t in p["tasks"]:
            api("POST", "/api/tasks", {"project_id": pid, **t})
            n_t += 1
        final = api("GET", f"/api/projects/{pid}")
        if not final["folder_path"]:
            no_folder.append(f"{p['nr']} {p['project']['name']}")
        print(f"  angelegt: {p['nr']} {p['project']['name']} · {len(p['tasks'])} Aufgaben · Ordner: {final['folder_path'] or 'keiner gefunden'}")

    print(f"\n== Fertig: {n_p} Projekte, {n_t} Aufgaben angelegt, {len(skipped)} übersprungen")
    if no_folder:
        print(f"Kein NAS-Ordner gefunden ({len(no_folder)}):")
        for x in no_folder:
            print(f"  - {x}")


if __name__ == "__main__":
    main()

"""End-to-End-Durchlauf mit Playwright: echte Klicks in der gebauten App, Screenshots nach shots/ neben dieser Datei.

Server vorher mit leerer Test-Datenbank starten, nie gegen backend/data:
  PMTH_DATA=<leerer Ordner> python -m uvicorn app.main:app --port 8765   (im Ordner backend)
"""
import json
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:8765"
# Eigenes Chromium (z. B. wenn der Download von playwright install nicht geht): PMTH_CHROMIUM=<Pfad zur chrome-Binary>
LAUNCH = {"executable_path": os.environ["PMTH_CHROMIUM"]} if os.environ.get("PMTH_CHROMIUM") else {}
OUT = Path(__file__).resolve().parent / "shots"
OUT.mkdir(exist_ok=True)
LAPTOP = {"width": 1366, "height": 768}
today = date.today()
iso = lambda d: d.isoformat()  # noqa: E731

# ---- Leeres Dashboard auf Laptop-Breite, bevor Testdaten entstehen
with sync_playwright() as pw:
    b = pw.chromium.launch(**LAUNCH)
    pg = b.new_context(viewport=LAPTOP, locale="de-DE").new_page()
    pg.goto(BASE + "/")
    pg.wait_for_timeout(600)
    pg.screenshot(path=str(OUT / "20_laptop_dashboard_leer.png"))
    b.close()

# ---- Testdaten über die API (schneller als Formulare), Formulare werden unten separat geklickt
api = httpx.Client(base_url=BASE, timeout=30)
NAS = Path(tempfile.gettempdir()) / "nas_test"; (NAS / "2026").mkdir(parents=True, exist_ok=True)
api.put("/api/settings", json={"base_path": str(NAS)})
meta = api.get("/api/meta").json()
tpl = {t["name"]: t["id"] for t in meta["templates"]}
users = {u["code"]: u["id"] for u in meta["users"]}

p1 = api.post("/api/projects", json={"project_number": "26-301", "name": "WP Testfeld – Nachmessung 4x N163", "category": "wea", "client": "Enercon",
                                     "status": "in_bearbeitung", "order_date": iso(today - timedelta(days=28)), "offered_weeks": 8,
                                     "template_id": tpl["WEA-Vermessung"]}).json()
p2 = api.post("/api/projects", json={"project_number": "26-298", "name": "BESS Hollenstedt, Schallprognose", "category": "gutachten", "client": "greentech",
                                     "status": "in_bearbeitung", "order_date": iso(today - timedelta(days=35)), "offered_weeks": 5,
                                     "template_id": tpl["Gutachten / Prognose"]}).json()
p3 = api.post("/api/projects", json={"project_number": "26-310", "name": "KiTa Sonnenweg – Nachhallzeitmessung", "category": "messung", "client": "Stadt Oldenburg",
                                     "status": "beauftragt", "order_date": iso(today - timedelta(days=3)), "offered_weeks": 4, "template_id": tpl["Messung"]}).json()
p4 = api.post("/api/projects", json={"project_number": "26-312", "name": "BESS Wittmund II", "category": "gutachten", "client": "european energy", "status": "angebot",
                                     "request_date": iso(today - timedelta(days=6)), "offer_date": iso(today - timedelta(days=2))}).json()
p5 = api.post("/api/projects", json={"project_number": "26-290", "name": "Tankstelle B75, Immissionsprognose", "category": "gutachten", "client": "CLASSIC",
                                     "status": "wartet_kunde", "order_date": iso(today - timedelta(days=20)), "offered_weeks": 6, "template_id": tpl["Gutachten / Prognose"]}).json()

# p1: erste Aufgaben erledigt, eine Aufgabe heute fällig, eine überfällig
for t in p1["tasks"][:3]:
    api.post(f"/api/tasks/{t['id']}/complete")
api.put(f"/api/tasks/{p1['tasks'][3]['id']}", json={"due_date": iso(today), "status": "in_bearbeitung", "progress": 40})
api.put(f"/api/tasks/{p1['tasks'][4]['id']}", json={"due_date": iso(today + timedelta(days=2))})
# p2: Berechnung überfällig, wartet auf Unterlagen
for t in p2["tasks"][:1]:
    api.post(f"/api/tasks/{t['id']}/complete")
api.put(f"/api/tasks/{p2['tasks'][1]['id']}", json={"status": "wartet", "waiting_for": "Herstellerdatenblätter", "waiting_on": "greentech", "due_date": iso(today - timedelta(days=1))})
api.put(f"/api/tasks/{p2['tasks'][2]['id']}", json={"due_date": iso(today - timedelta(days=3)), "priority": "hoch"})
api.post("/api/notes", json={"project_id": p2["id"], "content": "Kunde hat die Lageplan-Revision geschickt, Trafo-Standort hat sich um 12 m verschoben."})
api.post("/api/notes", json={"project_id": p1["id"], "task_id": p1["tasks"][4]["id"], "content": "Betreiber bestätigt Modus NR VIIs für die Messnacht."})
api.post("/api/tasks", json={"project_id": p5["id"], "title": "Rückfrage Nachtbetrieb Waschanlage", "status": "wartet", "waiting_for": "Betriebszeiten", "waiting_on": "CLASSIC",
                             "waiting_since": iso(today - timedelta(days=5)), "reminder_date": iso(today)})

def shot(page, name):
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)

with sync_playwright() as pw:
    browser = pw.chromium.launch(**LAUNCH)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="de-DE")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto(BASE + "/")
    expect(page.get_by_role("heading", name=re.compile("^Heute"))).to_be_visible()
    shot(page, "01_dashboard")

    # Aufgabe über das Dashboard abhaken
    first = page.locator("[role=checkbox]").first
    first.click()
    page.wait_for_timeout(600)
    shot(page, "02_dashboard_abgehakt")

    # Neues Projekt über das Formular (Tastenkürzel p). Der Ordner liegt schon auf dem "NAS", die App legt nie einen an
    (NAS / "2026" / "26-315 Auftrag WP Moorriem – Vermessung 3x E-160").mkdir()
    page.keyboard.press("p")
    expect(page.get_by_role("dialog")).to_be_visible()
    page.get_by_placeholder("26-234").fill("26-315")
    page.get_by_placeholder("z. B. WP Testfeld, Nachmessung").fill("WP Moorriem – Vermessung 3x E-160")
    page.locator("select").nth(0).select_option("wea")
    page.locator("input[type=date]").nth(2).fill(iso(today))
    page.locator("input[type=number]").first.fill("8")
    page.wait_for_timeout(500)
    shot(page, "03_projekt_neu")
    page.get_by_role("button", name="Projekt anlegen").click()
    expect(page.get_by_text("WP Moorriem")).to_be_visible()
    page.wait_for_timeout(600)
    shot(page, "04_projektseite")
    # Vorhandener Ordner wurde übernommen. Nach dem Phasenwechsel bleibt er wie er ist, die App zeigt nur den Hinweis
    ordner = page.locator("section", has_text="Projektordner").first
    expect(ordner).to_contain_text("26-315 Auftrag WP Moorriem")
    page.locator("select").nth(0).select_option("anfrage")
    page.wait_for_timeout(800)
    assert [e.name for e in (NAS / "2026").iterdir()] == ["26-315 Auftrag WP Moorriem – Vermessung 3x E-160"]
    expect(ordner).to_contain_text("Ordner heißt noch Auftrag. Benenne ihn auf dem NAS in Anfrage um.")
    expect(page.get_by_role("button", name="Erwarteten Namen kopieren")).to_be_visible()
    shot(page, "04b_ordner_hinweis")
    page.locator("select").nth(0).select_option("in_bearbeitung")
    page.wait_for_timeout(800)
    assert [e.name for e in (NAS / "2026").iterdir()] == ["26-315 Auftrag WP Moorriem – Vermessung 3x E-160"]
    expect(ordner).not_to_contain_text("Ordner heißt noch")

    # Aufgabe öffnen und Frist verschieben
    page.get_by_text("Messung durchführen").first.click()
    expect(page.get_by_role("dialog")).to_be_visible()
    shot(page, "05_aufgabe_dialog")
    page.get_by_role("button", name="+3 AT").click()
    page.wait_for_timeout(400)
    # Datum aus der Zwischenablage ins Fristfeld einfügen (deutsches Format)
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate("navigator.clipboard.writeText('24.12.2026')")
    due = page.get_by_role("dialog").locator("input[type=date]").nth(1)
    due.click()
    page.keyboard.press("Control+V")
    page.wait_for_timeout(300)
    assert due.input_value() == "2026-12-24", due.input_value()
    shot(page, "05b_datum_eingefuegt")
    page.keyboard.press("Escape")

    # Neue Aufgabe über Tastenkürzel n
    page.keyboard.press("n")
    expect(page.get_by_role("dialog")).to_be_visible()
    page.get_by_placeholder("z. B. Messdaten auswerten").fill("Windmessmast-Daten anfordern")
    page.get_by_role("button", name="heute").click()
    page.get_by_role("button", name="Aufgabe speichern").click()
    page.wait_for_timeout(500)

    # Folgeauftrag: Projekt abschließen, neue Runde starten, alte Aufgaben bleiben nur lesbar
    api.post(f"/api/projects/{p3['id']}/complete", json={"open_tasks": "erledigt"})
    page.goto(BASE + f"/projekte/{p3['id']}")
    page.get_by_role("button", name="Folgeauftrag starten").click()
    dlg = page.get_by_role("dialog")
    expect(dlg).to_be_visible()
    # echtes Tippen: der Fokus muss im Titelfeld bleiben (früher sprang er aufs X und "p" öffnete den Projektdialog)
    page.keyboard.type("Planänderung 2026", delay=20)
    assert dlg.get_by_placeholder("z. B. Planänderung 2026").input_value() == "Planänderung 2026"
    assert page.get_by_role("dialog").count() == 1
    dlg.get_by_role("button", name="Folgeauftrag starten").click()
    expect(page.get_by_text("Folgeauftrag 2")).to_be_visible()
    expect(page.get_by_role("tab", name="2 Planänderung 2026")).to_be_visible()
    page.wait_for_timeout(500)
    shot(page, "05c_folgeauftrag")
    page.get_by_role("tab", name="1 Erstauftrag").click()
    expect(page.get_by_text("Nur zum Nachlesen")).to_be_visible()
    shot(page, "05d_folgeauftrag_runde1")
    assert [e.name for e in (NAS / "2026").iterdir()] == ["26-315 Auftrag WP Moorriem – Vermessung 3x E-160"]

    page.goto(BASE + "/aufgaben")
    expect(page.get_by_text("Meine Aufgaben")).to_be_visible()
    shot(page, "06_aufgaben")
    page.goto(BASE + "/projekte")
    page.wait_for_timeout(400)
    shot(page, "07_projekte")
    page.goto(BASE + "/kalender")
    page.wait_for_timeout(500)
    shot(page, "08_kalender")
    page.goto(BASE + "/zeitplan")
    page.wait_for_timeout(600)
    shot(page, "09_zeitplan")
    page.goto(BASE + "/einstellungen")
    page.wait_for_timeout(400)
    shot(page, "10_einstellungen")

    # Suche
    page.goto(BASE + "/")
    page.locator("#global-search").fill("Hollen")
    page.wait_for_timeout(600)
    shot(page, "11_suche")

    # Dark Mode
    page.keyboard.press("Escape")
    page.get_by_title("Dunkler Modus").click()
    page.wait_for_timeout(400)
    shot(page, "12_dashboard_dark")
    page.goto(BASE + f"/projekte/{p2['id']}")
    page.wait_for_timeout(600)
    shot(page, "13_projektseite_dark")

    # Mobil
    mob = browser.new_context(viewport={"width": 390, "height": 844}, locale="de-DE").new_page()
    mob.goto(BASE + "/")
    mob.wait_for_timeout(600)
    mob.screenshot(path=str(OUT / "14_mobil.png"))

    # Laptop 1366x768: Dashboard voll, Kalender Monat (Standard) und Woche
    lap = browser.new_context(viewport=LAPTOP, locale="de-DE").new_page()
    lap.on("pageerror", lambda e: errors.append(str(e)))
    lap.goto(BASE + "/")
    expect(lap.get_by_role("heading", name=re.compile("^Heute"))).to_be_visible()
    lap.wait_for_timeout(500)
    lap.screenshot(path=str(OUT / "21_laptop_dashboard.png"))
    lap.goto(BASE + "/kalender")
    expect(lap.get_by_role("button", name="Monat")).to_be_visible()
    lap.wait_for_timeout(600)
    lap.screenshot(path=str(OUT / "22_laptop_kalender_monat.png"))
    lap.get_by_role("button", name="Woche").click()
    lap.wait_for_timeout(600)
    lap.screenshot(path=str(OUT / "23_laptop_kalender_woche.png"))
    lap.reload()
    lap.wait_for_timeout(600)
    assert lap.evaluate("localStorage.getItem('calendar_view')") == "woche", "Kalenderansicht wird nicht gemerkt"

    browser.close()
    print("Konsolenfehler:", json.dumps(errors, indent=1, ensure_ascii=False) if errors else "keine")

d = api.get("/api/dashboard").json()
print("Dashboard:", {k: d["counts"][k] for k in ("today", "overdue", "this_week", "waiting_tasks", "active_projects", "critical_projects")})
print("Projekte:", [(p["project_number"], p["signal"], p["progress"]) for p in api.get("/api/projects").json()])

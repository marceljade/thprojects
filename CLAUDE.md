# CLAUDE.md – Projektmanagement T&H

Lokale Web-App für die tägliche Projekt- und Aufgabensteuerung eines Projektingenieurs im Schallimmissionsschutz (T&H Ingenieure, Bremen). Nutzer: Marcel Cording (Kürzel MC). Sprache der Oberfläche und aller Rückmeldungen: Deutsch, Sie-freie Du-Form, Sentence case, keine Semikolons in Texten.

## Ziel in einem Satz

Beim Öffnen am Morgen in wenigen Sekunden sehen: Was ist heute fällig, was ist überfällig, was kommt als Nächstes, welche Projekte brauchen Aufmerksamkeit, wo hängt etwas an Kunde oder Kollegen. Alles andere ordnet sich dem unter. Ein Feature, das die Oberfläche voller macht, ohne diese Fragen besser zu beantworten, wird nicht gebaut.

Prioritäten in dieser Reihenfolge: Übersichtlichkeit · täglicher Nutzen · schnelle Bedienung · zuverlässige Daten · Projekt-/Aufgabenstruktur · Design · Automatisierung · Erweiterbarkeit.

## Stack und Aufbau

- Backend: Python 3.11+, FastAPI, SQLAlchemy 2, SQLite (`backend/data/projekte.db`), Pydantic 2, openpyxl. Port 8765, nur Python auf dem Zielrechner (Windows).
- Frontend: React 18, TypeScript, Vite, Tailwind, lucide-react, TanStack Query, react-router. Wird gebaut nach `backend/static` und vom Backend ausgeliefert.
- Start: `start.bat` (Windows), `start.sh` (Linux/macOS zum Testen).

```
backend/app/
  config.py        Pfade, Port, DATABASE_URL (PMTH_* Umgebungsvariablen)
  enums.py         Status, Priorität, Kategorie, Fälligkeit, Ampel – fest im Code, Labels hier
  models.py        ORM-Tabellen
  schemas.py       Pydantic-DTOs (Out mit berechneten Feldern, Create/Update)
  scheduling.py    DIE EINZIGE STELLE für Arbeitstage, Fälligkeit, Fortschritt, Ampel, Warnungen, Vorlagenfristen
  migrate.py       Schema-Abgleich beim Start (nur ADD COLUMN / CREATE TABLE, nie löschen)
  seed.py          Grunddaten beim ersten Start (Bearbeiter, Aufgabenarten, Vorlagen, Feiertage, Einstellungen)
  services/        common (Settings, Protokoll, Serialisierung), projects, tasks, notes, folders, dashboard, views (Kalender/Zeitplan/Suche), admin (Vorlagen, Bearbeiter, Export, Backup)
  routers/api.py   alle Routen, keine Logik
backend/tests/     pytest (scheduling + API-Ablauf + Ordner + Migration)
frontend/src/
  api/             client.ts, types.ts (Spiegel der DTOs), hooks.ts (TanStack Query, nach jeder Mutation invalidateQueries)
  lib/format.ts    Datum/KW/Labels/Farbklassen
  components/      layout/Shell (Sidebar, Topbar, Suche, Glocke, Dialog-Kontext useUi), ui/, tasks/, projects/, schedule/Gantt
  pages/           Dashboard, Tasks, Projects, ProjectDetail, Calendar, Schedule, ActivityPage, Settings
e2e.py             Playwright-Durchlauf mit Screenshots nach shots/ (Server muss laufen, mit PMTH_DATA auf leeren Ordner, nie gegen backend/data)
README.md          Nutzerdoku, Logik, Update-Anleitung
```

## Feste Regeln (Invarianten)

1. Fristen-, Fortschritts- und Ampellogik nur in `scheduling.py`, reine Funktionen ohne DB. Frontend rechnet nichts davon nach, es zeigt Felder aus den DTOs.
2. Berechnete Werte (Fortschritt, Fälligkeit, Projektfrist, Ampel) werden nie gespeichert, immer beim Lesen berechnet.
3. Jede schreibende Aktion läuft über einen Service und schreibt ins `activity_log` (`common.log`). Router enthalten keine Logik.
4. Schemaänderungen sind additiv (neue Spalte mit Default). `migrate.py` ergänzt sie beim Start. Spalten umbenennen oder löschen nur mit ausdrücklicher Freigabe und Migrationsskript.
5. `backend/data/` nie anfassen, nie ins Zip, nie löschen. Enthält die echten Daten des Nutzers.
6. Status und Priorität bleiben Enums im Code. Aufgabenarten, Vorlagen, Bearbeiter, Feiertage sind Daten.
7. Nach jeder Frontend-Änderung `npm run build`, sonst sieht der Nutzer nichts davon. Das Build-Ergebnis in `backend/static` gehört ins Paket.
8. Fehlermeldungen sagen, was passiert ist und was zu tun ist, in der Stimme der App, ohne Entschuldigung. Leere Zustände laden zum Handeln ein.
9. Design: ruhig, viel Weißraum, eine Akzentfarbe (Petrol), Semantikfarben nur für Fälligkeit und Ampel. Keine Excel-Optik, keine bunten Karten, keine Animationen ohne Anlass. Tokens in `index.css`, Komponentenklassen `.card .btn-* .input .chip`.
10. Keine neuen Abhängigkeiten ohne Grund. Keine Cloud, keine Anmeldung.

## Fachliche Entscheidungen (nicht neu diskutieren)

- Projektnummer `JJ-NNN` ist der fachliche Schlüssel, `id` nur technisch.
- Kategorien: `wea` (WEA-Vermessung), `messung`, `gutachten`, `intern`. Steuern Filter, Zeitplan, Vorlagenvorschlag.
- Projektstatus: anfrage, angebot, beauftragt, in_bearbeitung, wartet_kunde, interne_pruefung, abgeschlossen, auf_eis, abgelehnt. Aktiv sind beauftragt bis interne_pruefung.
- Aufgabenstatus: nicht_begonnen, geplant, in_bearbeitung, wartet (mit waiting_for / waiting_on / waiting_since / reminder_date), erledigt, entfaellt.
- Projektfrist = target_deadline oder order_date + offered_weeks · 7 (Kalendertage, vertraglich). Aufgabenfristen aus Vorlagen = Projektfrist minus Offset in Arbeitstagen, Feiertagstabelle, bei zu kurzer Restzeit proportional gestaucht.
- Fortschritt gewichtet über Aufgaben außer entfaellt, Gewicht aus Aufgabenart.
- Projektordner `<Basispfad>\20JJ\<Nr> <Anfrage|Auftrag> <Name>`. Phase Anfrage für anfrage/angebot, Auftrag ab beauftragt. Die App liest nur: vorhandenen Ordner suchen (`find_folder`), Pfad erkennen, Ordner öffnen. Sie legt nie Ordner an und benennt nie um, der Ablageort ist das NAS (Entscheidung 01.10.2026, nicht wieder einbauen).
- Auftragsdatum eingetragen → Status springt von anfrage/angebot auf beauftragt.
- Pfad im Feld Projektordner (Neues Projekt) → `folders.parse_folder_path` / `parseFolderPath` füllen Nummer, Name, Status (Anfrage → anfrage, Auftrag → beauftragt) nur in leere Felder, Status gilt als leer solange anfrage. Rückmeldung per Toast.
- Dashboard hat genau vier Bereiche: Heute (überfällig + heute + rote Projekte mit reasons), Als Nächstes, Aktive Projekte (sortiert rot → gelb → grün, dann Frist, zweite Zeile mit reasons/warnings bei gelb/rot), Wartet auf Rückmeldung. „Zuletzt" nur, wenn darunter Platz im Viewport ist. Leere Bereiche sind eine Textzeile ohne Kasten. Schalter in dashboard_widgets: heute, upcoming, active_projects, waiting, activity (alte Schlüssel attention/projects werden ignoriert).
- Farbträger auf dem Dashboard: nur die Zahl im Kachelstreifen und die linke Kante (rot überfällig/rotes Projekt, orange heute). Sonst keine Semantikfarbe.
- Kalender: Standard Monat, Ansicht in localStorage (`calendar_view`). Monat und Woche füllen die Höhe des Viewports, Sa/So in der Woche nur breit, wenn dort Aufgaben liegen.
- `.page` ist volle Breite mit 20 px Rand, `.page-narrow` (1240 px) nur für Formularseiten wie Einstellungen. Sidebar unter 1400 px standardmäßig eingeklappt (Laptop 1366 startet eingeklappt).
- Datumsfelder sind `DateInput` (ui/index.tsx): tippen, Kalender oder Einfügen aus der Zwischenablage (`parsePastedDate` in format.ts: TT.MM.JJJJ, TT.MM.JJ, TT.MM., ISO). Kein nacktes `<input type="date">` mehr.
- Kein Excel-Import. Export nach Excel/CSV ja.
- Ein Nutzer, keine Anmeldung, „Ich bin" in den Einstellungen. Mehrbenutzer später über users + activity_log.user_id.

## So wird gearbeitet

**Vor dem Code**: Aufgabe in zwei Sätzen wiederholen, betroffene Dateien nennen, dann bauen. Bei Unklarheit eine Frage, nicht fünf. Expensive-to-redo-Änderungen (Datenmodell, Navigation, Dashboard-Struktur) kurz als Plan zeigen, Rest direkt umsetzen.

**Kleine Schritte**: eine fachliche Änderung je Durchgang. Logik zuerst in `scheduling.py` oder einem Service mit Test, dann API, dann Typen in `types.ts`, dann UI.

**Prüfen ist Pflicht, nicht Option**:
```
cd backend && .venv/bin/python -m pytest -q          # Linux/macOS
cd backend && .venv\Scripts\python -m pytest -q      # Windows
cd frontend && npx tsc --noEmit && npm run build
```
Bei UI-Änderungen zusätzlich `python e2e.py` bei laufendem Server und die betroffenen Screenshots in `shots/` ansehen. Nie „sollte funktionieren" schreiben, wenn es nicht gelaufen ist.

**Abschluss jeder Aufgabe**: `npm run build` ausführen, `backend/static` mit committen, Branch pushen, Pull Request nach `main` erstellen und mergen. Der Nutzer hat lokal kein Git und holt den Stand per „Download ZIP" von `main`. Was nicht auf `main` ist, kommt bei ihm nicht an.

**Vor jeder UI-Änderung**: einmal `python -m playwright install chromium` in der venv ausführen, falls der Browser fehlt. Geht der Download nicht (Cloud-Sitzung hinter Proxy), ein vorhandenes Chromium per `PMTH_CHROMIUM=/opt/pw-browsers/chromium` an `e2e.py` geben. Danach `e2e.py` bei laufendem Server laufen lassen und die Screenshots in `shots/` prüfen.

**Definition of Done**: Tests grün, Build grün, Typen und DTOs synchron, Protokolleintrag für neue Schreibaktionen, README-Abschnitt angepasst, wenn sich Verhalten für den Nutzer ändert, CLAUDE.md-Abschnitt „Entscheidungen" oder „Backlog" angepasst, wenn etwas entschieden oder erledigt wurde.

## Tokens sparen

- Diese Datei ist das Gedächtnis. Nicht bei jedem Start README, alle Services und alle Seiten lesen. Gezielt grep/Glob, dann nur die Funktion lesen, die geändert wird.
- `backend/static`, `node_modules`, `shots`, `.venv`, `data` nie lesen oder listen.
- Delegieren an günstigere Modelle (Subagent mit `model: haiku` oder `sonnet`), wenn die Aufgabe klar umrissen ist: Tests ausführen und Ergebnis zusammenfassen, Review einer Änderung gegen die Invarianten oben, Screenshots prüfen, Typen zwischen `schemas.py` und `types.ts` abgleichen, README-Absätze nachziehen, Suche nach Verwendungsstellen. Das Hauptmodell macht Architektur, Datenmodell, Scheduling-Logik und alles, was mehr als zwei Dateien zusammen verstehen muss.
- Explore-Agent für „wo wird X verwendet" statt selbst zehn Dateien zu öffnen.
- Keine ganzen Dateien neu schreiben, wenn ein Edit reicht. Keine Code-Blöcke in der Antwort wiederholen, die ohnehin in der Datei liegen.
- Ausgaben von pytest/build auf die letzten Zeilen kürzen (`| tail`).
- Nicht spekulieren, was in einer Datei steht. Kurz nachsehen oder gezielt fragen.

## Statusmeldung an den Nutzer

Kurz, immer gleich aufgebaut, am Ende jedes Durchgangs:

```
Erledigt: <was sich geändert hat, eine Zeile je Punkt>
Geprüft:  <welche Befehle gelaufen sind, Ergebnis in Zahlen>
Offen:    <was noch fehlt oder was ich wissen muss, sonst „nichts">
```

Zwischendurch nur melden, wenn sich die Richtung ändert oder eine Entscheidung ansteht. Keine Zusammenfassung des Codes, keine Wiederholung der Aufgabe, keine Floskeln.

## Nicht tun

- Keine UserForms-Logik, kein Excel-Nachbau, keine Tabellen mit 20 Spalten als Hauptansicht.
- Keine Features, die nicht aus einer der fünf Morgenfragen oben folgen, ohne Rückfrage.
- Keine Priorisierung „erfinden", die nicht aus Fristen, Status oder Priorität folgt. Jede Hervorhebung trägt ihren Grund als Text (`reasons`, `warnings`).
- Keine stillen Datenänderungen: jede Automatik (Statussprung, Fristen stauchen) ist im Protokoll oder in einer Rückmeldung sichtbar. Keine Schreibzugriffe auf das Dateisystem außerhalb von `backend/data`.
- Keine Semikolons in deutschen UI-Texten, keine Großschreibung ganzer Wörter, keine „→"-Anhängsel an Buttons.

## Backlog (Reihenfolge = Vorschlag, Nutzer entscheidet)

1. Drag & Drop für Aufgabenreihenfolge auf der Projektseite (heute Pfeile)
2. Tastatur in Listen: j/k bewegen, e erledigen, Enter öffnen
3. Dashboard-Bereiche per Drag verschieben (heute nur ein-/ausblenden)
4. Wochenbericht als Export (erledigt / fällig / wartet je Woche)
5. Rechnungsstatus je Projekt (gestellt, bezahlt) als eigene Felder, wenn Aufgabe „Rechnung" nicht reicht
6. Zeiterfassung je Aufgabe (Start/Stopp), erst wenn Marcel sie wirklich braucht
7. Outlook: Aufgabe als Termin anlegen (ICS-Download reicht als erster Schritt)
8. Netzwerkbetrieb mit mehreren Nutzern: Anmeldung, `PMTH_HOST=0.0.0.0`, PostgreSQL

Erledigt und nicht mehr offen: Excel-System (VBA, separates Paket), Web-App v1.0 mit Dashboard, Aufgaben, Projekten, Kalender, Zeitplan, Aktivitäten, Einstellungen, Export, Backup, Projektordner-Automatik, Schema-Migration. Pfad einfügen im Projektformular. Datum einfügen in Datumsfelder. Ordner-Automatik (anlegen, umbenennen, abgleichen) wieder ausgebaut. Verdichtung für Laptop 1366×768 (volle Breite, vier Dashboard-Bereiche, Kalender füllt die Höhe, e2e-Screenshots bei 1366×768).

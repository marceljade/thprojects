# Projektmanagement T&H – lokale Web-App

Stand 01.10.2026 · Version 1.0.0

Projekte → Aufgaben → Notizen/Aktivitäten. Läuft komplett lokal auf dem eigenen PC, Daten in einer SQLite-Datei neben der Anwendung.

## Start unter Windows

1. Ordner auf ein lokales Laufwerk kopieren (Pfad ohne Sonderzeichen). Die Datenbank sollte nicht direkt auf dem NAS liegen, SQLite verträgt Netzlaufwerke schlecht. Sicherungen lassen sich per Kopie dorthin legen.
2. Python 3.11 oder neuer muss installiert sein (`python --version` in der Eingabeaufforderung).
3. `start.bat` doppelklicken. Beim ersten Start wird in `backend\.venv` eine eigene Python-Umgebung mit den fünf benötigten Paketen angelegt, das dauert etwa eine Minute und braucht einmalig Internet. Danach öffnet sich der Browser mit `http://localhost:8765`.
4. Beenden: das minimierte Server-Fenster schließen.

Beim ersten Öffnen ist die Datenbank leer. Reihenfolge, die sich bewährt: Einstellungen prüfen (Ich bin, Basispfad zum NAS, Bearbeiter, Vorlagen) → laufende Projekte anlegen, je mit passender Vorlage → Fristen nachziehen.

## Tastatur

`n` neue Aufgabe · `p` neues Projekt · `/` Suche · `Esc` schließt Dialoge · in Notizfeldern `Strg+Enter` speichert.

In jedes Datumsfeld kannst du ein Datum aus der Zwischenablage einfügen (`Strg+V`), z. B. `15.10.2026`, `15.10.26` oder `2026-10-15`. Was kein Datum ist, wird mit Hinweis abgelehnt.

## Was wo liegt

| Pfad | Inhalt |
|---|---|
| `backend/app/` | FastAPI-Backend: `models.py` (Datenmodell), `scheduling.py` (alle Fristen-, Fortschritts- und Ampellogik), `services/`, `routers/api.py`, `seed.py` (Grunddaten beim ersten Start) |
| `backend/static/` | fertig gebautes Frontend, wird vom Backend ausgeliefert |
| `backend/data/projekte.db` | die Datenbank. Sichern = Datei kopieren |
| `backend/data/backups/` | automatische Sicherungen (einmal täglich beim Start, die letzten 30 bleiben) |
| `backend/tests/` | pytest: `cd backend && .venv\Scripts\python -m pytest` |
| `frontend/` | React/TypeScript-Quellen. Nur nötig, wenn an der Oberfläche entwickelt wird: `npm install`, `npm run build` schreibt nach `backend/static` |
| `e2e.py` | Playwright-Durchlauf mit Screenshots (Entwicklung) |

## Logik in Kurzform

- **Projektfrist** = Ziel-Frist (manuell) oder sonst Auftragsdatum + Wochen · 7.
- **Vorlagenfristen** = Projektfrist minus Offset in Arbeitstagen (Feiertagstabelle). Passt der Vorlagenzeitraum nicht mehr in die Restzeit, werden die Offsets proportional gestaucht, damit keine Frist in der Vergangenheit entsteht.
- **Fälligkeit** je Aufgabe: Überfällig · Heute · Demnächst (≤ 3 Arbeitstage, einstellbar) · Diese Woche · Später · Ohne Frist · Erledigt. Erledigte und entfallene Aufgaben sind nie überfällig.
- **Fortschritt** = gewichtet über alle Aufgaben außer „Entfällt". Gewicht kommt aus der Aufgabenart, je Aufgabe änderbar.
- **Ampel Projekt**: rot bei überfälliger Aufgabe oder überschrittener Projektfrist · gelb bei Frist in ≤ 3 bzw. ≤ 5 Arbeitstagen · grün sonst · grau bei Anfrage/Angebot/Auf Eis · abgeschlossen. Dazu Hinweise: kein Bearbeiter, keine offene Aufgabe, keine Projektfrist, Aufgaben ohne Frist, Aufgaben deutlich nach der Projektfrist, mehr offene Aufgaben als Arbeitstage.
- **Wartet auf Rückmeldung** ist ein Aufgabenstatus mit „worauf, von wem, seit wann, Erinnerung am". Erinnerungen erscheinen in der Glocke.
- **Dashboard** hat vier Bereiche: Heute (überfällig, heute fällig, rote Projekte mit Grund), Als Nächstes, Aktive Projekte (rot vor gelb vor grün, dann nach Frist) und Wartet auf Rückmeldung. Welche Bereiche erscheinen, stellst du in den Einstellungen ein.
- **Kalender** startet in der Monatsansicht und merkt sich die zuletzt gewählte Ansicht im Browser.
- **Kategorien**: WEA-Vermessung · Messung · Gutachten/Prognose · Intern. Steuern Filter, Zeitplan und den Vorlagenvorschlag.
- **Historie**: Anlegen, Erledigen, Status-, Frist-, Bearbeiter-, Prioritätsänderungen, Notizen, Vorlagen.

## Projektordner

Die App verändert auf dem NAS nichts. Sie legt keine Ordner an, benennt keine um, verschiebt und löscht nichts. Sie liest nur: den Ordner zur Projektnummer finden und öffnen. Ordner legst du selbst an und benennst sie selbst um.

Erwarteter Name: `<Basispfad>\20JJ\<Projektnr> <Anfrage|Auftrag> <Projektname>`, zum Beispiel `…\2024\24-019 Auftrag Schall Schatten WP Neuscharrel, LK Cloppenburg`. „Anfrage" bei Status Anfrage und Angebot erstellt, „Auftrag" ab Beauftragt.

- **Pfad einfügen**: gibt es den Ordner schon, kannst du im Formular „Neues Projekt" als Erstes den Pfad ins Feld Projektordner einfügen. Projektnummer, Projektname und Status (Anfrage oder Beauftragt) werden daraus übernommen, aber nur in Felder, die noch leer sind.
- **Finden**: bleibt das Feld leer, sucht die App im Jahresordner des Basispfads nach einem Ordner, der mit der Projektnummer beginnt, und übernimmt ihn. Das Formular zeigt vorab „Erwarteter Ordner: …" mit gefunden oder nicht gefunden. Findet sie beim Anlegen nichts, probiert sie es bei jedem Öffnen der Projektseite erneut, bis du den Ordner angelegt hast. Jede Übernahme steht im Protokoll.
- **Öffnen**: „Projektordner öffnen" auf der Projektseite öffnet den hinterlegten Ordner im Explorer.
- **Abweichung**: passt der Ordnername nicht zum erwarteten Namen, zeigt die Projektseite einen Hinweis („Kein Ordner gefunden", „Ordner heißt noch Anfrage", „Ordnername weicht ab") mit dem Knopf „Erwarteten Namen kopieren". Umbenennen tust du auf dem NAS. Beim nächsten Öffnen der Projektseite findet die App den Ordner unter dem neuen Namen wieder, solange er mit der Projektnummer beginnt.

## Update auf eine neue Version – Daten behalten

Die Projekte liegen ausschließlich in `backend\data\projekte.db` (plus Sicherungen in `backend\data\backups`). Alles andere ist Programm und kann ersetzt werden.

1. Server beenden (Server-Fenster schließen).
2. Sicherheitskopie von `backend\data` machen.
3. Neues Zip entpacken und den Ordner `backend\data` aus der alten Installation hineinkopieren. Alternativ nur `backend\app` und `backend\static` aus dem neuen Zip über die alte Installation kopieren.
4. `start.bat` – beim Start gleicht die App das Datenbankschema automatisch ab: neue Tabellen und neue Spalten werden ergänzt, vorhandene Daten bleiben. Was ergänzt wurde, steht im Server-Fenster.

Spalten werden dabei nie gelöscht oder umbenannt. Sollte das einmal nötig sein, gibt es ein Skript dazu und einen Hinweis im Changelog.

## Erweiterung

- PostgreSQL: Umgebungsvariable `PMTH_DATABASE_URL=postgresql+psycopg://…` setzen, `psycopg` installieren.
- Netzwerkbetrieb: `PMTH_HOST=0.0.0.0` – dann aber Firewall beachten, es gibt keine Anmeldung. „Projektordner öffnen" funktioniert nur auf dem Rechner, auf dem der Server läuft, sonst wird der Pfad zum Kopieren angezeigt.
- Alle Berechnungen liegen in `scheduling.py`, alle Schreibzugriffe in `services/`. Neue Felder: `models.py` + `schemas.py` + Service + Frontend-Typ.
- Datenbankänderungen: Tabellen werden beim Start angelegt (`create_all`), neue Spalten in bestehenden Datenbanken brauchen eine Migration (Alembic) oder ein manuelles `ALTER TABLE`.

## API

Swagger-Oberfläche unter `http://localhost:8765/docs`. Wichtigste Routen: `/api/dashboard`, `/api/projects`, `/api/tasks`, `/api/notes`, `/api/activity`, `/api/search?q=`, `/api/calendar`, `/api/schedule`, `/api/templates`, `/api/users`, `/api/settings`, `/api/export/excel`, `/api/export/csv`, `/api/backups`.

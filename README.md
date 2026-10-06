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

- **Frist und geplant am**: die Frist ist der Termin, „geplant am" der Tag, an dem du die Aufgabe machen willst. Das Dashboard „Heute" zeigt, was heute Frist hat, heute geplant ist oder liegen geblieben ist (geplant vor heute, noch offen, dann mit „geplant für Montag"). „Überfällig" richtet sich nur nach der Frist, eine überfällige Aufgabe steht nur dort, auch wenn sie heute geplant ist. Outlook bekommt weiter nur Fristen.

- **Projektfrist** = Ziel-Frist (manuell) oder sonst Auftragsdatum + Wochen · 7.
- **Vorlagenfristen** = Projektfrist minus Offset in Arbeitstagen (Feiertagstabelle). Passt der Vorlagenzeitraum nicht mehr in die Restzeit, werden die Offsets proportional gestaucht, damit keine Frist in der Vergangenheit entsteht.
- **Fälligkeit** je Aufgabe: Überfällig · Heute · Demnächst (≤ 3 Arbeitstage, einstellbar) · Diese Woche · Später · Ohne Frist · Erledigt. Erledigte und entfallene Aufgaben sind nie überfällig.
- **Fortschritt** = gewichtet über alle Aufgaben außer „Entfällt". Gewicht kommt aus der Aufgabenart, je Aufgabe änderbar.
- **Ampel Projekt**: rot bei überfälliger Aufgabe oder überschrittener Projektfrist · gelb bei Frist in ≤ 3 bzw. ≤ 5 Arbeitstagen · grün sonst · grau bei Anfrage/Angebot/Auf Eis · abgeschlossen. Dazu Hinweise: kein Bearbeiter, keine offene Aufgabe, keine Projektfrist, Aufgaben ohne Frist, Aufgaben deutlich nach der Projektfrist, mehr offene Aufgaben als Arbeitstage.
- **Wartet auf Rückmeldung** ist ein Aufgabenstatus mit „worauf, von wem, seit wann, Erinnerung am". Erinnerungen erscheinen in der Glocke.
- **Dashboard** hat vier Bereiche: Heute (überfällig, heute fällig, rote Projekte mit Grund), Als Nächstes, Aktive Projekte (rot vor gelb vor grün, dann nach Frist) und Wartet auf Rückmeldung. Welche Bereiche erscheinen, stellst du in den Einstellungen ein.
- **Kalender** zum Planen: Monat (Standard) und Woche, die Ansicht merkt sich der Browser. Jede Aufgabe steht am Tag „geplant am", sonst am Fristtag. Ziehen mit der Maus setzt „geplant am", die Frist ändert sich dabei nie, die änderst du nur im Aufgaben-Dialog (dort gibt es „Geplant am" mit heute, morgen, +1 Tag, −1 Tag als Tastatur-Ersatz). Rechts die Leiste „Ungeplant" mit offenen Aufgaben ohne Frist und ohne Plantag, nach Projekt gruppiert, hoch zuerst. Von dort auf einen Tag ziehen plant, zurück in die Leiste hebt die Planung auf. Liegt der Plantag nach der Frist, ist die Aufgabe rot mit dem Grund „nach Frist geplant", blockiert aber nichts. Ist eine Aufgabe an einem anderen Tag geplant als ihre Frist, steht am Fristtag eine kleine Markierung „Frist: …". Projektfristen stehen als Markierung „Projektfrist · Nr". Wochenende und Feiertage sind erlaubt und optisch abgesetzt. Im Monat zeigt ein Tag höchstens vier Einträge, „+n weitere" klappt auf. In der Woche steht oben im Tag die Anzahl der Aufgaben. Erledigte bleiben an ihrem Tag, durchgestrichen und nicht verschiebbar. Jede Verschiebung steht im Protokoll.
- **Kategorien**: WEA-Vermessung · Messung · Gutachten/Prognose · Intern. Steuern Filter, Zeitplan und den Vorlagenvorschlag.
- **Historie**: Anlegen, Erledigen, Status-, Frist-, Bearbeiter-, Prioritätsänderungen, Notizen, Vorlagen.

## Folgeaufträge

Ein Projekt ist abgeschlossen, später kommt zum Beispiel eine Planänderung. Dann beginnt im selben Projekt ein neuer Durchgang mit derselben Projektnummer und demselben Ordner: Anfrage, Angebot, Auftrag, Bearbeitung, Abschluss.

- **Starten**: auf der Projektseite eines abgeschlossenen Projekts „Folgeauftrag starten", Titel (z. B. „Planänderung 2026"), Startstatus Anfrage oder Angebot, Datum und optional eine Vorlage. Die bisherige Runde wird abgeschlossen, das Projekt steht wieder auf Anfrage, Auftragsdatum, Dauer und Frist sind leer.
- **Runden**: über der Aufgabenliste schaltest du zwischen „1 Erstauftrag", „2 Planänderung 2026" usw. um. Die aktuelle Runde ist vorausgewählt. Frühere Runden sind nur zum Nachlesen, ihre Aufgaben lassen sich öffnen, aber nicht abhaken oder verschieben.
- **Tagesansichten**: Dashboard, Aufgabenliste, Kalender und Zeitplan zeigen nur die Aufgaben der aktuellen Runde. Status, Frist, Fortschritt und Ampel eines Projekts beziehen sich immer auf die aktuelle Runde. Ab Runde 2 steht hinter dem Projektnamen ein kleiner Chip „Folgeauftrag 2".
- **Notizen** bleiben projektweit sichtbar, die Historie zeigt den Rundenwechsel. Der Export hat eine Spalte „Runde".
- Auf dem NAS ändert sich nichts. Als erwarteter Ordnername gilt ab Runde 2 immer die Phase Auftrag, auch wenn die neue Runde noch Anfrage ist.

## Outlook

Die App kann ihre Fristen in einen eigenen Outlook-Kalender schreiben. Einweg: App nach Outlook, die App liest keine Outlook-Termine.

- **Voraussetzung**: das klassische Outlook (Microsoft 365, klassische Ansicht) auf diesem Rechner, mit dem Postfach eingerichtet. Die Termine liegen im Postfach und erscheinen damit auch im neuen Outlook, in Outlook im Web und auf dem Handy, geschrieben werden sie aber nur über das klassische Outlook.
- **Ordner**: beim ersten Abgleich legt die App unter deinem Kalender den Ordner „Projektfristen" an. Nur dort schreibt, ändert und löscht sie, und auch dort nur ihre eigenen Termine. Der Hauptkalender und alle anderen Ordner werden nie angefasst. Eigene Termine, die du selbst in „Projektfristen" anlegst, bleiben unberührt.
- **Was drin steht**: jede offene Aufgabe mit Frist als ganztägiger Termin am Fristtag, Betreff „Projektnr. Projektname: Aufgabe". Jede Projektfrist eines aktiven Projekts als „Projektnr. Projektname: Projektfrist". Priorität hoch oder kritisch bekommt die Kategorie „Projektfristen" in Rot, die App legt sie beim ersten Abgleich in deiner Kategorienliste an. Alles ohne Erinnerung und als „Frei", damit der Kalender nichts blockiert.
- **Abgleich**: in den Einstellungen unter Outlook. „Aus" (Standard) schreibt nichts. „Manuell" zeigt den Knopf „Mit Outlook abgleichen" auf der Kalenderseite und in den Einstellungen. „Automatisch" gleicht beim Start und ein paar Sekunden nach jeder Änderung an Fristen oder Status im Hintergrund ab. Der Abgleich ist vollständig: fehlende Termine werden angelegt, geänderte aktualisiert, Termine zu erledigten, entfallenen oder gelöschten Aufgaben entfernt. Die Rückmeldung sagt „x angelegt, y geändert, z entfernt", der Zeitpunkt des letzten Abgleichs steht in den Einstellungen.
- **Leeren**: „Outlook-Kalender leeren" entfernt alle von der App angelegten Termine aus „Projektfristen", mit Rückfrage. Beim nächsten Abgleich kommen sie wieder.
- **Wenn es hakt**: die Meldung sagt, was fehlt. Outlook nicht installiert, Outlook nicht erreichbar (einmal starten und das Postfach öffnen), oder Outlook hat den Zugriff abgelehnt (Sicherheitsabfrage in Outlook mit „Zulassen" bestätigen). Ein Fehler im Abgleich bricht nie eine Änderung in der App ab, er steht nur im Protokoll und in den Einstellungen.

## Projektordner

Die App verändert auf dem NAS nichts. Sie legt keine Ordner an, benennt keine um, verschiebt und löscht nichts. Sie liest nur: den Ordner zur Projektnummer finden und öffnen. Ordner legst du selbst an und benennst sie selbst um. Das ist technisch abgesichert: Sobald ein Basispfad gesetzt ist, blockt ein Schreibschutz im Server jeden schreibenden Dateizugriff unterhalb dieses Pfads, egal aus welchem Teil der App, mit einer klaren Meldung. In den Einstellungen steht dann „Schreibschutz aktiv".

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

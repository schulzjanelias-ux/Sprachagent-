# Architektur

Ziel: klein genug, um in zwei Wochen real getestet zu werden; sauber genug, um
nicht weggeworfen zu werden (Brief §16).

---

## 1. Überblick

```
  Handy (PWA)                    Firmenserver                     Büro
┌──────────────┐          ┌──────────────────────┐        ┌────────────────┐
│ Aufnahme     │  HTTPS   │ FastAPI              │        │ Bauablaufmappe │
│ Bestätigung  │ ───────► │  ├ Auth (Cookie)     │        │  (Original,    │
│ Ausgangskorb │          │  ├ Berichts-Workflow │        │   unberührt)   │
│ (IndexedDB)  │ ◄─────── │  ├ Transkribierer ─┐ │        └────────┬───────┘
└──────────────┘          │  ├ Strukturierer  ─┼─┼──► KI-Anbieter   │ Kopie
                          │  ├ Validierung     │ │                  ▼
                          │  └ Export ─────────┘ │        ┌────────────────┐
                          │       │              │        │ befüllte Kopie │
                          │  ┌────▼─────┐        │ ─────► │ + XLSX + CSV   │
                          │  │ SQLite   │        │        └────────────────┘
                          │  └──────────┘        │
                          └──────────────────────┘
```

Ein Prozess, eine Datenbankdatei, ein Reverse-Proxy davor. Kein Broker, kein
Cache-Server, kein Container-Cluster.

---

## 2. Verzeichnisstruktur

```
Sprachagent-/
├─ app/
│  ├─ main.py                     FastAPI-App, Lifespan, Static-Mount
│  ├─ config.py                   Einstellungen aus .env (pydantic-settings)
│  ├─ datenbank.py                Engine, Session, Migrationen
│  ├─ modelle.py                  SQLAlchemy-Tabellen
│  ├─ schemas.py                  Pydantic: Ein-/Ausgabe, LLM-Schema
│  ├─ sicherheit.py               Passwortprüfung, Cookie, Ratenbegrenzung
│  ├─ abhaengigkeiten.py          aktueller Benutzer, Projektzugriff
│  ├─ routen/
│  │   ├─ anmeldung.py            POST /api/anmelden|abmelden|passwort, GET /api/ich
│  │   ├─ stammdaten.py           GET  /api/projekte, /api/gewerke, /api/einheiten
│  │   │                          (alle erst nach Anmeldung, D-11)
│  │   ├─ berichte.py             Aufnahme → Entwurf → Rückfrage → Bestätigung
│  │   └─ export.py               POST /api/export
│  ├─ dienste/
│  │   ├─ transkription/
│  │   │   ├─ basis.py            Protocol Transkribierer
│  │   │   ├─ whisper_api.py      Whisper-kompatibler Endpunkt
│  │   │   ├─ faster_whisper.py   lokal
│  │   │   └─ attrappe.py         deterministisch, für Tests
│  │   ├─ strukturierung/
│  │   │   ├─ basis.py            Protocol Strukturierer
│  │   │   ├─ claude.py           Claude API, striktes JSON-Schema
│  │   │   └─ attrappe.py
│  │   ├─ mengen.py               deutsche Zahlen → Decimal
│  │   ├─ einheiten.py            Normalisierung auf die zentrale Liste
│  │   ├─ datum.py                „gestern", „letzten Freitag" → date
│  │   ├─ vollstaendigkeit.py     Lückenprüfung, Formulierung der Rückfrage
│  │   ├─ dialog.py               Rundenführung, Zusammenfassung
│  │   └─ excel/
│  │       ├─ geometrie.py        Datum/Slot → Zeile, Geometrieprüfung
│  │       ├─ leser.py            Stammdaten aus der Mappe lesen
│  │       ├─ befueller.py        Kopie befüllen, Medien reparieren, prüfen
│  │       └─ export.py           XLSX + CSV
│  ├─ statisch/                   index.html, app.js, stil.css, sw.js, manifest
│  └─ cli.py                      stammdaten-laden · mappe-befuellen · benutzer-anlegen
├─ konfiguration/
│  ├─ benutzer.yaml               Anmeldename, Rolle, Passwort-Hash, Excel-Name
│  ├─ projekte.yaml               Projekt → Mappenpfad
│  └─ einheiten.yaml              zulässige Einheiten + Synonyme
├─ referenz/                      Bauablaufmappe (Analysegrundlage)
├─ werkzeuge/mappe_analysieren.py
├─ tests/
└─ docs/
```

---

## 3. Datenmodell

Der Brief (§6) gibt `DailyReport` / `DailyReportItem` vor. Vier Tabellen kommen
hinzu, weil sie ohne sie nicht funktionieren würden: `anwesenheit` (Zeiten je
Mitarbeiter — Excel braucht F und G, D-03), `dialogschritte` (Nachweis, was
gesagt wurde), `exportlauf` und `exportzuordnung` (was ist in welcher Mappe
gelandet — verhindert Doppelbuchungen, R-06 im Mapping).

```
mitarbeiter          projekte
─────────────        ──────────────
id                   id                      Einheiten liegen NICHT in der
anmeldename          name                    Datenbank, sondern in
anzeigename          mappe_pfad              konfiguration/einheiten.yaml.
excel_name  ─┐       baubeginn               Eine zweite Quelle waere eine
passwort_hash│       bauende                 Fehlerquelle ohne Gewinn (D-07).
rolle        │       aktiv
regelbeginn  │
aktiv        │
             │
             │   berichte
             │   ──────────────────────────────────────────
             └──► mitarbeiter_id
                  projekt_id
                  datum
                  status         entwurf|rueckfrage|bestaetigt|storniert
                  rohtranskript                    (Brief §6)
                  bemerkung                        → Excel J
                  bestaetigt_am
                  version                          Korrekturen, D-13
                  ersetzt_bericht_id
                  erstellt_am
                       │
        ┌──────────────┼──────────────┬────────────────┐
        ▼              ▼              ▼                ▼
  positionen        anwesenheiten  dialogschritte  exportzuordnungen
  ────────────────  ─────────────  ──────────────  ─────────────────
  taetigkeit        gewerk         sprecher        exportlauf_id
  beschreibung      beginn         text            bericht_id
  menge  Decimal    ende           audio_dauer     ziel_zeile
  einheit_code      quelle         erstellt_am     ziel_slot
  geschaetzt  bool  (gesprochen|
  konfidenz   float  abgeleitet|
  reihenfolge        korrigiert)
```

Entwurfsentscheidungen:

- **`menge` ist `Decimal`, nie `float`.** Abrechnungsnahe Werte.
- **`gewerk` sitzt an der Anwesenheit, nicht am Bericht.** Ein Mitarbeiter kann
  vormittags Trockenbau und nachmittags Maler machen — und genau danach rechnet
  `Eigenleistung` ab. Jede Anwesenheit ist genau eine Zeile in der Mappe.
- **`konfidenz` je Position.** Brief §8: Unsicherheit muss sichtbar werden.
- **`quelle` in `anwesenheit`.** Macht abgeleitete Zeiten (D-03) im Nachhinein
  unterscheidbar.
- **Nie hart löschen.** Storno und Versionierung statt `DELETE` (D-13).
- **Der Exportlauf ist je Zielzeile eindeutig, nicht je Bericht.** Wer an einem
  Tag zwei Gewerke gearbeitet hat, belegt zwei Zeilen und erscheint zweimal im
  selben Lauf. Eine Regel auf (Lauf, Bericht) verbietet genau den Fall, der die
  Eigenleistung erst richtig rechnen lässt — das ist beim Ende-zu-Ende-Test
  aufgefallen, nicht beim Entwurf.
- **SQLite braucht zwei Einstellungen je Verbindung**, die es nicht von selbst
  mitbringt: `PRAGMA foreign_keys=ON` (sonst wird gar nichts geprüft) und
  `journal_mode=WAL` (sonst blockiert ein Exportlauf jede Erfassung).
- **Mengen als Text, nicht als `NUMERIC`.** SQLite kennt kein `Decimal`;
  SQLAlchemys `Numeric` weicht dort auf `float` aus und verliert `12,5` oder
  `0,1`. Bei abrechnungsnahen Werten ist das nicht hinnehmbar — deshalb
  `DezimalAlsText`.

---

## 4. Ablauf eines Berichts

```
1  POST /api/berichte/aufnahme        Audio + projekt_id + client_uuid
                                      → Transkription
                                      → Strukturierung (LLM, striktes Schema)
                                      → Pydantic-Validierung
                                      → Normalisierung (Einheiten, Mengen, Datum)
                                      → Lückenprüfung
      ◄── { bericht_id, entwurf, fehlende_felder[], rueckfrage|null }

2  POST /api/berichte/{id}/rueckfrage  Audio oder Text
                                       → Transkription
                                       → Zusammenführung mit dem Entwurf
      ◄── { entwurf, fehlende_felder[], rueckfrage|null }        max. 2 Runden

3  PATCH /api/berichte/{id}            manuelle Korrektur einzelner Felder
      ◄── { entwurf }

4  POST /api/berichte/{id}/bestaetigen  erwartete Version zur Kollisionsprüfung
      ◄── { status: "bestaetigt", beleg }
```

Zwei Eigenschaften, die dieser Ablauf haben muss:

**Idempotenz.** Jeder Bericht trägt eine clientseitig erzeugte `client_uuid`
mit `UNIQUE`-Bedingung. Bei schlechtem Netz geht die Antwort verloren, das
Handy sendet erneut — der zweite Aufruf liefert denselben Bericht zurück,
statt Stunden zu verdoppeln. Ohne das ist die geforderte automatische
Wiederholung (Brief §21 L) gefährlich.

**Kein stiller Fehlschlag.** Jede Antwort trägt einen Zustand, den das Frontend
anzeigt. Der Mitarbeiter sieht immer, ob sein Bericht angekommen ist (Brief §28).

### Der Rückfragedialog

Fehlende Angaben werden zu **einer** Frage gebündelt, nicht zu einer je Feld
(D-12). Zwei Positionen ohne Menge ergeben:

> Wie viel habt ihr bei Spachtelarbeiten und Schleifarbeiten geschafft?

Die Antwort wird den offenen Positionen zugeordnet — zuerst über den Namen der
Tätigkeit (`gespachtelt` trifft `Spachtelarbeiten`), sonst der Reihe nach, aber
nur wenn die Anzahl genau aufgeht. Bleibt es mehrdeutig, wird **nichts geraten**;
die Lücke bleibt offen.

Zwei Eigenschaften, die den Dialog vor sich selbst schützen:

- **Bestätigtes wird nie überschrieben.** Eine unglückliche zweite Aufnahme darf
  eine klare Angabe aus der ersten nicht verdrängen.
- **Nach zwei Runden ist Schluss.** Was dann noch fehlt, wird markiert und von
  Hand ergänzt. Ein Dialog, der länger dauert als das Formular, das er ersetzen
  soll, hat sein Ziel verfehlt.

Schlägt die Auswertung der Antwort fehl, bleibt der bisherige Entwurf erhalten
und der Mitarbeiter bekommt einen Hinweis — der Stand geht nie verloren.

---

## 5. Austauschbare Anbieter

```python
class Transkribierer(Protocol):
    def transkribiere(self, audio: bytes, mime: str, vokabular: list[str]) -> Transkript: ...

class Strukturierer(Protocol):
    def strukturiere(self, transkript: str, kontext: Kontext) -> Rohentwurf: ...
```

Auswahl über `.env` (`TRANSKRIPTION_ANBIETER=whisper_api|faster_whisper|attrappe`).
Die Attrappen sind kein Wegwerfcode: Sie machen die gesamte Testsuite ohne
Netz, ohne Schlüssel und ohne Kosten lauffähig.

### Aufruf des Sprachmodells

- Modell `claude-opus-5`
- striktes JSON-Schema über `output_config.format`, `additionalProperties: false`
- niedrige Effort-Stufe — Extraktion, keine Schlussfolgerung
- serverseitige `fallbacks`-Behandlung und Prüfung von `stop_reason` vor dem
  Lesen des Inhalts; eine Ablehnung darf keinen Traceback erzeugen, sondern
  führt ins manuelle Formular
- Systemprompt mit den 12 Gewerken, den Einheiten und der Regel: **niemals
  raten** — fehlende Werte bleiben `null`

**Das Modell liefert nie ein aufgelöstes Datum und nie eine normalisierte
Einheit.** Es liefert den Wortlaut („gestern", „Quadratmeter"); Auflösung und
Normalisierung passieren deterministisch im Code. So ist beides ohne API-Aufruf
testbar (Brief §21 N) und kann nicht halluzinieren.

---

## 6. Frontend

Sechs Bildschirme: Anmeldung · Projektwahl · Aufnahme · Rückfrage ·
Bestätigung · eigene Berichte. Statisches HTML, kein Build-Schritt.

**Aufnahme.** `MediaRecorder`; Android liefert WebM/Opus, iOS MP4/AAC — beides
wird serverseitig akzeptiert und beim Anbieter konvertiert. Maximal 90 Sekunden,
danach automatischer Stopp mit Hinweis.

**Ausgangskorb (Brief §21 L, R-06).** Jede Aufnahme landet zuerst in IndexedDB,
danach beginnt der Versand. Automatische Wiederholung mit wachsendem Abstand;
der Status jedes Eintrags ist dauerhaft sichtbar:

```
● noch nicht gesendet     ◐ wird gesendet     ✓ gespeichert     ✕ Fehler
```

Ehrlich bleibt die Anzeige dadurch, dass „gespeichert" erst nach der
Serverbestätigung erscheint. iOS Safari kennt kein Background Sync — offene
Einträge werden beim nächsten Öffnen versendet, und die App sagt das auch so,
statt Zustellung zu suggerieren.

**Fehlt das Netz beim Aufnehmen**, bietet die App sofort das manuelle Formular
an. Der Mitarbeiter steht dann noch vor dem Handy; zwei Stunden später nicht
mehr.

**Gestaltung** (Brief §19): neutral, hochwertig, wenig Rauschen. Farben,
Abstände und Radien als CSS-Variablen in einer Datei — das HAG-CI wird später
dort und nur dort gesetzt. Touch-Ziele mindestens 56 px, Aufnahmeknopf deutlich
größer. Kontraste nach WCAG AA, weil das Handy auf der Baustelle in der Sonne
gehalten wird.

---

## 7. Sicherheit

| Thema | Umsetzung |
|---|---|
| Anmeldung | Anmeldename + Passwort (min. 10 Zeichen), Argon2id (D-11) |
| Session | signiertes Cookie, `HttpOnly`, `Secure`, `SameSite=Lax`, 30 Tage. Eine `sitzungs_kennung` je Konto beendet bei Passwortwechsel **alle** laufenden Sitzungen, auch auf anderen Geräten |
| Geheimnisse | ausschließlich `.env`; `.env` und `konfiguration/*.yaml` in `.gitignore` |
| Zugriff | jeder Endpunkt hinter Authentifizierung; Stammdaten erst **nach** Anmeldung — die App ist öffentlich erreichbar (D-10) und darf die Belegschaft nicht preisgeben; Berichte nur eigene, außer Rolle `bauleiter` |
| Eingaben | Pydantic an der Grenze; Dateigröße und MIME-Typ des Audios begrenzt |
| Protokolle | kein Passwort, kein Audio, keine Transkripte auf `INFO`; Fehler mit Vorgangs-ID statt Inhalt |
| Audio | nach erfolgreicher Transkription gelöscht (D-09) |
| Ratenbegrenzung | Anmeldung je Konto **und** je IP: Verzögerung ab 3 Fehlversuchen, Sperre nach 10 für 15 Minuten. Nur je Konto ließe das Durchprobieren vieler Konten zu, nur je Adresse das aus einem Botnetz |
| Kein Konten-Orakel | Unbekanntes Konto und falsches Passwort erzeugen dieselbe Meldung **und** dieselbe Rechenzeit — gegen einen nicht existierenden Nutzer wird ein Blindhash geprüft |
| Datenschutz | Nutzung ausschließlich zur Leistungsdokumentation; keine Auswertung des Arbeitsverhaltens |

---

## 8. Betrieb

Ein `uvicorn`-Prozess hinter Reverse-Proxy (D-10). Systemd-Unit mit Neustart.
Tägliches Backup der SQLite-Datei per `VACUUM INTO` — konsistent auch bei
laufendem Zugriff — mit 30 Tagen Vorhaltung.

Gesundheitsendpunkt `/api/status` meldet: Datenbank erreichbar, Mappenpfade
lesbar, Anbieter konfiguriert. Strukturierte Protokolle nach `stdout`.

Wiederherstellung: Datenbank zurückspielen, `mappe-befuellen` erneut ausführen.
Weil die Mappe nie beschrieben wird (D-01), gibt es keinen Zustand, der sich
nicht neu erzeugen ließe.

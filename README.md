# HAG · Digitaler Tagesbericht

Sprachgeführte Erfassung von Bautagesberichten mit Export in die bestehende
HAG-Bauablaufmappe.

> **Stand: Phase 0 — Analyse abgeschlossen, Implementierung noch nicht begonnen.**
> Dieses Repository enthält derzeit die Analyse der Bauablaufmappe, die
> Architektur, das Backlog und die Entscheidungsdokumentation.

---

## Ausgangslage in einem Absatz

Mitarbeiter sprechen am Feierabend einen Tagesbericht ins Handy. Die Anwendung
transkribiert, erkennt Bauvorhaben, Gewerk, Tätigkeiten, Mengen und Einheiten,
fragt gezielt nach, was fehlt, lässt den Mitarbeiter bestätigen und erzeugt
daraus einen Export für die bestehende Excel-Projektmappe. Die Mappe bleibt das
führende Controlling-System und wird von der Anwendung **nie verändert** —
befüllt werden ausschließlich Kopien.

## Dokumentation

| Datei | Inhalt |
|---|---|
| [`docs/PROJECT.md`](docs/PROJECT.md) | Produktkontext, Umfang, Analysebericht |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Technik, Datenmodell, API, Sicherheit |
| [`docs/EXCEL-MAPPING.md`](docs/EXCEL-MAPPING.md) | vollständige Mappenanalyse und Feldabbildung |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Entscheidungen, offene Punkte, Risiken |
| [`docs/MVP-BACKLOG.md`](docs/MVP-BACKLOG.md) | Epics, Aufwände, Sprint 1 |
| [`docs/BETRIEB-ZUGANG.md`](docs/BETRIEB-ZUGANG.md) | Zugangswege vom Handy, Konfiguration, Prüfprotokoll |

## Befehle

```bash
# Einrichtung
python3 -m app.cli projekt-anlegen "Musterstraße 12" --mappe /pfad/mappe.xlsx
python3 -m app.cli benutzer-anlegen ahrens --anzeigename "M. Ahrens" \
    --excel-name Ahrens --regelbeginn 07:00

# Betrieb
python3 -m app.cli mappe-pruefen  /pfad/mappe.xlsx
python3 -m app.cli export --projekt "Musterstraße 12" --probelauf
python3 -m app.cli export --projekt "Musterstraße 12"
```

`export` erzeugt eine befüllte **Kopie** der Bauablaufmappe, ein
strukturiertes XLSX und zwei CSV-Dateien — und protokolliert, welcher Bericht
in welche Zeile ging, damit ein zweiter Lauf die Stunden nicht verdoppelt.
Die Meistermappe wird nie beschrieben.

## Analyse nachvollziehen

```bash
pip install openpyxl
python3 werkzeuge/mappe_analysieren.py
```

Das Skript ist read-only und belegt alle Strukturannahmen aus
`docs/EXCEL-MAPPING.md`: Tagesblöcke, Spaltenrollen, Datenvalidierungen,
Stammdatenlisten, abhängige Auswertungen und den Round-Trip-Verlust.
Ändert die HAG die Mappe, zeigt ein erneuter Lauf sofort, welche Annahme
gebrochen ist.

Alle Strukturbefunde wurden nach der Anonymisierung erneut verifiziert und
gelten unverändert.

## Die drei Befunde, die alles bestimmen

1. **Die Mappe rechnet in Stunden, nicht in Mengen.**
   `Eigenleistung!F = SUMIF(Gewerk; Arbeitsstunden)` — für Leistungsmenge und
   Einheit gibt es keine Zielspalte. → `docs/DECISIONS.md` · D-02
2. **Stunden sind eine Formel.** Nur Arbeitsanfang und -ende erzeugen einen
   Wert; eine gesprochene Stundenzahl erzeugt keinen. → D-03
3. **Eine Mappe ist ein Bauvorhaben.** Bauvorhaben, Baubeginn und Bauende sind
   Einzelzellen. → D-04

## Entschieden

**D-10 · Zugang.** Öffentlich erreichbare Web-App mit Anmeldename und Passwort,
kein VPN, kein Client auf dem Handy. Cloudflare Tunnel und eigene Domain sind
beide möglich und in [`docs/BETRIEB-ZUGANG.md`](docs/BETRIEB-ZUGANG.md)
konfiguriert — die App ist proxy-neutral.

**D-11 · Anmeldung.** Passwort statt PIN (min. 10 Zeichen, Argon2id). Weil die
App öffentlich erreichbar ist, zeigt die Anmeldemaske **keine
Mitarbeiterliste**; der Name wird getippt.

## Offen, bevor gebaut wird

| ID | Frage |
|---|---|
| **D-09** | Auftragsverarbeitungsvertrag für die Transkription, oder Start mit lokalem Modell? |
| **D-02** | Mengen als Text in Spalte I, oder rechenbar in einem neuen Blatt? |
| **D-03** | Ist ein abgeleiteter Regelarbeitsbeginn zulässig? |

## Hinweis zum Datenschutz

`referenz/` enthält eine **anonymisierte** Fassung der Bauablaufmappe: Die 28
Mitarbeiternamen sind durch erfundene ersetzt, die Struktur ist unverändert
(1841 verbundene Bereiche, 8 Validierungen, 9 definierte Namen, alle Formeln).
Die Produktivmappe der HAG gehört nicht ins Repository — `konfiguration/projekte.yaml`
verweist im Betrieb auf ihren Pfad im Dateisystem.

```bash
python3 werkzeuge/mappe_anonymisieren.py ORIGINAL.xlsx referenz/ZIEL.xlsx
```

Das Skript ersetzt ausschließlich `Listen!B2:B29` und prüft anschließend, dass
die Mappenstruktur unverändert ist; andernfalls verwirft es die Ausgabe.
Details: `docs/DECISIONS.md` · D-15.

Die Lieferantenliste enthält weiterhin reale Firmennamen. Das sind
Geschäfts-, keine personenbezogenen Daten — vor einer Veröffentlichung des
Repositorys aber ebenfalls zu prüfen.

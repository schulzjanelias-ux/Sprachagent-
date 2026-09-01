# MVP-Backlog

Aufwand in Personentagen, ein Entwickler. **P1** = ohne dies kein MVP.

---

## Übersicht

| Epic | Titel | Prio | Aufwand | Hängt ab von |
|---|---|---|---|---|
| 00 | Fundament und Projektgerüst | P1 | 1,0 | — |
| 07 | Datenmodell und Datenbank | P1 | 1,5 | 00 |
| 09 | Excel-Geometrie und Stammdaten | P1 | 2,0 | 00 |
| 01 | Benutzer und Anmeldung | P1 | 1,5 | 00, 07 |
| 03 | Transkription | P1 | 1,5 | 00 |
| 04 | Strukturierung per KI | P1 | 2,5 | 03, 07 |
| 05 | Validierung und Rückfrage | P1 | 2,0 | 04 |
| 02 | Sprachaufnahme im Browser | P1 | 2,0 | 01 |
| 06 | Bestätigung und Speicherung | P1 | 1,5 | 05, 02 |
| 08 | Export | P1 | 2,5 | 09, 06 |
| 10 | Tests | P1 | 2,5 | fortlaufend |
| 11 | Betrieb und Auslieferung | P1 | 1,5 | 08 |
| 12 | Ausgangskorb und Fehlertoleranz | P1 | 2,0 | 02, 06 |
| 13 | Gestaltung und Feinschliff | P2 | 1,5 | 12 |

**Summe P1: 24 Personentage · mit P2: 25,5** — realistisch 5–6 Wochen inklusive
Abstimmung, Nacharbeit und Pilotbetreuung.

---

## EPIC 00 · Fundament — P1 · 1,0 PT

Projektgerüst, `.env`-Konfiguration, Protokollierung, `/api/status`,
Testgerüst, CI mit Linter und Testlauf.

**Fertig, wenn:** `pytest` grün läuft, `/api/status` antwortet, kein Geheimnis
im Repository, CI läuft bei jedem Push.

---

## EPIC 07 · Datenmodell — P1 · 1,5 PT

Die acht Tabellen aus `ARCHITECTURE.md` §3, Migrationen, Repository-Funktionen,
Testdaten.

**Fertig, wenn:** Ein Bericht mit drei Positionen und zwei Anwesenheiten lässt
sich schreiben und vollständig zurücklesen; `client_uuid` ist eindeutig;
`menge` ist als `Decimal` nachweislich verlustfrei.

---

## EPIC 09 · Excel-Geometrie und Stammdaten — P1 · 2,0 PT

Vorgezogen, weil das Datenmodell davon abhängt.

- Stammdaten aus der Mappe lesen: 28 Mitarbeiter, 12 Gewerke, 81 Feiertage,
  Bauvorhaben, Baubeginn, Bauende
- `datum_zu_zeile()` und `zeile_zu_datum()` nach `EXCEL-MAPPING.md` §5
- Geometrieprüfung: Blockhöhe 10, Blockstart 6, Formeln in H und K vorhanden
- Sonntags- und Feiertagsprüfung, Slot-Kapazitätsprüfung

**Fertig, wenn:** Für 20 bekannte Datumswerte stimmt die berechnete Zeile mit
der tatsächlichen Zelle in der echten Mappe überein; ein manipuliertes
Testexemplar lässt die Geometrieprüfung fehlschlagen.

---

## EPIC 01 · Benutzer und Anmeldung — P1 · 1,5 PT

Anmeldung mit Name + PIN, bcrypt, signiertes Cookie, Ratenbegrenzung, Rollen,
Befehl `benutzer-anlegen`. Jeder Benutzer trägt seinen `excel_name`.

**Fertig, wenn:** Session überlebt Neustart und Browserneustart; falsche PIN
wird verzögert; kein Endpunkt ist ohne Anmeldung erreichbar; kein PIN in einem
Protokoll auffindbar.

---

## EPIC 03 · Transkription — P1 · 1,5 PT

Interface `Transkribierer`, Adapter für Whisper-API, faster-whisper und
Attrappe. Vokabular-Prompt aus Gewerken, Mitarbeiternamen und Einheiten.
Audio nach Erfolg löschen.

**Fertig, wenn:** Anbieterwechsel ist eine `.env`-Zeile; Zeitüberschreitung und
API-Fehler erzeugen eine verständliche deutsche Meldung, keinen Traceback; die
Testsuite läuft ohne Netz.

---

## EPIC 04 · Strukturierung per KI — P1 · 2,5 PT

Claude-Aufruf mit striktem JSON-Schema, Pydantic-Nachvalidierung,
Einheiten-Normalisierung, deutsche Zahlen, Datumsauflösung, Konfidenz je
Position. Gewerke-Zuordnung aus der Tätigkeit.

**Fertig, wenn:** Das Beispiel aus Brief §3 ergibt zwei Positionen mit 65 m²
und 40 m²; `ungefähr 45 Quadratmeter` → `45` / `m²` / `geschaetzt`;
`rund 12,5 qm` → `12.5` / `m²`; eine erfundene Menge taucht in keinem Testfall
auf; Datum und Einheit sind ohne API-Aufruf testbar.

---

## EPIC 05 · Validierung und Rückfrage — P1 · 2,0 PT

Lückenprüfung gegen die sieben Pflichtfelder, **eine gebündelte** Frage (D-12),
Zusammenführung der Antwort, höchstens zwei Runden, danach manuelles Formular.
Mehrdeutigkeit als Auswahl statt als Vermutung.

**Fertig, wenn:** Zwei Positionen ohne Menge erzeugen genau eine Frage; die
Antwort ordnet die Mengen richtig zu; nach zwei Runden endet der Dialog mit
markierten Lücken statt in einer Schleife.

---

## EPIC 02 · Sprachaufnahme im Browser — P1 · 2,0 PT

`MediaRecorder` für iOS Safari und Android Chrome, großer Aufnahmeknopf,
Pegelanzeige, 90-Sekunden-Grenze, Berechtigungsdialog, PWA-Manifest,
Service Worker.

**Fertig, wenn:** Aufnahme läuft auf einem echten iPhone und einem echten
Android-Gerät; ohne sicheren Kontext erscheint eine erklärende deutsche
Meldung; verweigerte Mikrofonfreigabe führt ins manuelle Formular.

---

## EPIC 06 · Bestätigung und Speicherung — P1 · 1,5 PT

Zusammenfassung im Layout aus Brief §12, Felder einzeln korrigierbar,
`BESTÄTIGEN` / `ÄNDERN`, Speicherung erst bei Bestätigung, Beleg, eigene
Berichte, Korrekturfenster (D-13).

**Fertig, wenn:** Ohne Bestätigung existiert kein Datensatz mit Status
`bestaetigt`; doppeltes Absenden erzeugt dank `client_uuid` einen Bericht;
Korrektur erzeugt eine neue Version, keine Überschreibung.

---

## EPIC 08 · Export — P1 · 2,5 PT

XLSX (strukturiert), CSV (UTF-8 mit BOM, `;`, Dezimalkomma), Befehl
`mappe-befuellen` mit `--probelauf`, Vorprüfungen, Medienreparatur,
Integritätsprüfung, Exportprotokoll gegen Doppelbuchung.

**Fertig, wenn:** Die befüllte Kopie öffnet in Excel ohne Reparaturhinweis;
`H` zeigt nach Neuberechnung die erwarteten Stunden; `Eigenleistung` summiert
korrekt je Gewerk; das Logo ist erhalten; `--probelauf` schreibt nichts;
ein zweiter Lauf meldet die bereits eingespielten Berichte.

---

## EPIC 12 · Ausgangskorb und Fehlertoleranz — P1 · 2,0 PT

IndexedDB-Warteschlange, automatische Wiederholung mit wachsendem Abstand,
sichtbarer Status je Eintrag, manuelles Formular als Rückfallebene,
Idempotenz über `client_uuid`.

**Fertig, wenn:** Bei abgeschaltetem Netz bleibt die Aufnahme erhalten und wird
nach Rückkehr des Netzes zugestellt; kein Eintrag verschwindet stillschweigend;
kein Bericht entsteht doppelt; „gespeichert" erscheint ausschließlich nach
Serverbestätigung.

---

## EPIC 10 · Tests — P1 · 2,5 PT

Die Testmatrix aus Brief §21, vollständig:

| | Fall | Ebene |
|---|---|---|
| A | korrekte Spracheingabe | Ende-zu-Ende, Attrappe |
| B | mehrere Leistungen | Einheitentest Strukturierung |
| C | fehlende Menge | Rückfragedialog |
| D | fehlende Einheit | Rückfragedialog |
| E | fehlendes Bauvorhaben | Validierung |
| F | unsichere Erkennung | Konfidenz, Auswahlrückfrage |
| G | Korrektur | API + Versionierung |
| H | Bestätigung | Zustandsübergänge |
| I | Export | XLSX/CSV gegen erwartete Struktur |
| J | Excel-Mapping | **gegen die echte Mappe** in `referenz/` |
| K | fehlerhafte API-Antwort | Zeitüberschreitung, ungültiges JSON, Ablehnung |
| L | Netzwerkfehler | Ausgangskorb, Idempotenz |
| M | Sonderzeichen | Umlaute, `m²`, `;` im Freitext |
| N | deutsche Zahlen | `12,5` · `ungefähr 45` · `eineinhalb` |

Zusätzlich läuft `mappe_analysieren.py` als Test: Ändert die HAG die
Mappenstruktur, schlägt die Suite fehl, statt still falsch zu exportieren (R-01).

**Fertig, wenn:** Alle 14 Fälle grün; die Suite läuft ohne Netz und ohne
API-Schlüssel; ein realistischer Ende-zu-Ende-Test von der Audiodatei bis zur
befüllten Mappenkopie läuft durch (Akzeptanzkriterium 15).

---

## EPIC 11 · Betrieb — P1 · 1,5 PT

Systemd-Unit, Zugang nach D-10 einrichten (Konfiguration für alle drei Wege
liegt in `docs/BETRIEB-ZUGANG.md` bereit), tägliches Backup per `VACUUM INTO`,
`/api/status`, Betriebsanleitung, Einrichtungsanleitung für die Handys.

Enthält das **Prüfprotokoll aus `BETRIEB-ZUGANG.md` §7**: neun Schritte auf
einem echten iPhone und einem echten Android-Gerät, im Mobilfunknetz. Ohne
diesen Durchlauf gilt EPIC 02 nicht als abgenommen.

**Fertig, wenn:** Neuaufsetzen auf einem leeren Rechner gelingt allein anhand
der README; nach Neustart läuft der Dienst wieder; ein Backup lässt sich
nachweislich zurückspielen.

---

## EPIC 13 · Gestaltung — P2 · 1,5 PT

Gestaltungsvariablen an einer Stelle, Touch-Ziele ab 56 px, Kontraste nach
WCAG AA, Zustände für Laden, Fehler und Leerlauf, Verhalten bei greller Sonne.

**Fertig, wenn:** Die Oberfläche ist auf einem 360-px-Gerät ohne Querscrollen
bedienbar; das HAG-CI lässt sich durch Austausch einer Datei setzen.

---

## Sprint 1 — Vorschlag (5 Arbeitstage)

**Ziel: Der Weg von der Audiodatei bis in eine befüllte Mappenkopie steht —
noch ohne Oberfläche.** Danach ist bewiesen, dass das Kernrisiko des Projekts
(Excel-Mapping) beherrscht ist.

| Tag | Inhalt | Ergebnis |
|---|---|---|
| 1 | EPIC 00 + Beginn 07 | Gerüst, CI, Tabellen |
| 2 | EPIC 07 + 09 | Datenmodell, Geometrie gegen echte Mappe |
| 3 | EPIC 09 + 03 | Stammdaten geladen, Transkription mit Attrappe |
| 4 | EPIC 04 | Strukturierung, Einheiten, deutsche Zahlen, Tests B/N |
| 5 | EPIC 08 (Teil) | `mappe-befuellen --probelauf`, Test J grün |

**Sprint-Abnahme:** Eine Beispiel-Audiodatei erzeugt über die Befehlszeile eine
befüllte Mappenkopie, in der `Eigenleistung` die richtigen Stunden je Gewerk
summiert — und die Originalmappe ist unverändert.

Sprint 2 bringt die Oberfläche (02, 05, 06), Sprint 3 Ausgangskorb, Betrieb
und Pilot (12, 11, 13).

---

## Vor Sprint 1 zu klären

| ID | Frage | Blockiert |
|---|---|---|
| **D-10** | Tailscale, Cloudflare Tunnel oder eigene Domain? | EPIC 02 (ohne HTTPS kein Mikrofon) **und EPIC 01** (PIN-Länge, ggf. Gerätebindung: bis zu +1 PT) |
| **D-09** | AVV für die Transkription, oder lokal starten? | EPIC 03, Pilotbeginn |
| **D-02** | Mengen als Text in Spalte I, oder rechenbar? | EPIC 08/09, Umfang |
| **D-03** | Abgeleiteter Regelbeginn zulässig? | EPIC 04/05, Dialoggestaltung |

D-02 und D-03 blockieren Sprint 1 nicht — das Datenmodell trägt beide Varianten.
**D-10 und D-09 müssen vor Sprint 2 beantwortet sein.**

Bei D-10 ist die Vorarbeit erledigt: Alle drei Wege sind in
`docs/BETRIEB-ZUGANG.md` mit lauffähiger Konfiguration ausgearbeitet, die App
wird proxy-neutral gebaut. Offen ist allein die Wahl — und die hängt an einer
nichttechnischen Frage: **Diensthandys oder private Handys?**

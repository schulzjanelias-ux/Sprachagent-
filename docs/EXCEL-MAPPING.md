# Excel-Mapping — Bauablaufmappe Projektcontrolling

Analysegegenstand: `referenz/Bauablaufmappe_Projektcontrolling_anonymisiert.xlsx`
Alle Angaben sind maschinell erhoben und mit `python3 werkzeuge/mappe_analysieren.py`
jederzeit reproduzierbar. Ändert die HAG die Mappe, zeigt ein erneuter Lauf sofort,
welche Annahme gebrochen ist.

---

## 1. Workbook-Struktur

| # | Worksheet | Sichtbar | Bereich | Rolle für dieses Projekt |
|---|---|---|---|---|
| 1 | `Projektübersicht` | ja | B2:Q70 | Stammdaten + Cockpit. **Quelle** für Bauvorhaben, Baubeginn, Bauende |
| 2 | `Zeiterfassung` | ja | A1:Q3665 | **Das Zielblatt.** Einziges Schreibziel der App |
| 3 | `Zeiterfassung Export` | **nein** | A1:N3665 | Druckaufbereitung, komplett formelgetrieben. **Nicht anfassen** |
| 4 | `Materialkosten` | ja | A1:K305 | außerhalb des MVP |
| 5 | `Rechnungsstand` | ja | A1:Q305 | außerhalb des MVP |
| 6 | `Rechnungsprüfung` | ja | A1:W317 | außerhalb des MVP |
| 7 | `Nachunternehmer` | ja | A1:M106 | außerhalb des MVP |
| 8 | `Eigenleistung` | ja | A1:N105 | **liest** Zeiterfassung (Gewerk × Stunden) |
| 9 | `KPI-Basis` | ja | B2:I25 | Kennzahlen, rein verknüpft |
| 10 | `Listen` | ja | A1:AC367 | **Stammdatenquelle** für alle Dropdowns |

Der Name `Zeiterfassung Export` ist irreführend: Das Blatt ist keine
Import-Schnittstelle, sondern eine ausgeblendete Druckansicht. Jede seiner
Zellen ist eine `INDEX`-Formel auf `Zeiterfassung`. Schreiben dorthin zerstört
die Druckaufbereitung, ohne Daten ins Controlling zu bringen.

### Definierte Namen

| Name | Bereich | n | Verwendung |
|---|---|---|---|
| `MitarbeiterListe` | `Listen!$B$2:$B$29` | 28 | Dropdown `Zeiterfassung!D` |
| `GewerkeListe` | `Listen!$A$2:$A$13` | 12 | Dropdown `Zeiterfassung!E`, `Eigenleistung!A` |
| `Berlin_Feiertage` | `Listen!$E$2:$E$82` | 81 | sperrt die Eingabe an Feiertagen |
| `NUGewerkeListe` | `Listen!$N$2:$N$8` | 7 | Nachunternehmer |
| `LieferantenListe` | `Listen!$P$2:$P$12` | 11 | Materialkosten |
| `RechnungsartenListe` | `Listen!$X$2:$X$4` | 3 | Rechnungsstand |
| `ErfassungDatumListe` | `Listen!$AB$2:$AB$367` | 366 | Schnellnavigation |
| `ErfassungKWListe` | `Listen!$AC$2:$AC$54` | 53 | Schnellnavigation |
| `Stundenexport_Druckbereich` | dynamisch | — | Druckbereich der Exportansicht |

---

## 2. Aufbau des Blattes `Zeiterfassung`

```
Zeile 1–4   Kopf, Navigation, Formeltitel
Zeile 5     Spaltenüberschriften   ← AutoFilter A5:J3665, Fixierung ab D6
Zeile 6     erste Datenzeile
Zeile 3665  letzte Datenzeile
```

### Das Kalendergerüst ist vorgeneriert

Spalte K erzeugt die Arbeitstage selbst:

```excel
K6  = ... WORKDAY.INTL('Projektübersicht'!$F$11-1; 1; "0000001") ...
K16 = ... WORKDAY.INTL('Projektübersicht'!$F$11-1; 2; "0000001") ...
K26 = ... WORKDAY.INTL('Projektübersicht'!$F$11-1; 3; "0000001") ...
```

Die Maske `"0000001"` bedeutet: **nur Sonntag ist arbeitsfrei.** Montag bis
Samstag sind Kalendertage im Gerüst. Das erklärt den Dateinamen
„ohne Sonntage". Feiertage stehen sehr wohl im Gerüst — sie werden nicht
ausgelassen, sondern per Datenvalidierung für die Eingabe gesperrt (§4).

**Konsequenz:** Die App erzeugt keine Zeilen. Sie befüllt vorhandene. Die
Zeilennummer ist vollständig aus Baubeginn und Datum berechenbar (§5).

### Tagesblöcke — 10 Zeilen je Tag

Maschinell nachgewiesen: 366 verbundene Bereiche je in den Spalten A, B, C, I, J,
alle exakt 10 Zeilen hoch, Blockabstand exakt 10, erster Block ab Zeile 6.

```
Zeilen  6–15   Tag 1     ┐ Zeilen 6–10  : 5 sichtbare Mitarbeiter-Slots
Zeilen 16–25   Tag 2     ┆ Zeilen 11–15 : 5 aufklappbare Slots (Gliederungsebene 1)
Zeilen 26–35   Tag 3     ┆                → Hinweis in L7: „MEHR ALS 5 MITARBEITER?"
   …                     ┆
Zeilen 3656–3665  Tag 366┘
```

**Kapazität: maximal 10 Mitarbeiter je Tag und Bauvorhaben.** Ein elfter
Mitarbeiter hat keinen Platz — die App muss das abfangen, statt still zu
überschreiben (siehe `docs/DECISIONS.md` · R-03).

366 Blöcke ohne Sonntage entsprechen rund 14 Kalendermonaten Bauzeit.

### Spaltenrollen

| Spalte | Überschrift | Typ | Format | App darf schreiben |
|---|---|---|---|---|
| A | KW | Formel `WEEKNUM(K;21)` | `"KW "00` | **nein** |
| B | DATUM | Formel `=K` | `dd.mm.yyyy` | **nein** |
| C | TAG | Formel `=K` | `dddd` | **nein** |
| D | MITARBEITER | Eingabe, Dropdown | General | **ja**, je Zeile |
| E | GEWERK | Eingabe, Dropdown | General | **ja**, je Zeile |
| F | ARBEITSANFANG | Eingabe, Uhrzeit | `hh:mm` | **ja**, je Zeile |
| G | ARBEITSENDE | Eingabe, Uhrzeit | `hh:mm` | **ja**, je Zeile |
| H | ARBEITSSTUNDEN | **Formel** | `0.00` | **nein** |
| I | ARBEITEN / LEISTUNGEN | Eingabe, Freitext | General | **ja**, 1× je Tag |
| J | TAGESBEMERKUNG | Eingabe, Freitext | General | **ja**, 1× je Tag |
| K | DATUM INTERN | **Formel** | `dd.mm.yyyy` | **nein** |
| L | KW / Hinweistexte | Layout | — | **nein** |

Spalten I und J sind über den gesamten 10-Zeilen-Block verbunden. Beschreibbar
ist nur die **oberste Zelle** des Blocks. Ein Schreibversuch in `I7` bei
verbundenem `I6:I15` wirft in openpyxl einen Fehler.

### Die beiden Formeln, auf die es ankommt

```excel
Zeiterfassung!H6  = IF(OR(F6="";G6="");"";ROUND(MOD(G6-F6;1)*24;2))
Eigenleistung!F6  = IF(A6="";"";SUMIF(Zeiterfassung!$E$6:$E$3665; A6; Zeiterfassung!$H$6:$H$3665))
Projektübersicht!F22 = SUM(Zeiterfassung!$H$6:$H$3665)
```

`MOD(G-F;1)` behandelt Nachtschichten korrekt (Ende < Anfang).
Von `H` laufen Eigenkosten → Deckungsbeitrag → Marge → Cockpit.

**Die App liefert F und G. H entsteht in Excel.** Eine Stundenzahl direkt nach
H zu schreiben, würde die Formel löschen und das Blatt für alle Folgetage
inkonsistent machen.

---

## 3. Stammdaten — geschlossene Wertelisten

Die App darf **ausschließlich** diese Werte liefern. Ein abweichender String
verletzt die Dropdown-Validierung und, schlimmer, fällt in `Eigenleistung`
lautlos aus der `SUMIF`-Summe: Die Stunden sind dann in der Mappe, aber in
keiner Auswertung.

**Gewerke (12)** — Ziel `Zeiterfassung!E`

```
Bauleitung · Rückbau · Maurer · Trockenbau · Elektro · Sanitär/Heizung
Fliesen · Maler · Bodenleger · Tischler · Reinigung · Sonstiges
```

**Mitarbeiter (28)** — Ziel `Zeiterfassung!D`

```
Ahrens, Berkhoff, Böttger, Cordes, S.Dallmann, D. Dallmann, Emmrich, Fahnert,
Gollnick, Grewe, Hasselbach, Hüttemann, Immig, Jarosch, … (28 gesamt)
```

> Die Namen in `referenz/` sind **anonymisiert** (R-04). Die Produktivmappe der
> HAG enthält an dieser Stelle die echten Namen. Die Struktur ist identisch —
> `werkzeuge/mappe_anonymisieren.py` ersetzt ausschließlich `Listen!B2:B29`.

Es sind **Nachnamen**, teilweise mit Initial zur Unterscheidung
(`S.Dallmann` vs. `D. Dallmann` — man beachte das Leerzeichen beim zweiten).
Diese Uneinheitlichkeit stammt aus dem Original und wurde bewusst nachgebildet:
Der Exportvergleich muss exakt sein, ein „aufgeräumter" Name trifft die Liste
nicht mehr.

Ein Eintrag ist keine Person, sondern ein Platzhalter: `SO (extern)`. Die App
behandelt ihn wie einen Mitarbeiter ohne Anmeldung — er kann in der Mappe
stehen, sich aber nicht anmelden.

Die App speichert den Listenstring als `mitarbeiter.excel_name` unverändert und
nutzt intern eine eigene ID. Anzeigename und Exportname sind getrennt zu halten.

---

## 4. Datenvalidierungen

| Bereich | Typ | Regel |
|---|---|---|
| `D6:D3665` | Liste | `=IF(COUNTIF(Berlin_Feiertage;$K6)=0; MitarbeiterListe; "")` |
| `E6:E3665` | Liste | `=IF(COUNTIF(Berlin_Feiertage;$K6)=0; GewerkeListe; "")` |
| `F6:F3665` | benutzerdef. | `=OR(F6=""; AND(COUNTIF(Berlin_Feiertage;$K6)=0; ISNUMBER(F6); F6>=0; F6<1))` |
| `G6:G3665` | benutzerdef. | analog zu F |
| `I6:I3665` | benutzerdef. | `=COUNTIF(Berlin_Feiertage;$K6)=0` |
| `J6:J3665` | benutzerdef. | analog zu I |

Zwei Regeln, die die App übernehmen muss:

1. **An Berliner Feiertagen ist jede Eingabe gesperrt.** 81 Termine, 2025–2032,
   Quelle `FeiertG_BE`. Die App validiert das serverseitig gegen dieselbe Liste
   und weist die Erfassung mit klarer Meldung ab.
2. **Uhrzeiten sind Excel-Bruchteile eines Tages:** `0 ≤ x < 1`.
   `07:00` = `7/24` = `0.2916666…`, `16:30` = `0.6875`.
   openpyxl schreibt einen Float; das Zellformat `hh:mm` stellt ihn als Uhrzeit dar.

Sonntage sind gar nicht erst im Gerüst — es gibt keine Zeile dafür.

---

## 5. Adressierung — vom Datum zur Zelle

Vorbedingungen: `Projektübersicht!F11` (Baubeginn) und `F13` (Bauende) sind
gesetzt, das Datum ist kein Sonntag und liegt in der Bauzeit.

```
tagesindex(d) = Anzahl der Nicht-Sonntage im Intervall [Baubeginn … d]
              = (d − Baubeginn + 1) − Anzahl Sonntage in [Baubeginn … d]

blockstart(d) = 6 + (tagesindex(d) − 1) × 10
zeile(d, slot) = blockstart(d) + (slot − 1)          slot ∈ 1…10
```

Zielzellen:

```
D{zeile}  Mitarbeiter          je Mitarbeiterzeile
E{zeile}  Gewerk               je Mitarbeiterzeile
F{zeile}  Arbeitsanfang        je Mitarbeiterzeile
G{zeile}  Arbeitsende          je Mitarbeiterzeile
I{blockstart}  Leistungstext   genau einmal je Tag
J{blockstart}  Tagesbemerkung  genau einmal je Tag
```

Beispiel — Baubeginn 01.09.2026 (Dienstag), Bericht vom 10.09.2026 (Donnerstag):

```
Nicht-Sonntage vom 01.09. bis 10.09. = 10 Kalendertage − 1 Sonntag (06.09.) = 9
blockstart = 6 + (9 − 1) × 10 = 86
Slot 1 → Zeile 86 (D86, E86, F86, G86) · Leistungstext → I86 · Bemerkung → J86
Slot 2 → Zeile 87 …
```

Die Slotvergabe erfolgt stabil und deterministisch: alphabetisch nach
`excel_name`, damit ein erneuter Export dieselbe Belegung erzeugt.

---

## 6. Feldabbildung App → Mappe

Legende: **Menge** und **Einheit** haben kein Ziel in der Mappe. Die
Auflösung dieses Konflikts ist `docs/DECISIONS.md` · **D-02**; die Zeile
„Leistungstext" unten zeigt die empfohlene Variante A.

| App-Feld | Export-Feld | Sheet | Zelle | Transformation |
|---|---|---|---|---|
| `report.datum` | `zeile` | Zeiterfassung | — | → Zeilennummer nach §5. Kein Schreiben nach B/K |
| `project.name` | — | Projektübersicht | `B9` | **nur Prüfung**: muss übereinstimmen, sonst Abbruch |
| `employee.excel_name` | `mitarbeiter` | Zeiterfassung | `D{zeile}` | 1:1 aus `MitarbeiterListe`, sonst Abbruch |
| `report_item.gewerk` | `gewerk` | Zeiterfassung | `E{zeile}` | 1:1 aus `GewerkeListe`. Mehrere Gewerke → mehrere Slots |
| `attendance.beginn` | `arbeitsanfang` | Zeiterfassung | `F{zeile}` | `HH:MM` → `(h*60+m)/1440`, Float `0…<1` |
| `attendance.ende` | `arbeitsende` | Zeiterfassung | `G{zeile}` | wie oben. Nachtschicht erlaubt (`MOD`) |
| — | — | Zeiterfassung | `H{zeile}` | **niemals schreiben**, Excel rechnet |
| `report_items[*]` | `leistungstext` | Zeiterfassung | `I{blockstart}` | **Normalisierte Serialisierung**, siehe unten |
| `report.bemerkung` | `tagesbemerkung` | Zeiterfassung | `J{blockstart}` | Freitext, auf 500 Zeichen gekürzt |
| `report_item.menge` | `menge` | — | — | **kein Ziel** → Variante A: in Leistungstext, strukturiert zusätzlich in CSV/XLSX |
| `report_item.einheit` | `einheit` | — | — | dito |
| `report.id` | `bericht_id` | — | — | nur im strukturierten Export, für Rückverfolgung |

### Serialisierung des Leistungstextes (Spalte I)

Ein Tag, ein Feld, mehrere Leistungen — deshalb ein festes, wieder
einlesbares Format statt Prosa:

```
Spachtelarbeiten 65 m²; Schleifarbeiten 40 m²; Türen grundieren 8 Stück
```

Regeln:

- Positionen durch `; ` getrennt, Reihenfolge wie erfasst
- je Position `Tätigkeit` `Menge` `Einheit`
- Menge deutsch formatiert, ohne Tausenderpunkt: `12,5`
- Positionen ohne Menge erscheinen als reine Tätigkeit
- Gesamtlänge auf 900 Zeichen begrenzt, danach `…` und Verweis auf die
  Bericht-ID; der strukturierte Export bleibt vollständig
- Zeilenumbrüche werden zu `; ` normalisiert (Spalte I hat `wrap_text`, aber
  Umbrüche erschweren das Wiedereinlesen)

Damit ist Spalte I für Menschen lesbar **und** maschinell zurücklesbar — die
Mappe bleibt in ihrer Struktur unberührt.

---

## 7. Exportstrategie

Nachgewiesenes Problem: Ein openpyxl-Schreibvorgang auf der Mappe verliert
`xl/media/image1.png` (das eingebettete Logo im Cockpit-Drawing). Alles andere —
Formeln, 1841 verbundene Bereiche, 8 Datenvalidierungen, das Diagramm, die 9
definierten Namen, die Kommentare — bleibt erhalten.

Daraus folgt (`docs/DECISIONS.md` · D-01): **Die Meistermappe wird nie
beschrieben.** Der Export erzeugt drei Artefakte:

| Artefakt | Zweck | Format |
|---|---|---|
| `tagesberichte_<projekt>_<von>_<bis>.xlsx` | Prüfen und Freigeben durch das Büro | strukturiert, inkl. Menge/Einheit, je Position eine Zeile |
| `tagesberichte_<projekt>_<von>_<bis>.csv` | maschinelle Weiterverarbeitung | UTF-8 mit BOM, `;`-getrennt, deutsche Dezimalkommas |
| `<mappe>_befuellt_<zeitstempel>.xlsx` | einspielbare **Kopie** der Bauablaufmappe | zellgenau befüllt, Medien wiederhergestellt |

Das dritte Artefakt entsteht über den Befehl `mappe-befuellen`:

1. Meistermappe wird **kopiert**, das Original nie geöffnet-und-gespeichert
2. Vorprüfung: Bauvorhaben stimmt überein, Baubeginn/Bauende gesetzt,
   alle Mitarbeiter- und Gewerkenamen in den Listen, kein Feiertag,
   kein Sonntag, keine Zielzelle bereits belegt, Slot-Kapazität ausreichend
3. `--probelauf` gibt nur den Änderungsbericht aus, schreibt nichts
4. Schreiben ausschließlich in `D/E/F/G{zeile}` und `I/J{blockstart}`
5. **Medienreparatur:** fehlende ZIP-Einträge werden aus dem Original
   zurückgeschrieben — verifiziert, dass danach kein Eintrag mehr fehlt
6. Abschlussprüfung: Blattzahl, Merges, Validierungen, Formeln in H und K
   unverändert; sonst wird die Ausgabedatei verworfen

Diese Schritte sind Gegenstand der Tests J (Excel-Mapping) und I (Export) aus
Brief §21 — siehe `docs/MVP-BACKLOG.md` · EPIC 10.

---

## 8. Risiken dieses Mappings

| ID | Risiko | Wirkung | Umgang |
|---|---|---|---|
| M-1 | Baubeginn/Bauende nicht gesetzt | Kalendergerüst leer, keine Zieladresse | Export bricht mit klarer Meldung ab |
| M-2 | HAG ändert Blockhöhe oder Spaltenreihenfolge | Daten landen in falschen Zeilen | `mappe_analysieren.py` als Testfall im CI; Export prüft die Geometrie vor jedem Lauf |
| M-3 | Mehr als 10 Mitarbeiter an einem Tag | Slots reichen nicht | Export meldet Überlauf namentlich, schreibt nichts |
| M-4 | Zielzelle bereits von Hand befüllt | stille Überschreibung | Vorprüfung meldet Konflikt, `--überschreiben` nur explizit |
| M-5 | Name weicht von der Liste ab | Stunden fallen aus `SUMIF` | harte Validierung gegen `Listen`, kein Fuzzy-Matching beim Export |
| M-6 | Zwei Exportläufe für denselben Zeitraum | doppelte Stunden | jeder Bericht trägt seine `bericht_id`; eingespielte IDs werden protokolliert |
| M-7 | Mappe in Excel geöffnet während Export | Kopie unkritisch, Einspielen scheitert | Ausgabe ist immer eine neue Datei mit Zeitstempel |

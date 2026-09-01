# HAG PROJECT 01 — Digitaler Tagesbericht

**Status:** Phase 0 abgeschlossen (Analyse). Implementierung noch nicht begonnen.
**Stand:** 01.09.2026

---

## 1. Worum es geht

Bauleiter und Monteure der HAG dokumentieren ihre Tagesleistung heute manuell.
Diese Anwendung nimmt am Feierabend eine Sprachnachricht entgegen, macht daraus
einen strukturierten Tagesbericht und liefert ihn in einem Format, das in die
bestehende Bauablaufmappe eingespielt werden kann.

Die Excel-Projektmappe bleibt das führende Controlling-System. Die App ersetzt
sie nicht — sie befüllt sie.

**Erfolgsmaßstab:** Ein Mitarbeiter gibt nach Feierabend in 1–2 Minuten einen
vollständigen, strukturierten Tagesbericht ab.

---

## 2. Was die Analyse ergeben hat

Die mitgelieferte Mappe wurde vollständig vermessen
(`werkzeuge/mappe_analysieren.py`, Details in `docs/EXCEL-MAPPING.md`).
Drei Befunde bestimmen das gesamte Produkt:

### Befund 1 — Die Mappe rechnet in Stunden, nicht in Mengen

Die einzige Formel, die Leistungsdaten wirtschaftlich auswertet, lautet:

```
Eigenleistung!F6 = SUMIF(Zeiterfassung!$E:$E; A6; Zeiterfassung!$H:$H)
                            Gewerk           ↑        Arbeitsstunden
```

Von dort laufen Eigenkosten, Deckungsbeitrag und Marge weiter in `KPI-Basis`
und ins Projektcockpit. **Die Wirtschaftlichkeit des Projekts hängt an
`Gewerk` × `Arbeitsstunden` — an nichts sonst.**

Für `Leistungsmenge` und `Einheit` (Brief §5, Pflichtfelder 6 und 7) gibt es in
der gesamten Mappe **keine Zielspalte**. Die Leistungsbeschreibung ist ein
einzelnes, über den Tagesblock verbundenes Freitextfeld (Spalte I).

→ Das ist der zentrale Zielkonflikt des Projekts. Auflösung in
`docs/DECISIONS.md` · **D-02** (DECISION REQUIRED).

### Befund 2 — Stunden sind eine Formel, keine Eingabe

```
Zeiterfassung!H6 = IF(OR(F6="";G6="");"";ROUND(MOD(G6-F6;1)*24;2))
                         Anfang  Ende
```

Wer „acht Stunden gearbeitet" sagt, erzeugt in der Mappe **keine Stunde**.
Nur `ARBEITSANFANG` + `ARBEITSENDE` erzeugen einen Wert in H — und nur H fließt
ins Controlling.

→ Die App muss Anfangs- und Endzeit erfassen. Siehe **D-03**.

### Befund 3 — Eine Mappe ist genau ein Bauvorhaben

Bauvorhaben (`Projektübersicht!B9`), Baubeginn (`F11`) und Bauende (`F13`) sind
Einzelzellen. Das Kalendergerüst der Zeiterfassung wird daraus erzeugt.
Es gibt kein Feld für ein zweites Bauvorhaben.

→ Die App ist mehrprojektfähig, der Export läuft je Bauvorhaben gegen genau
eine Mappe. Siehe **D-04**.

---

## 3. Pflichtdaten — Brief gegen Mappe

| # | Brief §5 fordert | Ziel in der Mappe | Bewertung |
|---|---|---|---|
| 1 | Datum | `Zeiterfassung!B` (Formel aus K) | vorhanden, adressiert über die Zeilennummer |
| 2 | Mitarbeiter | `Zeiterfassung!D` | vorhanden, **geschlossene Liste** (28 Namen) |
| 3 | Bauvorhaben | `Projektübersicht!B9` | je Mappe fix, nicht je Zeile |
| 4 | Tätigkeit | `Zeiterfassung!E` (GEWERK) | vorhanden, **geschlossene Liste** (12 Gewerke) |
| 5 | Leistungsbeschreibung | `Zeiterfassung!I` | Freitext, **1× je Tag** (verbundene Zelle) |
| 6 | Leistungsmenge | — | **kein Ziel** → D-02 |
| 7 | Einheit | — | **kein Ziel** → D-02 |
| + | Arbeitszeit | `F`/`G` → `H` | **faktisch Pflicht**, sonst bleibt das Controlling leer → D-03 |

„Tätigkeit" im Brief und „Gewerk" in der Mappe sind nicht dasselbe:
*Spachtelarbeiten* ist eine Tätigkeit, *Trockenbau* ein Gewerk. Die App erfasst
beides und ordnet die Tätigkeit einem Gewerk zu (`docs/EXCEL-MAPPING.md` §6).

---

## 4. Produktumfang MVP

**Enthalten**

1. Anmeldung, Mitarbeiter eindeutig identifiziert
2. Bauvorhaben aus Auswahlliste
3. Sprachaufnahme im Browser (iOS Safari, Android Chrome)
4. Transkription über austauschbares Anbieter-Interface
5. Strukturierung per LLM mit striktem JSON-Schema, serverseitig validiert
6. Mehrere Leistungspositionen je Bericht
7. Vollständigkeitsprüfung mit **einer gebündelten** Rückfrage
8. Zusammenfassung, Korrektur, Bestätigung
9. Speicherung in SQLite (führend für die App)
10. Export als XLSX + CSV, einspielbar in die Bauablaufmappe
11. Mapping-Dokumentation und automatisierte Tests

**Nicht enthalten** (Brief §15): ERP, Lohnabrechnung, GPS-Erkennung,
BI-Dashboards, native Apps, Rechnungsstellung.

**Bewusst nicht gebaut, obwohl naheliegend**

- Kein Rückschreiben in die Meistermappe (D-01)
- Keine Materialerfassung — `Materialkosten` hat eigene Belegpflicht
- Keine Freitext-Einheiten — normalisierte Liste (D-07)

---

## 5. Nutzerablauf

```
Anmelden (einmalig, Session bleibt)
   ↓
Bauvorhaben wählen (vorbelegt: letztes Projekt)
   ↓
Aufnahmeknopf, frei sprechen
   ↓
Transkription + Strukturierung
   ↓
Fehlt etwas?  ── nein ──┐
   ↓ ja                 │
EINE gebündelte         │
Rückfrage, per Sprache  │
oder Tippen beantworten │
   ↓                    │
   └────────────────────┤
                        ↓
              Zusammenfassung prüfen
                        ↓
              [ BESTÄTIGEN ] / [ ÄNDERN ]
                        ↓
              Gespeichert · Beleg sichtbar
                        ↓
              Export (Büro, wöchentlich)
```

Die Rückfrage ist bewusst **eine** Runde mit allen Lücken gebündelt, nicht eine
Frage je Feld. Ein Dialog mit vier Rückfragen kostet mehr Zeit als das Formular,
das er ersetzen soll.

---

## 6. Rollen

| Rolle | Rechte |
|---|---|
| `mitarbeiter` | eigene Berichte anlegen, ansehen, am selben Tag korrigieren |
| `bauleiter` | zusätzlich alle Berichte des Projekts lesen, Export auslösen |

Mehr Rollen braucht der MVP nicht.

---

## 7. Dokumentenübersicht

| Datei | Inhalt |
|---|---|
| `docs/PROJECT.md` | dieses Dokument — Kontext, Umfang, Analyse-Kurzfassung |
| `docs/ARCHITECTURE.md` | Technik, Datenmodell, API, Sicherheit |
| `docs/EXCEL-MAPPING.md` | vollständige Mappenanalyse und Feldabbildung |
| `docs/DECISIONS.md` | Entscheidungen, offene Punkte, Risiken |
| `docs/MVP-BACKLOG.md` | Epics, Aufwände, Abhängigkeiten, Sprint 1 |
| `docs/BETRIEB-ZUGANG.md` | Zugangswege vom Handy, Konfiguration, Prüfprotokoll (D-10) |
| `werkzeuge/mappe_analysieren.py` | reproduzierbarer Nachweis der Mappenstruktur |
| `werkzeuge/mappe_anonymisieren.py` | erzeugt die anonymisierte Referenzmappe (D-15) |

---

## 8. Offene Punkte, die die HAG entscheiden muss

Vollständig mit Optionen und Empfehlung in `docs/DECISIONS.md`:

| ID | Frage | blockiert |
|---|---|---|
| **D-02** | Wohin mit Menge und Einheit? | Datenmodell, Export |
| **D-03** | Anfang/Ende erfassen statt Stundenzahl? | Sprachdialog, UX |
| **D-09** | Transkription in der Cloud oder im Haus? | Datenschutz, Betrieb |
| **D-10** | Tailscale, Cloudflare Tunnel oder eigene Domain? | Nutzbarkeit überhaupt, **und** der Umfang der Anmeldung (D-11) |

D-10 ist kein Betriebsdetail: Ohne HTTPS geben iOS und Android das Mikrofon
nicht frei. Da die Erfassung **auf der Baustelle** stattfindet, scheidet die
billigste Lösung — nur im Firmen-WLAN erreichbar — aus. Drei Wege sind in
`docs/BETRIEB-ZUGANG.md` mit Konfiguration und Prüfprotokoll ausgearbeitet;
die Wahl bestimmt über D-11 auch die Länge der PIN und damit den Aufwand
von EPIC 01.

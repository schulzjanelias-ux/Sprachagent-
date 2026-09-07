# Entscheidungen, offene Punkte, Risiken

Legende: **ENTSCHIEDEN** — vom Team getroffen, umsetzbar.
**DECISION REQUIRED** — die HAG muss entscheiden, mit Empfehlung.

---

## D-01 · Die Meistermappe wird nie beschrieben — ENTSCHIEDEN

**Kontext.** Der Brief (§13) verlangt, die Mappe nicht unnötig zu verändern.
Ein empirischer Round-Trip-Test zeigt, was openpyxl beim Speichern anrichtet:

```
VERLUST: xl/media/image1.png
erhalten: Formeln, 1841 Merges, 8 Validierungen, Diagramm, 9 definierte Namen, Kommentare
```

Ein einziger Schreibvorgang kostet das eingebettete Logo. Der Verlust ist
reparierbar (nachgewiesen), aber er zeigt: openpyxl versteht diese Mappe nicht
vollständig. Bei jedem künftigen Excel-Feature kann derselbe stille Verlust an
anderer Stelle auftreten.

**Entscheidung.** Der Export schreibt ausschließlich in **Kopien**. Die
Originalmappe wird nur lesend geöffnet. Die befüllte Kopie durchläuft nach dem
Schreiben eine Integritätsprüfung (Blätter, Merges, Validierungen, Formeln in H
und K) und eine Medienreparatur; schlägt eine Prüfung fehl, wird die Ausgabe
verworfen statt ausgeliefert.

**Konsequenz.** Das Büro erhält eine fertige Mappe zum Ablegen, nicht eine
veränderte Originaldatei. Rückfallebene ist immer das Original.

---

## D-02 · Leistungsmenge und Einheit haben kein Ziel in der Mappe — DECISION REQUIRED

**Der zentrale Zielkonflikt des Projekts.**

Der Brief macht Menge (§5.6) und Einheit (§5.7) zu Pflichtfeldern und verlangt
(§14), dass der Export „keine unstrukturierten Freitexte als alleinige
Datenquelle" enthält. Die Mappe hat für beides keine Spalte. Sie rechnet
ausschließlich über `Gewerk × Arbeitsstunden`; die Leistungsbeschreibung ist ein
je Tag verbundenes Freitextfeld ohne jede Auswertung.

Beide Anforderungen sind gleichzeitig nur erfüllbar, wenn die Menge zwei Wege
geht: strukturiert in die App-Datenbank und den Export, lesbar in die Mappe.

### Optionen

| | Variante | Mappe verändert | Menge strukturiert | Aufwand |
|---|---|---|---|---|
| **A** | Menge/Einheit strukturiert in DB + Export-XLSX/CSV; in Spalte I ein normalisiert serialisierter Text | nein | ja, außerhalb der Mappe | gering |
| **B** | Zusätzliches Blatt `Leistungen Import` in der Mappenkopie | additiv, kein Bestandsblatt berührt | ja, in der Mappe | mittel |
| **C** | Neue Spalten in `Zeiterfassung` | ja, invasiv | ja | hoch |

Variante C ist abzulehnen: Der AutoFilter `A5:J3665`, der Druckbereich, die
`INDEX`-Formeln des Export-Blattes und 40.361 Formelbezüge auf `Zeiterfassung`
hängen an der aktuellen Spaltenordnung.

**Empfehlung: A jetzt, B als Option nachrüstbar.**

Variante A hält die Mappe unangetastet und erfüllt §14, weil der maßgebliche
strukturierte Export XLSX/CSV ist — Spalte I ist die menschenlesbare Beigabe,
nicht die Datenquelle. Format der Serialisierung:

```
Spachtelarbeiten 65 m²; Schleifarbeiten 40 m²; Türen grundieren 8 Stück
```

**Was die HAG entscheiden muss:** Reicht es, dass Mengen im Controlling als Text
in Spalte I stehen und strukturiert nur in App und Export vorliegen? Oder sollen
Mengen in der Mappe rechenbar sein (dann Variante B)?

Diese Antwort bestimmt, ob EPIC 09 zwei oder vier Tage kostet — das Datenmodell
ist in beiden Fällen dasselbe und wird schon jetzt so gebaut.

---

## D-03 · Stunden nur über Anfangs- und Endzeit — DECISION REQUIRED

**Kontext.**

```excel
Zeiterfassung!H = IF(OR(F="";G="");"";ROUND(MOD(G-F;1)*24;2))
Eigenleistung!F = SUMIF(Zeiterfassung!E; Gewerk; Zeiterfassung!H)
```

Sagt ein Mitarbeiter „acht Stunden", entsteht in der Mappe **keine Stunde**.
Ohne F und G bleiben Stunden-Ist, Eigenkosten, Deckungsbeitrag und
Eigenleistungsmarge leer — also genau das Controlling, für das die App gebaut
wird. Eine Stundenzahl direkt nach H zu schreiben, würde die Formel zerstören.

**Empfehlung: Anfang und Ende erfassen, Dauer als Komfortweg.**

- Die App fragt „Von wann bis wann?" statt „Wie viele Stunden?"
- Nennt jemand nur eine Dauer, wird sie mit dem hinterlegten Regelbeginn des
  Mitarbeiters (Standard 07:00) zu einem Zeitfenster ergänzt — **sichtbar
  markiert** als abgeleitet, in der Bestätigung korrigierbar
- Pausen bildet die Mappe nicht ab; die App erfasst sie nicht und suggeriert
  auch nicht, sie zu berücksichtigen

**Was die HAG entscheiden muss:** Ist der abgeleitete Regelbeginn zulässig, oder
muss die Zeit immer explizit genannt werden? Das ist eine arbeitsrechtliche
Frage, keine technische — abgeleitete Zeiten sind für die Arbeitszeit­doku­men­ta­tion
nach § 16 ArbZG möglicherweise nicht ausreichend.

---

## D-04 · Eine Mappe ist genau ein Bauvorhaben — ENTSCHIEDEN

Bauvorhaben, Baubeginn und Bauende sind Einzelzellen in `Projektübersicht`.
Das Kalendergerüst wird daraus erzeugt.

**Entscheidung.** Die App ist mehrprojektfähig (Tabelle `projekte` mit Pfad zur
zugehörigen Mappe). Der Export läuft je Projekt gegen genau eine Mappe und
prüft vorab, dass `Projektübersicht!B9` mit dem Projektnamen übereinstimmt —
sonst Abbruch. Das verhindert den teuersten denkbaren Fehler: Stunden im
falschen Projekt.

---

## D-05 · Harte Validierung gegen die Stammdatenlisten — ENTSCHIEDEN

Weicht ein Name von `MitarbeiterListe` oder `GewerkeListe` ab, verletzt er nicht
nur das Dropdown — er fällt in `Eigenleistung` lautlos aus der `SUMIF`-Summe.
Die Stunden stehen dann in der Mappe und fehlen trotzdem in jeder Auswertung.
Das ist der gefährlichste Fehlermodus überhaupt, weil er unsichtbar ist.

**Entscheidung.** Export bricht bei unbekannten Werten ab. **Kein
Fuzzy-Matching beim Schreiben.** Unschärfe ist ausschließlich im
Sprachverständnis erlaubt (die KI darf „Trockenbauarbeiten" zu `Trockenbau`
zuordnen) — und das Ergebnis geht durch die Bestätigung des Mitarbeiters.

---

## D-06 · Feiertage und Sonntage sperren — ENTSCHIEDEN

Die Mappe sperrt die Eingabe an den 81 Berliner Feiertagen und kennt für
Sonntage gar keine Zeile. Die App validiert serverseitig gegen dieselbe
Feiertagsliste (aus der Mappe eingelesen, nicht neu gepflegt) und lehnt die
Erfassung mit klarer Meldung ab, statt sie erst beim Export scheitern zu lassen.

Der Mitarbeiter erfährt den Fehler damit am Feierabend, nicht das Büro drei
Wochen später.

---

## D-07 · Einheiten normalisiert, zentral konfiguriert — ENTSCHIEDEN

Zulässige Einheiten (`konfiguration/einheiten.yaml`):

```
m²  ·  lfm  ·  m³  ·  Stück  ·  kg  ·  Liter  ·  Stunden  ·  Pauschal
```

Normalisierung gesprochener Formen:

| gesprochen / transkribiert | normalisiert |
|---|---|
| Quadratmeter, qm, m2, m^2, QM | `m²` |
| laufende Meter, lfdm, Laufmeter, lm | `lfm` |
| Kubikmeter, cbm, m3 | `m³` |
| Stk, Stck, Stueck, St. | `Stück` |
| Kilogramm, kilo, Kg | `kg` |
| l, ltr, Ltr | `Liter` |
| Std, Stunde, h | `Stunden` |
| pauschal, psch, Pau. | `Pauschal` |

Die Normalisierung läuft **deterministisch im Code**, nicht im LLM. Unbekannte
Einheiten werden nicht geraten, sondern erzeugen eine Rückfrage.

Deutsche Zahlen ebenso deterministisch: `12,5` → `12.5`; `ungefähr 45` → `45`
mit Flag `geschaetzt=true`; `eineinhalb` → `1.5`. Tausenderpunkte werden nur bei
eindeutigem Muster (`1.250`) interpretiert.

---

## D-08 · Technikstack — ENTSCHIEDEN

| Baustein | Wahl | Begründung |
|---|---|---|
| Backend | Python 3.11 + FastAPI | openpyxl-Ökosystem, Pydantic-Validierung, schnelle Iteration |
| Datenbank | SQLite + WAL | Ein Server, wenige Nutzer. Eine Datei, triviales Backup. Migrationspfad zu Postgres offen |
| Frontend | Statisches HTML/CSS/JS, PWA | Keine Installation, kein Build-Schritt, kein Framework-Ballast für sechs Bildschirme |
| Excel | openpyxl | einzige Bibliothek mit Formel- und Merge-Erhalt in diesem Umfang |
| Auth | Session-Cookie, signiert | siehe D-11 |

Kein Docker-Zwang, kein Kubernetes, keine Message-Queue. Der MVP läuft als ein
Prozess hinter einem Reverse-Proxy.

---

## D-09 · Spracherkennung: Anbieter und Kosten — ENTSCHIEDEN, mit offener Datenschutzfrage

### Geprüfte Alternativen

| Anbieter | Deutsch | Kosten/min | Datenlage | Bewertung |
|---|---|---|---|---|
| **OpenAI Whisper API** | sehr gut, robust bei Dialekt und Nebengeräuschen | ~$0.006 | US-Anbieter, AVV verfügbar | beste Erkennung pro Euro |
| Deepgram Nova | gut | ~$0.004 | US-Anbieter | günstiger, bei Handwerksbegriffen schwächer |
| Azure AI Speech | gut | ~$0.015 | EU-Region wählbar, AVV Standard | datenschutzfreundlichste Cloud, teurer |
| faster-whisper lokal (large-v3) | sehr gut | 0 | Daten verlassen das Haus nicht | Hardware nötig; auf reiner CPU 1–3× Echtzeit |

### Entscheidung

**Whisper API für den Pilot, hinter dem Interface `Transkribierer`.**
Der lokale `faster-whisper`-Adapter wird im selben Sprint mitgeliefert, damit
ein Wechsel eine Zeile in der `.env` ist und keine Migration.

Qualitätshebel, der nichts kostet: Whisper akzeptiert einen Vokabular-Prompt.
Wir übergeben die 12 Gewerke, die 28 Mitarbeiternamen und die Einheitenliste.
Das verbessert genau die Begriffe, auf die es ankommt.

### Strukturierung

**Claude API, Modell `claude-opus-5`**, mit striktem JSON-Schema
(`output_config.format`), niedriger Effort-Stufe (die Aufgabe ist Extraktion,
keine Schlussfolgerung) und serverseitiger Pydantic-Nachvalidierung. Das Modell
liefert nie ein Datum und nie eine normalisierte Einheit — beides rechnet der
Code, damit es testbar bleibt.

### Kosten je Tagesbericht — korrigiert nach Messung

Die erste Schätzung ging von rund 60 Sekunden Audio je Bericht aus,
Rückfrage eingerechnet. **Vier echte Sprachnachrichten aus dem Betrieb dauerten
48, 67, 76 und 82 Sekunden** — im Mittel 68 Sekunden für die *erste* Aufnahme
allein. Mit einer Rückfragerunde sind rund 90 Sekunden realistisch, also
anderthalbmal so viel wie angenommen.

```
Transkription   ~90 s Audio inkl. Rückfrage          $0.009
Strukturierung  ~1.250 Eingabe- / ~550 Ausgabetoken  $0.020
Rückfragerunde  ~1.500 Eingabe- / ~550 Ausgabetoken  $0.021
                                                     ─────────
                                                     ~$0.050  ≈ 5 Cent
```

Hochrechnung: 20 Mitarbeiter × 250 Arbeitstage ≈ 5.000 Berichte ≈ **250–350 €
im Jahr**, zuzüglich Wiederholungen. Die Korrektur ändert die Größenordnung
nicht — gegenüber der eingesparten Bürozeit bleibt das vernachlässigbar und
rechtfertigt keine Qualitätskompromisse beim Modell.

### DECISION REQUIRED — Auftragsverarbeitung

Sprachaufnahmen von Mitarbeitern sind personenbezogene Daten. Vor dem Einsatz
mit echten Aufnahmen braucht es einen **AVV mit dem Transkriptionsanbieter**
und eine Information der Beschäftigten; bei einem Betriebsrat ist dieser zu
beteiligen. Ist das nicht kurzfristig zu klären, startet der Pilot mit dem
lokalen `faster-whisper`-Adapter — schlechtere Latenz, kein Datenabfluss.

**Zusätzlich entschieden:** Audiodateien werden nach erfolgreicher
Transkription **gelöscht**, nicht archiviert (§20: keine personenbezogenen Daten
unnötig speichern). Aufbewahrt wird der Transkripttext als Nachweis.

---

## D-10 · Erreichbarkeit der App vom Handy — ENTSCHIEDEN

**Das ist kein Betriebsdetail.** Browser geben das Mikrofon nur in einem
sicheren Kontext frei. Über `http://192.168.x.x` ist `navigator.mediaDevices`
bereits `undefined` — die Aufnahme startet weder in iOS Safari noch in Android
Chrome. Dafür gibt es keinen Workaround.

**Randbedingungen (HAG, 01.09.2026):**

1. Die Erfassung findet **auf der Baustelle** statt, im Mobilfunknetz.
2. Eine **öffentlich erreichbare Web-App mit Anmeldename und Passwort** ist
   ausreichend.

**Entscheidung.** Die App wird über eine reguläre HTTPS-Adresse
veröffentlicht. Kein VPN, kein Client auf dem Handy: Der Mitarbeiter öffnet
eine Adresse und meldet sich an. Damit entfällt Option A (Tailscale) — nicht
aus technischen Gründen, sondern weil eine VPN-App auf den Telefonen den
niedrigschwelligen Zugang zunichtemachen würde, von dem der Erfolg des
Produkts abhängt.

**Zwei gleichwertige Wege dorthin**, beide in `docs/BETRIEB-ZUGANG.md` mit
lauffähiger Konfiguration:

| | Weg | Offener Port | Dritter im Datenpfad |
|---|---|---|---|
| **B** | Cloudflare Tunnel | nein | **ja** — Cloudflare beendet TLS, AVV nötig |
| **C** | Eigene Domain + Caddy | **ja**, 443 | nein |

Die Wahl zwischen B und C ist eine reine Betriebsfrage der HAG-IT und berührt
den Code nicht: Die App ist proxy-neutral gebaut — Bindung an `127.0.0.1`,
`--proxy-headers`, keine absoluten URLs, `Secure`-Cookie, Startwarnung ohne
TLS. Sie läuft hinter beiden ohne eine Zeile Änderung.

**Empfehlung für den Pilot: B.** Kein offener Port am Firmenrechner, in einer
Stunde eingerichtet. Der AVV mit Cloudflare kommt ohnehin neben D-09 auf den
Tisch. Für den Dauerbetrieb ist C die sauberere Wahl, sobald die IT den Dienst
betreuen will.

**Folge, die nicht verhandelbar ist:** Ein öffentlich erreichbarer Dienst
verändert die Anforderungen an die Anmeldung — siehe D-11.

---

## D-11 · Authentifizierung — ENTSCHIEDEN (ersetzt die PIN-Variante)

**Vorgabe der HAG:** Anmeldename und Passwort genügen.

Das ist die richtige Entscheidung, und sie räumt ein Problem aus dem Weg, das
die ursprünglich geplante vierstellige PIN am offenen Internet gehabt hätte:
10.000 Kombinationen sind kein Schutz für einen Dienst, den jeder erreichen
kann.

### Festlegungen

| Punkt | Umsetzung |
|---|---|
| Anmeldung | Anmeldename (frei wählbar, nicht der Excel-Name) + Passwort |
| Passwortlänge | mindestens 10 Zeichen, keine Zeichenklassenpflicht |
| Speicherung | Argon2id, `konfiguration/benutzer.yaml`, nie im Klartext, nie im Code |
| Erstvergabe | Bauleitung legt Konto mit Einmalpasswort an, Wechsel bei der ersten Anmeldung erzwungen |
| Zurücksetzen | durch die Bauleitung über `benutzer-passwort-neu`; kein Selbstbedienungsweg per E-Mail |
| Sitzung | signiertes Cookie, `HttpOnly`, `Secure`, `SameSite=Lax`, 30 Tage rollierend |
| Ratenbegrenzung | je Konto **und** je IP; Verzögerung ab drei Fehlversuchen, Sperre nach zehn für 15 Minuten |
| Protokoll | Zeitpunkt, Konto, Ergebnis — niemals das Passwort, niemals ein Teil davon |

Keine Zeichenklassenpflicht, dafür Mindestlänge: Erzwungene Sonderzeichen
erzeugen `Sommer2026!` und Zettel am Bildschirm. Länge schützt besser und ist
auf einer Baustelle mit Handschuhen eher tippbar.

### Die Anmeldung zeigt keine Mitarbeiterliste mehr

Ursprünglich war der Name als **Auswahlliste** geplant — bequem bei 28
Personen und unbedenklich, solange die App nur intern erreichbar ist.

Öffentlich erreichbar ist dieselbe Auswahlliste zweierlei: eine
Veröffentlichung der Belegschaft und die halbe Zugangsinformation, frei Haus.
Deshalb:

- Der Anmeldename wird **getippt**, nicht ausgewählt
- Die Endpunkte `/api/mitarbeiter` und `/api/projekte` liefern erst **nach**
  erfolgreicher Anmeldung Daten
- Die Fehlermeldung lautet immer `Anmeldename oder Passwort ist falsch` —
  nie „Benutzer unbekannt", das würde gültige Namen verraten
- Fehlversuche brauchen unabhängig vom Grund gleich lang (kein Zeitunterschied
  zwischen unbekanntem Konto und falschem Passwort)

Der Anmeldename ist bewusst **nicht** der `excel_name` aus der
Mitarbeiterliste der Mappe. Die Zuordnung passiert intern; damit ist aus einem
erratenen Anmeldenamen nicht automatisch der Klarname ableitbar.

### Was das für den Aufwand bedeutet

EPIC 01 bleibt bei 1,5 PT. Der Mehraufwand für Argon2id, doppelte
Ratenbegrenzung und den erzwungenen Passwortwechsel wird dadurch aufgewogen,
dass die in `BETRIEB-ZUGANG.md` §5 skizzierte **Gerätebindung entfällt** — sie
war nur nötig, um eine schwache PIN am offenen Netz abzustützen.

---

## D-12 · Eine gebündelte Rückfrage, nicht eine je Feld — ENTSCHIEDEN

Der Brief zeigt in §3 genau dieses Verhalten („Die App fragt NICHT zehn Dinge
ab"). Fehlen Menge und Einheit zu zwei Positionen, entsteht **eine** Frage:

> „Wie viel habt ihr gespachtelt und wie viel geschliffen?"

Höchstens zwei Runden. Bleibt danach etwas offen, wird der Bericht mit
markierten Lücken zur manuellen Ergänzung angeboten, statt den Mitarbeiter in
einer Schleife festzuhalten. Ein Dialog, der länger dauert als das Formular,
das er ersetzt, hat sein Ziel verfehlt.

---

## D-13 · Korrekturfenster: derselbe Tag — ENTSCHIEDEN

Bestätigte Berichte sind bis Mitternacht des Erfassungstages durch den
Verfasser änderbar, danach nur noch durch die Bauleitung. Jede Änderung
erzeugt eine neue Version; **es wird nie hart gelöscht**, ein Storno setzt den
Status. Grund: Sobald exportiert wurde, muss nachvollziehbar bleiben, was in
der Mappe gelandet ist.

---

## D-14 · SQLite ist die Wahrheit der App, die Mappe das Controlling — ENTSCHIEDEN

Die Datenbank ist jederzeit die vollständige Quelle; jeder Export ist daraus
reproduzierbar (Brief §14). Geht eine befüllte Mappenkopie verloren, wird sie
neu erzeugt. Umgekehrt gilt das nicht — deshalb ist die DB und nicht die Mappe
das Backup-Ziel.

---

## D-15 · Referenzmappe im Repository ist anonymisiert — ENTSCHIEDEN

**Kontext.** Die mitgelieferte Mappe ist Testgrundlage für das Excel-Mapping
(Akzeptanzkriterium 12) und muss deshalb im Repository liegen. Sie enthielt
28 echte Mitarbeiternamen in `Listen!B2:B29`.

**Entscheidung.** Im Repository liegt ausschließlich
`referenz/Bauablaufmappe_Projektcontrolling_anonymisiert.xlsx` mit erfundenen
Namen. Erzeugt von `werkzeuge/mappe_anonymisieren.py`.

Die Ersetzung erfolgt **zellgenau**, nicht als Textersatz über die Datei. Grund:
Der Listeneintrag `Berlin` kommt als Wort auch im definierten Namen
`Berlin_Feiertage`, in der Spaltenüberschrift `Feiertage Berlin` und in einem
Zellkommentar vor. Ein globales Suchen-und-Ersetzen hätte die Feiertagssperre
der Datenvalidierung zerstört — und zwar lautlos.

Die Ersatznamen bilden die Eigenheiten des Originals bewusst nach, weil der
Code sie beherrschen muss:

| Eigenheit des Originals | Nachbildung in der Referenzmappe |
|---|---|
| ein Nachname doppelt, per Initial unterschieden, mit uneinheitlichem Leerzeichen | `S.Dallmann` / `D. Dallmann` |
| ein Eintrag ist keine Person, sondern ein Platzhalter | `SO (extern)`, unverändert übernommen |
| Umlaute in Namen | `Böttger`, `Hüttemann`, `Öztürk` |
| zwei Einträge nachträglich angehängt, außerhalb der Sortierung | `Nowak`, `Öztürk` |

Die ursprünglichen Namen sind hier bewusst nicht dokumentiert.

Nach der Ersetzung prüft das Skript Blattzahl, 1841 Merges, 8 Validierungen,
9 definierte Namen, die Formeln in H6 und K6, das Diagramm, die 12 Gewerke und
die 81 Feiertage. Weicht etwas ab, wird die Ausgabe verworfen statt
ausgeliefert. Der Lauf bestätigte: Struktur unverändert.

**Für den Pilotbetrieb** zeigt `konfiguration/projekte.yaml` auf die echte
Mappe außerhalb des Repositorys. Die anonymisierte Fassung dient nur den Tests.

**Offen (gering):** `LieferantenListe` enthält 11 reale Lieferantennamen. Das
sind Geschäftsdaten, keine personenbezogenen — deshalb belassen. Soll das
Repository später öffentlich werden, sind sie mit demselben Skript ersetzbar.

---

## Risiken

| ID | Risiko | Wirkung | Gegenmaßnahme |
|---|---|---|---|
| **R-01** | HAG ändert die Mappenstruktur | Export schreibt in falsche Zeilen | `mappe_analysieren.py` läuft als Test im CI; Export prüft die Geometrie vor jedem Lauf und bricht ab |
| **R-02** | Baustellenlärm, Dialekt, Fachbegriffe | falsche Erkennung | Vokabular-Prompt; Bestätigungsschritt ist Pflicht; Unsicherheit wird angezeigt, nicht geglättet |
| **R-03** | Mehr als 10 Mitarbeiter je Tag | kein Slot in der Mappe | Export meldet Überlauf namentlich und schreibt nichts |
| **R-04** | Personenbezug in der Referenzmappe | personenbezogene Daten im Repository | **Erledigt:** `referenz/` enthält nur die anonymisierte Mappe (28 erfundene Namen, Struktur identisch). Die Produktivmappe bleibt außerhalb des Repositorys. Siehe D-15 |
| **R-05** | KI erfindet Mengen | falsche Abrechnungsgrundlage | Schema erlaubt `null`; fehlende Menge erzeugt Rückfrage; niedrige Konfidenz wird markiert; nichts wird ohne Bestätigung gespeichert |
| **R-06** | Kein Netz auf der Baustelle | Bericht geht verloren | Aufnahme im Browser puffern, automatisch wiederholen, Status „noch nicht gesendet" dauerhaft sichtbar |
| **R-07** | Bauzeit über 366 Nicht-Sonntage | Gerüst reicht nicht | Export prüft die Bauzeit und meldet, dass die Mappe verlängert werden muss |
| **R-09** | Erkennungsqualität an echter Bausprache ist **ungemessen** | Die Oberfläche würde um eine Annahme herum gebaut | Werkzeug `realitaetstest.py` liegt bereit; es fehlt nur ein API-Schlüssel. **Vor EPIC 02 nachzuholen** |
| **R-08** | Modellantwort unbrauchbar oder abgelehnt | Bericht blockiert | Serverseitige Validierung; bei Fehler manuelles Formular mit vorausgefülltem Transkript — der Mitarbeiter kommt nie in eine Sackgasse |

---

## Technische Schulden (bewusst aufgenommen)

| ID | Schuld | Warum vertretbar | Wann fällig |
|---|---|---|---|
| T-01 | Stammdaten (Mitarbeiter, Gewerke) werden aus der Mappe importiert, nicht in der App gepflegt | Die Mappe ist die Wahrheit; doppelte Pflege wäre schlimmer | wenn die App führend wird |
| T-02 | Keine Mandantentrennung auf DB-Ebene | ein Unternehmen, ein Server | bei Mehrfirmenbetrieb |
| T-03 | Export ist synchron | Sekunden bei realistischen Mengen | ab ~10.000 Berichten je Lauf |
| T-04 | Kein Offline-Sprachmodell im Browser | unrealistisch für den MVP | — |
| T-06 | Fehlversuchszähler liegt im Arbeitsspeicher, nicht in der Datenbank | Ein Prozess, 28 Nutzer — eine Tabelle wäre Aufwand ohne Gewinn. Ein Neustart setzt die Zähler zurück, aber den kann ein Angreifer nicht auslösen | sobald die App auf mehreren Prozessen läuft |
| T-05 | Kein Migrationswerkzeug — das Schema entsteht über `create_all` | Solange keine Echtdaten liegen, ist ein Schemawechsel ein Neuanlegen. Alembic jetzt einzuführen wäre Aufwand ohne Nutzen | **vor dem Pilotbetrieb**, sobald die erste echte Erfassung in der Datenbank steht |

## Später, nicht jetzt

Baustellenerkennung per GPS · Fotos zum Tagesbericht · Materialerfassung ·
Auswertung je Mitarbeiter · Push-Erinnerung am Feierabend ·
Rückschreiben direkt in die Meistermappe · Postgres.

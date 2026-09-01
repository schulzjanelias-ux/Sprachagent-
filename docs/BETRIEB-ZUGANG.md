# Zugang vom Handy zum Server (D-10)

Entscheidungsgrundlage für die HAG-IT. Drei Wege, jeweils mit lauffähiger
Beispielkonfiguration, Prüfprotokoll und Folgen für Datenschutz und Sicherheit.

---

## 1. Warum das kein Betriebsdetail ist

Browser geben Kamera und Mikrofon nur in einem **sicheren Kontext** frei —
HTTPS mit gültigem Zertifikat oder `localhost`. Ohne das schlägt der Aufruf
fehl, mit dem die App ihre Kernfunktion startet:

```javascript
navigator.mediaDevices.getUserMedia({ audio: true })
// über http://192.168.x.x ist navigator.mediaDevices bereits undefined
```

Es gibt dafür **keinen Workaround.** Kein Schalter, keine Bibliothek, keine
Einstellung im Handy. Eine Anwendung, die die Sprachaufnahme nicht starten
kann, ist zu 100 % unbenutzbar, egal wie gut alles andere gebaut ist.

Deshalb ist D-10 der einzige echte Blocker im Projekt.

## 2. Was die Randbedingung „Erfassung auf der Baustelle" ausschließt

Die Mitarbeiter erfassen unterwegs, im Mobilfunknetz. Damit fällt die
einfachste und billigste Lösung weg:

> **Nicht mehr möglich:** selbstsigniertes Zertifikat oder interner Reverse-Proxy,
> nur im Firmen-WLAN erreichbar. Kostet nichts, braucht keinen Anbieter — hilft
> aber nicht, wenn das Handy gar nicht im Firmennetz ist.

Der Server muss von außerhalb des Firmennetzes erreichbar sein. Die drei
verbleibenden Wege unterscheiden sich darin, **wer den Weg dorthin bereitstellt
und wer dabei die Sprachaufnahmen sehen kann.**

---

## 3. Die Optionen

### Option A · Tailscale (VPN)

Ein WireGuard-basiertes Netz zwischen Firmenrechner und Diensthandys. Der
Server bekommt einen Namen wie `hag-server.tailnet-name.ts.net` mit echtem
Let's-Encrypt-Zertifikat. Kein Port wird nach außen geöffnet.

```bash
# auf dem Firmenrechner
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# HTTPS für die App auf Port 8000 bereitstellen
sudo tailscale serve --bg 8000
# -> https://hag-server.tailnet-name.ts.net
```

Voraussetzung: In der Tailscale-Verwaltung müssen **MagicDNS** und
**HTTPS-Zertifikate** aktiviert sein.

Auf dem Handy: Tailscale-App installieren, mit dem Firmenkonto anmelden. Die
App bleibt im Hintergrund und leitet nur den Verkehr zum Firmennetz um, nicht
den gesamten Datenverkehr des Telefons.

| | |
|---|---|
| **Dafür** | Kein Dritter sieht die Aufnahmen. Kein offener Port. Geräteverwaltung eingebaut — ein ausgeschiedener Mitarbeiter wird zentral entfernt. Kein zusätzlicher Auftragsverarbeiter neben D-09. |
| **Dagegen** | Eine App auf jedem Handy, die installiert, angemeldet und aktiv gehalten werden muss. Nutzerlizenzen für 28 Personen. Bei schlechtem Netz kommt der VPN-Aufbau zur ohnehin wackligen Verbindung hinzu. |
| **Passt, wenn** | es Diensthandys gibt. |

### Option B · Cloudflare Tunnel

Der Firmenrechner baut eine ausgehende Verbindung zu Cloudflare auf; von dort
wird die App unter einer eigenen Subdomain veröffentlicht. Kein eingehender
Port, keine App auf dem Handy — die Mitarbeiter öffnen eine ganz normale
Adresse im Browser.

```bash
cloudflared tunnel login
cloudflared tunnel create tagesbericht
cloudflared tunnel route dns tagesbericht tagesbericht.hag-beispiel.de
```

```yaml
# /etc/cloudflared/config.yml
tunnel: <TUNNEL-ID>
credentials-file: /etc/cloudflared/<TUNNEL-ID>.json
ingress:
  - hostname: tagesbericht.hag-beispiel.de
    service: http://localhost:8000
  - service: http_status:404
```

```bash
sudo cloudflared service install    # als Dienst dauerhaft starten
```

| | |
|---|---|
| **Dafür** | Nichts auf dem Handy zu installieren — der niedrigste denkbare Widerstand für den Nutzer. Kein offener Port. Funktioniert in jedem Netz. Schnell eingerichtet. |
| **Dagegen** | **Cloudflare beendet die TLS-Verbindung und sieht die hochgeladenen Sprachaufnahmen im Klartext.** Damit wird Cloudflare zum Auftragsverarbeiter — ein zweiter AVV zusätzlich zu D-09. Eine Domain bei Cloudflare ist Voraussetzung. |
| **Passt, wenn** | private Handys genutzt werden und der zweite AVV vertretbar ist. |

### Option C · Eigene Domain mit Caddy

Klassisch: Subdomain auf die Firmen-IP, Portfreigabe 443, automatische
Zertifikate.

```caddyfile
# /etc/caddy/Caddyfile
tagesbericht.hag-beispiel.de {
    reverse_proxy localhost:8000

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
    }

    request_body {
        max_size 25MB          # Audio-Uploads begrenzen
    }
}
```

Ohne feste IP zusätzlich ein DynDNS-Eintrag. Sind Portfreigaben nicht
erwünscht, geht Let's Encrypt auch per DNS-Challenge — dann bleibt 80/443
zu, es wird aber ein API-Zugang beim DNS-Anbieter gebraucht.

| | |
|---|---|
| **Dafür** | Kein Dritter im Datenpfad. Keine App auf dem Handy. Keine laufenden Lizenzkosten. Volle Kontrolle. |
| **Dagegen** | **Der Firmenrechner hängt am offenen Internet.** Erfordert Zustimmung und Pflege durch die IT: Updates, Überwachung, Absicherung. Siehe Abschnitt 5 — das ändert die Anforderungen an die Anmeldung. |
| **Passt, wenn** | eine IT da ist, die einen exponierten Dienst betreuen will. |

---

## 4. Die eine Frage, die entscheidet

```
Nutzen die Mitarbeiter Diensthandys oder private Handys?

  Diensthandys ──────────────► Option A (Tailscale)
                               VPN-App zumutbar, beste Datenlage

  Private Handys ────────────► Option B (Cloudflare Tunnel)
                               VPN auf Privatgeräten ist ein
                               Mitbestimmungs- und Akzeptanzthema;
                               dafür ein zweiter AVV

  Eigene IT vorhanden und ───► Option C (Caddy)
  offener Dienst gewollt       plus die Härtung aus Abschnitt 5
```

Eine VPN-App auf privaten Telefonen zu verlangen, ist keine rein technische
Frage: Sie berührt die Mitbestimmung und wird erfahrungsgemäß schlecht
angenommen. Wenn die HAG keine Diensthandys stellt, ist Option A praktisch
kaum durchsetzbar — unabhängig davon, dass sie technisch die sauberste wäre.

---

## 5. Folge für die Anmeldung: D-10 verändert D-11

Bisher vorgesehen (D-11): Name aus einer Liste plus **vierstellige PIN**.

Das ist eine gute Entscheidung — **hinter einem VPN.** Am offenen Internet ist
es keine mehr:

> 28 bekannte Nachnamen × 10.000 PINs. Der Nutzername steht in einer
> Auswahlliste, ist also kein Geheimnis. Wer die Adresse kennt, hat einen
> überschaubaren Suchraum vor sich.

Deshalb gilt:

| Zugangsweg | Anforderung an die Anmeldung |
|---|---|
| **A · Tailscale** | Vierstellige PIN genügt. Das VPN ist die erste Schranke, die PIN unterscheidet nur noch die Personen untereinander. |
| **B · Cloudflare Tunnel** | PIN **sechsstellig**, strikte Ratenbegrenzung je Konto und je IP, Sperre nach zehn Fehlversuchen. Zusätzlich empfohlen: Cloudflare Access als vorgelagerte Schranke. |
| **C · Caddy, offen** | Wie B, zusätzlich Gerätebindung: Die erste Anmeldung eines Geräts wird durch die Bauleitung freigegeben, danach trägt das Gerät ein langlebiges Token. |

**Diese Kopplung ist der eigentliche Grund, warum D-10 vor Sprint 2 fallen
muss.** Der Aufwand für EPIC 01 unterscheidet sich zwischen Option A und
Option C um etwa einen Personentag — Gerätebindung und verschärfte
Ratenbegrenzung sind kein Nachrüstdetail, sondern verändern das Datenmodell
der Sitzungen.

---

## 6. Was die App unabhängig von der Entscheidung mitbringt

Damit die Wahl den Code **nicht** berührt, wird die Anwendung von Anfang an
proxy-neutral gebaut. Alle drei Optionen laufen dann ohne Codeänderung.

**Server hinter dem Proxy starten**

```bash
uvicorn app.main:app \
    --host 127.0.0.1 --port 8000 \
    --proxy-headers --forwarded-allow-ips=127.0.0.1
```

Der Dienst lauscht ausschließlich auf `127.0.0.1`. Er ist damit auch dann
nicht direkt erreichbar, wenn versehentlich eine Portfreigabe entsteht.

**Regeln im Code**

- Keine absoluten URLs erzeugen; alle Verweise relativ
- `X-Forwarded-Proto` respektieren, damit die App ihr eigenes Schema kennt
- Session-Cookie mit `Secure`, `HttpOnly`, `SameSite=Lax`
- Beim Start eine Warnung ins Protokoll, wenn ohne TLS und ohne Proxy-Header
  gestartet wurde
- Obergrenze für die Audio-Uploadgröße serverseitig, nicht nur im Proxy

**Ehrliche Meldung im Frontend statt stummem Fehler**

```javascript
if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
  zeigeHinweis(
    "Die Aufnahme ist über diese Adresse nicht möglich, weil die Verbindung " +
    "nicht gesichert ist. Bitte die App über die offizielle Adresse öffnen. " +
    "Du kannst den Bericht solange von Hand eintragen."
  );
  formularAnzeigen();          // Erfassung bleibt möglich
}
```

Kein weißer Bildschirm, keine tote Schaltfläche: Der Mitarbeiter erfährt den
Grund und kann trotzdem arbeiten.

---

## 7. Prüfprotokoll — bevor der Pilot startet

Auf einem echten iPhone **und** einem echten Android-Gerät, im Mobilfunknetz,
nicht im WLAN:

| # | Prüfung | Erwartet |
|---|---|---|
| 1 | Adresse im Browser öffnen | Seite lädt, Schlosssymbol sichtbar |
| 2 | `window.isSecureContext` in der Konsole | `true` |
| 3 | Aufnahmeknopf drücken | Systemabfrage nach Mikrofonzugriff erscheint |
| 4 | Freigeben und 10 s sprechen | Aufnahme läuft, Pegel sichtbar |
| 5 | Absenden | Bericht kommt an, Status wechselt auf gespeichert |
| 6 | Zur Startseite hinzufügen, als PWA öffnen | Aufnahme funktioniert auch dort |
| 7 | Flugmodus ein, aufnehmen, absenden | Status „noch nicht gesendet", nichts geht verloren |
| 8 | Flugmodus aus | Eintrag wird automatisch zugestellt |
| 9 | Am nächsten Tag erneut öffnen | Noch angemeldet (30-Tage-Sitzung) |

Punkt 6 ist erfahrungsgemäß die Stolperstelle: Der Mikrofonzugriff aus einer
zum Startbildschirm hinzugefügten Web-App verhielt sich in älteren
iOS-Versionen anders als im Safari-Tab. Das muss auf dem tatsächlich
eingesetzten Gerätestand geprüft werden, nicht angenommen.

Punkt 7 und 8 prüfen den Ausgangskorb (EPIC 12) — genau den Fall, für den er
gebaut ist.

---

## 8. Empfehlung

**Gibt es Diensthandys: Option A (Tailscale).** Beste Datenlage, kein
zusätzlicher Auftragsverarbeiter, die vierstellige PIN aus D-11 bleibt
ausreichend.

**Gibt es keine: Option B (Cloudflare Tunnel)** für den Pilot, mit
sechsstelliger PIN und Ratenbegrenzung. Der zweite AVV ist der Preis dafür,
dass die Mitarbeiter nichts installieren müssen — und Akzeptanz entscheidet
bei diesem Produkt über Erfolg oder Misserfolg.

Option C ist die richtige Wahl für den Dauerbetrieb, wenn die HAG-IT den
Dienst ohnehin betreuen will. Für einen Pilot mit wenigen Nutzern ist der
Betreuungsaufwand aber der schlechteste Einstieg.

**Für Sprint 1 wird nichts davon gebraucht.** Die Entscheidung muss vor
Sprint 2 (EPIC 02, Sprachaufnahme) fallen, weil sie über EPIC 01 den Umfang
der Anmeldung mitbestimmt.

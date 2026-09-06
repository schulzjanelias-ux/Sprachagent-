"""Anmeldung, Sitzung und Missbrauchsschutz (EPIC 01, D-11).

Die App ist oeffentlich erreichbar (D-10). Daraus folgen drei Dinge, die bei
einem nur intern erreichbaren Dienst verzichtbar waeren:

1. Ein echtes Passwort statt einer PIN. 10.000 Kombinationen sind kein Schutz
   fuer etwas, das jeder aufrufen kann.
2. Keine Auskunft darueber, welche Konten existieren - weder ueber die
   Fehlermeldung noch ueber die Antwortzeit.
3. Ratenbegrenzung je Konto **und** je Herkunftsadresse. Nur je Konto liesse
   das Durchprobieren vieler Konten zu, nur je Adresse das Durchprobieren
   aus einem Botnetz.
"""
from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Einstellungen, einstellungen

protokoll = logging.getLogger(__name__)

_hasher = PasswordHasher()

# Gegen diesen Hash wird geprueft, wenn es das Konto nicht gibt. Ohne das
# waere ein unbekannter Anmeldename an der kuerzeren Antwortzeit erkennbar -
# und damit die Belegschaft durchprobierbar.
_BLINDHASH = _hasher.hash("blindprobe-ohne-bedeutung")

SITZUNG_COOKIE = "hag_sitzung"

VERZOEGERUNG_AB_VERSUCH = 3
SPERRE_AB_VERSUCH = 10
SPERRE_MINUTEN = 15
VERZOEGERUNG_SEKUNDEN = 1.0


class AnmeldeFehler(Exception):
    """Anmeldung nicht moeglich. Die Meldung ist bewusst unspezifisch."""


class Gesperrt(AnmeldeFehler):
    """Zu viele Fehlversuche."""


# --- Passwoerter -----------------------------------------------------------

def passwort_hashen(passwort: str) -> str:
    return _hasher.hash(passwort)


def passwort_pruefen(hash_wert: str, passwort: str) -> bool:
    try:
        _hasher.verify(hash_wert, passwort)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def blindpruefung() -> None:
    """Gleiche Rechenzeit, wenn das Konto nicht existiert."""
    try:
        _hasher.verify(_BLINDHASH, "falsch")
    except VerifyMismatchError:
        pass


def passwort_bewerten(passwort: str, mindestlaenge: int | None = None) -> list[str]:
    """Gibt die Gruende zurueck, warum ein Passwort nicht taugt.

    Bewusst nur Mindestlaenge, keine Zeichenklassenpflicht: Erzwungene
    Sonderzeichen erzeugen 'Sommer2026!' und Zettel am Bildschirm. Laenge
    schuetzt besser und ist mit Handschuhen eher tippbar (D-11).
    """
    grenze = mindestlaenge or einstellungen().passwort_laenge_min
    gruende = []
    if len(passwort) < grenze:
        gruende.append(f"Das Passwort muss mindestens {grenze} Zeichen haben.")
    if passwort.strip() != passwort:
        gruende.append("Das Passwort darf nicht mit einem Leerzeichen beginnen oder enden.")
    if passwort.lower() in ("passwort12", "hag1234567", "1234567890"):
        gruende.append("Dieses Passwort ist zu leicht zu erraten.")
    return gruende


def einmalpasswort() -> str:
    """Lesbares Erstpasswort fuer die Ausgabe durch die Bauleitung."""
    return secrets.token_urlsafe(9)


def sitzungs_kennung_erzeugen() -> str:
    return secrets.token_hex(16)


# --- Sitzungscookie --------------------------------------------------------

def _serialisierer(konfiguration: Einstellungen) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(konfiguration.sitzung_schluessel, salt="hag-sitzung")


def sitzung_ausstellen(mitarbeiter_id: int, sitzungs_kennung: str,
                       konfiguration: Einstellungen | None = None) -> str:
    konfiguration = konfiguration or einstellungen()
    return _serialisierer(konfiguration).dumps(
        {"mid": mitarbeiter_id, "sk": sitzungs_kennung})


def sitzung_lesen(rohwert: str,
                  konfiguration: Einstellungen | None = None) -> tuple[int, str] | None:
    """Cookie pruefen. None bei Faelschung oder Ablauf - nie eine Ausnahme."""
    konfiguration = konfiguration or einstellungen()
    try:
        daten = _serialisierer(konfiguration).loads(
            rohwert, max_age=konfiguration.sitzung_tage * 86400)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(daten, dict) or "mid" not in daten:
        return None
    return int(daten["mid"]), str(daten.get("sk", ""))


def cookie_einstellungen(konfiguration: Einstellungen | None = None) -> dict:
    konfiguration = konfiguration or einstellungen()
    return {
        "key": SITZUNG_COOKIE,
        "httponly": True,
        "secure": konfiguration.https_aktiv,
        "samesite": "lax",
        "max_age": konfiguration.sitzung_tage * 86400,
        "path": "/",
    }


# --- Ratenbegrenzung -------------------------------------------------------

@dataclass
class _Zaehler:
    versuche: int = 0
    gesperrt_bis: datetime | None = None


@dataclass
class Fehlversuche:
    """Zaehlt Fehlversuche je Konto und je Herkunftsadresse.

    Im Arbeitsspeicher: Bei einem Prozess und 28 Nutzern waere eine Tabelle
    Aufwand ohne Gewinn. Ein Neustart setzt die Zaehler zurueck - der
    Angreifer kann keinen ausloesen, deshalb ist das hinnehmbar. Bei mehreren
    Prozessen muesste das wandern (vermerkt als T-06).
    """

    _konten: dict[str, _Zaehler] = field(default_factory=dict)
    _adressen: dict[str, _Zaehler] = field(default_factory=dict)

    def _pruefen(self, ablage: dict[str, _Zaehler], schluessel: str,
                 jetzt: datetime) -> None:
        zaehler = ablage.get(schluessel)
        if zaehler and zaehler.gesperrt_bis and zaehler.gesperrt_bis > jetzt:
            verbleibend = int((zaehler.gesperrt_bis - jetzt).total_seconds() / 60) + 1
            raise Gesperrt(
                f"Zu viele Fehlversuche. Bitte in {verbleibend} Minuten erneut "
                f"versuchen.")

    def sperre_pruefen(self, anmeldename: str, adresse: str,
                       jetzt: datetime | None = None) -> None:
        jetzt = jetzt or datetime.now()
        self._pruefen(self._konten, anmeldename.lower(), jetzt)
        self._pruefen(self._adressen, adresse, jetzt)

    def verzoegerung(self, anmeldename: str) -> float:
        zaehler = self._konten.get(anmeldename.lower())
        if zaehler and zaehler.versuche >= VERZOEGERUNG_AB_VERSUCH:
            return VERZOEGERUNG_SEKUNDEN
        return 0.0

    def fehlversuch(self, anmeldename: str, adresse: str,
                    jetzt: datetime | None = None) -> None:
        jetzt = jetzt or datetime.now()
        for ablage, schluessel in ((self._konten, anmeldename.lower()),
                                   (self._adressen, adresse)):
            zaehler = ablage.setdefault(schluessel, _Zaehler())
            zaehler.versuche += 1
            if zaehler.versuche >= SPERRE_AB_VERSUCH:
                zaehler.gesperrt_bis = jetzt + timedelta(minutes=SPERRE_MINUTEN)

    def zuruecksetzen(self, anmeldename: str, adresse: str) -> None:
        self._konten.pop(anmeldename.lower(), None)
        self._adressen.pop(adresse, None)

    def leeren(self) -> None:
        self._konten.clear()
        self._adressen.clear()


fehlversuche = Fehlversuche()


def bremsen(sekunden: float) -> None:
    if sekunden > 0:
        time.sleep(sekunden)

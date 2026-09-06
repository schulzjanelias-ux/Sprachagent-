"""Anmeldung, Abmeldung, Passwortwechsel (EPIC 01, D-11)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.abhaengigkeiten import angemeldeter_mitarbeiter, datenbank
from app.config import einstellungen
from app.modelle import Mitarbeiter
from app.sicherheit import (
    AnmeldeFehler, Gesperrt, SITZUNG_COOKIE, blindpruefung, bremsen,
    cookie_einstellungen, fehlversuche, passwort_bewerten, passwort_hashen,
    passwort_pruefen, sitzung_ausstellen, sitzungs_kennung_erzeugen,
)

protokoll = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["anmeldung"])

# Immer dieselbe Meldung: "Benutzer unbekannt" wuerde gueltige Anmeldenamen
# verraten, und die Belegschaft ist damit durchprobierbar (D-11).
ABGELEHNT = "Anmeldename oder Passwort ist falsch."


class AnmeldeDaten(BaseModel):
    anmeldename: str = Field(min_length=1, max_length=64)
    passwort: str = Field(min_length=1, max_length=256)


class PasswortDaten(BaseModel):
    altes_passwort: str = Field(min_length=1, max_length=256)
    neues_passwort: str = Field(min_length=1, max_length=256)


class MitarbeiterAuskunft(BaseModel):
    anzeigename: str
    rolle: str
    passwort_wechseln: bool


def _herkunft(anfrage: Request) -> str:
    """Herkunftsadresse hinter dem Reverse-Proxy (D-10)."""
    weitergereicht = anfrage.headers.get("x-forwarded-for", "")
    if weitergereicht:
        return weitergereicht.split(",")[0].strip()
    return anfrage.client.host if anfrage.client else "unbekannt"


@router.post("/anmelden", response_model=MitarbeiterAuskunft)
def anmelden(daten: AnmeldeDaten, anfrage: Request, antwort: Response,
             sitzung: Session = Depends(datenbank)) -> MitarbeiterAuskunft:
    adresse = _herkunft(anfrage)

    try:
        fehlversuche.sperre_pruefen(daten.anmeldename, adresse)
    except Gesperrt as fehler:
        protokoll.warning("Anmeldung gesperrt für %s von %s",
                          daten.anmeldename, adresse)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(fehler)) from fehler

    bremsen(fehlversuche.verzoegerung(daten.anmeldename))

    mitarbeiter = sitzung.scalar(
        select(Mitarbeiter).where(
            func.lower(Mitarbeiter.anmeldename) == daten.anmeldename.lower()))

    if mitarbeiter is None or not mitarbeiter.aktiv:
        # Gleiche Rechenzeit wie bei einem vorhandenen Konto.
        blindpruefung()
        fehlversuche.fehlversuch(daten.anmeldename, adresse)
        protokoll.info("Anmeldung fehlgeschlagen von %s", adresse)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, ABGELEHNT)

    if not passwort_pruefen(mitarbeiter.passwort_hash, daten.passwort):
        fehlversuche.fehlversuch(daten.anmeldename, adresse)
        protokoll.info("Anmeldung fehlgeschlagen von %s", adresse)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, ABGELEHNT)

    fehlversuche.zuruecksetzen(daten.anmeldename, adresse)

    if not mitarbeiter.sitzungs_kennung:
        mitarbeiter.sitzungs_kennung = sitzungs_kennung_erzeugen()
        sitzung.flush()

    antwort.set_cookie(
        value=sitzung_ausstellen(mitarbeiter.id, mitarbeiter.sitzungs_kennung),
        **cookie_einstellungen())
    protokoll.info("Anmeldung erfolgreich: Konto %s", mitarbeiter.id)

    return MitarbeiterAuskunft(
        anzeigename=mitarbeiter.anzeigename, rolle=mitarbeiter.rolle.value,
        passwort_wechseln=mitarbeiter.passwort_wechseln)


@router.post("/abmelden", status_code=status.HTTP_204_NO_CONTENT)
def abmelden(antwort: Response) -> None:
    antwort.delete_cookie(SITZUNG_COOKIE, path="/")


@router.get("/ich", response_model=MitarbeiterAuskunft)
def ich(mitarbeiter: Mitarbeiter = Depends(angemeldeter_mitarbeiter)) -> MitarbeiterAuskunft:
    return MitarbeiterAuskunft(
        anzeigename=mitarbeiter.anzeigename, rolle=mitarbeiter.rolle.value,
        passwort_wechseln=mitarbeiter.passwort_wechseln)


@router.post("/passwort", status_code=status.HTTP_204_NO_CONTENT)
def passwort_aendern(daten: PasswortDaten, antwort: Response,
                     mitarbeiter: Mitarbeiter = Depends(angemeldeter_mitarbeiter),
                     sitzung: Session = Depends(datenbank)) -> None:
    if not passwort_pruefen(mitarbeiter.passwort_hash, daten.altes_passwort):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "Das bisherige Passwort ist falsch.")

    gruende = passwort_bewerten(daten.neues_passwort)
    if gruende:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, " ".join(gruende))

    mitarbeiter.passwort_hash = passwort_hashen(daten.neues_passwort)
    mitarbeiter.passwort_wechseln = False
    # Alle bisherigen Sitzungen beenden - auch die auf anderen Geraeten.
    mitarbeiter.sitzungs_kennung = sitzungs_kennung_erzeugen()
    sitzung.flush()

    antwort.set_cookie(
        value=sitzung_ausstellen(mitarbeiter.id, mitarbeiter.sitzungs_kennung),
        **cookie_einstellungen())
    protokoll.info("Passwort geändert: Konto %s", mitarbeiter.id)

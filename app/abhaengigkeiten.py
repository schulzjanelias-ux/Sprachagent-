"""Gemeinsame Abhaengigkeiten der Endpunkte."""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.datenbank import sitzung as sitzung_oeffnen
from app.modelle import Mitarbeiter, Rolle
from app.sicherheit import SITZUNG_COOKIE, sitzung_lesen

NICHT_ANGEMELDET = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Bitte anmelden.",
)


def datenbank() -> Iterator[Session]:
    with sitzung_oeffnen() as offen:
        yield offen


def angemeldeter_mitarbeiter(
    hag_sitzung: str | None = Cookie(default=None, alias=SITZUNG_COOKIE),
    sitzung: Session = Depends(datenbank),
) -> Mitarbeiter:
    if not hag_sitzung:
        raise NICHT_ANGEMELDET

    gelesen = sitzung_lesen(hag_sitzung)
    if gelesen is None:
        raise NICHT_ANGEMELDET

    mitarbeiter_id, sitzungs_kennung = gelesen
    mitarbeiter = sitzung.get(Mitarbeiter, mitarbeiter_id)
    if mitarbeiter is None or not mitarbeiter.aktiv:
        raise NICHT_ANGEMELDET

    # Ein Passwortwechsel setzt die Kennung neu und beendet damit alle noch
    # laufenden Sitzungen - wer sein Passwort aendert, weil es kompromittiert
    # war, will genau das.
    if mitarbeiter.sitzungs_kennung != sitzungs_kennung:
        raise NICHT_ANGEMELDET

    return mitarbeiter


def bauleiter(
    mitarbeiter: Mitarbeiter = Depends(angemeldeter_mitarbeiter),
) -> Mitarbeiter:
    if mitarbeiter.rolle != Rolle.bauleiter:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dieser Bereich ist der Bauleitung vorbehalten.")
    return mitarbeiter

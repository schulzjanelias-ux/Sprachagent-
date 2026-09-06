"""Stammdaten fuer die Oberflaeche - ausschliesslich nach Anmeldung.

Die App ist oeffentlich erreichbar (D-10). Eine frei abrufbare Projekt- oder
Mitarbeiterliste waere eine Veroeffentlichung der Belegschaft und der
Kundenbeziehungen (D-11).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.abhaengigkeiten import angemeldeter_mitarbeiter, datenbank
from app.dienste.einheiten import einheiten_laden
from app.dienste.excel.leser import MappenFehler, stammdaten_lesen
from app.modelle import Mitarbeiter, Projekt

router = APIRouter(prefix="/api", tags=["stammdaten"],
                   dependencies=[Depends(angemeldeter_mitarbeiter)])


class ProjektAuskunft(BaseModel):
    id: int
    name: str


class EinheitAuskunft(BaseModel):
    code: str
    bezeichnung: str


@router.get("/projekte", response_model=list[ProjektAuskunft])
def projekte(sitzung: Session = Depends(datenbank)) -> list[ProjektAuskunft]:
    zeilen = sitzung.scalars(
        select(Projekt).where(Projekt.aktiv.is_(True)).order_by(Projekt.name))
    return [ProjektAuskunft(id=p.id, name=p.name) for p in zeilen]


@router.get("/einheiten", response_model=list[EinheitAuskunft])
def einheiten() -> list[EinheitAuskunft]:
    return [EinheitAuskunft(code=e.code, bezeichnung=e.bezeichnung)
            for e in einheiten_laden()]


@router.get("/gewerke", response_model=list[str])
def gewerke(projekt_id: int, sitzung: Session = Depends(datenbank)) -> list[str]:
    """Gewerke aus der Mappe des Projekts - sie ist die Wahrheit (T-01)."""
    projekt = sitzung.get(Projekt, projekt_id)
    if projekt is None:
        return []
    try:
        from pathlib import Path
        return list(stammdaten_lesen(Path(projekt.mappe_pfad)).gewerke)
    except MappenFehler:
        return []

"""FastAPI-Anwendung: Aufbau, Lebenszyklus, Gesundheitsendpunkt.

Die App laeuft hinter einem Reverse-Proxy (D-10). Sie erzeugt deshalb keine
absoluten URLs und verlaesst sich fuer das eigene Schema auf die vom Proxy
gesetzten Forwarded-Header, die uvicorn mit --proxy-headers auswertet.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import __version__
from app.config import einstellungen, protokollierung_einrichten
from app.datenbank import einrichten as datenbank_einrichten
from app.routen import anmeldung, stammdaten

protokoll = logging.getLogger(__name__)


@asynccontextmanager
async def lebenszyklus(app: FastAPI):
    e = einstellungen()
    protokollierung_einrichten(e.protokoll_stufe)

    protokoll.info("HAG Tagesbericht %s startet", __version__)
    for warnung in e.warnungen():
        protokoll.warning("BETRIEB: %s", warnung)

    e.datenbank_pfad.parent.mkdir(parents=True, exist_ok=True)
    e.export_verzeichnis.mkdir(parents=True, exist_ok=True)
    datenbank_einrichten()

    yield

    protokoll.info("HAG Tagesbericht beendet")


app = FastAPI(
    title="HAG · Digitaler Tagesbericht",
    version=__version__,
    lifespan=lebenszyklus,
    docs_url=None,      # keine oeffentliche API-Dokumentation (D-10: oeffentlich erreichbar)
    redoc_url=None,
    openapi_url=None,
)


app.include_router(anmeldung.router)
app.include_router(stammdaten.router)


@app.get("/api/status")
def status() -> JSONResponse:
    """Betriebsbereitschaft. Bewusst ohne Anmeldung erreichbar.

    Gibt keine Inhalte preis - nur, ob die Bestandteile erreichbar sind.
    """
    e = einstellungen()
    pruefungen = {
        "datenbankverzeichnis": e.datenbank_pfad.parent.is_dir(),
        "konfiguration": e.konfiguration_verzeichnis.is_dir(),
        "exportverzeichnis": e.export_verzeichnis.is_dir(),
    }
    bereit = all(pruefungen.values())

    return JSONResponse(
        status_code=200 if bereit else 503,
        content={
            "status": "bereit" if bereit else "nicht bereit",
            "version": __version__,
            "pruefungen": pruefungen,
            "warnungen": e.warnungen(),
        },
    )

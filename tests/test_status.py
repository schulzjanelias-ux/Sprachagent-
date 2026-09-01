"""EPIC 00 · Fundament: Der Dienst startet und meldet seinen Zustand."""
from fastapi.testclient import TestClient

from app.main import app


def test_status_meldet_bereit():
    with TestClient(app) as klient:
        antwort = klient.get("/api/status")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["status"] == "bereit"
    assert all(daten["pruefungen"].values())


def test_api_dokumentation_ist_nicht_oeffentlich():
    """Die App ist oeffentlich erreichbar (D-10) - kein Schema nach aussen."""
    with TestClient(app) as klient:
        for pfad in ("/docs", "/redoc", "/openapi.json"):
            assert klient.get(pfad).status_code == 404, pfad


def test_unsicherer_schluessel_wird_gemeldet():
    """Der Vorgabeschluessel darf nicht stillschweigend akzeptiert werden."""
    from app.config import Einstellungen, UNSICHERER_SCHLUESSEL

    e = Einstellungen(sitzung_schluessel=UNSICHERER_SCHLUESSEL)
    assert e.schluessel_ist_unsicher
    assert any("SITZUNG_SCHLUESSEL" in w for w in e.warnungen())

    sicher = Einstellungen(sitzung_schluessel="x" * 48)
    assert not sicher.schluessel_ist_unsicher
    assert not any("SITZUNG_SCHLUESSEL" in w for w in sicher.warnungen())


def test_fehlendes_https_wird_gemeldet():
    from app.config import Einstellungen

    e = Einstellungen(sitzung_schluessel="x" * 48, https_aktiv=False)
    assert any("HTTPS_AKTIV" in w for w in e.warnungen())

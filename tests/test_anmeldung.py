"""EPIC 01 · Anmeldung (D-11).

Die App ist oeffentlich erreichbar (D-10). Geprueft wird deshalb nicht nur,
dass die Anmeldung funktioniert, sondern auch, dass sie **nichts verraet**:
weder ueber die Fehlermeldung noch ueber die Antwortzeit noch ueber frei
abrufbare Stammdaten.
"""
from __future__ import annotations

import time as zeitmodul
from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.datenbank import einrichten
from app.modelle import Mitarbeiter, Projekt, Rolle
from app.sicherheit import (
    SITZUNG_COOKIE, SPERRE_AB_VERSUCH, fehlversuche, passwort_bewerten,
    passwort_hashen, passwort_pruefen, sitzung_ausstellen, sitzung_lesen,
    sitzungs_kennung_erzeugen,
)

PASSWORT = "Baustelle2026xy"


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    monkeypatch.setenv("DATENBANK_PFAD", str(tmp_path / "auth.db"))
    monkeypatch.setenv("SITZUNG_SCHLUESSEL", "t" * 48)
    monkeypatch.setenv("HTTPS_AKTIV", "false")
    from app.config import einstellungen
    einstellungen.cache_clear()
    fehlversuche.leeren()
    yield
    einstellungen.cache_clear()
    fehlversuche.leeren()


@pytest.fixture
def klient(umgebung, tmp_path):
    from app.main import app

    maschine = einrichten(tmp_path / "auth.db")
    with sessionmaker(bind=maschine, future=True)() as offen:
        offen.add_all([
            Mitarbeiter(anmeldename="ahrens", anzeigename="M. Ahrens",
                        excel_name="Ahrens", passwort_hash=passwort_hashen(PASSWORT),
                        regelbeginn=time(7, 0),
                        sitzungs_kennung=sitzungs_kennung_erzeugen()),
            Mitarbeiter(anmeldename="chef", anzeigename="K. Böttger",
                        excel_name="Böttger", passwort_hash=passwort_hashen(PASSWORT),
                        rolle=Rolle.bauleiter,
                        sitzungs_kennung=sitzungs_kennung_erzeugen()),
            Mitarbeiter(anmeldename="ehemalig", anzeigename="Ausgeschieden",
                        excel_name="Cordes", passwort_hash=passwort_hashen(PASSWORT),
                        aktiv=False, sitzungs_kennung=sitzungs_kennung_erzeugen()),
            Projekt(name="Musterstraße 12", mappe_pfad="/tmp/m.xlsx"),
        ])
        offen.commit()

    with TestClient(app) as k:
        yield k


def anmelden(klient, name="ahrens", passwort=PASSWORT):
    return klient.post("/api/anmelden", json={"anmeldename": name, "passwort": passwort})


# --- Glueckspfad -----------------------------------------------------------

def test_anmeldung_setzt_sitzungscookie(klient):
    antwort = anmelden(klient)
    assert antwort.status_code == 200
    assert antwort.json()["anzeigename"] == "M. Ahrens"
    assert SITZUNG_COOKIE in klient.cookies


def test_anmeldename_ist_unabhaengig_von_der_schreibweise(klient):
    assert anmelden(klient, name="AHRENS").status_code == 200


def test_nach_anmeldung_sind_stammdaten_erreichbar(klient):
    anmelden(klient)
    assert klient.get("/api/ich").status_code == 200
    assert klient.get("/api/projekte").status_code == 200
    assert len(klient.get("/api/einheiten").json()) == 8


def test_abmelden_beendet_die_sitzung(klient):
    anmelden(klient)
    assert klient.post("/api/abmelden").status_code == 204
    assert klient.get("/api/ich").status_code == 401


# --- Was die Anmeldung nicht verraten darf --------------------------------

def test_stammdaten_ohne_anmeldung_gesperrt(klient):
    """Eine frei abrufbare Liste waere eine Veroeffentlichung der Belegschaft."""
    for pfad in ("/api/ich", "/api/projekte", "/api/einheiten"):
        assert klient.get(pfad).status_code == 401, pfad


def test_unbekanntes_konto_und_falsches_passwort_klingen_gleich(klient):
    unbekannt = anmelden(klient, name="gibtesnicht")
    falsch = anmelden(klient, passwort="falschfalsch")
    assert unbekannt.status_code == falsch.status_code == 401
    assert unbekannt.json()["detail"] == falsch.json()["detail"]
    assert "unbekannt" not in unbekannt.json()["detail"].lower()


def test_unbekanntes_konto_dauert_genauso_lange(klient):
    """Ohne Blindpruefung waere die Belegschaft an der Antwortzeit
    durchprobierbar."""
    def messen(name):
        beginn = zeitmodul.perf_counter()
        anmelden(klient, name=name, passwort="falschfalsch")
        return zeitmodul.perf_counter() - beginn

    vorhanden = min(messen("ahrens") for _ in range(3))
    unbekannt = min(messen("gibtesnicht") for _ in range(3))
    fehlversuche.leeren()
    # Argon2 dominiert beide Wege; der Unterschied darf nicht auswertbar sein.
    assert abs(vorhanden - unbekannt) < vorhanden * 0.6


def test_ausgeschiedener_mitarbeiter_kommt_nicht_hinein(klient):
    assert anmelden(klient, name="ehemalig").status_code == 401


# --- Ratenbegrenzung -------------------------------------------------------

def test_sperre_nach_zu_vielen_fehlversuchen(klient):
    for _ in range(SPERRE_AB_VERSUCH):
        anmelden(klient, passwort="falschfalsch")
    gesperrt = anmelden(klient, passwort="falschfalsch")
    assert gesperrt.status_code == 429
    assert "Minuten" in gesperrt.json()["detail"]
    # Auch das richtige Passwort hilft waehrend der Sperre nicht.
    assert anmelden(klient).status_code == 429


def test_erfolgreiche_anmeldung_setzt_den_zaehler_zurueck(klient):
    for _ in range(SPERRE_AB_VERSUCH - 2):
        anmelden(klient, passwort="falschfalsch")
    assert anmelden(klient).status_code == 200
    for _ in range(SPERRE_AB_VERSUCH - 2):
        anmelden(klient, passwort="falschfalsch")
    assert anmelden(klient).status_code == 200


# --- Sitzungscookie --------------------------------------------------------

def test_gefaelschtes_cookie_wird_abgewiesen(klient):
    anmelden(klient)
    klient.cookies.set(SITZUNG_COOKIE, "beliebiger.unsinn.hier")
    assert klient.get("/api/ich").status_code == 401


def test_cookie_eines_anderen_schluessels_gilt_nicht():
    from app.config import Einstellungen
    einer = Einstellungen(sitzung_schluessel="a" * 48)
    anderer = Einstellungen(sitzung_schluessel="b" * 48)
    keks = sitzung_ausstellen(1, "kennung", einer)
    assert sitzung_lesen(keks, einer) == (1, "kennung")
    assert sitzung_lesen(keks, anderer) is None


def test_cookie_traegt_schutzmerkmale(klient):
    antwort = anmelden(klient)
    kopfzeile = antwort.headers["set-cookie"].lower()
    assert "httponly" in kopfzeile
    assert "samesite=lax" in kopfzeile


# --- Passwortwechsel -------------------------------------------------------

def test_passwortwechsel_beendet_alte_sitzungen(klient):
    """Wer sein Passwort aendert, weil es kompromittiert war, will genau das."""
    anmelden(klient)
    altes_cookie = klient.cookies.get(SITZUNG_COOKIE)

    antwort = klient.post("/api/passwort", json={
        "altes_passwort": PASSWORT, "neues_passwort": "NeuesPasswort2026"})
    assert antwort.status_code == 204

    klient.cookies.set(SITZUNG_COOKIE, altes_cookie)
    assert klient.get("/api/ich").status_code == 401


def test_passwortwechsel_braucht_das_alte_passwort(klient):
    anmelden(klient)
    antwort = klient.post("/api/passwort", json={
        "altes_passwort": "falschfalsch", "neues_passwort": "NeuesPasswort2026"})
    assert antwort.status_code == 401


def test_zu_kurzes_passwort_wird_abgelehnt(klient):
    anmelden(klient)
    antwort = klient.post("/api/passwort", json={
        "altes_passwort": PASSWORT, "neues_passwort": "kurz"})
    assert antwort.status_code == 400
    assert "10 Zeichen" in antwort.json()["detail"]


def test_wechselpflicht_wird_gemeldet(klient, tmp_path):
    """Ein Einmalpasswort muss beim ersten Anmelden gewechselt werden."""
    maschine = einrichten(tmp_path / "auth.db")
    with sessionmaker(bind=maschine, future=True)() as offen:
        from sqlalchemy import select
        mitarbeiter = offen.scalar(
            select(Mitarbeiter).where(Mitarbeiter.anmeldename == "ahrens"))
        mitarbeiter.passwort_wechseln = True
        offen.commit()
    assert anmelden(klient).json()["passwort_wechseln"] is True


# --- Rollen ----------------------------------------------------------------

def test_rolle_wird_gemeldet(klient):
    assert anmelden(klient).json()["rolle"] == "mitarbeiter"
    klient.post("/api/abmelden")
    assert anmelden(klient, name="chef").json()["rolle"] == "bauleiter"


# --- Passwortbewertung -----------------------------------------------------

@pytest.mark.parametrize("passwort,taugt", [
    ("Baustelle2026xy", True),
    ("dies ist ein langer satz", True),      # keine Zeichenklassenpflicht
    ("kurz", False),
    ("neunzeich", False),
    (" Leerzeichen2026 ", False),
    ("passwort12", False),
])
def test_passwortbewertung(passwort, taugt):
    assert (passwort_bewerten(passwort) == []) is taugt


def test_hash_ist_argon2id_und_bei_gleichem_passwort_verschieden():
    einer, anderer = passwort_hashen(PASSWORT), passwort_hashen(PASSWORT)
    assert einer.startswith("$argon2id$")
    assert einer != anderer, "ohne Salz waeren gleiche Passwoerter erkennbar"
    assert passwort_pruefen(einer, PASSWORT) and passwort_pruefen(anderer, PASSWORT)

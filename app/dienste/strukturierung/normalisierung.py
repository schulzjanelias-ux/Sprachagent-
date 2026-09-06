"""Rohentwurf des Modells -> geprueften Entwurf.

Hier passiert alles, was das Sprachmodell nicht tun darf: Datum aufloesen,
Einheiten normalisieren, deutsche Zahlen lesen, Gewerke gegen die Liste
pruefen. Vollstaendig deterministisch und ohne API-Aufruf testbar.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.dienste.datum import aufloesen, nachmittag_korrigieren, uhrzeit_aufloesen
from app.dienste.einheiten import normalisieren as einheit_normalisieren
from app.dienste.mengen import parsen as menge_parsen
from app.dienste.strukturierung.basis import (
    Entwurf, EntwurfLeistung, Kontext, Rohentwurf,
)


def normalisieren(roh: Rohentwurf, kontext: Kontext, transkript: str) -> Entwurf:
    unklarheiten = list(roh.unklarheiten)

    # --- Datum ------------------------------------------------------------
    datum = aufloesen(roh.datum_wortlaut, kontext.heute)
    datum_abgeleitet = roh.datum_wortlaut is None
    if datum is None:
        unklarheiten.append(
            f"Die Datumsangabe {roh.datum_wortlaut!r} war nicht eindeutig. "
            f"Es gilt vorlaeufig der Erfassungstag.")
        datum, datum_abgeleitet = kontext.heute, True
    elif datum > kontext.heute:
        unklarheiten.append(
            f"Das erkannte Datum {datum:%d.%m.%Y} liegt in der Zukunft. "
            f"Es gilt vorlaeufig der Erfassungstag.")
        datum, datum_abgeleitet = kontext.heute, True

    # --- Gewerk -----------------------------------------------------------
    gewerk = roh.gewerk
    if gewerk and gewerk not in kontext.gewerke:
        # Kein Fuzzy-Matching: ein abweichender Name faellt in der Mappe
        # lautlos aus der Auswertung (D-05).
        unklarheiten.append(
            f"Das Gewerk {gewerk!r} steht nicht in der Liste des Betriebs.")
        gewerk = None

    # --- Leistungen -------------------------------------------------------
    leistungen = []
    for position in roh.leistungen:
        menge = menge_parsen(position.menge_wortlaut)
        einheit = einheit_normalisieren(position.einheit_wortlaut)

        if position.menge_wortlaut and menge is None:
            unklarheiten.append(
                f"Bei {position.taetigkeit!r} war die Menge "
                f"{position.menge_wortlaut!r} nicht als Zahl lesbar.")
        if position.einheit_wortlaut and einheit is None:
            unklarheiten.append(
                f"Bei {position.taetigkeit!r} ist {position.einheit_wortlaut!r} "
                f"keine bekannte Einheit.")

        leistungen.append(EntwurfLeistung(
            taetigkeit=position.taetigkeit.strip(),
            beschreibung=position.beschreibung,
            menge=menge.wert if menge else None,
            einheit=einheit,
            geschaetzt=menge.geschaetzt if menge else False,
            konfidenz=position.konfidenz,
            menge_wortlaut=position.menge_wortlaut,
            einheit_wortlaut=position.einheit_wortlaut,
        ))

    # --- Arbeitszeit (D-03) ----------------------------------------------
    beginn = uhrzeit_aufloesen(roh.arbeitszeit.beginn_wortlaut)
    ende = uhrzeit_aufloesen(roh.arbeitszeit.ende_wortlaut)
    ende, _ = nachmittag_korrigieren(beginn, ende)
    zeit_abgeleitet = False

    if beginn is None and ende is None and roh.arbeitszeit.dauer_wortlaut:
        # Nur eine Dauer genannt. Die Mappe rechnet aber aus Anfang und Ende
        # (D-03) - also mit dem Regelbeginn ergaenzen und **sichtbar** als
        # abgeleitet markieren, damit der Mitarbeiter es korrigieren kann.
        dauer = menge_parsen(roh.arbeitszeit.dauer_wortlaut)
        if dauer and kontext.regelbeginn:
            beginn = kontext.regelbeginn
            ende = _zeit_plus_stunden(beginn, float(dauer.wert))
            zeit_abgeleitet = True
            unklarheiten.append(
                f"Es wurde nur eine Dauer genannt ({roh.arbeitszeit.dauer_wortlaut}). "
                f"Angenommen: {beginn:%H:%M} bis {ende:%H:%M}. Bitte pruefen.")
        elif dauer:
            unklarheiten.append(
                f"Es wurde nur eine Dauer genannt ({roh.arbeitszeit.dauer_wortlaut}). "
                f"Fuer die Zeiterfassung werden Anfang und Ende gebraucht.")

    return Entwurf(
        datum=datum, transkript=transkript, gewerk=gewerk, leistungen=leistungen,
        beginn=beginn, ende=ende, bemerkung=roh.bemerkung,
        unklarheiten=unklarheiten, datum_abgeleitet=datum_abgeleitet,
        zeit_abgeleitet=zeit_abgeleitet,
        dauer_wortlaut=roh.arbeitszeit.dauer_wortlaut)


def _zeit_plus_stunden(beginn: time, stunden: float) -> time:
    gerechnet = datetime.combine(date(2000, 1, 1), beginn) + timedelta(hours=stunden)
    return gerechnet.time()

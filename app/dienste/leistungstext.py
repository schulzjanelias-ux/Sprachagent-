"""Serialisierung der Leistungspositionen fuer Spalte I (D-02, Variante A).

Die Mappe hat genau ein Freitextfeld je Tag - ueber den Zehnerblock verbunden -
und keine Spalte fuer Menge und Einheit. Damit die Angaben trotzdem nicht
verlorengehen, werden sie in ein festes, wieder einlesbares Format gebracht:

    Spachtelarbeiten 65 m²; Schleifarbeiten 40 m²; Türen grundieren 8 Stück

Der massgebliche strukturierte Export bleibt XLSX/CSV (Briefing §14). Spalte I
ist die menschenlesbare Beigabe, nicht die Datenquelle.
"""
from __future__ import annotations

from decimal import Decimal

from app.dienste.berichte import Leistung

TRENNER = "; "
LAENGE_MAX = 900          # Spalte I ist 52 Zeichen breit, umbricht aber


def menge_deutsch(menge: Decimal) -> str:
    """Dezimalkomma, kein Tausenderpunkt, keine ueberfluessigen Nullen.

        Decimal("65")    -> "65"
        Decimal("12.5")  -> "12,5"
        Decimal("12.50") -> "12,5"
    """
    normalisiert = menge.normalize()
    # normalize() macht aus 100 die Exponentialform 1E+2 - das zurueckdrehen
    if normalisiert == normalisiert.to_integral_value():
        normalisiert = normalisiert.quantize(Decimal(1))
    return f"{normalisiert:f}".replace(".", ",")


def position_als_text(leistung: Leistung) -> str:
    teile = [leistung.taetigkeit.strip()]
    if leistung.menge is not None:
        teile.append(menge_deutsch(leistung.menge))
        if leistung.einheit:
            teile.append(leistung.einheit)
    return " ".join(teile)


def serialisieren(leistungen: list[Leistung] | tuple[Leistung, ...],
                  bericht_id: str | None = None) -> str:
    """Alle Positionen eines Tages zu einem Zellinhalt zusammenfuehren.

    Zeilenumbrueche werden zu Trennern normalisiert: Spalte I hat zwar
    Zeilenumbruch aktiviert, Umbrueche erschweren aber das Wiedereinlesen.
    """
    stuecke = []
    for leistung in leistungen:
        text = position_als_text(leistung)
        if text:
            stuecke.append(" ".join(text.split()))     # \n, \t, Mehrfachleerzeichen

    if not stuecke:
        return ""

    text = TRENNER.join(stuecke)
    if len(text) <= LAENGE_MAX:
        return text

    # Kuerzen an einer Positionsgrenze, nicht mitten im Wort. Der vollstaendige
    # Datensatz steht im strukturierten Export - hier bleibt der Verweis.
    hinweis = f" … vollstaendig in Bericht {bericht_id}" if bericht_id else " …"
    grenze = LAENGE_MAX - len(hinweis)
    gekuerzt = text[:grenze]
    if TRENNER in gekuerzt:
        gekuerzt = gekuerzt[:gekuerzt.rfind(TRENNER)]
    return gekuerzt + hinweis

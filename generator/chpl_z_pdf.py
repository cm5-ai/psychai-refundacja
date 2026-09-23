#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EKSTRAKTOR PUNKTOW ChPL Z ORYGINALNEGO PDF - 2026-09-23.

DLACZEGO NOWY. Stary wyciag (chpl_cache.py) kotwiczyl sie na KAZDYM wystapieniu
"4.3." po ktorym stala wielka litera. Odsylacz w srodku zdania ("patrz punkt
4.5.") i podnumeracja ("4.4. Niewydolnosc nerek") wygladaly dla niego jak
naglowek sekcji. Skutek: 42 punkty niosly tresc innego punktu, 221 bylo
urwanych, a ekstrakcja zglaszala zero bledow.

CO SIE ZMIENIA. Naglowek sekcji ChPL ma trzy wlasciwosci naraz, i dopiero
wszystkie trzy razem go identyfikuja:
  1. stoi na POCZATKU LINII (odsylacz stoi w srodku zdania),
  2. po numerze stoi SLOWO NAGLOWKOWE ustalone prawem,
  3. numery rosna monotonicznie w dokumencie.
Stary kod sprawdzal tylko "po numerze stoi wielka litera".

ZRODLO: oryginalny PDF z rejestru, pobrany przez przegladarke lekarza
(runtime ma 403 z proxy). Tekst z pdftotext -layout.
"""
import re, subprocess, sys, os, json

SLOWA = {
    "4.1": ["wskazania do stosowania"],
    "4.2": ["dawkowanie i sposób podawania"],
    "4.3": ["przeciwwskazania"],
    "4.4": ["specjalne ostrzeżenia i środki ostrożności",
            "ostrzeżenia specjalne i środki ostrożności"],
    "4.5": ["interakcje z innymi produktami leczniczymi",
            "interakcje z innymi lekami"],
    # Warianty redakcyjne 4.6 wykryte na 187 etykietach 2026-09-23. Kolejnosc
    # slow rozni sie miedzy producentami; dopasowanie po PIERWSZYCH 18 znakach
    # wymaga wiec osobnego wariantu dla kazdej kolejnosci.
    "4.6": ["wpływ na płodność, ciążę i laktację",
            "wpływ na płodność, ciążę i karmienie",
            "wpływ na ciążę i laktację",
            "ciąża, karmienie piersią i wpływ na płodność",
            "płodność, ciąża i laktacja",
            "ciąża i laktacja", "ciąża i karmienie piersią"],
    "4.7": ["wpływ na zdolność prowadzenia pojazdów"],
    "4.8": ["działania niepożądane"],
    "4.9": ["przedawkowanie"],
    "5.1": ["właściwości farmakodynamiczne"],
    "5.2": ["właściwości farmakokinetyczne"],
    "5.3": ["przedkliniczne dane o bezpieczeństwie"],
    "6.1": ["wykaz substancji pomocniczych"],
}
CHCE = ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.8", "5.2"]

SMIECI = (re.compile(r"^\s*Strona\s+\d+\s+z\s+\d+\s*$"),
          re.compile(r"^\s*\d+\s*$"),
          re.compile(r"^\s*\d+\s*/\s*\d+\s*$"))


def tekst_z_pdf(sciezka):
    r = subprocess.run(["pdftotext", "-layout", sciezka, "-"],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("pdftotext kod %d: %s" % (r.returncode, r.stderr[:200]))
    return r.stdout.decode("utf-8", "replace")


def kotwice(t):
    """Naglowki sekcji: poczatek linii + numer + slowo naglowkowe.

    Zwraca [(numer, pozycja_startu, pozycja_konca_naglowka)] w kolejnosci
    wystapienia. NIE zwraca odsylaczy - te stoja w srodku linii.
    """
    out = []
    # \f = wysuw strony. Naglowek stojacy tuz po lamaniu strony jest nim
    # poprzedzony i wzorzec bez \f po prostu go NIE WIDZI. Tak przepadly
    # 4.4 i 4.8 fluoksetyny oraz 4.3 walproinianu w pierwszym tescie.
    for m in re.finditer(r"^[ \t\f\xa0]*([456]\.\d{1,2})\.?[ \t\xa0]+(\S[^\n]{0,80})",
                         t, re.M):
        nr, ogon = m.group(1), m.group(2).lower()
        # ODSYLACZ CYTUJACY PELNY TYTUL. W czesci etykiet odsylacz brzmi
        # "(patrz punkt 4.4 Ostrzezenia specjalne ... )" i przy zawijaniu
        # wiersza jego druga czesc laduje na POCZATKU LINII - wyglada wtedy
        # dokladnie jak naglowek. Roznica jest deterministyczna: prawdziwy
        # naglowek to SAM TYTUL, odsylacz ciagnie za soba nawias zamykajacy
        # albo dalszy ciag zdania.
        if ")" in ogon or ogon.rstrip().endswith((":", ";", ",")):
            continue
        for s in SLOWA.get(nr, []):
            if ogon.startswith(s[:18]):
                out.append((nr, m.start(), m.end(1)))
                break
    return out


def czysc(s):
    linie = [l for l in s.splitlines()
             if not any(w.match(l) for w in SMIECI)]
    return " ".join(" ".join(linie).split())


def punkty(sciezka):
    """Zwraca (punkty, diagnostyka). Punkt konczy sie na NASTEPNEJ kotwicy."""
    t = tekst_z_pdf(sciezka)
    k = kotwice(t)
    # ChPL ma spis tresci na poczatku - ten sam numer pojawia sie dwa razy.
    # Bierzemy OSTATNIE wystapienie kazdego numeru przed kolejnym wiekszym:
    # spis tresci ma sekcje puste, wlasciwa sekcja ma tresc.
    wynik, diag = {}, {"kotwic": len(k), "duplikaty": []}
    for i, (nr, start, _) in enumerate(k):
        koniec = k[i + 1][1] if i + 1 < len(k) else len(t)
        tresc = czysc(t[start:koniec])
        if nr not in CHCE:
            continue
        if nr in wynik:
            diag["duplikaty"].append(nr)
            if len(tresc) <= len(wynik[nr]):
                continue
        wynik[nr] = tresc
    diag["brak"] = sorted(set(CHCE) - set(wynik))
    return wynik, diag


if __name__ == "__main__":
    p, d = punkty(sys.argv[1])
    print(json.dumps({"dlugosci": {k: len(v) for k, v in sorted(p.items())},
                      "diag": d}, ensure_ascii=False, indent=1))
    if len(sys.argv) > 2:
        print("\n--- %s ---\n%s" % (sys.argv[2], p.get(sys.argv[2], "BRAK")[:1500]))

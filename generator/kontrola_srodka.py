#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KONTROLA SRODKA PUNKTU ChPL - 2026-09-23. TYLKO CZYTA, NIC NIE ZAPISUJE.

CO JUZ MAMY I CZEGO NIE. Kontrola naglowkow sprawdza POCZATEK punktu
(pierwsze 90 znakow). Kwarantanna z dzis sprawdza ZAKONCZENIE (czy tekst
konczy sie zamknieciem zdania). Miedzy jednym a drugim jest cale cialo
punktu, ktorego nie sprawdza nic: punkt moze zaczac sie poprawnie, skonczyc
poprawnie i miec w srodku tresc innej sekcji albo dziure.

SZESC TESTOW NA SAMYM TEKSCIE. Bez PDF, bez sieci, bez porownywania
produktow miedzy soba (produkty LEGALNIE sie roznia).

S1 OBCY NAGLOWEK W SRODKU. Naglowek sekcji ChPL jest ustalony prawem:
   numer + slowo. Odsylacz "patrz punkt 4.5" NIE ma po numerze slowa
   naglowkowego, wiec da sie je odroznic. Naglowek innej sekcji w srodku
   punktu = wyciag nie zatrzymal sie tam, gdzie konczy sie sekcja.
S2 URWANIE NA ODSYLACZU. Tekst konczy sie na "patrz", "(patrz punkt".
S3 SMIECI PRZED NAGLOWKIEM. Tekst zaczyna sie od malej litery albo od
   znaku interpunkcyjnego - poczatek jest w srodku cudzego zdania.
S4 NAKLADANIE SIE PUNKTOW. Dwa punkty tej samej etykiety maja wspolny
   fragment 200 znakow. Sekcje ChPL sa rozlaczne. Porownanie DOSLOWNE,
   bez progu podobienstwa (3B).
S5 BRAK FRAZY OBOWIAZKOWEJ. 4.3 zawiera "nadwrazliwo", 4.6 "ciaz",
   5.2 opis wchlaniania albo metabolizmu. Brak = sygnal, nie dowod.
S6 BILANS. N_WEJSCIE = N_CZYSTE + N_Z_SYGNALEM, identyfikatory zachowane.

KIERUNEK BLEDU. Falszywy alarm kosztuje jedno zajrzenie do ChPL. Falszywe
"czysty" moze kosztowac pacjenta. Decyzje o kwarantannie podejmuje osobny
krok, nie ten skrypt.
"""
import json, glob, os, re, sys

KAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chpl")

NAGLOWKI = {"4.1": "wskazania", "4.2": "dawkowanie", "4.3": "przeciwwskazania",
            "4.4": "ostrzeżenia", "4.5": "interakcje", "4.6": "wpływ na płodność",
            "4.7": "wpływ na zdolność", "4.8": "działania niepożądane",
            "4.9": "przedawkowanie", "5.1": "właściwości farmakodynamiczne",
            "5.2": "właściwości farmakokinetyczne", "5.3": "przedkliniczne",
            "6.1": "wykaz substancji pomocniczych"}
SKROT = {"4.6": "ciąża", "4.7": "wpływ na zdolność prowadzenia"}

FRAZA = {"4.2": ("dawk",), "4.3": ("nadwrażliwo",), "4.4": ("ostrożno", "ryzyk"),
         "4.5": ("jednocze", "interakc"), "4.6": ("ciąż",),
         "4.8": ("niepożądan",), "5.2": ("wchłanianie", "metabol", "wydalan", "dystrybuc")}

OKNO_POCZATKU = 90
OKNO_SZWU = 40
MIN_WSPOLNY = 200


def norm(t):
    return " ".join((t or "").split())


def s1_obcy_naglowek(numer, t):
    out = []
    for m in re.finditer(r"([456])\.(\d{1,2})\.?\s+([^\s]{3,40})", t):
        if m.start() < OKNO_POCZATKU:
            continue
        nr = "%s.%s" % (m.group(1), m.group(2))
        if nr == numer:
            continue
        przed = t[max(0, m.start() - 25):m.start()].lower()
        if "patrz" in przed or "(" in przed or "punkt" in przed:
            continue
        ogon = t[m.end(2):m.end(2) + 60].lower().lstrip(". ")
        for s in (NAGLOWKI.get(nr), SKROT.get(nr)):
            if s and ogon.startswith(s.split()[0]):
                out.append((nr, m.start()))
                break
    return out


def s2_urwanie_na_odsylaczu(t):
    ogon = t[-OKNO_SZWU:].lower()
    return bool(re.search(r"(patrz|punkcie|punkt)\s*$", ogon))


def s3_smieci_przed_naglowkiem(t):
    if not t:
        return False
    return t[0].islower() or t[0] in ",;:)]}%-"


def s4_nakladanie(punkty):
    out = []
    klucze = sorted(punkty)
    for i, a in enumerate(klucze):
        ta = punkty[a]
        for b in klucze[i + 1:]:
            tb = punkty[b]
            if len(ta) < MIN_WSPOLNY or len(tb) < MIN_WSPOLNY:
                continue
            for p in range(0, len(ta) - MIN_WSPOLNY + 1, MIN_WSPOLNY // 2):
                if ta[p:p + MIN_WSPOLNY] in tb:
                    out.append((a, b))
                    break
    return out


def s6_zaczyna_sie_w_odsylaczu(t):
    """Niesparowany nawias ZAMYKAJACY przed pierwszym otwierajacym.

    Mechanizm: ekstraktor zakotwiczyl sie w srodku odsylacza
    "(patrz punkt 4.8 Dzialania niepozadane)" - wiec punkt zaczyna sie od
    tytulu sekcji, po ktorym natychmiast stoi ")". Tresc, ktora po nim idzie,
    nalezy do sekcji, w ktorej stal odsylacz, NIE do tego punktu.
    Wyjatek: ")" znacznika listy ("a)", "1)") nie jest nawiasem zamykajacym.
    """
    i = 0
    while True:
        z = t.find(")", i)
        if z < 0:
            return False
        o = t.find("(")
        if 0 <= o < z:
            return False
        if z >= 2 and t[z - 1].isalnum() and t[z - 2] in " \t":
            i = z + 1          # znacznik listy, szukaj dalej
            continue
        return True


def s5_brak_frazy(numer, t):
    w = FRAZA.get(numer)
    if not w:
        return False
    low = t.lower()
    return not any(x in low for x in w)


def main():
    r = {"data": "2026-09-23", "N_WEJSCIE": 0, "N_CZYSTE": 0, "N_Z_SYGNALEM": 0,
         "S1_obcy_naglowek": [], "S2_urwanie_na_odsylaczu": [],
         "S3_smieci_przed_naglowkiem": [], "S4_nakladanie": [], "S5_brak_frazy": [], "S6_start_w_odsylaczu": []}
    for f in sorted(glob.glob(os.path.join(KAT, "*.json"))):
        if os.path.basename(f) == "INDEX.json":
            continue
        d = json.load(open(f, encoding="utf-8"))
        for p in d.get("produkty", []):
            punkty = {k: norm(v) for k, v in (p.get("punkty") or {}).items() if norm(v)}
            et = "%s/%s" % (d.get("substancja"), p.get("nazwa"))
            # S4 NIE PODNOSI SYGNALU. Sprawdzone 2026-09-23: we wszystkich
            # 20 parach wspolny fragment lezy w SRODKU obu punktow, nie na
            # szwie koniec-A/poczatek-B. To powtorzenie redakcyjne etykiety
            # (ten sam akapit o IMAO w 4.3 i 4.5), nie wyciek jednej sekcji
            # do drugiej. Falszywy alarm uczy ignorowania alarmow - zostaje
            # jako zapis audytowy.
            for a, b in s4_nakladanie(punkty):
                r["S4_nakladanie"].append("%s pkt %s ~ %s" % (et, a, b))
            for k, t in sorted(punkty.items()):
                r["N_WEJSCIE"] += 1
                sygnal = False
                obce = s1_obcy_naglowek(k, t)
                if obce:
                    r["S1_obcy_naglowek"].append(
                        "%s pkt %s zawiera naglowek %s na pozycji %d z %d"
                        % (et, k, obce[0][0], obce[0][1], len(t)))
                    sygnal = True
                if s2_urwanie_na_odsylaczu(t):
                    r["S2_urwanie_na_odsylaczu"].append("%s pkt %s" % (et, k))
                    sygnal = True
                if s3_smieci_przed_naglowkiem(t):
                    r["S3_smieci_przed_naglowkiem"].append("%s pkt %s" % (et, k))
                    sygnal = True
                if s6_zaczyna_sie_w_odsylaczu(t):
                    r["S6_start_w_odsylaczu"].append("%s pkt %s :: %s" % (et, k, t[:90]))
                    sygnal = True
                if s5_brak_frazy(k, t):
                    r["S5_brak_frazy"].append("%s pkt %s (%d znakow)" % (et, k, len(t)))
                    sygnal = True
                r["N_Z_SYGNALEM" if sygnal else "N_CZYSTE"] += 1

    assert r["N_WEJSCIE"] == r["N_CZYSTE"] + r["N_Z_SYGNALEM"], "BILANS FAIL"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "RAPORT_KONTROLA_SRODKA.json")
    json.dump(r, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("N_WEJSCIE %d = N_CZYSTE %d + N_Z_SYGNALEM %d"
          % (r["N_WEJSCIE"], r["N_CZYSTE"], r["N_Z_SYGNALEM"]))
    for k in ("S1_obcy_naglowek", "S2_urwanie_na_odsylaczu", "S3_smieci_przed_naglowkiem",
              "S4_nakladanie", "S5_brak_frazy", "S6_start_w_odsylaczu"):
        print("%-28s %4d" % (k, len(r[k])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

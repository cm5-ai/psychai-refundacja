#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REPLAY — sedzia puszczony na zapisanych tekstach, bez modelu i bez kosztu.

PO CO. Sedzia zestawu blokujacego zmienial sie 2026-09-25 szesc razy w ciagu
dnia. Kazda zmiana mogla naprawic jeden falszywy alarm i zrobic drugi.
Bez zapisanych tekstow sprawdzenie tego kosztuje lekarza kolejny wieczor
przy modelu; z nimi kosztuje sekundy.

DWA ZRODLA, LICZONE OSOBNO — I TO JEST ISTOTA, NIE PORZADKI:
  odpowiedzi/  SUROWE odpowiedzi modelu, wklejone z okien. Mowia, jak model
               sie zachowal.
  fikstury/    teksty ulozone recznie, z gory znanym werdyktem. Mowia, czy
               sedzia umie rozroznic. Zaden nie wyszedl z modelu.
Zsumowanie ich dalo by mianownik, ktory klamie w obie strony.

CZEGO NIE MIERZY. Zachowania modelu DZISIAJ. Kazdy tekst jest z przeszlosci
albo z reki czlowieka. Zielony replay znaczy: sedzia na tych tekstach mowi
to, co ma mowic. Nie znaczy, ze model je wyprodukuje.

DLACZEGO NIE STOI JESZCZE W BRAMCE PRZED PCHNIECIEM [2026-09-25].
Piec z dziewieciu zapisanych odpowiedzi rozjezdza sie z sedzia i wszystkie
piec naleza do JEDNEJ rodziny: krotka zada, zeby w odpowiedzi PADL WIDOCZNY
PIN albo nazwa pola. Warstwa 40 par. 3 w rewizji z 2026-09-24 mowi coś
przeciwnego: "Adresu pola NIE pokazujesz przy wizycie (...) MILCZENIE
ZNACZY: wartosc z karty". To nie jest blad kodu — to sprzecznosc miedzy
plikami, a par. 4 warstwy 40 zabrania rozstrzygac ja wlasnym domyslem.
Do czasu rozstrzygniecia replay JEST POMIAREM, nie bramka: wchodzi do
bramki dopiero, gdy ta rodzina ma jeden wynik. Zielona bramka z wylaczona
rodzina bylaby gorsza niz brak bramki.

GRANICA WZROSTU [Grok, R13]. Korpus rosnacy przez dopisywanie przebiegow,
ktore "juz raz bolaly", staje sie pamiecia awarii sedziego i zaczyna klamac
tak samo jak katalog mutacji. Fikstura wchodzi razem z KROTKA albo
z nazwanym defektem sedziego, nigdy "bo akurat mamy tekst".
"""
import io, os, re, sys

KAT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KAT)
import json
import bramka_wydania as BW

NAZWA = re.compile(r"_([A-Z0-9-]+)_(PASS|FAIL)\.txt$")


def wczytaj(kat):
    out = []
    sciezka = os.path.join(KAT, kat)
    if not os.path.isdir(sciezka):
        return out
    for n in sorted(os.listdir(sciezka)):
        if not n.endswith(".txt") or n == "README.txt":
            continue
        m = NAZWA.search(n)
        naglowek = None
        linie = []
        for l in io.open(os.path.join(sciezka, n), encoding="utf-8"):
            if l.startswith("#"):
                naglowek = naglowek or l
                continue
            linie.append(l)
        tekst = "".join(linie).strip()
        if m:
            ident, werdykt = m.group(1), m.group(2)
        else:
            # Stary uklad: pierwsza linia '# <ID> <PASS|FAIL> — powod'.
            mm = re.match(r"#\s*(\S+)\s+(PASS|FAIL)\b", naglowek or "")
            if not mm:
                out.append((n, None, None, tekst,
                            "NAZWA ANI NAGLOWEK NIE MOWIA, KTORA KROTKA I JAKI WERDYKT"))
                continue
            ident, werdykt = mm.group(1), mm.group(2)
        out.append((n, ident, werdykt, tekst, None))
    return out


def main():
    zestaw = json.load(io.open(os.path.join(KAT, "zestaw_blokujacy.json"),
                               encoding="utf-8"))
    W = {v["id"]: v for v in zestaw["WINIETY"]}

    print("=" * 70)
    print("REPLAY SEDZIEGO — zapisane teksty, zero modelu")
    print("=" * 70)

    kod = 0
    for kat, opis in (("fikstury", "teksty reczne, znany werdykt"),
                      ("odpowiedzi", "surowe odpowiedzi modelu")):
        poz = wczytaj(kat)
        print()
        print("%s/ — %s   N_WEJSCIE %d" % (kat, opis, len(poz)))
        if not poz:
            print("  FAIL: ZERO POZYCJI. Zero tekstow to zero wiedzy, nie zielone.")
            kod = 1
            continue
        zgodne = rozjazd = nieczytelne = 0
        for nazwa, ident, ocz, tekst, blad in poz:
            if blad:
                print("  ?      %-42s %s" % (nazwa[:42], blad))
                nieczytelne += 1
                continue
            v = W.get(ident)
            if v is None:
                print("  ?      %-42s krotki %s nie ma w zestawie" % (nazwa[:42], ident))
                nieczytelne += 1
                continue
            naruszenia = BW.twarde(v, tekst)
            dzis = "FAIL" if naruszenia else "PASS"
            if dzis == ocz:
                zgodne += 1
                print("  ok     %-42s %-5s" % (nazwa[:42], dzis))
            else:
                rozjazd += 1
                kod = 1
                print("  ROZJAZD %-41s oczekiwane %s, sedzia %s   %s"
                      % (nazwa[:41], ocz, dzis,
                         "; ".join(naruszenia)[:60] if naruszenia else "brak naruszen"))
        print("  BILANS: N_WEJSCIE %d = zgodne %d + rozjazdy %d + nieczytelne %d"
              % (len(poz), zgodne, rozjazd, nieczytelne))
        if nieczytelne:
            kod = 1

    print()
    print("CZEGO TO NIE DOWODZI: ze model odpowie tak samo jutro. Dowodzi,")
    print("ze sedzia na TYCH tekstach mowi to, co ma mowic.")
    return kod


if __name__ == "__main__":
    sys.exit(main())

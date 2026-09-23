#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POKRYCIE LISTY SUBSTANCJI PRZEZ SPIS RPL.

PO CO. Spis RPL powstaje przez filtr po prefiksach ATC. Lista substancji, ktore
paczka ma obslugiwac, mieszka w INNYM PLIKU. Te dwie listy nigdy sie nie
spotykaly, wiec nikt nie sprawdzil, czy filtr w ogole przepuszcza to, czego
potrzebujemy. 2026-09-23 okazalo sie, ze nie przepuszcza: prefiksy nie
obejmuja N04 ani C07, a na liscie sa biperyden, triheksyfenidyl, amantadyna
i propranolol.

Filtr, ktory odrzuca dane, musi sie rozliczyc (3B). Ten skrypt jest tym
rozliczeniem po stronie ODBIORCY filtra: nie pyta, ile pozycji odpadlo,
tylko czy zostalo to, po co filtr byl robiony.

CZEGO TEN SKRYPT NIE ORZEKA. "Nie znalazlem" to nie "nie ma". Substancja bez
pokrycia moze byc (a) niezarejestrowana w PL, (b) poza filtrem ATC. To sa dwa
rozne stany i rozroznia je CZLOWIEK, nie ten skrypt. Bez tego rozroznienia
brak etykiety wyglada jak brak leku.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polityka

polityka.sprawdz_semantyke("CHPL_LAYER", "WSKAZANIE", "DETERMINISTYCZNY",
                           ("nazwa_powszechna", "atc"))

ROZSTRZYGNIECIA = "generator/pokrycie_rozstrzygniecia.json"


def main():
    spis = json.load(open(sys.argv[1], encoding="utf-8"))
    meta = spis.get("metadata", {})
    lista = [l.strip() for l in open(sys.argv[2], encoding="utf-8")
             if l.strip() and not l.startswith("#")]
    # POKRYCIE LICZONE Z FAKTYCZNEGO WYNIKU, nie z podobienstwa nazw.
    # Pierwsza wersja tego skryptu porownywala polska nazwe z lacinska po
    # pierwszych znakach i zglosila 39 brakow, z ktorych wiekszosc miala
    # etykiete w cache. Kontrola mylaca sie 39 razy zostaje zignorowana,
    # czyli nie zatrzymuje niczego - to ten sam blad, przed ktorym stoi.
    # Substancja jest POKRYTA wtedy i tylko wtedy, gdy cache ma dla niej
    # co najmniej jeden produkt. Zero zalozen o nazwach.
    indeks = {}
    if os.path.exists(sys.argv[3]):
        indeks = json.load(open(sys.argv[3], encoding="utf-8")).get("substancje", {})
    znane = {}
    if os.path.exists(ROZSTRZYGNIECIA):
        znane = json.load(open(ROZSTRZYGNIECIA, encoding="utf-8"))
    prefiksy = tuple(meta.get("atc_prefiksy") or ())

    pokryte, niepokryte = [], []
    for s in lista:
        (pokryte if (indeks.get(s) or {}).get("produkty") else niepokryte).append(s)

    # DANE KONTRA KOD. Metadane spisu zapisuja prefiksy uzyte PRZY JEGO BUDOWIE.
    # Kod moze byc od tego czasu poprawiony, a spis nie przebudowany - i wtedy
    # lek wpisany do filtra nadal nie istnieje w danych. Tak wlasnie 2026-09-23
    # biperyden, triheksyfenidyl, amantadyna i propranolol byly "dodane" w
    # kodzie (N04AA, N04BB, C07AA05) i nieobecne w spisie. Porownanie jest
    # deterministyczne: rownosc zbiorow, nie ocena.
    w_kodzie = ()
    try:
        import spis_rpl
        w_kodzie = tuple(spis_rpl.ATC_PREFIX)
    except Exception as e:
        print("UWAGA: nie da sie odczytac ATC_PREFIX z spis_rpl.py (%s)" % e)
    if w_kodzie and set(w_kodzie) != set(prefiksy):
        brak = sorted(set(w_kodzie) - set(prefiksy))
        nad = sorted(set(prefiksy) - set(w_kodzie))
        print("SPIS NIEAKTUALNY WOBEC KODU.")
        if brak:
            print("  w kodzie, brak w spisie: %s" % ", ".join(brak))
            print("  -> leki z tych grup NIE MOGA sie znalezc, dopoki spis nie")
            print("     zostanie przebudowany ze zrodlowego CSV.")
        if nad:
            print("  w spisie, brak w kodzie: %s" % ", ".join(nad))
        print()
    print("PREFIKSY ATC FILTRA (wg metadanych spisu): %s" % ", ".join(prefiksy))
    print("SUBSTANCJI NA LISCIE: %d" % len(lista))
    print("  pokrytych spisem:   %d" % len(pokryte))
    print("  bez pokrycia:       %d" % len(niepokryte))
    print("BILANS: %d + %d = %d" % (len(pokryte), len(niepokryte), len(lista)))
    assert len(pokryte) + len(niepokryte) == len(lista), "BILANS POKRYCIA"

    if niepokryte:
        print("\nBEZ POKRYCIA - kazda pozycja wymaga rozstrzygniecia czlowieka:")
        for s in niepokryte:
            r = znane.get(s) or {}
            print("  %-18s %s" % (s, r.get("stan", "NIEROZSTRZYGNIETE "
                  "- czy niezarejestrowany w PL, czy poza filtrem ATC?")))
    nieroz = [s for s in niepokryte if (znane.get(s) or {}).get("stan") is None]
    if nieroz:
        print("\nNIEROZSTRZYGNIETYCH: %d. Dopoki trwaja, brak etykiety dla tych "
              "lekow wyglada w karcie jak brak leku." % len(nieroz))
    return 1 if nieroz else 0


if __name__ == "__main__":
    raise SystemExit(main())

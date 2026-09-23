#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KWARANTANNA CACHE ChPL - 2026-09-23.

PO CO. Ekstraktor kotwiczyl sie na numerze punktu wystepujacym WEWNATRZ tekstu
(odsylacz "patrz punkt 4.5.", podnumeracja "4.4. Niewydolnosc nerek") zamiast na
naglowku sekcji. Skutek: czesc punktow niesie tresc INNEGO punktu, czesc jest
urwana w polowie zdania. Ekstrakcja zglaszala zero uciec i zero brakow.
Przebudowa cache jest dzis niemozliwa - rejestr nieosiagalny (403 z proxy).

CO ROBI TEN SKRYPT. Przenosi znane zle punkty POZA aktywne pole "punkty", do
pol, dla ktorych modul 19 MA JUZ zdefiniowane zachowanie:
  - tresc obca  -> usunieta z "punkty", kopia w "punkty_odrzucone",
                   numer dopisany do "punkty_nieznalezione"
                   (modul 19: "napisz to; bez liczby")
  - tekst urwany -> zostaje w "punkty", numer dopisany do "punkty_uciete"
                   (modul 19: "tekst jest NIEPELNY", cytat, adnotacja)
Dzieki temu kwarantanna dziala BEZ zmiany modulu 19 i bez akcji lekarza.

CZEGO NIE ROBI. Nie przerabia testu odbioru tak, zeby kwarantanna wygladala jak
PASS. Plik z deklaracja KWARANTANNA z definicji NIE JEST cache produkcyjnym.
Deklaracji nie umie wystawic generator - patrz test T18 w chpl_test_odbioru.

TEST URWANIA - DETERMINISTYCZNY, KONIECZNY, NIEWYSTARCZAJACY. Tekst punktu
konczacy sie inaczej niz zamknieciem zdania NIE JEST dowodem ucziecia w sensie
logicznym, ale jest wlasnoscia samego tekstu, nie podobienstwem ani progiem
(3B). Kierunek bledu: falszywe "urwany" kosztuje jedno dodatkowe zajrzenie do
ChPL, falszywe "pelny" moze kosztowac pacjenta.
"""
import json, glob, os, sys, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polityka

DZIS = "2026-09-23"
KONCE = ('.', ':', ';', ')', '%', '"', '”', '?', '!', ']')

POWOD_OBCA = ("Tresc punktu nie odpowiada jego numerowi - ekstraktor zakotwiczyl "
              "sie na odsylaczu wewnatrz tekstu. Wykryte 2026-09-23. "
              "To NIE znaczy, ze etykieta nie ma tego punktu - znaczy, ze my go nie mamy.")
POWOD_URWANY = ("Tekst nie konczy sie zamknieciem zdania - podejrzenie ucziecia "
                "przez ekstraktor. Wykryte 2026-09-23.")


def urwany(t):
    """Deterministyczna wlasnosc samego tekstu. Bez progow i podobienstwa."""
    s = (t or "").rstrip()
    if not s:
        return False
    return s[-1] not in KONCE


def obce(produkt):
    """Punkty oznaczone wczesniej jako niosace tresc innego punktu."""
    nk = produkt.get("NAGLOWEK_NIEZGODNY") or {}
    return sorted(nk.get("punkty") or [])


def przetworz(d, sucho):
    zmiany = {"obce": [], "urwane": []}
    for p in d.get("produkty", []):
        punkty = p.get("punkty") or {}
        stare = set(punkty)

        do_usuniecia = [k for k in obce(p) if k in punkty]
        do_uciecia = [k for k in punkty if k not in do_usuniecia and urwany(punkty[k])]

        if not do_usuniecia and not do_uciecia:
            continue

        etykieta = "%s/%s" % (d.get("substancja"), p.get("nazwa"))

        # BRAMA 1 - czy wolno tak sklasyfikowac. Podstawa decyzji siega TRESCI
        # punktu (jego zakonczenie) i wczesniejszej kontroli naglowka, nie samej
        # nazwy pola.
        polityka.sprawdz_semantyke(
            "CHPL_LAYER", "ZAPIS", "DETERMINISTYCZNY",
            ("tresc_punktu", "zakonczenie_tekstu", "naglowek_punktu"))

        nowe = stare - set(do_usuniecia)
        # BRAMA 2 - czy wolno tym nadpisac stan produkcyjny. Kazdy ubytek
        # z jawna przyczyna ze zrodla kontroli.
        polityka.sprawdz_publikacje(
            "CHPL_LAYER", stare, nowe, "OK",
            {k: "ZATWIERDZONA_KOREKTA_MAPOWANIA" for k in do_usuniecia})

        for k in do_usuniecia:
            zmiany["obce"].append("%s pkt %s" % (etykieta, k))
        for k in do_uciecia:
            zmiany["urwane"].append("%s pkt %s" % (etykieta, k))

        if sucho:
            continue

        odrzucone = p.setdefault("punkty_odrzucone", {})
        for k in do_usuniecia:
            odrzucone[k] = {"tresc": punkty.pop(k), "powod": POWOD_OBCA,
                            "wykryto": DZIS}
        nz = p.setdefault("punkty_nieznalezione", [])
        for k in do_usuniecia:
            if k not in nz:
                nz.append(k)
        p["punkty_nieznalezione"] = sorted(nz)

        uc = p.setdefault("punkty_uciete", [])
        for k in do_uciecia:
            if k not in uc:
                uc.append(k)
        p["punkty_uciete"] = sorted(uc)

        p["KWARANTANNA"] = {"data": DZIS, "odrzucone": sorted(do_usuniecia),
                            "uciete": sorted(do_uciecia), "powod_urwania": POWOD_URWANY}
    return zmiany


def main():
    sucho = "--zapisz" not in sys.argv
    n_plik = 0
    suma = {"obce": [], "urwane": []}
    for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           "..", "chpl", "*.json"))):
        if os.path.basename(f) == "INDEX.json":
            continue
        d = json.load(open(f, encoding="utf-8"))
        z = przetworz(d, sucho)
        if z["obce"] or z["urwane"]:
            n_plik += 1
            suma["obce"] += z["obce"]
            suma["urwane"] += z["urwane"]
            if not sucho:
                d["STATUS"] = "KWARANTANNA"
                d["KWARANTANNA_DATA"] = DZIS
                json.dump(d, open(f, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1, sort_keys=True)
    print("plikow objetych:", n_plik)
    print("punktow usunietych (tresc obca):", len(suma["obce"]))
    print("punktow oznaczonych jako uciete:", len(suma["urwane"]))
    print("tryb:", "ZAPIS" if not sucho else "PROBNY (--zapisz zeby zapisac)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

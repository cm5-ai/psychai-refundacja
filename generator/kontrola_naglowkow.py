#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KONTROLA: CZY TRESC PUNKTU ODPOWIADA JEGO NUMEROWI.

ZNALEZISKO 2026-09-23. 42 z 1496 punktow w cache niosly tresc INNEGO punktu,
a ekstrakcja zglaszala zero ucziec i zero brakow - nic nie sygnalizowalo bledu.
Mechanizm: wyciag zakotwiczal sie na literalnym "4.3." albo "4.5." wystepujacym
WEWNATRZ tekstu jako odsylacz ("patrz punkt 4.5.") albo podnumeracja
("4.4. Niewydolnosc nerek"), zamiast na prawdziwym naglowku sekcji.

Skutek przy pacjencie: pytanie o przeciwwskazania do lurazydonu zwracalo
punkt 4.3 z trescia o ZAMIANIE LEKU PRZECIWPSYCHOTYCZNEGO. Zadnych
przeciwwskazan i zadnego sygnalu, ze cos jest nie tak.

KONTROLA JEST DETERMINISTYCZNA: naglowek punktu ChPL jest ustalony przez
prawo i zawsze zawiera to samo slowo. Brak tego slowa w pierwszych 90 znakach
= punkt podejrzany. To nie jest ocena tresci, tylko sprawdzenie etykiety.

CO ROBI Z WYNIKIEM: oznacza punkt jako NAGLOWEK_NIEZGODNY. Modul 19 ma juz
pojecie CHPL_KARANTANNA - wpis podejrzany, bez liczby z cache. Oznaczony
punkt ma byc traktowany tak samo: NIE CYTOWAC, powiedziec, ze nie mamy.
"""
import json, glob, os, sys

OCZEKIWANE = {"4.1": "wskazania", "4.2": "dawkowanie", "4.3": "przeciwwskazania",
              "4.4": "ostrzeżenia", "4.5": "interakcje", "4.6": "wpływ na płodność",
              "4.8": "działania niepożądane", "5.2": "właściwości farmakokinetyczne"}
OKNO = 90


def niezgodne(d):
    """Lista (produkt, punkt, poczatek) o naglowku niezgodnym z numerem."""
    out = []
    for p in d.get("produkty", []):
        for k, slowo in OCZEKIWANE.items():
            t = " ".join((p["punkty"].get(k) or "").split())
            if not t:
                continue
            if slowo not in t[:OKNO].lower():
                out.append((p.get("nazwa"), k, t[:80]))
    return out


def main():
    zapisz = "--zapisz" in sys.argv
    n_punktow = n_zle = n_plikow = 0
    dotkniete = []
    for f in sorted(glob.glob("chpl/*.json")):
        if f.endswith("INDEX.json"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        zle = niezgodne(d)
        for p in d.get("produkty", []):
            n_punktow += len([k for k in OCZEKIWANE if (p["punkty"].get(k) or "").strip()])
        if not zle:
            continue
        n_zle += len(zle)
        n_plikow += 1
        dotkniete.append((os.path.basename(f)[:-5], zle))
        if zapisz:
            for p in d.get("produkty", []):
                pods = sorted({k for nazwa, k, _ in zle if nazwa == p.get("nazwa")})
                if pods:
                    p["NAGLOWEK_NIEZGODNY"] = {
                        "punkty": pods,
                        "co_to_znaczy": ("Tresc tych punktow NIE odpowiada ich numerowi - "
                                         "wyciag zakotwiczyl sie na odsylaczu w tekscie, "
                                         "nie na naglowku sekcji."),
                        "co_zrobic": ("Traktowac jak CHPL_KARANTANNA: NIE cytowac tych "
                                      "punktow i nie podawac z nich liczb. Powiedziec, "
                                      "ze paczka nie ma tego punktu dla tego produktu."),
                        "czego_NIE_znaczy": ("To nie znaczy, ze lek nie ma przeciwwskazan "
                                             "ani ze etykieta ich nie zawiera - znaczy, ze "
                                             "my ich nie mamy."),
                        "wykryto": "2026-09-23",
                    }
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PUNKTOW W CACHE: %d" % n_punktow)
    print("  naglowek niezgodny z numerem: %d w %d plikach" % (n_zle, n_plikow))
    for lek, zle in dotkniete:
        print("  %-16s %s" % (lek, ", ".join(sorted({k for _, k, _ in zle}))))
    print("\n" + ("OZNACZONE." if zapisz else "(bez --zapisz nic nie zapisano)"))
    return 1 if n_zle else 0


if __name__ == "__main__":
    sys.exit(main())

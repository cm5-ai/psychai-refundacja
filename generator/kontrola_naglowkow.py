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


# ------------------------------------------------------------------ dlugosc
# CICHE UCIECIE. Kontrola naglowkow sprawdza tylko POCZATEK punktu. Punkt
# urwany na koncu ma poprawny naglowek i nic nie krzyczy.
#
# DLACZEGO NIE POROWNUJEMY PRODUKTOW MIEDZY SOBA. Produkty LEGALNIE sie
# roznia - ChPL Absenor wymienia w 4.3 orzeszki i soje, ktorych Convulex nie
# ma. Roznica dlugosci miedzy produktami NIE dowodzi bledu.
# DLACZEGO NIE POROWNUJEMY PUNKTOW WEWNATRZ ETYKIETY. Punkt 4.1 jest z natury
# krotki ("leczenie epizodow depresyjnych u doroslych") - taka kontrola
# zglaszala 89 falszywych alarmow, prawie same 4.1.
# CO ROBIMY: porownanie z typowa dlugoscia TEGO RODZAJU punktu w calym cache.
# 4.3 ma mediane 417 znakow, 4.4 az 6529 - wiec krotkie 4.3 jest normalne,
# a krotkie 4.4 nie.
#
# NIE KARANTANNA, TYLKO ADNOTACJA. Etykieta MOZE naprawde zawierac zdanie
# "nie przeprowadzono badan interakcji". Karantanna ukrylaby prawdziwa tresc.
# Tekst zostaje widoczny, a obok stoi liczba: ile ma, ile ma typowy punkt
# tego rodzaju. Ocene robi czytajacy.
import statistics

PROG = 0.10


def podejrzanie_krotkie(katalog="chpl"):
    dl = {k: [] for k in OCZEKIWANE}
    rek = []
    for f in sorted(glob.glob(os.path.join(katalog, "*.json"))):
        if f.endswith("INDEX.json"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        for p in d.get("produkty", []):
            nz = set((p.get("NAGLOWEK_NIEZGODNY") or {}).get("punkty") or [])
            for k in OCZEKIWANE:
                t = " ".join((p["punkty"].get(k) or "").split())
                if not t:
                    continue
                dl[k].append(len(t))
                rek.append((f, p, k, len(t), k in nz))
    med = {k: (statistics.median(v) if v else 0) for k, v in dl.items()}
    return [(f, p, k, n, med[k]) for f, p, k, n, oznaczony in rek
            if not oznaczony and n < med[k] * PROG], med


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
    kr, med = podejrzanie_krotkie()
    print()
    print("PUNKTY PODEJRZANIE KROTKIE (ponizej %d%% mediany swojego rodzaju): %d"
          % (int(PROG * 100), len(kr)))
    for f, p, k, n, m in sorted(kr, key=lambda z: z[3]):
        print("  %-16s %-22s %-4s %5d znakow, typowo %d"
              % (os.path.basename(f)[:-5], (p.get("nazwa") or "?")[:22], k, n, int(m)))
    if zapisz:
        for f, p, k, n, m in kr:
            d2 = json.load(open(f, encoding="utf-8"))
            for q in d2.get("produkty", []):
                if q.get("nazwa") != p.get("nazwa"):
                    continue
                w = q.setdefault("PODEJRZANIE_KROTKI", {})
                w[k] = {"znakow": n, "typowo_dla_tego_punktu": int(m),
                        "co_to_znaczy": ("Punkt jest wielokrotnie krotszy niz ten sam "
                                         "punkt w innych etykietach. Moze byc urwany "
                                         "przez wyciag albo naprawde krotki."),
                        "co_zrobic": ("Tresc pokazuj w calosci RAZEM z ta adnotacja. "
                                      "Nie twierdz, ze to pelna tresc punktu."),
                        "wykryto": "2026-09-23"}
            json.dump(d2, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n" + ("OZNACZONE." if zapisz else "(bez --zapisz nic nie zapisano)"))
    return 1 if n_zle else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRZEBIEG ZESTAWU BLOKUJACEGO — arkusz do wykonania i do oceny.

PO CO OSOBNY SKRYPT. Pytania musza pochodzic Z PLIKU, nie z przepisania
recznie. Przepisane pytanie rozjezdza sie z krotka po pierwszej korekcie
i wtedy mierzy sie cos innego, niz zadeklarowano — a nikt tego nie widzi,
bo obie wersje wygladaja sensownie.

    --pytania   (domyslnie) gotowe do wklejenia, po jednym na watek
    --arkusz    kryteria oceny: co ma paść, co nie moze paść

KAZDA WINIETA W OSOBNYM, SWIEZYM WATKU. W jednym watku model widzi
poprzednie pytania i odpowiedzi; zestaw mierzylby wtedy pamiec rozmowy,
a nie zawartosc paczki. Wyjatek: BLOK-5 jest z zalozenia wieloturowy
i cztery jego tury ida po kolei w JEDNYM watku.
"""
import json
import os
import sys

KAT = os.path.dirname(os.path.abspath(__file__))
ZEST = os.path.join(KAT, "zestaw_blokujacy.json")


def main():
    tryb = sys.argv[1] if len(sys.argv) > 1 else "--pytania"
    d = json.load(open(ZEST, encoding="utf-8"))
    w = d["WINIETY"]

    if tryb == "--pytania":
        print("ZESTAW BLOKUJACY — %d winiet, kazda w OSOBNYM SWIEZYM WATKU" % len(w))
        print("=" * 66)
        for i, v in enumerate(w, 1):
            print()
            print("--- WATEK %d/%d   [%s] ---" % (i, len(w), v["id"]))
            print(v["wejscie"])
        print()
        print("=" * 66)
        print("Wklej kazda odpowiedz w calosci, z numerem watku.")
        print("Odpowiedz skrocona albo streszczona nie nadaje sie do oceny:")
        print("czesc kryteriow dotyczy tego, czego w odpowiedzi NIE MA.")
        return 0

    if tryb == "--arkusz":
        print("KRYTERIA OCENY — czego szukam w kazdej odpowiedzi")
        print("=" * 66)
        for i, v in enumerate(w, 1):
            k = v["krotka"]
            print()
            print("WATEK %d  %s  [%s]" % (i, v["id"], v["klasa"]))
            print("  chroni:     %s" % v["chroni"])
            if k.get("wartosc"):
                print("  MA PASC:    %s  (%s)" % (k["wartosc"], k.get("wartosc_typ")))
            for m in (k.get("wymaga_z_paczki") or []):
                print("  MA PASC:    \"%s\"" % m)
            for m in (k.get("wymaga_zachowania") or []):
                print("  ZACHOWANIE: %s" % m)
            for z in (k.get("zakazane_wartosci") or []):
                wart = z.get("wartosc") if isinstance(z, dict) else z
                wyj = (z.get("chyba_ze") or []) if isinstance(z, dict) else []
                print("  NIE MOZE:   \"%s\"%s" % (wart,
                      ("   chyba ze zacytowane po to, by wykluczyc: %s" % wyj) if wyj else ""))
            print("  czemu trudna: %s" % v["czemu_trudna"][:150])
        print()
        print("=" * 66)
        print("FOIL oblewa, GDY MODEL ODPOWIE. Zestaw z samych HIT-ow mierzy")
        print("tylko, czy system umie powiedziec TAK.")
        return 0

    print("Nieznany tryb: %s" % tryb)
    return 2


if __name__ == "__main__":
    sys.exit(main())

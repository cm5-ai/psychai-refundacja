#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INWENTARZ MASTER — co jest regula wizyty, a co maszyneria zapisu.

Po co. 48% MASTER (43 886 z 91 310 znakow) to zapis rekordu: kod pacjenta,
szyfr, nazwa pliku, archiwum, zakaz dzielenia rekordu. Czytane na KAZDEJ
wizycie, takze gdy lekarz pyta wylacznie o dawke. To najdrozszy obowiazkowy
szum w calej paczce.

Czego ten plik NIE robi. NIE dzieli MASTER. Nie ma prawa: decyzja, po ktorej
stronie ma stac dana regula, jest kliniczna, nie mechaniczna, a regula, ktora
wyladuje po stronie COMMIT, przestaje obowiazywac przy wizycie i nikt tego nie
zauwazy. Ten plik przygotowuje LISTE DO DECYZJI LEKARZA i liczy, ile faktycznie
da sie zdjac.

Zasada klasyfikacji. JAWNA TABELA SLOW, nie podobienstwo. Sekcja trafia do
COMMIT tylko wtedy, gdy niesie slowo z listy COMMIT i ZADNEGO z listy RUNTIME.
Kazdy inny przypadek to DO_DECYZJI - czyli domyslnie ZOSTAJE w runtime.
Blad w strone "za duzo kontekstu" jest wolny. Blad w strone "zniknela regula"
jest cichy. Przy wizycie drugi jest nieporownanie gorszy.
"""
import os, re, sys

PROJEKT = os.path.expanduser("~/mnt/psychai-paczka/projekt")
MASTER = "MASTER_v20_2026-09-20.txt"

# Slowa maszynerii zapisu. Sekcja z ktorymkolwiek jest KANDYDATEM do COMMIT.
COMMIT = ("zapis", "commit", "rekord", "szyfr", "archiw", "nazwa pliku",
          "kod psy", "pesel", "dysk", "folder", "plik posredni", "serializ",
          "uciec", "ucieci", "ponown", "checkpoint")
# Slowa wizyty. Ich obecnosc UNIEWAZNIA kandydature, bez wyjatku.
RUNTIME = ("bramk", "blok", "red flag", "ostrzez", "dawk", "lek ", "leku",
           "przeciwwskaz", "ciaza", "ciąż", "laktac", "interakc", "refundac",
           "pacjent", "objaw", "rozpozn", "decyzj", "rekomend", "monitor",
           "odstaw", "pomost", "depot", "eGFR", "qtc", "opioid", "sud")


def bez_ogonkow(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def sekcje(L):
    h = [(i, l.strip()) for i, l in enumerate(L)
         if re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ0-9][A-ZĄĆĘŁŃÓŚŹŻ0-9 _\-/,\.\(\)]{6,}$', l.strip())
         and len(l.strip()) < 70]
    out = []
    for n, (i, t) in enumerate(h):
        j = h[n + 1][0] if n + 1 < len(h) else len(L)
        out.append({"tytul": t, "od": i, "do": j,
                    "znaki": sum(len(x) + 1 for x in L[i:j]),
                    "tekst": bez_ogonkow("\n".join(L[i:j]))})
    return out


def main():
    L = open(os.path.join(PROJEKT, MASTER), encoding="utf-8").read().split("\n")
    S = sekcje(L)
    caly = sum(len(x) + 1 for x in L)
    pokryte = sum(s["znaki"] for s in S)
    print("MASTER: %d linii, %d znakow" % (len(L), caly))
    print("Sekcji rozpoznanych: %d, pokrywaja %d zn (%.0f%%). Reszta to naglowek "
          "i tekst miedzy sekcjami - ZOSTAJE w runtime bez pytania."
          % (len(S), pokryte, 100.0 * pokryte / caly))
    print()

    for s in S:
        ma_c = [w for w in COMMIT if w in s["tekst"]]
        ma_r = [w for w in RUNTIME if bez_ogonkow(w) in s["tekst"]]
        if ma_c and not ma_r:
            s["strona"], s["czemu"] = "COMMIT", "slowa zapisu: " + ", ".join(ma_c[:3])
        elif ma_c and ma_r:
            s["strona"] = "DO_DECYZJI"
            s["czemu"] = "zapis (%s) ORAZ wizyta (%s)" % (", ".join(ma_c[:2]), ", ".join(ma_r[:3]))
        else:
            s["strona"], s["czemu"] = "RUNTIME", "brak slow zapisu"

    for strona in ("COMMIT", "DO_DECYZJI", "RUNTIME"):
        g = [s for s in S if s["strona"] == strona]
        print("=" * 78)
        print("%s — %d sekcji, %d znakow" % (strona, len(g), sum(x["znaki"] for x in g)))
        print("=" * 78)
        for s in sorted(g, key=lambda x: -x["znaki"]):
            if s["znaki"] < 400 and strona == "RUNTIME":
                continue
            print("  %6d zn  linie %4d-%4d  %-46s %s"
                  % (s["znaki"], s["od"] + 1, s["do"], s["tytul"][:46], s["czemu"][:40]))
        if strona == "RUNTIME":
            print("  (sekcje ponizej 400 zn pominiete w wydruku: %d, razem %d zn)"
                  % (sum(1 for s in g if s["znaki"] < 400),
                     sum(s["znaki"] for s in g if s["znaki"] < 400)))
        print()

    c = sum(s["znaki"] for s in S if s["strona"] == "COMMIT")
    d = sum(s["znaki"] for s in S if s["strona"] == "DO_DECYZJI")
    print("ILE DA SIE ZDJAC Z WIZYTY")
    print("  pewne COMMIT:           %6d zn  (~%d tys. tokenow)" % (c, c / 3500))
    print("  DO_DECYZJI lekarza:     %6d zn  (~%d tys. tokenow)" % (d, d / 3500))
    print("  gorna granica razem:    %6d zn  (~%d tys. tokenow)" % (c + d, (c + d) / 3500))
    print()
    print("NIC NIE ZOSTALO PODZIELONE. To jest lista do decyzji, nie zmiana.")
    print("Domyslna odpowiedz dla DO_DECYZJI brzmi ZOSTAJE - az lekarz powie inaczej.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

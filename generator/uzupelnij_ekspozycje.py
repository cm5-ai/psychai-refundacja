#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UZUPELNIENIE POLA EKSPOZYCJA W CACHE — 2026-09-24.

ZNALEZISKO. Slownik postaci liczy trzy rzeczy: DROGA, UWALNIANIE i EKSPOZYCJA
(DEPOT / POSREDNIA / KROTKA). Dwie pierwsze sa w kazdym wpisie. Trzecia — ta,
dla ktorej powstala tabela wyjatkow produktowych i caly detektor sierot LAI —
JEST TYLKO W 187 z 395 wpisow. Brakuje jej w 208, w tym we WSZYSTKICH TRZECH
produktach zuklopentyksolu: Clopixol, Clopixol-Depot i Clopixol-Acuphase.
Czyli akurat tam, gdzie roznica DEPOT / POSREDNIA / KROTKA zmienia dawke
i interwal, pola nie bylo wcale.

PRZYCZYNA. Pole dopisuje funkcja wpis() w skryptach dolaczajacych. Wpisy
dodane tymi skryptami je maja; 208 starszych, z przebudowy cache z PDF,
powstalo zanim ta funkcja istniala. Nikt tego nie zauwazyl, bo nic nie
sprawdzalo, czy pole jest — sprawdzalo sie tylko, czy jest POPRAWNE tam,
gdzie jest.

CZEGO TEN SKRYPT NIE ROBI. Nie zmienia zadnego istniejacego pola EKSPOZYCJA.
Dopisuje wylacznie tam, gdzie go NIE MA. Rozbieznosc z istniejacym wpisem
byla by znaleziskiem do przegladu, nie powodem do nadpisania.
"""
import glob, json, os, sys

KAT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(KAT, "..", "slownik"))
import postacie as PO

CHPL = os.path.join(KAT, "..", "chpl")


def main():
    sucho = "--zapisz" not in sys.argv
    we = dopisane = mialy = bez_postaci = 0
    rozklad, sieroty, wyjatki = {}, [], []
    zmienione = {}

    for f in sorted(glob.glob(os.path.join(CHPL, "*.json"))):
        if os.path.basename(f) == "INDEX.json":
            continue
        d = json.load(open(f, encoding="utf-8"))
        ruszony = False
        for p in d.get("produkty", []):
            we += 1
            if p.get("EKSPOZYCJA") is not None:
                mialy += 1
                continue
            if not p.get("postac"):
                bez_postaci += 1
                continue
            try:
                e = PO.ekspozycja(p, chpl_42=(p.get("punkty") or {}).get("4.2"))
            except KeyError as ex:
                # Napis postaci spoza slownika MA WYBUCHAC, nie wpadac po cichu
                # do UNKNOWN. Zbieramy i zglaszamy, nie zgadujemy.
                sieroty.append("%s / %s: napis postaci spoza slownika: %s"
                               % (os.path.basename(f)[:-5], p.get("nazwa"), str(ex)[:60]))
                continue
            p["EKSPOZYCJA"] = e
            dopisane += 1
            ruszony = True
            w = e.get("ekspozycja")
            rozklad[w] = rozklad.get(w, 0) + 1
            if e.get("zrodlo", "").startswith("WYJATEK") or w in ("DEPOT", "POSREDNIA"):
                wyjatki.append("%-22s %-26s -> %-10s (%s)"
                               % (os.path.basename(f)[:-5], (p.get("nazwa") or "")[:26],
                                  w, e.get("zrodlo")))
            syg = PO.kandydat_lai(p, chpl_42=(p.get("punkty") or {}).get("4.2"))
            if syg and w == "KROTKA":
                sieroty.append("%s / %s: sygnaly LAI %s, a wychodzi KROTKA — do przegladu"
                               % (os.path.basename(f)[:-5], p.get("nazwa"), syg))
        if ruszony:
            zmienione[f] = d

    print("N_WEJSCIE %d = mialy pole %d + dopisane %d + bez postaci %d + sieroty %d -> %s"
          % (we, mialy, dopisane, bez_postaci, len(sieroty),
             "BILANS OK" if we == mialy + dopisane + bez_postaci + len(sieroty) else "SPRAWDZ"))
    print("ROZKLAD dopisanych: %s" % ", ".join("%s=%d" % kv for kv in sorted(rozklad.items(), key=lambda x: -x[1])))
    print()
    print("DEPOT i POSREDNIA wsrod dopisanych (%d):" % len(wyjatki))
    for w in sorted(wyjatki):
        print("   " + w)
    print()
    print("DO PRZEGLADU (%d):" % len(sieroty))
    for s in sieroty[:30]:
        print("   " + s)
    if sucho:
        print("\nTRYB SUCHY. Dopisz --zapisz.")
        return 0
    for f, d in zmienione.items():
        json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print("\nZAPISANO %d plikow." % len(zmienione))
    return 0


if __name__ == "__main__":
    sys.exit(main())

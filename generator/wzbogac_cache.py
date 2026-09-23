#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOLOZENIE POSTACI I KLUCZY DO PRODUKTOW W CACHE. Bez pobierania czegokolwiek.

PO CO. Karta haloperidolu ma obok siebie Decaldol (dekanian, dawka na
wstrzykniecie co kilka tygodni) i Haloperidol WZF (postac krotka, dawka
dobowa). Karta zuklopentiksolu ma Acuphase (2-3 doby), Depot (tygodnie)
i tabletki. Karta rozdziela je po NAZWIE HANDLOWEJ, ale nigdzie nie mowi,
ktora to POSTAC - a przy szybkim czytaniu w gabinecie 12,5-25 mg obok
0,5 mg/dobe jest do pomylenia.

Przy arypiprazolu i flupentiksolu nazwa lacinska ICH NIE ROZROZNIA: Abilify
i Abilify Maintena to oba Aripiprazolum. Rozdziela je wylacznie postac.

CO ROBI. Do kazdego produktu w cache dokłada z RPL: postac, nazwa_powszechna
i atc. Klucz: RÓWNOŚĆ nazwy handlowej po kanonizacji bialych znakow i
wielkosci liter. Zero podobienstwa.

CZEGO NIE ROBI. Nie dotyka tresci punktow ChPL, nie zmienia zbioru produktow
i nie pobiera niczego. Brama publikacji pilnuje, ze zbior produktow jest
dokladnie ten sam przed i po.
"""
import json, glob, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polityka

polityka.sprawdz_semantyke("CHPL_LAYER", "ZAPIS", "DETERMINISTYCZNY",
                           ("nazwa", "postac", "nazwa_powszechna", "atc"))

def kan(s):
    return " ".join((s or "").split()).lower()

def main():
    zapisz = "--zapisz" in sys.argv
    rpl = json.load(open("rpl/RPL_PSYCH.json", encoding="utf-8"))["produkty"]
    po = collections.defaultdict(list)
    for p in rpl:
        po[kan(p.get("nazwa"))].append(p)

    n_prod = n_wzb = n_bez = 0
    bez = []
    for f in sorted(glob.glob("chpl/*.json")):
        if f.endswith("INDEX.json"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        przed = {q.get("nazwa") for q in d.get("produkty", [])}
        zmiana = False
        for q in d.get("produkty", []):
            n_prod += 1
            kand = po.get(kan(q.get("nazwa")))
            if not kand:
                # BRAK W SPISIE TO NIE BLAD PRODUKTU. Zapisujemy to jawnie,
                # zamiast zostawiac pole puste i udawac, ze postaci nie ma.
                q["klucz_rpl"] = {"stan": "PRODUKT_SPOZA_SPISU_RPL",
                                  "uwaga": "Nie znaleziono w spisie po rownosci nazwy. "
                                           "To nie znaczy, ze produktu nie ma."}
                n_bez += 1; bez.append((f[5:-5], q.get("nazwa"))); zmiana = True
                continue
            q["klucz_rpl"] = {
                "postac": sorted({(k.get("postac") or "?").strip() for k in kand}),
                "nazwa_powszechna": sorted({(k.get("nazwa_powszechna") or "?").strip()
                                            for k in kand}),
                "atc": sorted({a for k in kand for a in (k.get("atc") or [])}),
                "zrodlo": "RPL_PSYCH.json, rownosc nazwy handlowej",
            }
            n_wzb += 1; zmiana = True
        if zapisz and zmiana:
            polityka.sprawdz_publikacje("CHPL_LAYER", przed,
                                        {q.get("nazwa") for q in d.get("produkty", [])})
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("PRODUKTOW: %d  wzbogaconych: %d  spoza spisu: %d" % (n_prod, n_wzb, n_bez))
    print("BILANS: %d + %d = %d" % (n_wzb, n_bez, n_prod))
    assert n_wzb + n_bez == n_prod, "BILANS WZBOGACENIA"
    if bez:
        print("\nSPOZA SPISU (nie blad - odnotowane w pliku):")
        for lek, n in bez:
            print("   %-16s %s" % (lek, n))
    print("\n" + ("ZAPISANE." if zapisz else "(bez --zapisz nic nie zapisano)"))

main()

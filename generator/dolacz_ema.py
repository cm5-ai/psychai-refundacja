#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DOLACZENIE CHARAKTERYSTYK EMA - 2026-09-24.

Powod: 39 produktow iniekcyjnych nie ma w rejestrze krajowym ZADNEGO linku do
ChPL, bo to rejestracja centralna EMA. Sam rejestr nie jest w stanie ich wydac.
Zrodlo: EMA publikuje charakterystyke osobnym plikiem na jezyk, wzorzec
https://www.ema.europa.eu/pl/documents/product-information/<slug>-epar-product-information_pl.pdf
Polski plik zawiera ANEKS I, czyli ChPL. Ekstraktor czyta go BEZ ZMIAN.

KLUCZ: (kanoniczna nazwa produktu, klasa postaci) - ten sam co w reszcie
projektu. Jedna ChPL EMA obejmuje wszystkie moce produktu, wiec do cache
trafia jedna pozycja na (nazwa, postac), nie na moc.
"""
import json, glob, os, re, sys, hashlib

KAT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KAT)
sys.path.insert(0, os.path.join(KAT, "..", "slownik"))
import chpl_z_pdf
import postacie as PO

CHPL = os.path.join(KAT, "..", "chpl")
RPL = os.path.join(KAT, "..", "rpl", "RPL_PSYCH.json")
POBRANE = os.path.expanduser("~/mnt/Downloads")
DZIS = "2026-09-24"

# slug pliku EMA -> (nazwa produktu w RPL, plik cache)
MAPA = {
    "abilify-maintena": ("Abilify Maintena", "arypiprazol"),
    "abilify":          ("Abilify",          "arypiprazol"),
    "zypadhera":        ("Zypadhera",        "olanzapina"),
    "zyprexa":          ("Zyprexa",          "olanzapina"),
    "xeplion":          ("Xeplion",          "paliperydon"),
    "trevicta":         ("Trevicta",         "paliperydon"),
    "byannli":          ("BYANNLI",          "paliperydon"),
    "okedi":            ("Okedi",            "risperidon"),
    "buvidal":          ("Buvidal",          "buprenorfina"),
    "niapelf":          ("Niapelf",          "paliperydon"),
}
# Briviact (brywaracetam) i Byfavo (remimazolam) NIE sa dolaczane: tych
# substancji nie ma na liscie cache. Pobrane, ale nieuzyte - to decyzja
# o zakresie listy, nie o dostepnosci etykiety.


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def main():
    sucho = "--zapisz" not in sys.argv
    rpl = json.load(open(RPL, encoding="utf-8"))["produkty"]
    we = dodane = pominiete = bez_pdf = 0
    pliki, log = {}, []

    for slug, (nazwa, plik_cache) in sorted(MAPA.items()):
        we += 1
        pdf = os.path.join(POBRANE, "ema_%s_pl.pdf" % slug)
        if not os.path.exists(pdf):
            bez_pdf += 1
            log.append("BEZ PDF: %s" % slug)
            continue
        punkty, diag = chpl_z_pdf.punkty(pdf)

        # wszystkie pozycje RPL o tej nazwie, pogrupowane po postaci
        pasuje = [p for p in rpl if PO.kanon_nazwy(p.get("nazwa")) == PO.kanon_nazwy(nazwa)]
        wg_postaci = {}
        for p in pasuje:
            wg_postaci.setdefault(p.get("postac"), []).append(p)
        if not wg_postaci:
            log.append("BRAK W RPL: %s" % nazwa)
            continue

        f = os.path.join(CHPL, plik_cache + ".json")
        if f not in pliki:
            pliki[f] = json.load(open(f, encoding="utf-8"))
        d = pliki[f]
        mam = {(PO.kanon_nazwy(q.get("nazwa")), q.get("postac")) for q in d.get("produkty", [])}

        for postac, grupa in sorted(wg_postaci.items()):
            if (PO.kanon_nazwy(nazwa), postac) in mam:
                pominiete += 1
                continue
            wzor = sorted(grupa, key=lambda x: str(x.get("moc")))[0]
            kl = PO.postac_klasa(postac)
            moce = sorted({str(p.get("moc")) for p in grupa})
            wpis = {
                "nazwa": wzor.get("nazwa"),
                "moc": moce[0] if len(moce) == 1 else "; ".join(moce),
                "postac": postac,
                "podmiot": wzor.get("podmiot"),
                "zrodlo": "https://www.ema.europa.eu/pl/documents/product-information/"
                          "%s-epar-product-information_pl.pdf" % slug,
                "zrodlo_pliku": os.path.basename(pdf),
                "ZRODLO_REJESTRACJI": "EMA_PRODUCT_INFORMATION_PL",
                "sha256_pdf": sha(pdf),
                "stan": "OK",
                "punkty": punkty,
                "punkty_nieznalezione": diag["brak"],
                "punkty_uciete": [],
                "klucz_rpl": {
                    "atc": wzor.get("atc"),
                    "nazwa_powszechna": [wzor.get("nazwa_powszechna")],
                    "postac": [postac],
                    "zrodlo": "RPL 2026-09-23",
                },
                "DROGA": kl["droga"],
                "UWALNIANIE": kl["uwalnianie"],
                "EKSPOZYCJA": PO.ekspozycja(wzor, chpl_42=punkty.get("4.2")),
                "UWAGA_MOCE": ("Jedna charakterystyka EMA obejmuje wszystkie moce tego "
                               "produktu: %s" % ", ".join(moce)) if len(moce) > 1 else None,
            }
            if wpis["UWAGA_MOCE"] is None:
                del wpis["UWAGA_MOCE"]
            if not sucho:
                d.setdefault("produkty", []).append(wpis)
            dodane += 1
            log.append("+ %-14s %-20s %-46s %d pkt" % (plik_cache, nazwa, postac[:44], len(punkty)))

    if not sucho:
        for f, d in pliki.items():
            d["pobrano_ema"] = DZIS
            d["uwaga_ema"] = ("Produkty rejestracji centralnej EMA dolaczone 2026-09-24. "
                              "Zrodlo: charakterystyka EMA w wersji polskiej. Rejestr krajowy "
                              "nie zawiera dla nich linku do ChPL.")
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)

    for l in log:
        print("   ", l)
    print("BILANS: N_WEJSCIE=%d N_DODANE=%d N_POMINIETE=%d N_BEZ_PDF=%d" % (we, dodane, pominiete, bez_pdf))
    print("plikow dotknietych:", len(pliki), "| tryb:", "ZAPIS" if not sucho else "PROBNY")
    return 0


if __name__ == "__main__":
    sys.exit(main())

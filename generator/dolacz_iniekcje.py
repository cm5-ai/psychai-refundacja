#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DOLACZENIE ETYKIET INIEKCYJNYCH DO CACHE - 2026-09-24.

Powod: na 140 produktow iniekcyjnych w rejestrze 134 nie mialy wlasnej ChPL.
Cache trzymal etykiety doustne tych substancji. Detektor sierot LAI dzialal
przy iniekcjach prawie na slepo, bo kadencji nie mial z czego przeczytac.

ZRODLO: PDF pobrane przez przegladarke lekarza (runtime ma 403 przez proxy).
KLUCZ MAPOWANIA: KOD ATC, nie nazwa powszechna. Nazwa gubi produkty -
Buprenorphinum kontra Buprenorphini hydrochloridum to ta sama substancja
w cache, ale dwa rozne napisy. To ten sam wniosek co przy slowniku postaci.

CZEGO NIE RUSZA: istniejacych produktow. Skrypt WYLACZNIE DOKLADA nowe
pozycje. Produkt juz obecny w pliku (po identyfikatorze RPL) jest pomijany.
"""
import json, glob, os, re, sys, hashlib, datetime

KAT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KAT)
sys.path.insert(0, os.path.join(KAT, "..", "slownik"))
import chpl_z_pdf
import postacie as PO

CHPL = os.path.join(KAT, "..", "chpl")
RPL = os.path.join(KAT, "..", "rpl", "RPL_PSYCH.json")
LISTA = os.path.join(KAT, "..", "zrodla", "do_dolaczenia.json")
POBRANE = os.path.expanduser("~/mnt/Downloads")
DZIS = "2026-09-24"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def main():
    sucho = "--zapisz" not in sys.argv
    produkty = {p["id"]: p for p in json.load(open(RPL, encoding="utf-8"))["produkty"]}
    zadanie = json.load(open(LISTA, encoding="utf-8"))

    we = len(zadanie)
    dodane, pominiete, bez_pdf, bez_punktow = [], [], [], []
    pliki = {}

    for x in zadanie:
        plik = os.path.join(CHPL, x["plik"] + ".json")
        if plik not in pliki:
            pliki[plik] = json.load(open(plik, encoding="utf-8"))
        d = pliki[plik]
        prod = produkty.get(x["id"])
        if prod is None:
            pominiete.append((x["nazwa"], "brak w RPL"))
            continue

        # Czy ten produkt juz jest? Klucz: adres zrodla (jednoznaczny na produkt).
        mam = {str(p.get("zrodlo") or "") for p in d.get("produkty", [])}
        if x["url"] in mam:
            pominiete.append((x["nazwa"], "juz w cache"))
            continue

        pid = re.search(r"/medicinal-products/(\d+)/", x["url"]).group(1)
        sciezka = os.path.join(POBRANE, "chpl_%s.pdf" % pid)
        if not os.path.exists(sciezka):
            bez_pdf.append((x["nazwa"], pid))
            continue

        nowe, diag = chpl_z_pdf.punkty(sciezka)
        if not nowe:
            bez_punktow.append((x["nazwa"], diag.get("brak")))
            continue

        kl = PO.postac_klasa(prod.get("postac"))
        wpis = {
            "nazwa": prod.get("nazwa"),
            "moc": prod.get("moc"),
            "postac": prod.get("postac"),
            "podmiot": prod.get("podmiot"),
            "zrodlo": x["url"],
            "zrodlo_pliku": os.path.basename(sciezka),
            "sha256_pdf": sha(sciezka),
            "stan": "OK",
            "punkty": nowe,
            "punkty_nieznalezione": diag["brak"],
            "punkty_uciete": [],
            "klucz_rpl": {
                "atc": prod.get("atc"),
                "nazwa_powszechna": [prod.get("nazwa_powszechna")],
                "postac": [prod.get("postac")],
                "zrodlo": "RPL 2026-09-23",
            },
            "DROGA": kl["droga"],
            "UWALNIANIE": kl["uwalnianie"],
            "EKSPOZYCJA": PO.ekspozycja(prod, chpl_42=nowe.get("4.2")),
        }
        if not sucho:
            d.setdefault("produkty", []).append(wpis)
        dodane.append((x["plik"], prod.get("nazwa"), prod.get("moc"), len(nowe)))

    if not sucho:
        for plik, d in pliki.items():
            d["pobrano_iniekcje"] = DZIS
            d["uwaga_iniekcje"] = ("Produkty iniekcyjne dolaczone 2026-09-24 z etykiet "
                                   "pobranych przez przegladarke. Limit 3 produktow na "
                                   "substancje ich NIE obejmuje - byly poza cache'em.")
            json.dump(d, open(plik, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1, sort_keys=True)

    print("BILANS: N_WEJSCIE=%d N_DODANE=%d N_POMINIETE=%d N_BEZ_PDF=%d N_BEZ_PUNKTOW=%d"
          % (we, len(dodane), len(pominiete), len(bez_pdf), len(bez_punktow)))
    print("suma zgadza sie:", we == len(dodane) + len(pominiete) + len(bez_pdf) + len(bez_punktow))
    print("plikow dotknietych:", len(pliki))
    for e in bez_punktow:
        print("   BEZ PUNKTOW:", e)
    for e in bez_pdf:
        print("   BEZ PDF:", e)
    print("tryb:", "ZAPIS" if not sucho else "PROBNY")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DOLACZENIE LEKOW PRZECIWPARKINSONOWSKICH - 2026-09-24.

Powod: spis przepuszczal 23 z 208 produktow N04. Odciete byly wszystkie
inhibitory MAO-B (zespol serotoninowy z SSRI, SNRI, TLPD, tramadolem),
wszyscy agonisci dopaminy (zaburzenia kontroli impulsow, RLS), cala lewodopa
(figurowala w naszych kartach jako PRZECIWWSKAZANIE, a spis jej nie widzial)
i inhibitory COMT.

DWA ZRODLA, kazde z wlasnym oznaczeniem:
  rejestr krajowy  -> zrodlo = adres API RPL
  EMA              -> zrodlo = adres charakterystyki EMA + ZRODLO_REJESTRACJI
"""
import json, os, re, sys, hashlib

KAT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KAT)
sys.path.insert(0, os.path.join(KAT, "..", "slownik"))
import chpl_z_pdf
import postacie as PO

CHPL = os.path.join(KAT, "..", "chpl")
RPL = os.path.join(KAT, "..", "rpl", "RPL_PSYCH.json")
LISTA = os.path.join(KAT, "..", "zrodla", "do_pobrania_ksiazki.json")
POBRANE = os.path.expanduser("~/mnt/Downloads")
DZIS = "2026-09-24"

# slug EMA -> (nazwa produktu w RPL, plik cache)
EMA = {} if "--bez-ema" in sys.argv else {
    "sycrest":("Sycrest","asenapina"), "rxulti":("Rxulti","brexpiprazol"),
    "adasuve":("Adasuve","loksapina"), "quviviq":("Quviviq","darydoreksant"),
    "sunosi":("Sunosi","solriamfetol"), "hetlioz":("Hetlioz","tasymelteon"),
    "fintepla":("Fintepla","fenfluramina"), "keppra":("Keppra","lewetyracetam"),
    "zonegran":("Zonegran","zonisamid"),
}
# Clevor NIE jest dolaczany: to apomorfina WETERYNARYJNA. Ekstraktor zwrocil
# zero punktow, bo w tym dokumencie nie ma polskich naglowkow ChPL ludzkiej.


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def wpis(prod, punkty, diag, zrodlo, plik_pdf, ema=False, moce=None):
    kl = PO.postac_klasa(prod.get("postac"))
    w = {
        "nazwa": prod.get("nazwa"), "moc": moce or prod.get("moc"),
        "postac": prod.get("postac"), "podmiot": prod.get("podmiot"),
        "zrodlo": zrodlo, "zrodlo_pliku": os.path.basename(plik_pdf),
        "sha256_pdf": sha(plik_pdf), "stan": "OK", "punkty": punkty,
        "punkty_nieznalezione": diag["brak"], "punkty_uciete": [],
        "klucz_rpl": {"atc": prod.get("atc"),
                      "nazwa_powszechna": [prod.get("nazwa_powszechna")],
                      "postac": [prod.get("postac")], "zrodlo": "RPL 2026-09-23"},
        "DROGA": kl["droga"], "UWALNIANIE": kl["uwalnianie"],
        "EKSPOZYCJA": PO.ekspozycja(prod, chpl_42=punkty.get("4.2")),
    }
    if ema:
        w["ZRODLO_REJESTRACJI"] = "EMA_PRODUCT_INFORMATION_PL"
    return w


def main():
    sucho = "--zapisz" not in sys.argv
    rpl = json.load(open(RPL, encoding="utf-8"))["produkty"]
    pliki, log = {}, []
    we = dodane = pominiete = bez_pdf = 0

    def otworz(nazwa_pliku):
        f = os.path.join(CHPL, nazwa_pliku + ".json")
        if f not in pliki:
            if os.path.exists(f):
                pliki[f] = json.load(open(f, encoding="utf-8"))
            else:
                pliki[f] = {"substancja": nazwa_pliku, "pobrano": DZIS,
                            "punkty_zadane": ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.8", "5.2"],
                            "STATUS": "UTWORZONY_2026-09-24",
                            "uwaga": ("ChPL nalezy do PRODUKTU. Rozne produkty tej samej "
                                      "substancji moga sie roznic. Brak punktu != brak tresci."),
                            "produkty": []}
                log.append("NOWY PLIK: %s" % nazwa_pliku)
        return pliki[f]

    # --- zrodlo 1: rejestr krajowy
    for x in json.load(open(LISTA, encoding="utf-8")):
        we += 1
        pid = re.search(r"/medicinal-products/(\d+)/", x["url"]).group(1)
        pdf = os.path.join(POBRANE, "chpl_%s.pdf" % pid)
        if not os.path.exists(pdf):
            bez_pdf += 1; log.append("BEZ PDF: %s" % x["nazwa"]); continue
        prod = next((p for p in rpl if p["id"] == x["id"]), None)
        if prod is None:
            log.append("BRAK W RPL: %s" % x["nazwa"]); continue
        d = otworz(x["plik"])
        if x["url"] in {str(q.get("zrodlo") or "") for q in d["produkty"]}:
            pominiete += 1; continue
        punkty, diag = chpl_z_pdf.punkty(pdf)
        d["produkty"].append(wpis(prod, punkty, diag, x["url"], pdf))
        dodane += 1
        log.append("+ RPL %-12s %-22s %d pkt" % (x["plik"], x["nazwa"], len(punkty)))

    # --- zrodlo 2: EMA
    for slug, (nazwa, plik_cache) in sorted(EMA.items()):
        we += 1
        pdf = os.path.join(POBRANE, "ema_%s_pl.pdf" % slug)
        if not os.path.exists(pdf):
            bez_pdf += 1; log.append("BEZ PDF EMA: %s" % slug); continue
        pasuje = [p for p in rpl if PO.kanon_nazwy(p.get("nazwa")) == PO.kanon_nazwy(nazwa)]
        if not pasuje:
            log.append("BRAK W RPL: %s" % nazwa); continue
        punkty, diag = chpl_z_pdf.punkty(pdf)
        d = otworz(plik_cache)
        mam = {(PO.kanon_nazwy(q.get("nazwa")), q.get("postac")) for q in d["produkty"]}
        wg = {}
        for p in pasuje:
            wg.setdefault(p.get("postac"), []).append(p)
        url = ("https://www.ema.europa.eu/pl/documents/product-information/"
               "%s-epar-product-information_pl.pdf" % slug)
        for postac, grupa in sorted(wg.items()):
            if (PO.kanon_nazwy(nazwa), postac) in mam:
                pominiete += 1; continue
            wzor = sorted(grupa, key=lambda x: str(x.get("moc")))[0]
            moce = sorted({str(p.get("moc")) for p in grupa})
            d["produkty"].append(wpis(wzor, punkty, diag, url, pdf, ema=True,
                                      moce="; ".join(moce) if len(moce) > 1 else moce[0]))
            dodane += 1
            log.append("+ EMA %-12s %-22s %-40s %d pkt" % (plik_cache, nazwa, postac[:38], len(punkty)))

    if not sucho:
        for f, d in pliki.items():
            d["pobrano_n04"] = DZIS
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)

    for l in log:
        print("   ", l)
    print("BILANS: N_WEJSCIE=%d N_DODANE=%d N_POMINIETE=%d N_BEZ_PDF=%d" % (we, dodane, pominiete, bez_pdf))
    print("plikow: %d | tryb: %s" % (len(pliki), "ZAPIS" if not sucho else "PROBNY"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

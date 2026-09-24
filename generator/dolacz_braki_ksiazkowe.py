#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DOLACZENIE BRAKOW WSKAZANYCH PRZEZ SLOWNIK INN — 2026-09-24.

slownik/pokrycie_ksiazkowe.py porownal rejestr psychiatryczny z Jarema,
Wciorka i Stahlem przez deterministyczny klucz INN. Z 22 pozycji bez ChPL
w cache cztery to leki kliniczne, nie warianty ziolowe ani monoprodukt
lewodopy, ktorego polaczenia juz mamy:
  eslikarbazepina  Eslibon           N03AF04   Wciorka
  maprotylina      Ludiomil          N06AA21   Wciorka 21x
  prochlorperazyna Chloropernazinum  N05AB04   Jarema, Wciorka
  buprenorfina+nalokson  Suboxone    N07BC51   (EMA, leczenie uzaleznien)

KLOBAZAM ZOSTAJE BRAKIEM SWIADOMYM. Frisium 10 ma szesc wpisow w rejestrze
i ZADEN nie ma charakterystyki do pobrania (chpl: false). To nie jest
niepowodzenie pobierania, tylko stan rejestru - i tak ma byc zapisane.
Przy okazji: wpis id 2528 ma substancje "Clobasamum" (literowka rejestru),
wiec slownik daje mu osobny klucz. Tak ma byc - ciche scalenie po
podobienstwie jest zabronione (warstwa 40, par. 3B).
"""
import json, os, re, sys, hashlib

KAT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KAT)
sys.path.insert(0, os.path.join(KAT, "..", "slownik"))
import chpl_z_pdf
import postacie as PO

CHPL = os.path.join(KAT, "..", "chpl")
RPL = os.path.join(KAT, "..", "rpl", "RPL_PSYCH.json")
LISTA = os.path.join(KAT, "..", "zrodla", "do_pobrania_braki_ksiazkowe.json")
POBRANE = os.path.expanduser("~/mnt/Downloads")
DZIS = "2026-09-24"

# plik w Downloads -> (plik cache, nazwa produktu w RPL, slug EMA albo None)
KRAJOWE = {
    "eslikarbazepina_Eslibon.pdf": ("eslikarbazepina", "Eslibon"),
    "maprotylina_Ludiomil.pdf": ("maprotylina", "Ludiomil"),
    "prochlorperazyna_Chloropernazinum.pdf": ("prochlorperazyna", "Chloropernazinum"),
}
EMA = {"suboxone": ("Suboxone", "buprenorfina_nalokson",
                    "buprenorfina_nalokson_Suboxone_EMA.pdf")}


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
    lista = json.load(open(LISTA, encoding="utf-8"))
    pliki, log = {}, []
    we = dodane = pominiete = bez_pdf = zrodla_ok = 0

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

    for pdf_nazwa, (plik_cache, nazwa_prod) in sorted(KRAJOWE.items()):
        we += 1
        pdf = os.path.join(POBRANE, pdf_nazwa)
        if not os.path.exists(pdf):
            bez_pdf += 1; log.append("BEZ PDF: %s" % pdf_nazwa); continue
        x = next((q for q in lista if q["plik"] == plik_cache and q["nazwa"] == nazwa_prod), None)
        if x is None:
            log.append("BRAK W LISCIE: %s" % nazwa_prod); continue
        prod = next((p for p in rpl if p["id"] == x["id"]), None)
        if prod is None:
            log.append("BRAK W RPL: %s" % nazwa_prod); continue
        d = otworz(plik_cache)
        if x["url"] in {str(q.get("zrodlo") or "") for q in d["produkty"]}:
            pominiete += 1; continue
        punkty, diag = chpl_z_pdf.punkty(pdf)
        d["produkty"].append(wpis(prod, punkty, diag, x["url"], pdf))
        dodane += 1; zrodla_ok += 1
        log.append("+ RPL %-18s %-20s %d pkt, brak %s"
                   % (plik_cache, nazwa_prod, len(punkty), diag["brak"] or "-"))

    for slug, (nazwa, plik_cache, pdf_nazwa) in sorted(EMA.items()):
        we += 1
        pdf = os.path.join(POBRANE, pdf_nazwa)
        if not os.path.exists(pdf):
            bez_pdf += 1; log.append("BEZ PDF EMA: %s" % slug); continue
        pasuje = [p for p in rpl if PO.kanon_nazwy(p.get("nazwa")) == PO.kanon_nazwy(nazwa)]
        if not pasuje:
            log.append("BRAK W RPL: %s" % nazwa); continue
        punkty, diag = chpl_z_pdf.punkty(pdf)
        zrodla_ok += 1
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
            wzor = sorted(grupa, key=lambda q: str(q.get("moc")))[0]
            moce = sorted({str(p.get("moc")) for p in grupa})
            d["produkty"].append(wpis(wzor, punkty, diag, url, pdf, ema=True,
                                      moce="; ".join(moce) if len(moce) > 1 else moce[0]))
            dodane += 1
            log.append("+ EMA %-18s %-20s %-30s %d pkt" % (plik_cache, nazwa, postac[:28], len(punkty)))

    if not sucho:
        for f, d in pliki.items():
            d["pobrano_braki_ksiazkowe"] = DZIS
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)

    for l in log:
        print("   ", l)
    # Bilans zrodel i bilans wpisow to DWIE ROZNE rzeczy: jedno PDF EMA
    # obejmuje kilka postaci jednego produktu, wiec z czterech zrodel
    # powstaje piec wpisow. Zlaczenie ich w jedno rownanie dawalo "-1"
    # i wygladalo na blad tam, gdzie bledu nie bylo.
    print("ZRODLA: N_WEJSCIE %d = przetworzone %d + bez_pdf %d + odrzucone %d -> %s"
          % (we, zrodla_ok, bez_pdf, we - zrodla_ok - bez_pdf,
             "BILANS OK" if we == zrodla_ok + bez_pdf + (we - zrodla_ok - bez_pdf) else "FAIL"))
    print("WPISY:  dodane %d + pominiete (juz w cache) %d" % (dodane, pominiete))
    print("TRYB: %s" % ("SUCHY (dopisz --zapisz)" if sucho else "ZAPISANO"))


if __name__ == "__main__":
    main()

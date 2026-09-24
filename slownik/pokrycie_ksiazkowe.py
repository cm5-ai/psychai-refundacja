#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""POKRYCIE KSIAZKOWE — ile substancji psychiatrycznych z podrecznikow mamy w cache."""
import json, os, re, sys, unicodedata

TU = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TU)
sys.path.insert(0, TU)
import inn

KSIAZKI = [
    ("Jarema", os.path.expanduser("~/mnt/Downloads/psychiatria-marek-jarema_compress.txt")),
    ("Wciorka", os.path.expanduser("~/mnt/Downloads/Psychiatria Tom 1- 3 Podstawy psychiatrii - Wciórka, Rybakowski, Pużyński.txt")),
    ("Stahl", os.path.join(REPO, "zrodla", "ks_stahl.txt")),
]
MIN_SZUK = 4


def kanon_szuk(s):
    s = inn.bez_ogonkow(s or "").lower()
    s = s.replace("x", "ks").replace("ph", "f").replace("th", "t")
    s = s.replace("y", "i").replace("c", "k").replace("qu", "kw")
    return re.sub(r"[^a-z0-9]+", " ", s)


def tematy(k):
    rdzen = k.split("|")[0]
    if rdzen.startswith("CALA:"):
        rdzen = rdzen[5:]
    return {kanon_szuk(t).strip() for t in rdzen.split("+") if len(t.strip()) >= inn.MIN_TEMAT}


def kanon_prod(s):
    s = unicodedata.normalize("NFKC", s or "").replace(" ", " ")
    return re.sub(r"[^a-z0-9]+", "", inn.bez_ogonkow(s).lower())


def main():
    rpl = json.load(open(os.path.join(REPO, "rpl", "RPL_PSYCH.json")))
    prod = rpl["produkty"]
    klucze = {}
    for p in prod:
        k = inn.klucz(p.get("nazwa_powszechna") or "")
        d = klucze.setdefault(k, {"nazwy": set(), "atc": set(), "produkty": set()})
        d["nazwy"].add(p.get("nazwa_powszechna") or "")
        d["atc"].update(p.get("atc") or [])
        d["produkty"].add(p.get("nazwa") or "")
    print("A. REJESTR: produktow %d -> kluczy %d" % (len(prod), len(klucze)))

    teksty = {}
    for nazwa, sciezka in KSIAZKI:
        if not os.path.exists(sciezka):
            print("   BRAK PLIKU: %s" % sciezka); return 2
        teksty[nazwa] = kanon_szuk(open(sciezka, encoding="utf-8", errors="replace").read())
    print("B. KSIAZKI: %s" % ", ".join("%s %.1fMB" % (n, len(t)/1e6) for n, t in teksty.items()))

    idx = json.load(open(os.path.join(REPO, "chpl", "INDEX.json")))["substancje"]
    prod_do_klucza = {}
    for k, d in klucze.items():
        for nz in d["produkty"]:
            prod_do_klucza.setdefault(kanon_prod(nz), set()).add(k)
    mamy, bez_mostu, pl_nazwa = set(), [], {}
    for sub, meta in idx.items():
        traf = set()
        for nz in meta.get("produkty") or []:
            traf |= prod_do_klucza.get(kanon_prod(nz), set())
        if traf:
            mamy |= traf
            for k in traf:
                pl_nazwa.setdefault(k, set()).add(sub)
        else:
            bez_mostu.append(sub)
    print("C. CACHE: substancji %d -> kluczy rejestrowych %d; bez mostu %d %s"
          % (len(idx), len(mamy), len(bez_mostu), sorted(bez_mostu)))

    wym, niewym = {}, []
    for k, d in klucze.items():
        tm = tematy(k)
        gdzie = [n for n, t in teksty.items() if any(x in t for x in tm if len(x) >= MIN_SZUK)]
        (wym.setdefault(k, dict(d, gdzie=gdzie)) if gdzie else niewym.append(k))
    print("D. WZMIANKA: N_WEJSCIE %d = N_ZACHOWANE %d + N_ODRZUCONE %d -> %s"
          % (len(klucze), len(wym), len(niewym), len(klucze) == len(wym)+len(niewym)))

    slepe = sorted(k for k in niewym if k in mamy)
    print("   SLEPA PLAMKA WYSZUKIWANIA (mamy w cache, a szukanie nie trafilo): %d" % len(slepe))
    for k in slepe:
        print("     %-30s pl=%s  nazwy=%s" % (k[:30], sorted(pl_nazwa.get(k, [])),
                                              "; ".join(sorted(klucze[k]["nazwy"]))[:50]))

    maja = sorted(k for k in wym if k in mamy)
    braki = sorted(k for k in wym if k not in mamy)
    print()
    print("WYNIK: wymienionych i zarejestrowanych %d | mamy %d | brak %d | bilans %s"
          % (len(wym), len(maja), len(braki), len(wym) == len(maja)+len(braki)))
    print()
    for k in braki:
        d = wym[k]
        print("  %-34s %-12s %s" % (k[:34], ",".join(sorted(d["atc"]))[:12],
                                    "; ".join(sorted(d["nazwy"]))[:55]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

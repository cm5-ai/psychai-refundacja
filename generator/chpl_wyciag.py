#!/usr/bin/env python3
"""Wyciąg z ChPL dla wskazanych substancji: pobiera PDF z RPL i wypisuje wybrane punkty.
Nic nie zapisuje do repozytorium — wynik idzie do logu i artefaktu (ChPL to cudzy dokument).
Użycie: python3 generator/chpl_wyciag.py "lisdeksamfetamina,metylofenidat" [--punkty 4.2,4.4,4.5,5.2] [--znakow 2500] [--produkt ID]"""
import json, re, os, sys, subprocess, tempfile, argparse, unicodedata

def norm(s):
    s = unicodedata.normalize('NFKD', s.lower()); s = ''.join(c for c in s if not unicodedata.combining(c))
    for a, b in (("ph","f"),("th","t"),("x","ks"),("v","w"),("y","i"),("c","k")): s = s.replace(a, b)
    return s

def pdf_tekst(url):
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "a.pdf")
        if subprocess.run(["curl","-sSfL","--retry","3","-m","120","-o",p,url]).returncode: return None
        if os.path.getsize(p) < 1000: return None
        r = subprocess.run(["pdftotext","-layout",p,"-"], capture_output=True)
        return r.stdout.decode("utf-8","replace") if r.returncode == 0 else None

def punkty(t, chce, limit):
    t = " ".join(t.split())
    ms = list(re.finditer(r'(?<![\d.])([45])\.(\d{1,2})\.?\s+(?=[A-ZŁŚŻŹĆŃÓĘĄ])', t))
    out = {}
    for i, m in enumerate(ms):
        k = f"{m.group(1)}.{m.group(2)}"
        if k not in chce or k in out: continue
        out[k] = t[m.start(): ms[i+1].start() if i+1 < len(ms) else len(t)][:limit]
    return out

a = argparse.ArgumentParser(); a.add_argument("substancje"); a.add_argument("--punkty", default="4.2,4.4,4.5,5.2")
a.add_argument("--znakow", type=int, default=2500); a.add_argument("--produkt"); a.add_argument("--spis", default="rpl/RPL_PSYCH.json")
x = a.parse_args(); chce = set(x.punkty.split(","))
d = json.load(open(x.spis, encoding="utf-8"))
print("# WYCIĄG Z ChPL — punkty:", x.punkty, "| spis RPL stan:", d["metadata"]["stan_na_dzien"])
cele = []
if x.produkt:
    cele = [("(podany ID)", f"https://rejestrymedyczne.ezdrowie.gov.pl/api/rpl/medicinal-products/{x.produkt}/characteristic")]
else:
    for s in [q.strip() for q in x.substancje.split(",") if q.strip()]:
        q = norm(s)[:6]
        pr = [p for p in d["produkty"] if q in norm(p.get("substancja","") + " " + p.get("nazwa",""))]
        if not pr: print(f"\n## {s.upper()}: BRAK W SPISIE RPL (spis obejmuje wybrane ATC) — podaj --produkt ID albo poszerz spis"); continue
        widz = {}
        for p in pr: widz.setdefault(p.get("nazwa","?"), p)
        for p in list(widz.values())[:2]: cele.append((f"{s.upper()} / {p.get('nazwa')} {p.get('moc','')}", p.get("chpl")))
for etykieta, url in cele:
    print(f"\n## {etykieta}\nŹRÓDŁO: {url}")
    t = pdf_tekst(url)
    if not t: print("BŁĄD POBRANIA/ODCZYTU PDF"); continue
    got = punkty(t, chce, x.znakow)
    for k in sorted(chce):
        print(f"\n### ChPL {k}\n" + (got.get(k) or "— nie znaleziono punktu w tym dokumencie —"))

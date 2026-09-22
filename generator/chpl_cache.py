#!/usr/bin/env python3
"""Budowa CHPL_CACHE: jeden plik JSON na substancje, commitowany do repo.
Runtime czyta pojedynczy plik z raw.githubusercontent.com - nie caly cache.
Uzycie: python3 generator/chpl_cache.py --lista zrodla/chpl_cache_lista.txt [--tylko lek1,lek2] [--punkty 4.1,4.2,4.3,4.4,4.5,4.6,4.8,5.2]"""
import json, re, os, sys, subprocess, tempfile, argparse, unicodedata, hashlib, datetime

KATALOG = "chpl"
LIMIT_ZNAKOW = 6000          # na punkt; ChPL 4.4 potrafi byc dlugi
MAX_PRODUKTOW = 3            # na substancje; ChPL nalezy do PRODUKTU


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    for a, b in (("qu", "kw"), ("ph", "f"), ("th", "t"), ("x", "ks"), ("v", "w"), ("y", "i"), ("c", "k")):
        s = s.replace(a, b)
    return s


def szkielet(s):
    return re.sub(r'[^bcdfghjklmnpqrstvwxz]', '', norm(s))


SYNONIMY = {"walproinian": ["valproicum", "valproas"], "kwas walproinowy": ["valproicum"],
            "lit": ["lithii", "lithium"], "weglan litu": ["lithii carbonas"]}


def dopasuj(zapyt, produkty):
    """Pusta lista = NIE ZNALEZIONO. To nie znaczy, ze produktu nie ma."""
    trafy, widziane = [], set()
    q = szkielet(zapyt)[:5]
    if len(q) >= 4:
        for p in produkty:
            if q in szkielet(p.get("substancja", "") + " " + p.get("nazwa", "")):
                if id(p) not in widziane:
                    widziane.add(id(p)); trafy.append(p)
    for syn in SYNONIMY.get(zapyt.lower().strip(), []):
        qs = norm(syn)[:5]
        for p in produkty:
            if qs in norm(p.get("substancja", "") + " " + p.get("nazwa", "")):
                if id(p) not in widziane:
                    widziane.add(id(p)); trafy.append(p)
    return trafy


def pdf_tekst(url):
    """Zwraca (tekst, sha256_pdf) albo (None, powod)."""
    if not url:
        return None, "BRAK URL ChPL W SPISIE"
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "a.pdf")
        r = subprocess.run(["curl", "-sSfL", "--retry", "3", "-m", "120", "-o", p, url])
        if r.returncode:
            return None, f"BLAD POBRANIA (curl {r.returncode})"
        if os.path.getsize(p) < 1000:
            return None, "PLIK ZA MALY - to nie jest ChPL"
        sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
        r2 = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True)
        if r2.returncode:
            return None, "BLAD pdftotext"
        return (r2.stdout.decode("utf-8", "replace"), sha)


def punkty(t, chce):
    t = " ".join(t.split())
    ms = list(re.finditer(r'(?<![\d.])([45])\.(\d{1,2})\.?\s+(?=[A-ZŁŚŻŹĆŃÓĘĄ])', t))
    out = {}
    for i, m in enumerate(ms):
        k = f"{m.group(1)}.{m.group(2)}"
        if k not in chce or k in out:
            continue
        out[k] = t[m.start(): ms[i + 1].start() if i + 1 < len(ms) else len(t)][:LIMIT_ZNAKOW]
    return out


def plik_nazwy(s):
    return re.sub(r'[^a-z0-9]+', '_', norm(s)).strip('_')


ap = argparse.ArgumentParser()
ap.add_argument("--lista", default="zrodla/chpl_cache_lista.txt")
ap.add_argument("--tylko", default="")
ap.add_argument("--punkty", default="4.1,4.2,4.3,4.4,4.5,4.6,4.8,5.2")
ap.add_argument("--spis", default="rpl/RPL_PSYCH.json")
x = ap.parse_args()
chce = set(x.punkty.split(","))
dzis = datetime.date.today().isoformat()

d = json.load(open(x.spis, encoding="utf-8"))
substancje = [l.strip() for l in open(x.lista, encoding="utf-8") if l.strip() and not l.startswith("#")]
if x.tylko:
    chciane = {q.strip().lower() for q in x.tylko.split(",") if q.strip()}
    substancje = [s for s in substancje if s.lower() in chciane]

os.makedirs(KATALOG, exist_ok=True)
indeks = {}
if os.path.exists(f"{KATALOG}/INDEX.json"):
    indeks = json.load(open(f"{KATALOG}/INDEX.json", encoding="utf-8")).get("substancje", {})

for s in substancje:
    pr = dopasuj(s, d["produkty"])
    plik = plik_nazwy(s)
    if not pr:
        print(f"{s:22} NIE ZNALEZIONO w spisie RPL (nie znaczy, ze produktu nie ma)")
        indeks[s] = {"plik": None, "stan": "NIE_ZNALEZIONO_W_SPISIE", "sprawdzono": dzis}
        continue
    widz = {}
    for p in pr:
        widz.setdefault(p.get("nazwa", "?"), p)
    wybrane = list(widz.values())[:MAX_PRODUKTOW]
    rekord = {"substancja": s, "pobrano": dzis, "punkty_zadane": sorted(chce),
              "uwaga": "ChPL nalezy do PRODUKTU. Rozne produkty tej samej substancji moga sie roznic. Brak punktu != brak tresci.",
              "produkty": []}
    for p in wybrane:
        t, info = pdf_tekst(p.get("chpl"))
        if t is None:
            rekord["produkty"].append({"nazwa": p.get("nazwa"), "moc": p.get("moc"),
                                       "zrodlo": p.get("chpl") or "", "stan": info, "punkty": {}})
            print(f"{s:22} {p.get('nazwa'):22} {info}")
            continue
        got = punkty(t, chce)
        rekord["produkty"].append({"nazwa": p.get("nazwa"), "moc": p.get("moc"),
                                   "podmiot": p.get("podmiot"), "zrodlo": p.get("chpl"),
                                   "sha256_pdf": info, "stan": "OK",
                                   "punkty": {k: got[k] for k in sorted(got)},
                                   "punkty_nieznalezione": sorted(chce - set(got))})
        print(f"{s:22} {p.get('nazwa'):22} OK  punkty: {','.join(sorted(got)) or 'brak'}")
    json.dump(rekord, open(f"{KATALOG}/{plik}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    indeks[s] = {"plik": f"{KATALOG}/{plik}.json", "stan": "OK", "pobrano": dzis,
                 "produkty": [p["nazwa"] for p in rekord["produkty"]]}

json.dump({"opis": "Indeks CHPL_CACHE. Wlascicielem pinu jest sekcja CHPL_WYCIAG w module 19.",
           "zbudowano": dzis, "punkty": sorted(chce), "substancje": indeks},
          open(f"{KATALOG}/INDEX.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nGOTOWE: {len([v for v in indeks.values() if v.get('stan') == 'OK'])} substancji w cache, indeks: {KATALOG}/INDEX.json")

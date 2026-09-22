#!/usr/bin/env python3
"""TEST ODBIORU CHPL_CACHE. Zwraca kod 1, gdy cokolwiek nie przejdzie.
Sprawdza to, co LEZY W REPO, a nie to, co skrypt budujacy twierdzi.
Kazdy test jest niezalezny od funkcji uzytych do budowy cache'u -
inaczej test powtarzalby ten sam blad co generator."""
import json, os, re, sys, glob, unicodedata, datetime

KATALOG = "chpl"
MAX_WIEK_DNI = 45
bledy, ostrzezenia = [], []


def bez_ogonkow(s):
    s = unicodedata.normalize('NFKD', s.lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


def rdzen(s, n=5):
    """Niezalezna od generatora: zdejmuje ogonki, zostawia spolgloski."""
    return re.sub(r'[^bcdfghjklmnpqrstvwxz]', '', bez_ogonkow(s)
                  .replace('ph', 'f').replace('th', 't').replace('qu', 'kw')
                  .replace('x', 'ks').replace('v', 'w').replace('y', 'i')
                  .replace('c', 'k').replace('z', 's'))[:n]


if not os.path.isdir(KATALOG):
    print("FAIL: brak katalogu", KATALOG); sys.exit(1)
idx = json.load(open(f"{KATALOG}/INDEX.json", encoding="utf-8"))
subs = idx["substancje"]

# T1. Kazdy plik z INDEX istnieje.
for nazwa, v in subs.items():
    if v.get("plik") and not os.path.exists(v["plik"]):
        bledy.append(f"T1 {nazwa}: INDEX wskazuje {v['plik']}, pliku nie ma")

# T2. Zadnych sierot - plik, ktorego INDEX nie wskazuje.
uzywane = {os.path.basename(v["plik"]) for v in subs.values() if v.get("plik")}
for f in glob.glob(f"{KATALOG}/*.json"):
    b = os.path.basename(f)
    if b != "INDEX.json" and b not in uzywane:
        bledy.append(f"T2 sierota: {f} nie jest wskazany przez INDEX")

# T3. Nazwa pliku odpowiada nazwie substancji (wykrywa przemianowania).
for nazwa, v in subs.items():
    if v.get("plik"):
        oczek = re.sub(r'[^a-z0-9]+', '_', bez_ogonkow(nazwa)).strip('_') + ".json"
        if os.path.basename(v["plik"]) != oczek:
            bledy.append(f"T3 {nazwa}: plik {os.path.basename(v['plik'])}, oczekiwany {oczek}")

# T4-T8 na zawartosci.
for nazwa, v in subs.items():
    if not v.get("plik"):
        continue
    d = json.load(open(v["plik"], encoding="utf-8"))
    if d.get("substancja") != nazwa:
        bledy.append(f"T4 {nazwa}: pole substancja={d.get('substancja')}")
    if not d.get("produkty"):
        bledy.append(f"T4 {nazwa}: zero produktow przy stanie {v.get('stan')}")
    r = rdzen(nazwa)
    for p in d.get("produkty", []):
        etykieta = f"{nazwa}/{p.get('nazwa')}"
        if p.get("stan") != "OK":
            ostrzezenia.append(f"T5 {etykieta}: stan {p.get('stan')}")
            continue
        # T6. Uciecia.
        uc = p.get("punkty_uciete")
        if uc is None:
            bledy.append(f"T6 {etykieta}: brak pola punkty_uciete - plik ze starego generatora")
        elif uc:
            bledy.append(f"T6 {etykieta}: punkty uciete {uc}")
        # T7. Sygnatura zrodla.
        if not p.get("sha256_pdf"):
            bledy.append(f"T7 {etykieta}: brak sha256_pdf")
        if not (p.get("zrodlo") or "").startswith("https://rejestrymedyczne.ezdrowie.gov.pl/"):
            bledy.append(f"T7 {etykieta}: zrodlo spoza RPL: {p.get('zrodlo')}")
        # T8. KRZYZOWE PODPIECIE: tekst ChPL musi zawierac nazwe produktu
        # ALBO rdzen substancji. To lapie imipramina->Anafranil.
        tekst = " ".join(p.get("punkty", {}).values()).lower()
        marka = bez_ogonkow(p.get("nazwa", "")).split()[0] if p.get("nazwa") else ""
        ma_marke = marka and marka in bez_ogonkow(tekst)
        ma_rdzen = bool(r) and any(rdzen(w) == r for w in re.findall(r'[a-ząćęłńóśźż]+', bez_ogonkow(tekst)))
        if not (ma_marke or ma_rdzen):
            bledy.append(f"T8 {etykieta}: w tresci ChPL nie ma ani marki, ani rdzenia substancji - podejrzenie cudzej ChPL")
        # T9. Punkt nie moze byc pusty.
        for k, txt in p.get("punkty", {}).items():
            if len(txt.strip()) < 40:
                bledy.append(f"T9 {etykieta} pkt {k}: tekst krotszy niz 40 znakow")

# T10. Wiek cache.
try:
    wiek = (datetime.date.today() - datetime.date.fromisoformat(idx["zbudowano"])).days
    if wiek > MAX_WIEK_DNI:
        bledy.append(f"T10 cache ma {wiek} dni, prog {MAX_WIEK_DNI}")
except Exception as e:
    bledy.append(f"T10 nieczytelna data budowy: {e}")

print(f"substancji w INDEX: {len(subs)} | plikow: {len(glob.glob(KATALOG + '/*.json'))}")
for o in ostrzezenia[:40]:
    print("  UWAGA:", o)
if ostrzezenia[40:]:
    print(f"  ... i {len(ostrzezenia)-40} dalszych uwag")
for b in bledy[:60]:
    print("  BLAD:", b)
if bledy[60:]:
    print(f"  ... i {len(bledy)-60} dalszych bledow")
print(f"\nUWAG: {len(ostrzezenia)} | BLEDOW: {len(bledy)}")
if bledy:
    print("TEST ODBIORU: NIE PRZESZEDL"); sys.exit(1)
print("TEST ODBIORU: PRZESZEDL")

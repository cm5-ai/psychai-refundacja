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
        # T5b. NAGLOWEK PUNKTU MUSI ODPOWIADAC JEGO NUMEROWI.
        # 2026-09-23: 42 z 1496 punktow nioslo tresc INNEGO punktu, a test
        # odbioru tego nie widzial - sprawdzal uciecia i sha, nie tozsamosc
        # sekcji. Lurazydon mial w 4.3 tekst o zamianie leku przeciwpsycho-
        # tycznego zamiast przeciwwskazan. Wyciag zakotwiczal sie na
        # odsylaczu "patrz punkt 4.5." wewnatrz tekstu.
        nz = (p.get("NAGLOWEK_NIEZGODNY") or {}).get("punkty") or []
        for _k in nz:
            ostrzezenia.append(f"T5b {etykieta}: punkt {_k} ma tresc innego punktu - "
                               f"KARANTANNA, nie cytowac")
        OCZEK = {"4.1": "wskazania", "4.2": "dawkowanie", "4.3": "przeciwwskazania",
                 "4.4": "ostrzeżenia", "4.5": "interakcje", "4.6": "wpływ na płodność",
                 "4.8": "działania niepożądane", "5.2": "właściwości farmakokinetyczne"}
        for _k, _slowo in OCZEK.items():
            _t = " ".join((p["punkty"].get(_k) or "").split())
            if _t and _slowo not in _t[:90].lower() and _k not in nz:
                bledy.append(f"T5b {etykieta}: punkt {_k} nie ma w naglowku slowa "
                             f"'{_slowo}' i NIE jest oznaczony jako niezgodny")

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
        # T8b. DOMINACJA CUDZEJ SUBSTANCJI. Sama marka NIE wystarcza: produkt
        # omylkowo podpiety pod inna substancje nadal zawiera wlasna marke.
        # To przepuscilo prometazyna<-Pramatis (escitalopram), chlordiazepoksyd
        # <-Convulex (walproinian) i zamiane chlorpromazyna<->chlorprotiksen.
        slowa_txt = re.findall(r'[a-z]+', bez_ogonkow(tekst))
        # Nazwa handlowa NIE liczy sie jako wlasny rdzen: "Pramatis" ma ten sam
        # szkielet spolgloskowy co "prometazyna" (prmts) i wlasnie dlatego
        # zostala blednie dopasowana. Liczymy tylko slowa spoza marki.
        marka_sl = set(re.findall(r'[a-z]+', bez_ogonkow(p.get("nazwa", ""))))
        wlasny = sum(1 for w in slowa_txt if rdzen(w) == r and w not in marka_sl)
        obce = {}
        for inna in subs:
            ri = rdzen(inna)
            if not ri or ri == r or len(ri) < 5:
                continue
            n = sum(1 for w in slowa_txt if rdzen(w) == ri)
            if n:
                obce[inna] = n
        if obce and wlasny == 0:
            krol = max(obce.items(), key=lambda x: x[1])
            if krol[1] >= 3:
                bledy.append(f"T8b {etykieta}: tekst zdominowany przez {krol[0]} (x{krol[1]}), wlasnego rdzenia brak - CUDZA ChPL")
        # T9. Punkt nie moze byc pusty.
        for k, txt in p.get("punkty", {}).items():
            if len(txt.strip()) < 40:
                bledy.append(f"T9 {etykieta} pkt {k}: tekst krotszy niz 40 znakow")

# T16. TEN SAM PRODUKT POD DWIEMA SUBSTANCJAMI = pewne skazenie jednej z nich.
gdzie = {}
for nazwa, v in subs.items():
    if not v.get("plik"):
        continue
    try:
        d = json.load(open(v["plik"], encoding="utf-8"))
    except Exception:
        continue
    for p in d.get("produkty", []):
        gdzie.setdefault(p.get("nazwa", ""), set()).add(nazwa)
for prod, gdz in sorted(gdzie.items()):
    if len(gdz) > 1:
        bledy.append(f"T16 produkt {prod}: przypisany do {len(gdz)} substancji: {sorted(gdz)}")

# T10. Wiek cache.
try:
    wiek = (datetime.date.today() - datetime.date.fromisoformat(idx["zbudowano"])).days
    if wiek > MAX_WIEK_DNI:
        bledy.append(f"T10 cache ma {wiek} dni, prog {MAX_WIEK_DNI}")
except Exception as e:
    bledy.append(f"T10 nieczytelna data budowy: {e}")

# T18. GENERATOR NIE MOZE SAM OGLOSIC KWARANTANNY.
# Kwarantanna jest decyzja czlowieka o cache, ktorego nie da sie przebudowac.
# Gdyby generator umial ja wystawiac, "legalizowalby" wlasne uciecia - a wtedy
# T6 przestaje cokolwiek chronic. Dlatego: slowa KWARANTANNA nie ma prawa byc
# w kodzie budujacym cache.
try:
    _zrodlo = open("generator/chpl_cache.py", encoding="utf-8").read()
    if "KWARANTANNA" in _zrodlo:
        bledy.append("T18: generator chpl_cache.py zawiera slowo KWARANTANNA - "
                     "generator nie moze sam legalizowac wlasnych uciec")
except OSError:
    ostrzezenia.append("T18: nie odczytano generator/chpl_cache.py")

# STATUS KWARANTANNY - naglowek raportu. NIE zmienia werdyktu: plik
# w kwarantannie z definicji nie jest cache produkcyjnym.
_kw = []
for _f in sorted(glob.glob(KATALOG + "/*.json")):
    if os.path.basename(_f) == "INDEX.json":
        continue
    try:
        _d = json.load(open(_f, encoding="utf-8"))
    except Exception:
        continue
    if _d.get("STATUS") == "KWARANTANNA":
        _o = _u = 0
        for _p in _d.get("produkty", []):
            _k = _p.get("KWARANTANNA") or {}
            _o += len(_k.get("odrzucone") or [])
            _u += len(_k.get("uciete") or [])
        _kw.append((_d.get("substancja"), _o, _u))
        _kw_data = _d.get("KWARANTANNA_DATA", "?")
if _kw:
    print("=" * 60)
    print("CACHE W KWARANTANNIE od", _kw_data)
    print("plikow:", len(_kw),
          "| punktow odrzuconych (tresc obca):", sum(x[1] for x in _kw),
          "| oznaczonych jako uciete:", sum(x[2] for x in _kw))
    print("TEN CACHE NIE JEST PRODUKCYJNY. Runtime czyta go wylacznie przez")
    print("punkty_nieznalezione i punkty_uciete (modul 19). Przebudowa: rejestr")
    print("nieosiagalny 2026-09-23.")
    print("=" * 60)

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

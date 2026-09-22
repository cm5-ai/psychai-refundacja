#!/usr/bin/env python3
"""Automat wykazu MZ (tylko przygotowanie kandydata; zatwierdza lekarz).
1) Nowy wykaz „na 1 …” nowszy niż zrodla/ostatni_wykaz.txt -> pobiera xlsx
   do zrodla/, wypisuje parametry dla nowy-wykaz.yml (GITHUB_OUTPUT).
2) Nowe obwieszczenie ZMIENIAJĄCE / SPROSTOWANIE (spoza zrodla/obwieszczenia_znane.txt)
   -> alarm (exit 2): wymaga decyzji, nie jest przetwarzane automatycznie.
Nic nie wdraża: nie zmienia REFUNDACJA_DATA.json ani pinów w 39."""
import re, os, sys, html, datetime, urllib.request
BASE = "https://www.gov.pl"
LISTA = BASE + "/web/zdrowie/obwieszczenia-ministra-zdrowia-lista-lekow-refundowanych"
UA = {"User-Agent": "Mozilla/5.0 (psychai-refundacja automat)"}
MIES = {"stycznia":1,"lutego":2,"marca":3,"kwietnia":4,"maja":5,"czerwca":6,"lipca":7,
        "sierpnia":8,"września":9,"października":10,"listopada":11,"grudnia":12}
ZNANE = "zrodla/obwieszczenia_znane.txt"
def get(u, raw=False):
    b = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()
    return b if raw else html.unescape(b.decode("utf-8", "replace"))
def linki(t):
    for href, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, flags=re.S):
        txt = re.sub(r"<[^>]+>", " ", txt).replace("​", "")
        yield (href if href.startswith("http") else BASE + href), re.sub(r"\s+", " ", txt).strip()
def data(s, prefix):
    m = re.search(prefix + r"\s+(\d{1,2})\s+(" + "|".join(MIES) + r")\s+(\d{4})", s)
    return datetime.date(int(m.group(3)), MIES[m.group(2)], int(m.group(1))) if m else None
def out(k, v):
    print(f"{k}={v}")
    if os.environ.get("GITHUB_OUTPUT"):
        open(os.environ["GITHUB_OUTPUT"], "a").write(f"{k}={v}\n")
obw = [(h, x) for h, x in linki(get(LISTA)) if "wykazu refundowanych" in x and re.search(r"(?i)obwieszczen|sprostowan", x)]
if not obw: print("::error::Brak obwieszczeń na stronie MZ — zmienił się układ strony."); sys.exit(1)
typ = lambda x: "ZMIENIAJĄCE" if "zmieniaj" in x.lower() else ("SPROSTOWANIE" if "sprostowan" in x.lower() else "WYKAZ")
# --- 2) obwieszczenia zmieniające / sprostowania
znane = set(open(ZNANE, encoding="utf-8").read().split()) if os.path.exists(ZNANE) else None
if znane is None:  # pierwsze uruchomienie: stan wyjściowy, bez alarmów
    open(ZNANE, "w", encoding="utf-8").write("\n".join(h for h, _ in obw) + "\n"); out("znane_init", "1"); znane = {h for h, _ in obw}
alarm = [(h, x) for h, x in obw if h not in znane and typ(x) != "WYKAZ"]
# --- 1) nowy wykaz główny
m, y = open("zrodla/ostatni_wykaz.txt", encoding="utf-8").read().split()[1:3]
znany = datetime.date(int(y), MIES[m], 1)
glowne = sorted(((data(x, r"na"), h, x) for h, x in obw if typ(x) == "WYKAZ" and data(x, r"na")), reverse=True)
vf, h, x = glowne[0]
print(f"Znany wykaz: {znany}; najnowszy na stronie: {vf}")
if vf > znany:
    s = get(h)
    zal = [(hh, xx) for hh, xx in linki(s) if re.search(r"(\d+W)\s*_?\s*zalacznik\s*_?\s*do\s*_?\s*obwieszczenia.*\.xlsx", xx, re.I)]
    if not zal: print(f"::error::Nowy wykaz na {vf}, ale nie znalazłem xlsx załącznika: {h}"); sys.exit(1)
    hh, xx = zal[0]
    ozn = re.search(r"(\d+W)", xx).group(1)
    if os.path.isdir(f"kandydaci/{ozn}"):
        print(f"Kandydat {ozn} już istnieje — nic do zrobienia."); out("nowy", "0")
    else:
        b = get(hh, raw=True)
        if len(b) < 100_000 or not b[:2] == b"PK": print("::error::Pobrany plik nie wygląda na xlsx."); sys.exit(1)
        plik = f"{ozn}_zalacznik_do_obwieszczenia.xlsx"
        open(f"zrodla/{plik}", "wb").write(b)
        da = data(x, r"z dnia")
        cvu = datetime.date(vf.year + (vf.month + 2) // 12, (vf.month + 2) % 12 + 1, 1)
        out("nowy", "1"); out("plik", plik); out("oznaczenie", ozn); out("valid_from", vf.isoformat())
        out("data_aktu", da.isoformat() if da else "NIE_PODANO"); out("check_valid_until", cvu.isoformat()); out("url", h)
        print(f"::warning::NOWY WYKAZ {ozn} na {vf}: pobrano {plik} ({len(b)//1024} KB). Buduję kandydata. Pozycję Dz. Urz. uzupełnij przy zatwierdzeniu.")
else:
    out("nowy", "0")
if alarm:
    for h2, x2 in alarm: print(f"::error::NOWE {typ(x2)}: {x2} — {h2}")
    open(ZNANE, "a", encoding="utf-8").write("\n".join(h2 for h2, _ in alarm) + "\n")
    out("alarm", "1")

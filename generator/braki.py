"""BRAKI — wykaz MZ produktów zagrożonych brakiem dostępności (Dziennik Urzędowy MZ, PDF).
Szuka nowych pozycji Dziennika po ostatniej znanej (zrodla/braki_stan.json), rozpoznaje obwieszczenie po tytule,
wyciąga GTIN-y. Wyjście: braki/BRAKI.json (dla recepta.py --braki), braki/PSYCH.md (leki psychiatryczne z listy)."""
import json, re, os, sys, subprocess, tempfile, datetime

MIES = {m: i for i, m in enumerate(["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"], 1)}
TYTUL = re.compile(r"zagrożonych\s+brakiem\s+dostępności", re.I)

def pdf_txt(url):
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "a.pdf")
        r = subprocess.run(["curl", "-sSfL", "--retry", "2", "-m", "90", "-o", p, url])
        if r.returncode or not os.path.exists(p): return None
        r = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None

def data_pl(s):
    m = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", s)
    return datetime.date(int(m.group(3)), MIES[m.group(2)], int(m.group(1))).isoformat() if m and m.group(2) in MIES else None

def main():
    stan = json.load(open("zrodla/braki_stan.json")) if os.path.exists("zrodla/braki_stan.json") else {"rok": 2026, "poz": 49}
    rok, poz = stan["rok"], stan["poz"]
    znalezione, puste, sprawdzone = None, 0, 0
    for r_ in (rok, rok + 1) if datetime.date.today().year > rok else (rok,):
        p = poz + 1 if r_ == rok else 1
        puste = 0
        while puste < 6 and sprawdzone < 120:
            t = pdf_txt("https://dziennikmz.mz.gov.pl/DUM_MZ/%d/%d/akt.pdf" % (r_, p)); sprawdzone += 1
            if t is None: puste += 1
            else:
                puste = 0; stan.update(rok=r_, poz=p)
                if TYTUL.search(" ".join(t[:3000].split())): znalezione = (r_, p, t)
            p += 1
    os.makedirs("braki", exist_ok=True)
    if not znalezione:
        json.dump(stan, open("zrodla/braki_stan.json", "w")); print("Brak nowego obwieszczenia (sprawdzono %d pozycji Dziennika)." % sprawdzone); return
    r_, p, t = znalezione
    naglowek = " ".join(t[:3000].split())
    z_dnia = data_pl(naglowek.split("z dnia", 1)[1] if "z dnia" in naglowek else "")
    m = re.search(r"na dzień\s+(\d{1,2}\s+\S+\s+\d{4})", naglowek); stan_na = data_pl(m.group(1)) if m else None
    poz_ = []
    for l in t.splitlines():
        for g in re.findall(r"(?<!\d)(0?590\d{10})(?!\d)", l):
            poz_.append({"gtin": g.zfill(14), "linia": " ".join(l.split())[:220]})
    gt = sorted({x["gtin"] for x in poz_})
    if len(gt) < 20: print("BLOKADA: podejrzanie mało GTIN (%d) w Dz.Urz.MZ %d poz. %d" % (len(gt), r_, p)); sys.exit(2)
    out = {"zrodlo": "Obwieszczenie MZ w sprawie wykazu produktów zagrożonych brakiem dostępności", "dziennik": "Dz.Urz.MZ %d poz. %d" % (r_, p),
           "url": "https://dziennikmz.mz.gov.pl/DUM_MZ/%d/%d/akt.pdf" % (r_, p), "z_dnia": z_dnia, "stan_na": stan_na,
           "pobrano": datetime.date.today().isoformat(), "liczba_gtin": len(gt), "gtin": gt}
    stary = json.load(open("braki/BRAKI.json")) if os.path.exists("braki/BRAKI.json") else {}
    nowe = stary.get("dziennik") != out["dziennik"]
    json.dump(out, open("braki/BRAKI.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # przecięcie ze spisem RPL (leki psychiatryczne)
    psych = []
    if os.path.exists("rpl/RPL_PSYCH.json"):
        rpl = json.load(open("rpl/RPL_PSYCH.json", encoding="utf-8"))
        idx = {o["gtin"]: p_ for p_ in rpl["produkty"] for o in p_["opakowania"] if o["gtin"]}
        for g in gt:
            if g in idx: psych.append("- %s %s (%s) — GTIN %s" % (idx[g]["nazwa"], idx[g]["moc"], idx[g]["nazwa_powszechna"], g))
    R = ["# Braki MZ — leki psychiatryczne", "", "%s z dnia %s, stan na %s — %d GTIN ogółem, psychiatrycznych: %d" % (out["dziennik"], z_dnia, stan_na, len(gt), len(psych)), "", out["url"], ""] + sorted(psych)
    open("braki/PSYCH.md", "w", encoding="utf-8").write("\n".join(R) + "\n")
    stan.update(rok=r_, poz=p); json.dump(stan, open("zrodla/braki_stan.json", "w"))
    print(R[2])
    if nowe: open("ZGLOSZENIE", "w", encoding="utf-8").write("Nowe obwieszczenie o brakach: %s (stan na %s).\nLeki psychiatryczne na liście: %d\n\n%s\n\nSzczegóły: braki/PSYCH.md" % (out["dziennik"], stan_na, len(psych), "\n".join(sorted(psych)[:40])))

if __name__ == "__main__": main()

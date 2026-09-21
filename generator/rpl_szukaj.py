"""Wyszukiwarka w spisie RPL (rpl/RPL_PSYCH.json) do użytku w wątku wizyty.
Użycie: python3 rpl_szukaj.py RPL_PSYCH.json "kwetiapina" [--moc "100 mg"] [--wszystkie] [--today YYYY-MM-DD]
Wypisuje: produkty (marka, moc, postać, podmiot), opakowania w obrocie (GTIN, kategoria), link ChPL, komunikaty.
NIE wypisuje refundacji (fakty refundacyjne wyłącznie z REFUNDACJA_ENGINE) ani dawkowania."""
import json, sys, re, unicodedata, datetime, argparse

def norm(s):
    s = unicodedata.normalize('NFKD', s.lower()); s = ''.join(c for c in s if not unicodedata.combining(c))
    for a, b in (("qu", "kw"), ("ph", "f"), ("th", "t"), ("x", "ks"), ("v", "w"), ("y", "i"), ("c", "k"), ("ł", "l")):
        s = s.replace(a, b)
    return s

def stem(s):
    s = norm(s).strip()
    return re.sub(r'(um|us|a|i|e|y|u|o)$', '', s)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plik"); ap.add_argument("szukaj"); ap.add_argument("--moc"); ap.add_argument("--wszystkie", action="store_true")
    ap.add_argument("--today"); ap.add_argument("--max", type=int, default=15)
    a = ap.parse_args()
    d = json.load(open(a.plik, encoding='utf-8')); m = d["metadata"]
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    stan = datetime.date.fromisoformat(m["stan_na_dzien"]); wiek = (today - stan).days
    print("RPL_SPIS | stan %s | wiek %d dni | %s" % (stan, wiek, "AKTUALNY" if wiek <= 14 else "PRZETERMINOWANY (>14 dni) — potwierdź w RPL"))
    slowa = [w for w in re.split(r'\s+', a.szukaj.strip()) if w]
    def prefy(w):
        q = stem(w); return [x for x in dict.fromkeys([q if len(q) < 6 else q[:max(6, len(q) - 1)], q[:6], q[:5]]) if len(x) >= 3] or [norm(w)]
    hits = []
    for poziom in range(3):
        for p in d["produkty"]:
            toks = [norm(t) for t in re.split(r'[\s,;/()+-]+', " ".join([p["nazwa"], p["nazwa_powszechna"], p["substancja"]])) if t]
            if all(any(t.startswith(prefy(w)[min(poziom, len(prefy(w)) - 1)]) for t in toks) for w in slowa):
                if a.moc and norm(a.moc).replace(" ", "") not in norm(p["moc"]).replace(" ", ""): continue
                hits.append(p)
        if hits: break
    if not hits:
        print("BRAK_W_SPISIE: '%s' — spis obejmuje ATC %s; brak trafienia ≠ brak rejestracji. Sprawdź RPL." % (a.szukaj, ",".join(m["atc_prefiksy"]))); return
    subst = sorted({p["nazwa_powszechna"] for p in hits})
    print("SUBSTANCJE:", "; ".join(subst))
    print("PRODUKTY: %d" % len(hits))
    # zestawienie moc/postać w obrocie (opakowanie z GTIN, bez statusu)
    obrot = {}
    for p in hits:
        ok = [o for o in p["opakowania"] if o["gtin"] and not o["status"]]
        if ok: obrot.setdefault(p["postac"], set()).add(p["moc"])
    def mk(x):
        n = re.match(r'([\d,\.]+)', x); return (float(n.group(1).replace(',', '.')) if n else 1e9, x)
    print("POSTACI I MOCE (opakowania z GTIN, nieskasowane):")
    for f in sorted(obrot): print("  %s: %s" % (f, ", ".join(sorted(obrot[f], key=mk))))
    n = 0
    print("SZCZEGÓŁY:")
    for p in sorted(hits, key=lambda p: (p["nazwa_powszechna"], p["postac"], mk(p["moc"]), p["nazwa"])):
        op = p["opakowania"] if a.wszystkie else [o for o in p["opakowania"] if o["gtin"] and not o["status"]]
        if not op and not a.wszystkie: continue
        n += 1
        if n > a.max: print("  ... (ucięto po %d; zawęź: --moc albo nazwa handlowa)" % a.max); break
        opis = "; ".join("%s %s%s%s" % (o["opis"], o["kategoria"], " GTIN " + o["gtin"] if o["gtin"] else " bez GTIN", " [" + o["status"] + "]" if o["status"] else "") for o in op)
        print("  %s | %s | %s | %s | %s" % (p["nazwa"], p["moc"], p["postac"], p["podmiot"], opis))
        print("     ChPL: %s" % p["chpl"] + ("  KOMUNIKATY: " + " ".join(k for k in p["komunikaty_bezpieczenstwa"] if k.startswith("http")) if p["komunikaty_bezpieczenstwa"] else ""))
    ukryte = sum(1 for p in hits if not any(o["gtin"] and not o["status"] for o in p["opakowania"]))
    if ukryte and not a.wszystkie: print("POMINIĘTO %d produktów bez opakowań w obrocie (bez GTIN / skasowane) — --wszystkie pokazuje." % ukryte)
    print("PIN: [RPL_SPIS | stan %s | sha %s]" % (stan, m["sha256_zrodla"][:12]))

if __name__ == "__main__": main()

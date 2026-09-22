"""Spis leków psychiatrycznych z eksportu RPL (CSV) + zestawienie z danymi refundacji.
Wejście: RPL CSV, REFUNDACJA_DATA.json. Wyjście: rpl/RPL_PSYCH.json, rpl/RAPORT.md, rpl/KOMUNIKATY.md."""
import csv, io, json, re, sys, os, hashlib, collections, datetime
ATC_PREFIX = ("N03", "N05", "N06", "N07BB", "N07BC", "N02BF", "N02AE01", "C02AC02", "R06AD02", "N04AA", "N04BB", "C07AA05")   # przeciwpadaczkowe, psycholeptyki, psychoanaleptyki, uzależnienia, gabapentyna/pregabalina, buprenorfina
START = re.compile(r'(?:\b(\d{8,14})\s*¦\s*)?\b(Rpw|Rpz|Rp|OTC|Lz)\s*¦')
OLD = re.compile(r'(\d{8,14})\s*¦\s*([^¦]*?)\s*¦\s*(\d+)\s+(.*?)(?=\s+\d{8,14}\s*¦|$)', re.S)   # parser kontrolny (poprzednia wersja)

def parse(s):
    ms = list(START.finditer(s)); out = []
    for i, m in enumerate(ms):
        body = s[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(s)]
        f = [x.strip() for x in body.split('¦')]
        status, pozw, pid, opis, uwaga = None, None, None, "", None
        for j, x in enumerate(f):
            if re.fullmatch(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+', x): status = x; continue
            if re.fullmatch(r'[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż .&-]+', x): uwaga = x; continue
            if re.match(r'EU/\d', x): pozw = x; continue
            mm = re.match(r'(\d+)\s*(.*)', x, re.S)
            if mm: pid = mm.group(1); opis = " ".join([mm.group(2)] + f[j + 1:]); break
            opis = " ".join(f[j:]); break
        out.append({"gtin": m.group(1).zfill(14) if m.group(1) else None, "kategoria": m.group(2), "status": status,
                    "pozwolenie_eu": pozw, "id_opakowania": pid, "opis": " ".join(opis.replace('¦', ' ').split()),
                    **({"uwaga": uwaga} if uwaga else {})})
    return out

def main(csv_path, refund_path, out_json, out_md):
    raw = open(csv_path, 'rb').read()
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'replace')), delimiter=';'))
    need = ["Identyfikator Produktu Leczniczego", "Nazwa Produktu Leczniczego", "Nazwa powszechnie stosowana", "Rodzaj preparatu",
            "Moc", "Postać farmaceutyczna", "Kod ATC", "Podmiot odpowiedzialny", "Opakowanie", "Substancja czynna",
            "Ważność pozwolenia", "Numer pozwolenia", "Charakterystyka", "Ulotka"]
    miss = [k for k in need if k not in rows[0]]
    if miss: print("BLOKADA: brak kolumn", miss); sys.exit(2)
    ref = json.load(open(refund_path, encoding='utf-8'))
    ref_gtin = collections.defaultdict(list)
    for r in ref['leki']: ref_gtin[r['gtin']].append(r)
    def refund(g):
        rr = ref_gtin.get(g, []) if g else []
        return (sorted({x['poziom_odplatnosci'] for x in rr}) or None,
                sorted({x['pozycja_zrodlowa']['lp_w_wykazie'] for x in rr}, key=int) or None)
    prods, bad_pkg, uzup, probka, probka_uzup = [], 0, 0, [], []
    for r in rows:
        if r["Rodzaj preparatu"].strip().lower() != "ludzki": continue
        atcs = [a.strip() for a in re.split(r'[,\s]+', r["Kod ATC"]) if a.strip()]
        if not any(a.startswith(ATC_PREFIX) for a in atcs): continue
        o = r["Opakowanie"] or ""
        pk = parse(o)
        have = {p["gtin"] for p in pk if p["gtin"]}
        for g, kat, pid, opis in OLD.findall(o):          # kontrola: nic, co czytał stary parser, nie może zginąć
            g14 = g.zfill(14)
            if g14 in have: continue
            have.add(g14); uzup += 1
            pk.append({"gtin": g14, "kategoria": kat.strip(), "status": None, "pozwolenie_eu": None, "id_opakowania": pid,
                       "opis": " ".join(opis.replace('¦', ' ').split()), "odczyt": "kontrolny"})
            if len(probka_uzup) < 10: probka_uzup.append("%s | %s | %r" % (r["Nazwa Produktu Leczniczego"], r["Moc"], o[:400]))
        for p in pk: p["refundacja_A1"], p["refundacja_LP"] = refund(p["gtin"])
        if o.strip() and not pk:
            bad_pkg += 1
            if len(probka) < 25: probka.append("%s | %s | %r" % (r["Nazwa Produktu Leczniczego"], r["Moc"], o[:400]))
        prods.append({"id": r["Identyfikator Produktu Leczniczego"], "nazwa": r["Nazwa Produktu Leczniczego"].strip(),
                      "nazwa_powszechna": r["Nazwa powszechnie stosowana"].strip(), "substancja": r["Substancja czynna"].strip(),
                      "moc": r["Moc"].strip(), "postac": r["Postać farmaceutyczna"].strip(), "atc": atcs,
                      "podmiot": r["Podmiot odpowiedzialny"].strip(), "pozwolenie": r["Numer pozwolenia"].strip(),
                      "waznosc_pozwolenia": r["Ważność pozwolenia"].strip(),
                      "chpl": r["Charakterystyka"].strip(), "ulotka": r["Ulotka"].strip(),
                      "komunikaty_bezpieczenstwa": [k for k in re.split(r'\s+', (r.get("Komunikaty bezpieczeństwa") or "").strip()) if k],
                      "opakowania": pk})
    prods.sort(key=lambda p: (p["nazwa_powszechna"].lower(), p["nazwa"].lower(), p["moc"]))
    allpk = [o for p in prods for o in p["opakowania"]]
    m = re.search(r'(\d{8})', csv_path)
    meta = {"zrodlo": "Rejestr Produktów Leczniczych, eksport CSV (rejestrymedyczne.ezdrowie.gov.pl)",
            "stan_na_dzien": (datetime.datetime.strptime(m.group(1), "%Y%m%d").date().isoformat() if m else None),
            "sha256_zrodla": hashlib.sha256(raw).hexdigest(), "atc_prefiksy": list(ATC_PREFIX),
            "refundacja_dataset_id": ref['metadata']['dataset_id'],
            "uwaga": "RPL = pozwolenie na dopuszczenie do obrotu. NIE oznacza dostępności w aptece. Opakowanie bez GTIN = zwykle niewprowadzone na rynek PL. Brak dawkowania — dawkowanie wyłącznie z ChPL/kart DRUG_DB.",
            "produkty": len(prods), "opakowania": len(allpk), "bledy_parsowania_opakowan": bad_pkg,
            "opakowania_bez_gtin": sum(1 for o in allpk if not o["gtin"]),
            "opakowania_ze_statusem": dict(collections.Counter(o["status"] for o in allpk if o["status"])),
            "odczyt_kontrolny": uzup}
    try:
        old = json.load(open(out_json, encoding='utf-8'))
        old_k = {(p["id"], k) for p in old["produkty"] for k in p.get("komunikaty_bezpieczenstwa", [])}
        pierwszy = "komunikaty_bezpieczenstwa" not in (old["produkty"][0] if old["produkty"] else {})
    except Exception:
        old_k, pierwszy = set(), True
    nowe_k = [(p, k) for p in prods for k in p["komunikaty_bezpieczenstwa"] if (p["id"], k) not in old_k]
    meta["komunikaty_produkty"] = sum(1 for p in prods if p["komunikaty_bezpieczenstwa"])
    meta["nowe_komunikaty"] = 0 if pierwszy else len(nowe_k)
    # BLOKADA PRZED ZAPISEM. Do 2026-09-23 ta kontrola stala PO zapisaniu
    # rpl/RPL_PSYCH.json, a workflow mial "if: always()" i commitowal mimo
    # kodu 2. Wynik: spis odrzucony jako podejrzany i tak trafial do repo,
    # skad czyta go modul 19 (RPL_SPIS) przy wizycie.
    if meta["produkty"] < 300 or bad_pkg > meta["produkty"] * 0.01:
        print("produkty", meta["produkty"], "bledy", bad_pkg)
        print("BLOKADA: podejrzanie mało produktów albo błędy odczytu opakowań")
        sys.exit(2)
    K = ["# Komunikaty bezpieczeństwa — leki psychiatryczne (RPL)", "", "Stan RPL: %s" % meta["stan_na_dzien"], ""]
    if pierwszy: K += ["Pierwszy przebieg — stan wyjściowy, bez porównania.", ""]
    elif nowe_k: K += ["## NOWE od poprzedniego spisu (%d)" % len(nowe_k), ""] + ["- **%s** (%s, %s) — %s" % (p["nazwa"], p["nazwa_powszechna"], p["moc"], k) for p, k in nowe_k] + [""]
    else: K += ["Brak nowych komunikatów od poprzedniego spisu.", ""]
    K += ["## Wszystkie produkty z komunikatami (%d)" % meta["komunikaty_produkty"], ""]
    K += ["- %s (%s, %s): %s" % (p["nazwa"], p["nazwa_powszechna"], p["moc"], " ".join(p["komunikaty_bezpieczenstwa"])) for p in prods if p["komunikaty_bezpieczenstwa"]]
    open(out_md.replace("RAPORT.md", "KOMUNIKATY.md"), 'w', encoding='utf-8').write("\n".join(K) + "\n")
    out = json.dumps({"metadata": meta, "produkty": prods}, ensure_ascii=False, indent=1) + "\n"
    open(out_json, 'w', encoding='utf-8').write(out)
    subst = collections.defaultdict(lambda: collections.defaultdict(set))
    for p in prods: subst[p["nazwa_powszechna"]][p["postac"]].add(p["moc"])
    rpl_gtin = {o["gtin"] for o in allpk if o["gtin"]}
    A1_bez_rpl = sorted({(r['nazwa_postac_dawka'], r['gtin']) for g, rs in ref_gtin.items() for r in rs if g not in rpl_gtin})
    R = ["# Spis RPL — leki psychiatryczne", "", "Stan RPL: %s  " % meta["stan_na_dzien"],
         "Produkty: %d, opakowania: %d (bez GTIN: %d), błędy odczytu: %d, odczyt kontrolny: %d  " % (meta["produkty"], meta["opakowania"], meta["opakowania_bez_gtin"], bad_pkg, uzup),
         "Statusy opakowań: %s  " % (meta["opakowania_ze_statusem"] or "brak"),
         "Refundacja: %s  " % meta["refundacja_dataset_id"], "sha256 spisu: `%s`" % hashlib.sha256(out.encode()).hexdigest(), "",
         "## GTIN z wykazu refundacji nieznalezione w tym wyciągu RPL (%d)" % len(A1_bez_rpl), ""]
    R += ["- %s (GTIN %s)" % x for x in A1_bez_rpl[:80]] + [""]
    R += ["## Moce wg substancji i postaci", ""]
    for s in sorted(subst, key=str.lower):
        R.append("- **%s**: " % s + "; ".join("%s: %s" % (f, ", ".join(sorted(v))) for f, v in sorted(subst[s].items())))
    open(out_md, 'w', encoding='utf-8').write("\n".join(R) + "\n")
    os.makedirs("wyniki", exist_ok=True)
    open("wyniki/probka_opakowan.txt", "w", encoding="utf-8").write("NIEODCZYTANE:\n" + "\n".join(probka) + "\n\nODCZYT KONTROLNY (stary parser znalazł, nowy nie):\n" + "\n".join(probka_uzup) + "\n")
    print("bez_gtin", meta["opakowania_bez_gtin"], "statusy", meta["opakowania_ze_statusem"], "odczyt_kontrolny", uzup)
    print("nowe_komunikaty", meta["nowe_komunikaty"])
    if meta["nowe_komunikaty"]: open("NOWE_KOMUNIKATY", "w").write(str(meta["nowe_komunikaty"]))
    print("produkty", meta["produkty"], "opakowania", meta["opakowania"], "bledy", bad_pkg, "A1_bez_RPL", len(A1_bez_rpl))
    print("OK")

if __name__ == "__main__": main(*sys.argv[1:5])

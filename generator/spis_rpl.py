"""Spis leków psychiatrycznych z eksportu RPL (CSV) + zestawienie z danymi refundacji.
Wejście: RPL CSV, REFUNDACJA_DATA.json. Wyjście: rpl/RPL_PSYCH.json, rpl/RAPORT.md."""
import csv, io, json, re, sys, hashlib, collections, datetime
ATC_PREFIX = ("N03", "N05", "N06", "N07BB", "N07BC", "N02BF02")   # przeciwpadaczkowe, psycholeptyki, psychoanaleptyki, uzależnienia, pregabalina
PKG = re.compile(r'(\d{8,14})\s*¦\s*([^¦]*?)\s*¦\s*(\d+)\s+(.*?)(?=\s+\d{8,14}\s*¦|$)', re.S)

def main(csv_path, refund_path, out_json, out_md):
    raw = open(csv_path, 'rb').read()
    txt = raw.decode('utf-8-sig', 'replace')
    rows = list(csv.DictReader(io.StringIO(txt), delimiter=';'))
    need = ["Identyfikator Produktu Leczniczego", "Nazwa Produktu Leczniczego", "Nazwa powszechnie stosowana", "Rodzaj preparatu",
            "Moc", "Postać farmaceutyczna", "Kod ATC", "Podmiot odpowiedzialny", "Opakowanie", "Substancja czynna",
            "Ważność pozwolenia", "Numer pozwolenia", "Charakterystyka", "Ulotka"]
    miss = [k for k in need if k not in rows[0]]
    if miss: print("BLOKADA: brak kolumn", miss); sys.exit(2)
    ref = json.load(open(refund_path, encoding='utf-8'))
    ref_gtin = collections.defaultdict(list)
    for r in ref['leki']: ref_gtin[r['gtin']].append(r)
    prods, bad_pkg = [], 0
    for r in rows:
        if r["Rodzaj preparatu"].strip().lower() != "ludzki": continue
        atcs = [a.strip() for a in re.split(r'[,\s]+', r["Kod ATC"]) if a.strip()]
        if not any(a.startswith(ATC_PREFIX) for a in atcs): continue
        pk = []
        for g, kat, pid, opis in PKG.findall(r["Opakowanie"] or ""):
            g14 = g.zfill(14)
            rr = ref_gtin.get(g14, [])
            pk.append({"gtin": g14, "kategoria": kat.strip(), "opis": " ".join(opis.split()),
                       "refundacja_A1": sorted({x['poziom_odplatnosci'] for x in rr}) or None,
                       "refundacja_LP": sorted({x['pozycja_zrodlowa']['lp_w_wykazie'] for x in rr}, key=int) or None})
        if (r["Opakowanie"] or "").strip() and not pk: bad_pkg += 1
        prods.append({"id": r["Identyfikator Produktu Leczniczego"], "nazwa": r["Nazwa Produktu Leczniczego"].strip(),
                      "nazwa_powszechna": r["Nazwa powszechnie stosowana"].strip(), "substancja": r["Substancja czynna"].strip(),
                      "moc": r["Moc"].strip(), "postac": r["Postać farmaceutyczna"].strip(), "atc": atcs,
                      "podmiot": r["Podmiot odpowiedzialny"].strip(), "pozwolenie": r["Numer pozwolenia"].strip(),
                      "waznosc_pozwolenia": r["Ważność pozwolenia"].strip(),
                      "chpl": r["Charakterystyka"].strip(), "ulotka": r["Ulotka"].strip(), "opakowania": pk})
    prods.sort(key=lambda p: (p["nazwa_powszechna"].lower(), p["nazwa"].lower(), p["moc"]))
    m = re.search(r'(\d{8})', csv_path)
    meta = {"zrodlo": "Rejestr Produktów Leczniczych, eksport CSV (rejestrymedyczne.ezdrowie.gov.pl)",
            "stan_na_dzien": (datetime.datetime.strptime(m.group(1), "%Y%m%d").date().isoformat() if m else None),
            "sha256_zrodla": hashlib.sha256(raw).hexdigest(), "atc_prefiksy": list(ATC_PREFIX),
            "refundacja_dataset_id": ref['metadata']['dataset_id'],
            "uwaga": "RPL = pozwolenie na dopuszczenie do obrotu. NIE oznacza dostępności w aptece. Brak dawkowania — dawkowanie wyłącznie z ChPL/kart DRUG_DB.",
            "produkty": len(prods), "opakowania": sum(len(p["opakowania"]) for p in prods), "bledy_parsowania_opakowan": bad_pkg}
    out = json.dumps({"metadata": meta, "produkty": prods}, ensure_ascii=False, indent=1) + "\n"
    open(out_json, 'w', encoding='utf-8').write(out)
    # raport
    subst = collections.defaultdict(lambda: collections.defaultdict(set))
    for p in prods: subst[p["nazwa_powszechna"]][p["postac"]].add(p["moc"])
    A1_gtin = {g for g in ref_gtin}; rpl_gtin = {o["gtin"] for p in prods for o in p["opakowania"]}
    A1_bez_rpl = sorted({(r['nazwa_postac_dawka'], r['gtin']) for g, rs in ref_gtin.items() for r in rs if g not in rpl_gtin})
    R = ["# Spis RPL — leki psychiatryczne", "", "Stan RPL: %s  " % meta["stan_na_dzien"],
         "Produkty: %d, opakowania: %d, błędy parsowania opakowań: %d  " % (meta["produkty"], meta["opakowania"], bad_pkg),
         "Refundacja: %s  " % meta["refundacja_dataset_id"], "sha256 spisu: `%s`" % hashlib.sha256(out.encode()).hexdigest(), "",
         "## GTIN z wykazu refundacji nieznalezione w tym wyciągu RPL (%d)" % len(A1_bez_rpl), "",
         "Przyczyna zwykle: ATC spoza prefiksów (np. pregabalina N02BF, metadon), inny zapis GTIN.", ""]
    R += ["- %s (GTIN %s)" % x for x in A1_bez_rpl[:80]] + [""]
    R += ["## Moce wg substancji i postaci", ""]
    for s in sorted(subst, key=str.lower):
        R.append("- **%s**: " % s + "; ".join("%s: %s" % (f, ", ".join(sorted(v))) for f, v in sorted(subst[s].items())))
    open(out_md, 'w', encoding='utf-8').write("\n".join(R) + "\n")
    print("produkty", meta["produkty"], "opakowania", meta["opakowania"], "bledy", bad_pkg, "A1_bez_RPL", len(A1_bez_rpl))
    if meta["produkty"] < 300 or bad_pkg > meta["produkty"] * 0.05: print("BLOKADA: podejrzanie mało produktów albo dużo błędów parsowania"); sys.exit(2)

if __name__ == "__main__": main(*sys.argv[1:5])

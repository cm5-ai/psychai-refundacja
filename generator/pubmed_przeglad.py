"""Cotygodniowy przegląd PubMed dla PSYCH-AI.
Szuka WYŁĄCZNIE dowodów wysokiego poziomu z ostatnich N dni: wytyczne, metaanalizy, przeglądy
systematyczne, RCT. Zapisuje tytuł, czasopismo, datę, typ i link PMID — bez abstraktów (prawa wydawców).
Nic nie zmienia w kartach: raport jest materiałem do przeglądu przez lekarza."""
import json, re, sys, os, time, datetime, urllib.parse, subprocess, collections

E = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
DNI = int(os.environ.get("DNI", "7"))
TYP = '(guideline[pt] OR practice guideline[pt] OR meta-analysis[pt] OR systematic review[pt] OR randomized controlled trial[pt] OR "network meta-analysis"[tiab])'
POZIOM = [("WYTYCZNE", ("Guideline", "Practice Guideline")), ("METAANALIZA", ("Meta-Analysis",)),
          ("PRZEGLĄD SYST.", ("Systematic Review",)), ("RCT", ("Randomized Controlled Trial",))]

def get(url):
    for i in range(4):
        r = subprocess.run(["curl", "-sS", "-m", "60", url], capture_output=True)
        if r.returncode == 0 and r.stdout.strip().startswith(b"{"): time.sleep(0.4); return json.loads(r.stdout)
        time.sleep(2 + 2 * i)
    raise RuntimeError("PubMed niedostępny: " + url[:120])

def szukaj(q):
    u = E + "esearch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "term": "(%s) AND %s" % (q, TYP), "reldate": DNI,
        "datetype": "edat", "retmax": 200, "retmode": "json", "tool": "psychai-przeglad"})
    return get(u)["esearchresult"].get("idlist", [])

def opisz(ids):
    out = {}
    for i in range(0, len(ids), 150):
        u = E + "esummary.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids[i:i + 150]), "retmode": "json", "tool": "psychai-przeglad"})
        r = get(u)["result"]
        for pid in r.get("uids", []): out[pid] = r[pid]
    return out

def poziom(pt):
    for nazwa, typy in POZIOM:
        if any(t in pt for t in typy): return nazwa
    return "INNE"

def main():
    tematy = [l.split("|", 1) for l in open("zrodla/pubmed_tematy.txt", encoding="utf-8") if "|" in l and not l.startswith("#")]
    trafienia = collections.defaultdict(set)
    for et, q in tematy:
        for pid in szukaj(q.strip()): trafienia[pid].add(et.strip())
    info = opisz(sorted(trafienia))
    dzis = datetime.date.today()
    poz = [n for n, _ in POZIOM] + ["INNE"]
    rek = []
    for pid, et in trafienia.items():
        d = info.get(pid, {})
        pt = d.get("pubtype", [])
        rek.append({"pmid": pid, "poziom": poziom(pt), "tytul": d.get("title", "").strip(), "czasopismo": d.get("fulljournalname") or d.get("source", ""),
                    "data": d.get("pubdate", ""), "tematy": sorted(et)})
    rek.sort(key=lambda r: (poz.index(r["poziom"]), -len(r["tematy"]), r["czasopismo"]))
    licz = collections.Counter(r["poziom"] for r in rek)
    R = ["# Przegląd PubMed — %s (ostatnie %d dni)" % (dzis, DNI), "",
         "Tylko wytyczne, metaanalizy, przeglądy systematyczne i RCT. Bez abstraktów. Nic nie zmienia kart automatycznie.", "",
         "Razem: %d | " % len(rek) + " | ".join("%s: %d" % (p, licz.get(p, 0)) for p in poz if licz.get(p)), ""]
    LEKI = {l.split("|")[0].strip() for l in open("zrodla/pubmed_tematy.txt", encoding="utf-8") if "|" in l and not l.startswith("#") and l.split("|")[0].strip().isupper() and l.split("|")[0].strip() not in ("DEPRESJA", "DEPRESJA-LEKOOPORNA", "CHAD", "SCHIZOFRENIA", "LĘK", "OCD", "PTSD", "ADHD-DOROŚLI", "BEZSENNOŚĆ", "OKOŁOPORODOWE")}
    top = [r for r in rek if r["poziom"] in ("WYTYCZNE", "METAANALIZA", "PRZEGLĄD SYST.") and LEKI & set(r["tematy"])]
    if top:
        R += ["## NAJPIERW PRZECZYTAJ — farmakoterapia, wysoki poziom dowodu (%d)" % len(top), ""]
        R += ["- **%s** — %s — [PMID %s](https://pubmed.ncbi.nlm.nih.gov/%s/) — _%s_" % (r["tytul"], r["czasopismo"], r["pmid"], r["pmid"], ", ".join(r["tematy"])) for r in top] + [""]
    for p in poz:
        grupa = [r for r in rek if r["poziom"] == p]
        if not grupa: continue
        R += ["## %s (%d)" % (p, len(grupa)), ""]
        for r in grupa:
            R.append("- **%s** — %s, %s — [PMID %s](https://pubmed.ncbi.nlm.nih.gov/%s/) — _%s_" % (r["tytul"], r["czasopismo"], r["data"], r["pmid"], r["pmid"], ", ".join(r["tematy"])))
        R.append("")
    os.makedirs("pubmed", exist_ok=True)
    txt = "\n".join(R) + "\n"
    open("pubmed/PRZEGLAD_%s.md" % dzis, "w", encoding="utf-8").write(txt)
    open("pubmed/OSTATNI.md", "w", encoding="utf-8").write(txt)
    json.dump(rek, open("pubmed/OSTATNI.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(R[4])
    wysokie = [r for r in rek if r["poziom"] in ("WYTYCZNE", "METAANALIZA", "PRZEGLĄD SYST.")]
    open("ZGLOSZENIE", "w", encoding="utf-8").write(
        "Nowe publikacje (%d dni): %d, w tym wytyczne/metaanalizy/przeglądy: %d.\n\nNajważniejsze:\n" % (DNI, len(rek), len(wysokie)) +
        "\n".join("- [%s] %s — https://pubmed.ncbi.nlm.nih.gov/%s/ (%s)" % (r["poziom"], r["tytul"][:160], r["pmid"], ", ".join(r["tematy"])) for r in wysokie[:25]) +
        "\n\nPełna lista: pubmed/OSTATNI.md. Karty w projekcie NIE zmieniają się automatycznie.")

if __name__ == "__main__": main()

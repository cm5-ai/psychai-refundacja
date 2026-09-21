"""LactMed (NLM/NICHD, domena publiczna) -> lactmed/INDEKS.json + lactmed/leki/<ID>.json
Wejście: katalog z rozpakowanym lactmed_NBK501922 (*.nxml), data aktualizacji źródła, sha256 archiwum."""
import sys, os, re, json, glob, html.entities, datetime, hashlib
import xml.etree.ElementTree as ET

XML5 = {"amp", "lt", "gt", "quot", "apos"}
def fix_entities(t):
    t = re.sub(r'<!DOCTYPE[^>]*>', '', t, count=1)
    def rep(m):
        n = m.group(1)
        if n in XML5: return m.group(0)
        c = html.entities.html5.get(n + ";")
        return c.replace("&", "&amp;").replace("<", "&lt;") if c else ""
    return re.sub(r'&([A-Za-z][A-Za-z0-9]*);', rep, t)

def text(el):
    parts = []
    def walk(e):
        if e.tag == "xref": 
            if e.tail: parts.append(e.tail)
            return
        if e.text: parts.append(e.text)
        for c in e: walk(c)
        if e.tail: parts.append(e.tail)
    walk(el); t = "".join(parts)
    t = t.replace("[]", "").replace("[,]", "").replace("[, ]", "")
    t = re.sub(r'\[\s*[,\s–-]*\s*\]', '', t)
    return re.sub(r'\s+([.,;:])', r'\1', " ".join(t.split()))

def sections(sec, prefix=""):
    out = []
    title = sec.find("title"); tt = (prefix + " > " if prefix else "") + (text(title) if title is not None else "")
    paras = [text(p) for p in sec if p.tag in ("p", "list", "table-wrap")]
    paras = [p for p in paras if p]
    if paras: out.append([tt, "\n".join(paras)])
    for c in sec.findall("sec"): out += sections(c, tt)
    return out

def parse(path):
    root = ET.fromstring(fix_entities(open(path, encoding="utf-8").read()))
    part = root.find("book-part")
    if part is None: return None
    meta = part.find("book-part-meta")
    lid = meta.findtext("book-part-id") or os.path.basename(path)[:-5]
    title = text(meta.find("title-group/title"))
    kw = [text(k) for k in meta.findall("kwd-group/kwd")]
    d = meta.find("pub-history/date[@date-type='revised']")
    rev = "%s-%s-%s" % (d.findtext("year"), d.findtext("month").zfill(2), d.findtext("day").zfill(2)) if d is not None else None
    body = part.find("body"); secs = []
    if body is not None:
        for s in body.findall("sec"):
            if (s.findtext("title") or "").strip().lower() in ("references", "substance identification", "disclaimer"): continue
            secs += sections(s)
    return {"id": lid, "tytul": title, "synonimy": kw, "zaktualizowano": rev,
            "url": "https://www.ncbi.nlm.nih.gov/books/n/lactmed/%s/" % lid, "sekcje": secs}

def main(src, out, zrodlo_data, zrodlo_sha):
    os.makedirs(os.path.join(out, "leki"), exist_ok=True)
    idx, bledy = [], []
    for f in sorted(glob.glob(os.path.join(src, "*.nxml"))):
        try: r = parse(f)
        except Exception as e: bledy.append("%s: %s" % (os.path.basename(f), e)); continue
        if not r or not r["tytul"]: bledy.append("%s: brak tytułu" % os.path.basename(f)); continue
        fn = re.sub(r'[^A-Za-z0-9_-]', '_', r["id"]) + ".json"
        open(os.path.join(out, "leki", fn), "w", encoding="utf-8").write(json.dumps(r, ensure_ascii=False, indent=1) + "\n")
        idx.append({"id": r["id"], "tytul": r["tytul"], "zaktualizowano": r["zaktualizowano"],
                    "synonimy": [k for k in r["synonimy"] if len(k) <= 40 and not re.search(r'\d{3,}|UNII|HSDB|EC ', k)][:25], "plik": "leki/" + fn})
    idx.sort(key=lambda x: x["tytul"].lower())
    keep = {x["plik"].split("/")[1] for x in idx}
    for f in os.listdir(os.path.join(out, "leki")):
        if f not in keep: os.remove(os.path.join(out, "leki", f))
    meta = {"zrodlo": "Drugs and Lactation Database (LactMed), NICHD/NLM, NCBI Bookshelf NBK501922 — domena publiczna",
            "zrodlo_aktualizacja": zrodlo_data, "sha256_archiwum": zrodlo_sha,
            "stan_na_dzien": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2))).date().isoformat(),
            "wpisy": len(idx), "bledy": len(bledy),
            "uwaga": "Tylko laktacja. Nie obejmuje ciąży ani planowania ciąży. Nie zastępuje oceny klinicznej."}
    open(os.path.join(out, "INDEKS.json"), "w", encoding="utf-8").write(json.dumps({"metadata": meta, "wpisy": idx}, ensure_ascii=False, indent=0) + "\n")
    os.makedirs("wyniki", exist_ok=True)
    open("wyniki/lactmed.txt", "w", encoding="utf-8").write("wpisy %d bledy %d\n%s\n" % (len(idx), len(bledy), "\n".join(bledy[:30])))
    print("wpisy", len(idx), "bledy", len(bledy))
    if len(idx) < 1000 or len(bledy) > 20: print("BLOKADA"); sys.exit(2)
    print("OK")

if __name__ == "__main__": main(*sys.argv[1:5])

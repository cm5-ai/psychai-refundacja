"""Strażnik ChPL: dla substancji z kartami CORE pobiera ChPL (PDF z RPL) produktów w obrocie,
wyciąga tekst (pdftotext) i zapisuje WYŁĄCZNIE sumy kontrolne: całości i sekcji 4.1–4.9.
Zmiana -> raport per substancja + zgłoszenie. Treści ChPL nie zapisuje."""
import json, re, os, sys, hashlib, subprocess, tempfile, concurrent.futures as cf, datetime

def tekst_pdf(url):
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "a.pdf")
        r = subprocess.run(["curl", "-sSfL", "--retry", "3", "-m", "90", "-o", p, url])
        if r.returncode or not os.path.exists(p) or os.path.getsize(p) < 1000: return None
        r = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True)
        if r.returncode: return None
        return r.stdout.decode("utf-8", "replace")

def sekcje(t):
    t = " ".join(t.split())
    ms = list(re.finditer(r'(?<![\d.])4\.([1-9])\.?\s+(?=[A-ZŁŚŻŹĆŃÓĘĄ])', t))
    out, seen = {}, set()
    for i, m in enumerate(ms):
        k = "4." + m.group(1)
        if k in seen: continue
        seen.add(k)
        kon = ms[i + 1].start() if i + 1 < len(ms) else len(t)
        out[k] = hashlib.sha256(t[m.start():kon].encode()).hexdigest()[:16]
    return hashlib.sha256(t.encode()).hexdigest()[:16], out

def main():
    rpl = json.load(open("rpl/RPL_PSYCH.json", encoding="utf-8"))
    wz = [l.split() for l in open("zrodla/chpl_substancje.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
    cel = {}
    for p in rpl["produkty"]:
        if not p["chpl"] or not any(o["gtin"] and not o["status"] for o in p["opakowania"]): continue
        s = (p["nazwa_powszechna"] + " " + p["substancja"]).lower()
        for nazwa, w in wz:
            if w in s: cel[p["id"]] = {"sub": nazwa, "nazwa": p["nazwa"], "moc": p["moc"], "podmiot": p["podmiot"], "chpl": p["chpl"]}; break
    stary = json.load(open("zrodla/chpl_stan.json")) if os.path.exists("zrodla/chpl_stan.json") else {}
    nowy, bledy = {}, []
    def rob(pid):
        t = tekst_pdf(cel[pid]["chpl"])
        return pid, (sekcje(t) if t else None)
    with cf.ThreadPoolExecutor(4) as ex:
        for pid, w in ex.map(rob, list(cel)):
            if not w: bledy.append(pid); continue
            nowy[pid] = dict(cel[pid], sha=w[0], sekcje=w[1])
    for pid in bledy:
        if pid in stary: nowy[pid] = stary[pid]           # nie gubimy stanu przy błędzie pobrania
    zmiany = {}
    for pid, v in nowy.items():
        o = stary.get(pid)
        if not o or o.get("sha") == v["sha"] or pid in bledy: continue
        sek = sorted(k for k in set(o.get("sekcje", {})) | set(v["sekcje"]) if o.get("sekcje", {}).get(k) != v["sekcje"].get(k))
        zmiany.setdefault(v["sub"], []).append((v, sek))
    nowe_prod = [pid for pid in nowy if pid not in stary] if stary else []
    json.dump(nowy, open("zrodla/chpl_stan.json", "w"), ensure_ascii=False, indent=0, sort_keys=True)
    os.makedirs("wyniki", exist_ok=True)
    R = ["# Strażnik ChPL — %s" % datetime.date.today(), "",
         "Produkty sprawdzane: %d; błędy pobrania: %d; %s" % (len(cel), len(bledy), "pierwszy przebieg — stan wyjściowy" if not stary else "porównanie z poprzednim"), ""]
    if stary:
        R += ["## Zmienione ChPL (%d substancji)" % len(zmiany), ""]
        for s in sorted(zmiany):
            R.append("### %s — zmienione %d ChPL" % (s, len(zmiany[s])))
            for v, sek in zmiany[s][:15]:
                R.append("- %s %s (%s) — sekcje: %s — %s" % (v["nazwa"], v["moc"], v["podmiot"], ", ".join(sek) or "poza 4.x", v["chpl"]))
            R.append("")
        if nowe_prod: R += ["Nowe produkty w obserwacji: %d" % len(nowe_prod), ""]
    wazne = {"4.2", "4.3", "4.4", "4.5", "4.6"}
    alarm = [s for s in zmiany if any(wazne & set(sek) for _, sek in zmiany[s])]
    R += ["Sekcje istotne (4.2 dawkowanie, 4.3 przeciwwskazania, 4.4 ostrzeżenia, 4.5 interakcje, 4.6 ciąża/laktacja): " + (", ".join(sorted(alarm)) or "bez zmian")]
    open("wyniki/chpl.md", "w", encoding="utf-8").write("\n".join(R) + "\n"); print("\n".join(R[:6])); print(R[-1])
    if stary and zmiany: open("ALARM", "w").write("Zmienione ChPL: " + ", ".join("%s (%d)" % (s, len(zmiany[s])) for s in sorted(zmiany)) + "\nIstotne sekcje 4.2-4.6: " + (", ".join(sorted(alarm)) or "brak"))

if __name__ == "__main__": main()

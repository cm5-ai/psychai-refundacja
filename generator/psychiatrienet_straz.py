"""Strażnik Psychiatrienet: NIE kopiuje treści (prawa autorskie De Tijdstroom).
Zapisuje wyłącznie: listę adresów par z tabel zamian i sumy kontrolne tekstu stron par z indeksu modułu 19.
Zmiana sumy albo zniknięcie strony/węzła -> plik ALARM (workflow zakłada zgłoszenie)."""
import re, json, sys, hashlib, subprocess, html, os
B = "https://www.psychiatrienet.nl"
TAB = {"SwitchAntidepressants": B + "/switchtabel/show?id=SwitchAntidepressants",
       "SwitchAntipsychotics": B + "/switchtabel/show?id=SwitchAntipsychotics"}

def get(u):
    r = subprocess.run(["curl", "-sSL", "--retry", "3", "-m", "60", "-A", "Mozilla/5.0 (psychai-straz)", "-w", "\n%{http_code}", u], capture_output=True)
    body, _, code = r.stdout.decode("utf-8", "replace").rpartition("\n")
    return int(code or 0), body

def tekst(h):
    h = re.sub(r'(?is)<(script|style|noscript|header|footer|nav)[^>]*>.*?</\1>', ' ', h)
    h = re.sub(r'(?s)<!--.*?-->', ' ', h); h = re.sub(r'<[^>]+>', ' ', h)
    return " ".join(html.unescape(h).split())

def main():
    pary = [l.strip() for l in open("zrodla/psychiatrienet_pary.txt") if l.strip() and not l.startswith("#")]
    wezly = " ".join(l for l in open("zrodla/psychiatrienet_wezly.txt") if not l.startswith("#")).split()
    stare = json.load(open("zrodla/psychiatrienet_stan.json")) if os.path.exists("zrodla/psychiatrienet_stan.json") else {}
    stan, alarmy, linki = {"tabele": {}, "pary": {}}, [], set()
    for k, u in TAB.items():
        c, h = get(u)
        if c != 200: alarmy.append("tabela %s: HTTP %s" % (k, c)); continue
        l = set(re.findall(r'/switchdetail/([a-z0-9-]+)', h)); linki |= l
        stan["tabele"][k] = {"liczba_par": len(l), "sha256": hashlib.sha256(tekst(h).encode()).hexdigest()}
    brak_w = [w for w in wezly if linki and not any(x.startswith(w + "-") or x.endswith("-" + w) for x in linki)]
    if brak_w: alarmy.append("węzły z mapy 19 nieobecne w tabelach: " + ", ".join(brak_w))
    for p in pary:
        c, h = get(B + "/switchdetail/" + p)
        if c != 200: alarmy.append("para %s: HTTP %s" % (p, c)); continue
        stan["pary"][p] = hashlib.sha256(tekst(h).encode()).hexdigest()
        if p in stare.get("pary", {}) and stare["pary"][p] != stan["pary"][p]:
            alarmy.append("para %s: treść strony zmieniona — sprawdź indeks par w 19" % p)
    for k, v in stan["tabele"].items():
        o = stare.get("tabele", {}).get(k)
        if o and o["sha256"] != v["sha256"]: alarmy.append("tabela %s: zmieniona (par: %s -> %s)" % (k, o["liczba_par"], v["liczba_par"]))
    open("zrodla/psychiatrienet_stan.json", "w").write(json.dumps(stan, indent=1, sort_keys=True) + "\n")
    open("zrodla/psychiatrienet_adresy_par.txt", "w").write("\n".join(sorted(linki)) + "\n")
    os.makedirs("wyniki", exist_ok=True)
    rap = ["pierwszy przebieg — stan wyjściowy" if not stare else "porównanie z poprzednim przebiegiem",
           "pary w tabelach: %d; pary z indeksu 19 sprawdzone: %d/%d" % (len(linki), len(stan["pary"]), len(pary))] + (alarmy or ["bez zmian"])
    open("wyniki/psychiatrienet.txt", "w").write("\n".join(rap) + "\n"); print("\n".join(rap))
    if alarmy and stare: open("ALARM", "w").write("\n".join(alarmy))

if __name__ == "__main__": main()

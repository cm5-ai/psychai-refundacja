#!/usr/bin/env python3
"""Sonda strony MZ: spis obwieszczeń (w tym zmieniających i sprostowań)
oraz załączników najnowszego wykazu. Tylko odczyt; nic nie buduje."""
import re, sys, html, json, urllib.request
BASE = "https://www.gov.pl"
LISTA = BASE + "/web/zdrowie/obwieszczenia-ministra-zdrowia-lista-lekow-refundowanych"
UA = {"User-Agent": "Mozilla/5.0 (psychai-refundacja sonda)"}
def get(u):
    return html.unescape(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "replace"))
def linki(t):
    out = []
    for href, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, flags=re.S):
        txt = re.sub(r"<[^>]+>", " ", txt); txt = re.sub(r"\s+", " ", txt).strip()
        out.append((href if href.startswith("http") else BASE + href, txt))
    return out
t = get(LISTA)
obw = [(h, x) for h, x in linki(t) if re.search(r"(?i)obwieszczen|sprostowan", x) and "wykazu refundowanych" in x]
print(f"## Obwieszczenia na stronie MZ ({len(obw)})")
for h, x in obw[:12]:
    typ = "ZMIENIAJĄCE" if "zmieniaj" in x.lower() else ("SPROSTOWANIE" if "sprostowan" in x.lower() else "WYKAZ")
    print(f"- [{typ}] {x}\n  {h}")
glowne = [(h, x) for h, x in obw if "zmieniaj" not in x.lower() and "sprostowan" not in x.lower()]
if not glowne: print("::error::Brak głównego obwieszczenia na liście"); sys.exit(1)
h, x = glowne[0]
print(f"\n## Załączniki najnowszego wykazu\n{x}\n{h}")
s = get(h)
for hh, xx in linki(s):
    if "/attachment/" in hh or re.search(r"\.(xlsx|zip|pdf)\b", hh + " " + xx, re.I):
        print(f"- {xx}\n  {hh}")
print("\n## Fragmenty z 'Dz. Urz' / 'poz.'")
for m in re.findall(r"[^<>]{0,80}(?:Dz\.\s*Urz|poz\.)[^<>]{0,80}", s)[:10]:
    print("-", re.sub(r"\s+", " ", m).strip())

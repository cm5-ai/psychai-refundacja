"""Wyszukiwarka LactMed do wątku wizyty. Pobiera lactmed/INDEKS.json i wpis leku z repozytorium.
Użycie: python3 lactmed_szukaj.py "sertralina" [--pelne] [--today YYYY-MM-DD] [--baza URL]
Wypisuje tekst LactMed (angielski, dosłowny) z pinem. Niczego nie wylicza."""
import json, sys, re, unicodedata, datetime, argparse, subprocess
BAZA = "https://raw.githubusercontent.com/cm5-ai/psychai-refundacja/main/lactmed/"

def norm(s):
    s = unicodedata.normalize('NFKD', s.lower()); s = ''.join(c for c in s if not unicodedata.combining(c))
    for a, b in (("qu", "kw"), ("ph", "f"), ("th", "t"), ("x", "ks"), ("v", "w"), ("y", "i"), ("c", "k"), ("z", "s"), ("ł", "l")):
        s = s.replace(a, b)
    return s

def stem(s): return re.sub(r'(um|us|a|i|e|y|u|o)$', '', norm(s).strip())

def get(url):
    r = subprocess.run(["curl", "-sSfL", "--retry", "2", url], capture_output=True)
    if r.returncode: print("LACTMED: NIEDOSTĘPNY (pobranie %s)" % url); sys.exit(3)
    return json.loads(r.stdout.decode("utf-8"))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("szukaj"); ap.add_argument("--pelne", action="store_true")
    ap.add_argument("--today"); ap.add_argument("--baza", default=BAZA); a = ap.parse_args()
    idx = get(a.baza + "INDEKS.json"); m = idx["metadata"]
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    wiek = (today - datetime.date.fromisoformat(m["stan_na_dzien"])).days
    print("LACTMED | pobrano %s | źródło aktualizowane %s | %s" % (m["stan_na_dzien"], m["zrodlo_aktualizacja"], "AKTUALNY" if wiek <= 21 else "PRZETERMINOWANY (>21 dni)"))
    slowa = [w for w in a.szukaj.split() if w]
    def prefy(w):
        q = stem(w); return [x for x in dict.fromkeys([q if len(q) < 6 else q[:max(6, len(q) - 1)], q[:6], q[:5]]) if len(x) >= 3] or [norm(w)]
    hits = []
    poziom_trafienia = None
    for poziom in range(3):
        for e in idx["wpisy"]:
            for pole, waga in ((e["tytul"], 0), (" ".join(e["synonimy"]), 1)):
                toks = [norm(t) for t in re.split(r'[\s,;/()\[\]+-]+', pole) if t]
                if all(any(t.startswith(prefy(w)[min(poziom, len(prefy(w)) - 1)]) for t in toks) for w in slowa):
                    hits.append((waga, len(e["tytul"]), e)); break
        if hits:
            poziom_trafienia = poziom
            break
    if not hits: print("BRAK_W_LACTMED: '%s' — brak wpisu ≠ lek bezpieczny ani niebezpieczny." % a.szukaj); return
    hits.sort(key=lambda h: (h[0], h[1]))
    e = hits[0][2]
    if len(hits) > 1: print("INNE TRAFIENIA:", "; ".join(h[2]["tytul"] for h in hits[1:12]))
    # BRAMKA TOZSAMOSCI [R58/R59, 2026-09-28, zbieznie GPT i Grok, warstwa 40 par. 3B].
    # Werdykt (WPIS + sekcje + PIN) wychodzi WYLACZNIE przy trafieniu w TYTUL
    # (waga 0) na NAJSCISLEJSZYM poziomie prefiksu (poziom 0). Kazde inne
    # trafienie jest dopasowaniem PRZYBLIZONYM, a par. 3B zabrania go jako
    # zrodla danych przy pacjencie. Kandydat nie jest dana.
    # ZMIERZONE 2026-09-28 na 127 nazwach slownika paczki: brama przepuszcza
    # 103, blokuje 9; ZERO blednych przepuszczonych, ZERO poprawnych
    # zablokowanych. Szesc trafien w cudza substancje (metylofenidat->Temazepam,
    # chlorprotiksen->Chlorpromazine, lewomepromazyna->Levomilnacipran,
    # pirybedyl->Tripelennamine, promazyna->Promethazine, riwastygmina->Reserpine)
    # lezy w calosci poza (poziom 0, waga 0).
    # NIE DODANO warunku unikatu (jedno trafienie): zmierzone, ze zabilby
    # CZTERY poprawne trafienia, ktore maja wiecej niz jedno trafienie.
    # TO JEST WSTRZYMANIE, NIE NAPRAWA. Naprawa docelowa to jawne wiersze
    # nazwa->ID po podpisie lekarza (patrz paczka: rundy/R59_TABELA_...).
    if not (poziom_trafienia == 0 and hits[0][0] == 0):
        powod = "poziom %s, %s" % (poziom_trafienia, "synonim" if hits[0][0] else "tytul")
        print("TOZSAMOSC NIEUSTALONA: '%s' — dopasowanie przyblizone (%s)." % (a.szukaj, powod))
        print("KANDYDACI (to NIE sa dane o leku, tylko propozycje do sprawdzenia):")
        for h in hits[:12]:
            print("  - %s (%s)" % (h[2]["tytul"], h[2].get("id", "?")))
        print("Liczb, statusu ani pinu NIE podaje. Ustal lek po nazwie angielskiej")
        print("albo popros o wiersz slownika nazwa->ID (wymaga podpisu lekarza).")
        return
    d = get(a.baza + e["plik"])
    print("WPIS: %s (%s) | rewizja %s | %s" % (d["tytul"], d["id"], d["zaktualizowano"], d["url"]))
    for t, x in d["sekcje"]:
        if not a.pelne and len(x) > 2500: x = x[:2500] + " … [ucięto — --pelne]"
        print("\n## %s\n%s" % (t, x))
    print("\nPIN: [LACTMED | %s %s | rew. %s]" % (d["tytul"], d["id"], d["zaktualizowano"]))

if __name__ == "__main__": main()

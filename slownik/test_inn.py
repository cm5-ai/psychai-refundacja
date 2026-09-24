"""Testy slownika INN. Trzy rodzaje, jak przy slowniku postaci:
  A. WARTOWNICY - pary o znanej odpowiedzi, w tym te, na ktorych sie przewrocilem.
  B. KONTRPRZYKLADY - pary, ktore NIE MOGA dostac wspolnego klucza.
  C. BILANS SCALANIA - zaden klucz nie moze byc pusty; zubozone sa policzone.
"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inn

# A. Pary, ktore MUSZA dac ten sam klucz. Pierwsze cztery to moje wlasne bledy.
RAZEM = [
    ("Lithii carbonas", "Lithium carbonicum"),
    ("Methadoni hydrochloridum", "Methadonum"),
    ("Ketamini hydrochloridum", "Ketaminum"),
    ("Memantini hydrochloridum", "Memantinum"),
    ("Zolpidemi tartras", "Zolpidemum"),
    ("Acidum valproicum", "Natrii valproas"),
    ("Haloperidoli decanoas", "Haloperidolum"),
    ("Zuclopenthixoli acetas", "Zuclopenthixoli decanoas"),
    ("Carbidopum + Levodopum", "Levodopum + Carbidopa"),
    ("Bisoprololi fumaras", "Bisoprololum"),
]
# B. Pary, ktore NIE MOGA dac tego samego klucza.
OSOBNO = [
    ("Bifonazolum", "Bifonazolum + Urea"),
    ("Calcii carbonas", "Kalii chloridum"),
    ("Zuclopenthixolum", "Flupentixolum"),
    ("Olanzapinum", "Clozapinum"),
    ("Levodopum", "Carbidopum"),
    ("Escitalopramum", "Citalopramum"),
]
# Czy temat trafia w nazwe miedzynarodowa uzywana w ksiazkach.
W_KSIAZCE = [
    ("Lithii carbonas", "lithium"), ("Methadoni hydrochloridum", "methadone"),
    ("Ketamini hydrochloridum", "ketamine"), ("Quetiapinum", "quetiapine"),
    ("Acidum valproicum", "valproate"), ("Paliperidonum", "paliperidone"),
]


def uruchom():
    bledy = []
    for a, b in RAZEM:
        ka, kb = inn.klucz(a), inn.klucz(b)
        if ka != kb:
            bledy.append("RAZEM %r vs %r: %s != %s" % (a, b, ka, kb))
    print("A. pary, ktore maja sie zejsc: %d" % len(RAZEM))

    for a, b in OSOBNO:
        ka, kb = inn.klucz(a), inn.klucz(b)
        if ka == kb:
            bledy.append("OSOBNO %r vs %r dostaly WSPOLNY klucz %s" % (a, b, ka))
    print("B. pary, ktore maja zostac osobno: %d" % len(OSOBNO))

    for lac, inter in W_KSIAZCE:
        if not inn.w_tekscie(inn.klucz(lac), inter):
            bledy.append("W_KSIAZCE %r nie trafia w %r (klucz %s)" % (lac, inter, inn.klucz(lac)))
    print("   trafienia w nazwy miedzynarodowe: %d" % len(W_KSIAZCE))

    k = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = json.load(open(os.path.join(k, "slownik", "slownik_inn.json"), encoding="utf-8"))
    rej = d["REJESTR"]
    if "" in rej:
        bledy.append("BILANS: istnieje PUSTY klucz - to ciche scalenie")
    we = sum(len(v) for v in rej.values())
    print("C. bilans: nazw %d -> kluczy %d | zubozonych %d"
          % (we, len(rej), sum(1 for x in rej if "ZUBOZONY" in x)))

    print()
    if bledy:
        print("FAIL - %d bledow:" % len(bledy))
        for b in bledy:
            print("  -", b)
        return 1
    print("PASS - bez bledow.")
    return 0


if __name__ == "__main__":
    sys.exit(uruchom())

"""PROBA ZLOSLIWA — probuje zlamac slownik postaci, nie potwierdzic go.
Kazdy przypadek ma jawne OCZEKIWANIE. Rozbieznosc = znalezisko, nie porazka testu.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "slownik"))
import postacie as PO

ZNALEZISKA = []


def p(nazwa, postac, npow="Testinum", moc="10 mg"):
    return {"nazwa": nazwa, "postac": postac, "nazwa_powszechna": npow, "moc": moc}


def sprawdz(opis, prod, oczekiwanie, chpl=None):
    """oczekiwanie: 'RAISE' albo wartosc ekspozycji (None/KROTKA/DEPOT/POSREDNIA)"""
    try:
        e = PO.ekspozycja(prod, chpl_42=chpl)
        wynik = e["ekspozycja"]
        zrodlo = e.get("zrodlo")
    except KeyError as ex:
        wynik, zrodlo = "RAISE", str(ex)[:60]
    ok = (wynik == oczekiwanie)
    print("%-4s %-52s -> %-10s [%s]" % ("OK" if ok else "!!", opis, wynik, zrodlo))
    if not ok:
        ZNALEZISKA.append("%s: oczekiwano %s, jest %s" % (opis, oczekiwanie, wynik))
    return wynik


print("=" * 90)
print("A. NAPISY, KTORYCH NIE MA W SLOWNIKU — maja WYBUCHAC, nie klasyfikowac po cichu")
print("=" * 90)
sprawdz("wariant kolejnosci slow", p("X", "Zawiesina o przedłużonym uwalnianiu do wstrzykiwań"), "RAISE")
sprawdz("ampulkostrzykawka bez lacznika", p("X", "Roztwór do wstrzykiwań w ampułkostrzykawce"), "RAISE")
sprawdz("implant podskorny", p("X", "Implant podskórny"), "RAISE")
sprawdz("proszek + rozp. do roztworu o przedl.", p("X", "Proszek i rozpuszczalnik do sporządzania roztworu do wstrzykiwań o przedłużonym uwalnianiu"), "RAISE")
sprawdz("pusty napis", p("X", ""), "RAISE")
sprawdz("None", p("X", None), "RAISE")

print()
print("=" * 90)
print("B. NAZWA MYLACA — 'Depot' w nazwie leku DOUSTNEGO")
print("=" * 90)
sprawdz("tabletki o nazwie Cos Depot", p("Cos Depot", "Tabletki powlekane"), None)
sprawdz("tabletki o nazwie Consta Forte", p("Consta Forte", "Tabletki"), None)

print()
print("=" * 90)
print("C. ACETAS W INIEKCJI, ale NIE depot — ma zostac ZGLOSZONY jako sierota")
print("=" * 90)
prod = p("Nowylek", "Roztwór do wstrzykiwań", "Testosteroni acetas")
e = sprawdz("iniekcja z acetas, brak ChPL", prod, "KROTKA")
syg = PO.kandydat_lai(prod)
sierota = bool(syg) and e == "KROTKA"
print("     sygnaly: %s | SIEROTA: %s  <- tak ma byc: build ma zapytac" % (syg, sierota))
if not sierota:
    ZNALEZISKA.append("acetas w iniekcji nie zostal zgloszony jako sierota")

print()
print("=" * 90)
print("D. DZIURA UCZCIWA — depot bez tokenu, bez soli, bez ChPL")
print("=" * 90)
cichy = p("Paliperidon Nowy", "Roztwór do wstrzykiwań", "Paliperidonum", "100 mg")
e = sprawdz("depot calkowicie niemy", cichy, "KROTKA")
syg = PO.kandydat_lai(cichy)
print("     sygnaly: %s" % (syg or "BRAK"))
print("     WNIOSEK: bez ChPL taki produkt przechodzi jako KROTKA i nic go nie lapie.")
print("     To granica metody, nie blad. Musi byc nazwana w dokumentacji.")
# a teraz z ChPL
# Po poprawce z 2026-09-24 kadencja NIE klasyfikuje - jest alarmem. Produkt zostaje
# KROTKA, ale wchodzi na liste do przegladu. Dowod, ze tak musi byc: ChPL
# Clopixol-Acuphase pasuje do wzorca kadencji, bo opisuje przejscie na dekanian.
e2 = sprawdz("ten sam produkt, ale z ChPL 4.2 (kadencja = ALARM)", cichy, "KROTKA",
             chpl="Dawke podtrzymujaca podaje sie co cztery tygodnie do miesnia posladkowego.")
syg2 = PO.kandydat_lai(cichy, chpl_42="Dawke podtrzymujaca podaje sie co cztery tygodnie.")
print("     sygnaly z ChPL: %s" % syg2)

print()
print("=" * 90)
print("E. POSTAC WIELODROGOWA — jeden produkt, dwa koszyki")
print("=" * 90)
kl = PO.postac_klasa("Roztwór do wstrzykiwań / do infuzji")
print("     drogi: %s | uwalnianie: %s" % (kl["droga"], kl["uwalnianie"]))
if len(kl["droga"]) != 2:
    ZNALEZISKA.append("postac wielodrogowa nie dala dwoch drog")
kl2 = PO.postac_klasa("Roztwór do infuzji i roztwór doustny")
print("     drogi: %s" % kl2["droga"])

print()
print("=" * 90)
print("F. KANONIZACJA — czy tabela wyjatkow wytrzymuje drobne roznice w napisie")
print("=" * 90)
sprawdz("Fluanxol Depot — wzorzec", p("Fluanxol Depot", "Roztwór do wstrzykiwań"), "DEPOT")
sprawdz("spacja na koncu nazwy", p("Fluanxol Depot ", "Roztwór do wstrzykiwań"), "DEPOT")
sprawdz("male litery", p("fluanxol depot", "Roztwór do wstrzykiwań"), "DEPOT")
sprawdz("twarda spacja w nazwie", p("Fluanxol Depot", "Roztwór do wstrzykiwań"), "DEPOT")
sprawdz("mylnik zamiast lacznika", p("Clopixol–Depot", "Roztwór do wstrzykiwań"), "DEPOT")
sprawdz("spacja w nazwie z lacznikiem", p("Clopixol - Depot", "Roztwór do wstrzykiwań"), "DEPOT")

print()
print("=" * 90)
print("G. FALSZYWE DZIEDZICZENIE — nazwa podobna do wyjatku NIE moze dziedziczyc DEPOT")
print("=" * 90)
sprawdz("Fluanxol (sam, doustny)", p("Fluanxol", "Tabletki powlekane"), None)
sprawdz("Fluanxol Depot Forte (inny produkt)", p("Fluanxol Depot Forte", "Roztwór do wstrzykiwań"), "KROTKA")
sprawdz("Decaldol Mini (inny produkt)", p("Decaldol Mini", "Roztwór do wstrzykiwań"), "KROTKA")

print()
print("=" * 90)
if ZNALEZISKA:
    print("ZNALEZISKA: %d" % len(ZNALEZISKA))
    for z in ZNALEZISKA:
        print("  -", z)
else:
    print("ZNALEZISK: 0")

# psychai-refundacja

Pliki wykonawcze modułu refundacji PSYCH-AI (moduł 39).

- `REFUNDACJA_ENGINE.py` — silnik; jedyne źródło werdyktu refundacyjnego.
- `REFUNDACJA_DATA.json` — dane z wykazu A1 obwieszczenia MZ (publiczne).
- `generator/` — skrypt budujący dane z załącznika xlsx MZ.
- `kandydaci/` — dane nowego wykazu przed wdrożeniem (budowane automatem).
- `zrodla/` — załączniki xlsx MZ i ostatni znany wykaz.

**Brak danych pacjentów.** Repozytorium zawiera wyłącznie kod i publiczne dane MZ.

Moduł 39 pobiera pliki z konkretnych, przypiętych wersji (commit) i sprawdza ich sumy sha256.
Zmiana pliku w repozytorium NIE zmienia danych używanych przy wizycie, dopóki 39 nie wskaże nowej wersji.

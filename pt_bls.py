"""pt_bls.py - Alman Bundeslebensmittelschlüssel (BLS 4.0) besin tablosu (2026-10-27; kullanıcı: "kalori değerlerini BLS'den al, model uydurmasın").

Veri: Max Rubner-Institut (2025): Bundeslebensmittelschlüssel (BLS), Version 4.0 — Deutsche Nährstoffdatenbank. Karlsruhe.
DOI 10.25826/Data20251217-134202-0, lisans CC BY 4.0 (kaynak gösterilmeli; arayüzde "BLS 4.0 · Max Rubner-Institut" yazar).
İndirme: https://blsdb.de/download → modeller/bls/ (git dışı). `kur()` xlsx'ten küçük dizin yazar: modeller/bls/bls.json
[[kod, almanca ad, ingilizce ad, kcal, protein, yag, karb, lif, doymus], ...] (100 g, yenen kısım).
`ara(sorgu)` ad sözcüklerinde arar (Almanca ve İngilizce, umlaut'suz); `deger(kod)` 100 g değerleri.
Elle: `python pt_bls.py kur`, `python pt_bls.py ara "Reis gekocht"`.
"""
import json
import re
import threading
from pathlib import Path

KLASOR = Path(__file__).resolve().parent / "modeller" / "bls"
DIZIN = KLASOR / "bls.json"
KAYNAK = "BLS 4.0 · Max Rubner-Institut"
ALANLAR = ("kcal", "protein", "yag", "karb", "lif", "doymus")
SUTUN = {"ENERCC": "kcal", "PROT625": "protein", "FAT": "yag", "CHO": "karb", "FIBT": "lif", "FASAT": "doymus"}
_veri = None
_kilit = threading.Lock()


def kur():
    """xlsx → bls.json. Döner: kayıt sayısı."""
    import openpyxl
    xl = next(KLASOR.rglob("BLS_*_Daten_*.xlsx"))
    ws = openpyxl.load_workbook(xl, read_only=True).worksheets[0]
    satirlar = ws.iter_rows(values_only=True)
    bas = next(satirlar)
    yer = {SUTUN[h.split()[0]]: i for i, h in enumerate(bas) if h and h.split()[0] in SUTUN and "[" in h}
    out = []
    for r in satirlar:
        if not r[0]:
            continue
        sayi = []
        for a in ALANLAR:
            try:
                sayi.append(round(float(r[yer[a]] or 0), 2))
            except (TypeError, ValueError):
                sayi.append(0.0)
        out.append([r[0], r[1] or "", r[2] or "", *sayi])
    DIZIN.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    global _veri
    _veri = None
    return len(out)


def _norm(s):
    s = s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", s).split()


def _yukle():
    global _veri
    with _kilit:
        if _veri is None:
            if not DIZIN.exists():
                if not any(KLASOR.rglob("BLS_*_Daten_*.xlsx")):
                    _veri = {}
                    return _veri
                kur()
            L = json.loads(DIZIN.read_text())
            _veri = {x[0]: {"kod": x[0], "de": x[1], "en": x[2], "k": set(_norm(x[1]) + _norm(x[2])), "n": len(_norm(x[1])),
                            "dk": set(_norm(x[1])), "ek": set(_norm(x[2])),
                            "yuz": dict(zip(ALANLAR, x[3:9]))} for x in L}
    return _veri


def hazir():
    return bool(_yukle())


def deger(kod):
    """100 g değerleri ve adlar; yoksa None."""
    x = _yukle().get(kod)
    return {"kod": x["kod"], "de": x["de"], "en": x["en"], "yuz": dict(x["yuz"])} if x else None


def _eslesir(s, kelimeler):
    """Sözcük ya da bileşik sözcüğün parçası (Almanca: 'haehnchen' 'haehnchenbrust'ta geçer)."""
    return s in kelimeler or (len(s) >= 4 and any(s in k for k in kelimeler))


def ara(sorgu, n=10):
    """Ad sözcükleriyle arama: eşleşen sözcük sayısı önce, sonra kısa ad (genel kalem, 'gekocht' gibi hazırlık sözcükleri de sayılır)."""
    V = _yukle()
    q = [s for s in _norm(sorgu) if len(s) > 1]
    if not q or not V:
        return []
    puan = []
    for x in V.values():
        m = sum(1 for s in q if _eslesir(s, x["k"]))
        if m:
            ilk = _eslesir(q[0], set(_norm(x["de"])[:1]) | set(_norm(x["en"])[:1]))
            tam = x["dk"] <= set(q) or x["ek"] <= set(q)  # adın bütün sözcükleri sorguda: genel kalem ("Reis gekocht")
            puan.append((m + (0.5 if ilk else 0) + (1.5 if tam else 0) - x["n"] * 0.05, x))
    puan.sort(key=lambda t: -t[0])
    return [{"kod": x["kod"], "de": x["de"], "en": x["en"], "yuz": dict(x["yuz"])} for _, x in puan[:n]]


if __name__ == "__main__":
    import sys
    a = sys.argv[1:]
    if a[:1] == ["kur"]:
        print(kur(), "kayıt")
    elif a[:1] == ["ara"]:
        for x in ara(" ".join(a[1:])):
            print(x["kod"], x["de"], "|", x["en"], x["yuz"])

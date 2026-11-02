"""Bildirim geçmişi (2026-11-02): Mac bildirimi bir kez görünüp kayboluyordu; ürünlerin üst çubuğundaki zil bu kaydı gösterir.
Kayıt kayitlar/bildirimler.jsonl ({id, t, urun, baslik, metin, url}, son 500), okunma kayitlar/bildirim_okundu.json ({urun: zaman, "hepsi": zaman}).
urun: site ürün kodu (transcript, note, ghost, content, pt, ledger, office) ya da "genel" (her ürünün zilinde görünür: disk, Claude sınırı)."""
import json
import os
import threading
import time
import uuid
from pathlib import Path

KLASOR = Path(__file__).resolve().parent / "kayitlar"
YOL = KLASOR / "bildirimler.jsonl"
OKUNDU = KLASOR / "bildirim_okundu.json"
EN_COK = 500
_kilit = threading.Lock()


def _oku():
    try:
        satirlar = YOL.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    L = []
    for s in satirlar:
        try:
            L.append(json.loads(s))
        except ValueError:
            pass
    return L


def kaydet(baslik, metin="", urun="genel", url=""):
    """Asla hata fırlatmaz: bildirim kaydı yüzünden iş durmasın. Aynı bildirim 2 dakika içinde bir daha yazılmaz."""
    try:
        k = {"id": uuid.uuid4().hex[:12], "t": int(time.time() * 1000) / 1000, "urun": str(urun or "genel"),
             "baslik": str(baslik or "")[:160], "metin": str(metin or "")[:400], "url": str(url or "")[:500]}
        with _kilit:
            L = _oku()
            if any(x.get("baslik") == k["baslik"] and x.get("metin") == k["metin"] and x.get("urun") == k["urun"] and k["t"] - x.get("t", 0) < 120 for x in L[-20:]):
                return None
            KLASOR.mkdir(exist_ok=True)
            with open(YOL, "a", encoding="utf-8") as f:
                f.write(json.dumps(k, ensure_ascii=False) + "\n")
            if len(L) >= EN_COK + 100:
                g = YOL.with_suffix(f".{os.getpid()}.tmp")
                g.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in [*L, k][-EN_COK:]), encoding="utf-8")
                os.replace(g, YOL)
        return k
    except Exception:  # noqa: BLE001
        return None


def _okundu():
    try:
        return json.loads(OKUNDU.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _sinir(O, urun):
    return max(O.get(urun, 0), O.get("hepsi", 0))


def liste(urun="", n=60):
    """urun verilirse o ürünün ve genel bildirimler; yeni olan önce. Her satırda okunmamış işareti."""
    O, L = _okundu(), _oku()
    if urun:
        L = [x for x in L if x.get("urun") in (urun, "genel")]
    return [{**x, "yeni": x.get("t", 0) > _sinir(O, urun or x.get("urun", ""))} for x in L[::-1][:n]]


def okunmamis(urun):
    O = _okundu()
    s = _sinir(O, urun)
    return sum(1 for x in _oku() if x.get("urun") in (urun, "genel") and x.get("t", 0) > s)


def okundu(urun=""):
    """urun boşsa hepsi okundu sayılır."""
    with _kilit:
        O = _okundu()
        O[urun or "hepsi"] = time.time()
        KLASOR.mkdir(exist_ok=True)
        g = OKUNDU.with_suffix(f".{os.getpid()}.tmp")
        g.write_text(json.dumps(O), encoding="utf-8")
        os.replace(g, OKUNDU)

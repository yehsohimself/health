"""pt_kitaplik.py - Health hareket kitaplığı (2026-10-27; Lyfta / Nike Training Club esinli).

- Kaydedilenler: yer imi gibi; hızlı antrenmanda "Kaydettiklerimden" seçeneği bunları kullanır (pt/kaydedilenler.json).
- Hareket özeti: her hareketin kaç seansta yapıldığı, son tarih, kişisel rekor; hareket geçmişi (set set, grafik için).
- Kas durumu: son 7 günde kas başına set (hareket kartlarındaki birincil kaslar 1, ikincil 0,5 sayılır) ve tazelik
  (son yüklenmeden bu yana geçen süre: <24 sa yorgun, 24-48 sa toparlanıyor, >48 sa hazır). Hızlı antrenman odak önerisi bunu kullanır.
- Kas simgeleri: pt_medya/_kas/<kas>.jpg görselindeki limon yeşili parlamanın çevresinden kare kesit (kitaplıktaki kas şeridi için).
"""
import datetime as dt
import threading

import pt
import pt_kart

KAYDEDILENLER = pt.VERI / "kaydedilenler.json"
KAS = pt_kart.MEDYA / "_kas"
_kilit = threading.Lock()
_onbellek = {}


def kaydedilenler():
    return [k for k in pt._json(KAYDEDILENLER, {}).get("hareketler") or [] if isinstance(k, str)]


def kaydet(kod, kayitli=True):
    if kod not in pt.katalog():
        raise ValueError("Böyle bir hareket yok.")
    with _kilit:
        L = [k for k in kaydedilenler() if k != kod]
        if kayitli:
            L.insert(0, kod)
        pt._yaz(KAYDEDILENLER, {"hareketler": L[:300]})
    return L


def _seanslar(gun_sayisi):
    """(tarih, seans) çiftleri, eskiden yeniye. Önbellek: pt_oyun'un dosya imzası."""
    import pt_oyun
    imza = (pt_oyun._imza(), gun_sayisi)
    with _kilit:
        if _onbellek.get("imza") != imza:
            L = []
            for d in reversed(pt.gunler(gun_sayisi)):
                for s in d.get("seanslar") or []:
                    if s.get("bitti"):
                        L.append((d["tarih"], s))
            _onbellek.update(imza=imza, veri=L)
        return _onbellek["veri"]


def _degerler(h):
    return [float(x["deger"]) for x in h.get("setler") or [] if isinstance(x.get("deger"), (int, float))]


def hareket_ozet(gun_sayisi=365):
    out = {}
    for tarih, s in _seanslar(gun_sayisi):
        for h in s.get("hareketler") or []:
            k = h.get("kod")
            v = _degerler(h)
            o = out.setdefault(k, {"sayi": 0, "son": None, "rekor": None, "set": 0})
            o["sayi"] += 1
            o["son"] = tarih
            o["set"] += len(v)
            if v:
                o["rekor"] = max(v + ([o["rekor"]] if o["rekor"] is not None else []))
    return out


def hareket_gecmis(kod, gun_sayisi=365):
    if kod not in pt.katalog():
        raise ValueError("Böyle bir hareket yok.")
    L, en = [], None
    for tarih, s in _seanslar(gun_sayisi):
        for h in s.get("hareketler") or []:
            if h.get("kod") != kod:
                continue
            v = _degerler(h)
            if not v:
                continue
            rekor = en is not None and max(v) > en
            en = max(v + ([en] if en is not None else []))
            L.append({"tarih": tarih, "setler": v, "en_iyi": max(v), "toplam": sum(v), "rekor": rekor, "zorluk": h.get("zorluk")})
    kat = pt.katalog()
    return {"kod": kod, "olcu": kat[kod].get("olcu"), "kayitlar": L[-40:], "rekor": en, "hedef": pt.hedef(kod, kat),
            "aktif": bool((pt.ilerleme()["hareketler"].get(kod) or {}).get("aktif"))}


def kas_durumu(gun_sayisi=7):
    """Kas başına son 7 günde set, son yüklenme ve tazelik (0-1)."""
    K = pt_kart.kartlar()
    simdi = dt.datetime.now()
    set_, son = {}, {}
    for tarih, s in _seanslar(max(gun_sayisi, 7)):
        g = dt.datetime.fromisoformat(tarih + "T18:00")
        if s.get("t"):
            g = dt.datetime.fromtimestamp(s["t"])
        for h in s.get("hareketler") or []:
            n = len(_degerler(h)) or len(h.get("setler") or [])
            kas = ((K.get(h.get("kod")) or {}).get("kaslar")) or {}
            for agirlik, L in ((1.0, kas.get("birincil") or []), (0.5, kas.get("ikincil") or [])):
                for m in L:
                    if (simdi - g).days < gun_sayisi:
                        set_[m] = set_.get(m, 0) + n * agirlik
                    if n and agirlik == 1.0 and (m not in son or g > son[m]):
                        son[m] = g
    out = []
    for m in pt_kart.KASLAR:
        saat = (simdi - son[m]).total_seconds() / 3600 if m in son else None
        taze = 1.0 if saat is None else (0.3 if saat < 24 else 0.7 if saat < 48 else 1.0)
        out.append({"kas": m, "ad": pt_kart.KAS_AD.get(m, m), "set": round(set_.get(m, 0), 1), "son": son[m].isoformat(timespec="minutes") if m in son else None,
                    "saat": round(saat) if saat is not None else None, "taze": taze})
    return out


def kas_ikon(kod, boy=220):
    """Kas görselinde parlayan bölgenin çevresinden kare simge. Döner: dosya yolu ya da None."""
    kaynak = KAS / f"{kod}.jpg"
    hedef = KAS / f"{kod}_ikon.jpg"
    if not kaynak.exists():
        return None
    if hedef.exists() and hedef.stat().st_mtime >= kaynak.stat().st_mtime:
        return hedef
    from PIL import Image
    im = Image.open(kaynak).convert("RGB")
    k = im.resize((im.width // 4, im.height // 4))
    px = k.load()
    xs, ys = [], []
    for y in range(k.height):
        for x in range(k.width):
            r, g, b = px[x, y]
            if g > 140 and g - b > 70 and r < g and r > 70:          # limon yeşili parlama (#C4F23A ailesi)
                xs.append(x)
                ys.append(y)
    if len(xs) < 12:
        cx, cy, yari = im.width / 2, im.height * 0.42, im.width * 0.42
    else:
        xs.sort()
        ys.sort()
        n = len(xs)
        x0, x1 = xs[int(n * .03)] * 4, xs[int(n * .97) - 1] * 4
        y0, y1 = ys[int(n * .03)] * 4, ys[int(n * .97) - 1] * 4
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        yari = max(x1 - x0, y1 - y0) / 2 * 1.55 + 40
        yari = min(max(yari, im.width * 0.2), im.width / 2)
    x0, y0 = max(0, cx - yari), max(0, cy - yari)
    x1, y1 = min(im.width, x0 + 2 * yari), min(im.height, y0 + 2 * yari)
    x0, y0 = max(0, x1 - 2 * yari), max(0, y1 - 2 * yari)
    im.crop((int(x0), int(y0), int(x1), int(y1))).resize((boy, boy), Image.LANCZOS).save(hedef, "JPEG", quality=86)
    return hedef


def ikonlari_hazirla():
    return {k: bool(kas_ikon(k)) for k in pt_kart.KASLAR}


if __name__ == "__main__":
    print(ikonlari_hazirla())

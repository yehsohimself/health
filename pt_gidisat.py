"""Health: gidişat. Hareket ve oruç serileri, gün gün takvim, bir günün dökümü (2026-11-02; kullanıcı: "ana sayfada progress'i görmek istiyorum:
kaç günlük streak'teyim, şu gün şu kadar saat oruç yapmışım, ilgili güne tıklayınca o gün ne yapmışım çıkacak").

Hepsi günlük kayıtlardan kodla hesaplanır, ayrı durum dosyası yok. Oruç bir önceki günün son yemeğinden bugünün ilk yemeğine kadar sayılır ve BİTTİĞİ güne yazılır.
Son yemek işaretlenmemişse yeme saatinin planlanan uzunluğundan tahmin edilir ve `tahmini` olarak görünür."""
import datetime as dt
import time

import pt
import pt_beslenme

ORUC_TOLERANS_SA = 0.5      # 17 sa 42 dk'lık oruç 18 saatlik hedefi kaçırmış sayılmaz; gösterilen süre yine gerçek süredir
TAKVIM_GUN = 35
_ON = {}                    # tarih -> (dosya zamanı, gün kaydı)


def _gun(tarih):
    p = pt.gun_yolu(tarih)
    try:
        m = p.stat().st_mtime
    except OSError:
        return pt.gun(tarih)
    o = _ON.get(tarih)
    if o and o[0] == m:
        return o[1]
    d = pt.gun(tarih)
    _ON[tarih] = (m, d)
    return d


def _yeme_bas(d):
    L = [y.get("t") for y in d.get("yemekler") or [] if y.get("t")] + ([d["oruc_acildi"]] if d.get("oruc_acildi") else [])
    return min(L) if L else None


def _yeme_bit(d, pencere_sa=None):
    """Yeme saatinin bittiği an ve tahmin mi olduğu. Tahmin yalnız pencere_sa verilirse yapılır."""
    if d.get("oruc_kapandi"):
        return d["oruc_kapandi"], False
    L = [y.get("t") for y in d.get("yemekler") or [] if y.get("t")]
    if L:
        return max(L), False
    bas = _yeme_bas(d)
    if bas and pencere_sa:
        return bas + int(pencere_sa * 3600), True
    return None, False


def _onceki(tarih, n=1):
    return (dt.date.fromisoformat(tarih) - dt.timedelta(days=n)).isoformat()


def _pencere_sa(p=None):
    p = p or pt.profil()
    return float((p.get("beslenme") or {}).get("pencere_saat") or 6)


def oruc_hedefi(p=None):
    return 24 - _pencere_sa(p)


def oruc_gunu(tarih, p=None):
    """O gün biten oruç; kayıt yoksa None."""
    pen = _pencere_sa(p)
    bit = _yeme_bas(_gun(tarih))
    bas, tahmini = _yeme_bit(_gun(_onceki(tarih)), pen)
    if not bit or not bas or bit <= bas:
        return None
    saat = (bit - bas) / 3600
    if saat > 72:
        return None
    return {"saat": round(saat, 1), "bas_t": int(bas), "bit_t": int(bit), "tahmini": tahmini}


def suren_oruc(p=None, simdi=None):
    """Şu anki durum: {durum: 'oruc', bas_t, saat} ya da {durum: 'yeme', kalan_sa}; bilinmiyorsa None."""
    simdi = simdi or time.time()
    pen = _pencere_sa(p)
    bugun = pt.bugun().isoformat()
    d = _gun(bugun)
    bas = _yeme_bas(d)
    if bas:
        bit, tahmini = _yeme_bit(d) if d.get("oruc_kapandi") else (None, False)
        if not bit:
            sinir = bas + pen * 3600
            if simdi < sinir:
                return {"durum": "yeme", "bas_t": int(bas)}
            bit, tahmini = sinir, True
        return {"durum": "oruc", "bas_t": int(bit), "saat": round((simdi - bit) / 3600, 1), "tahmini": tahmini}
    bit, tahmini = _yeme_bit(_gun(_onceki(bugun)), pen)
    if not bit:
        return None
    return {"durum": "oruc", "bas_t": int(bit), "saat": round((simdi - bit) / 3600, 1), "tahmini": tahmini}


def hareket_gunu(tarih):
    """Biten seanslar ve dakika. Salondaki jiu-jitsu dersi ayrı kayıtsa o da sayılır."""
    d = _gun(tarih)
    S = [s for s in d.get("seanslar") or [] if s.get("bitti") and s.get("tur") != "dinlenme"]
    dk = sum(_sayi(s.get("sure_dk")) for s in S)
    if not any(s.get("tur") == "bjj_ders" for s in S):
        dk += sum(_sayi(b.get("sure_dk")) for b in d.get("bjj") or [])
    import pt_saglik
    Y = pt_saglik.yuruyusler(tarih)
    dk += sum(w["dk"] for w in Y)
    return {"dk": int(dk), "adet": len(S) + len(Y), "var": bool(S or d.get("bjj") or Y)}


def _sayi(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _ilk_tarih():
    L = sorted(f.stem for f in pt.GUNLUK.glob("*.json") if pt.tarih_gecerli(f.stem))
    return L[0] if L else None


def _seri(tamam_mi, ilk):
    """(süren seri, en uzun). Bugün henüz tamam değilse seri bozulmuş sayılmaz: gün bitmedi."""
    bugun = pt.bugun()
    if not ilk:
        return 0, 0
    gun, en, simdi_ = dt.date.fromisoformat(ilk), 0, 0
    while gun <= bugun:
        if tamam_mi(gun.isoformat()):
            simdi_ += 1
            en = max(en, simdi_)
        elif gun != bugun:
            simdi_ = 0
        gun += dt.timedelta(days=1)
    return simdi_, en


def gun_satiri(tarih, p=None):
    o, h = oruc_gunu(tarih, p), hareket_gunu(tarih)
    return {"tarih": tarih, "hareket_dk": h["dk"], "hareket": h["var"], "seans": h["adet"],
            "oruc_sa": o["saat"] if o else None, "oruc_tahmini": bool(o and o["tahmini"]),
            "oruc_tamam": bool(o and o["saat"] >= oruc_hedefi(p) - ORUC_TOLERANS_SA)}


def takvim(son=None, p=None):
    """`son`un bulunduğu haftanın pazarında biten beş hafta, pazartesiden başlar. Gelecek günler işaretli."""
    p = p or pt.profil()
    bugun = pt.bugun()
    s = dt.date.fromisoformat(son) if son and pt.tarih_gecerli(son) else bugun
    pazar = s + dt.timedelta(days=6 - s.weekday())
    ilk = _ilk_tarih()
    bas = pazar - dt.timedelta(days=TAKVIM_GUN - 1)
    if ilk:                                                     # ilk kaydın haftasından önceki boş haftalar gösterilmez
        ilk_g = dt.date.fromisoformat(ilk)
        bas = max(bas, min(ilk_g - dt.timedelta(days=ilk_g.weekday()), pazar - dt.timedelta(days=6)))
    L = []
    g = bas
    while g <= pazar:
        L.append({"tarih": g.isoformat(), "gelecek": True} if g > bugun else gun_satiri(g.isoformat(), p))
        g += dt.timedelta(days=1)
    return {"gunler": L, "son": pazar.isoformat(), "onceki": bool(ilk and dt.date.fromisoformat(ilk) < bas), "sonraki": pazar < bugun}


def ozet(son=None):
    p = pt.profil()
    bugun = pt.bugun()
    ilk = _ilk_tarih()
    hedef = oruc_hedefi(p)
    h_seri, h_en = _seri(lambda t: hareket_gunu(t)["var"], ilk)
    o_seri, o_en = _seri(lambda t: gun_satiri(t, p)["oruc_tamam"], ilk)
    yedi = [gun_satiri((bugun - dt.timedelta(days=i)).isoformat(), p) for i in range(6, -1, -1)]
    pzt = bugun - dt.timedelta(days=bugun.weekday())
    hafta = [gun_satiri((pzt + dt.timedelta(days=i)).isoformat(), p) for i in range(bugun.weekday() + 1)]
    orucler = [g["oruc_sa"] for g in yedi if g["oruc_sa"] is not None]
    son_oruc = next((g for g in reversed(yedi) if g["oruc_sa"] is not None), None)
    return {"hareket": {"seri": h_seri, "en_uzun": h_en, "bugun": yedi[-1]["hareket"], "hafta_gun": sum(1 for g in hafta if g["hareket"]),
                        "hafta_dk": sum(g["hareket_dk"] for g in hafta)},
            "oruc": {"seri": o_seri, "en_uzun": o_en, "hedef": hedef, "son": son_oruc, "ortalama": round(sum(orucler) / len(orucler), 1) if orucler else None,
                     "suren": suren_oruc(p), "bugun": yedi[-1]["oruc_tamam"]},
            "yedi": yedi, "takvim": takvim(son, p), "var": bool(ilk and (h_en or o_en or orucler)), "tolerans_dk": int(ORUC_TOLERANS_SA * 60)}


def _set_yazi(h):
    """'2 × 22' ya da '20, 25 sn'. Aynı değerler tek yazılır."""
    ad = pt.KATALOG.get(h.get("kod")) or {}
    D = [x.get("deger") for x in h.get("setler") or [] if x.get("deger") not in (None, "")]
    if not D:
        return ""
    birim = " sn" if ad.get("olcu") in ("sure", "sn", "saniye") else ""
    return f"{len(D)} × {D[0]}{birim}" if len(set(map(str, D))) == 1 else ", ".join(map(str, D)) + birim


def gun_ozet(tarih):
    """Bir günün dökümü: ne yapılmış, ne kadar oruç, ne yenmiş, nasıl uyumuş."""
    if not pt.tarih_gecerli(tarih):
        raise ValueError("Tarih geçersiz.")
    p = pt.profil()
    d = _gun(tarih)
    seanslar = []
    for s in d.get("seanslar") or []:
        if not s.get("bitti") or s.get("tur") == "dinlenme":
            continue
        seanslar.append({"baslik": s.get("baslik") or s.get("ad") or "Antrenman", "dk": int(_sayi(s.get("sure_dk"))), "zorluk": s.get("zorluk"), "not": s.get("not"),
                         "bitis_t": s.get("bitis_t"), "sohbet": s.get("kaynak") == "sohbet",
                         "hareketler": [{"ad": (pt.KATALOG.get(h.get("kod")) or {}).get("ad") or h.get("ad") or h.get("kod") or "", "setler": _set_yazi(h)}
                                        for h in s.get("hareketler") or [] if h.get("setler")]})
    import pt_saglik
    for w in pt_saglik.yuruyusler(tarih):
        seanslar.append({"baslik": w["ad"], "dk": w["dk"], "bitis_t": w["bit"], "yuruyus": True, "hareketler": [],
                         "not": f"{dt.datetime.fromtimestamp(w['bas']).strftime('%H:%M')} · telefon {w['adim']:,} adım saydı".replace(",", ".")})
    seanslar.sort(key=lambda x: x.get("bitis_t") or 0)
    yemekler = []
    for y in d.get("yemekler") or []:
        t = pt_beslenme.gun_toplam({"yemekler": [y]})
        yemekler.append({"ad": y.get("ad") or ", ".join(k.get("ad", "") for k in (y.get("kalemler") or [])[:3]), "t": y.get("t"), "kcal": t.get("kcal"), "protein": t.get("protein")})
    pen = _pencere_sa(p)
    bas = _yeme_bas(d)
    bit, bit_tahmini = _yeme_bit(d, pen if tarih != pt.bugun().isoformat() else None)
    sabah = d.get("sabah") or {}
    import pt_saglik
    return {"tarih": tarih, "adim": pt_saglik.adim_bilgi((pt_saglik.gun(tarih) or {}).get("adim"), p), "satir": gun_satiri(tarih, p), "hedef_oruc": oruc_hedefi(p), "oruc": oruc_gunu(tarih, p),
            "yeme": {"bas_t": bas, "bit_t": bit, "tahmini": bit_tahmini} if bas else None,
            "seanslar": seanslar, "yemekler": yemekler, "toplam": pt_beslenme.gun_toplam(d),
            "bjj": [{k: b.get(k) for k in ("sure_dk", "zorluk", "not")} for b in d.get("bjj") or []],
            "sabah": {k: sabah.get(k) for k in ("isik", "uyku", "uyku_saat", "enerji", "hasta", "not")} if sabah else None,
            "kilo": d.get("kilo"), "bel_cm": d.get("bel_cm"), "su_ml": d.get("su_ml"), "agri": [{k: a.get(k) for k in ("bolge", "puan", "tur")} for a in d.get("agri") or []],
            "moduller": sorted((d.get("moduller") or {}).keys()) if isinstance(d.get("moduller"), dict) else (d.get("moduller") or []),
            "aksam": (d.get("aksam") or {}).get("koc") if isinstance(d.get("aksam"), dict) else None}

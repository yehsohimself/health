"""pt_hikaye.py - Haftanın hikâyesi (2026-10-31; kullanıcı: "deneyim humanize edilmeli, bambaşka deneyimler entegre edilmeli").

Hafta sonunda (ya da istendiğinde) haftanın kısa, tam ekran, kaydırılan özeti: hareketli günler, ne yapıldığı, en iyi an, sağlık dozu,
Apple Sağlık (adım, uyku), kilo, gelecek hafta. Bütün sayılar kodla günlüklerden hesaplanır; son kartın cümlesi haftalık koç mesajından
(varsa) ya da kuraldan gelir. Uydurma yok: verisi olmayan kart hiç gösterilmez.
"""
import datetime as dt
import statistics

import pt

TUR_AD = {"kalistenik": "Güç", "bjj_solo": "Jiu-jitsu (evde)", "bjj_ders": "Jiu-jitsu dersi", "flow": "Akış", "mobilite": "Hareketlilik",
          "bisiklet": "Bisiklet", "kardiyo": "Kardiyo", "test": "Test", "spor": "Spor", "yuruyus": "Yürüyüş"}
SPOR_AD = {"futbol": "Futbol", "basketbol": "Basketbol", "tenis": "Tenis", "yuzme": "Yüzme", "kosu": "Koşu", "yuruyus": "Yürüyüş",
           "bisiklet": "Bisiklet", "yoga": "Yoga", "pilates": "Pilates", "bjj": "Jiu-jitsu"}
GUN = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def varsayilan_hafta(bugun=None):
    """Cumartesi-pazar: bu hafta; pazartesi-salı: geçen hafta; diğer günler bu hafta (sürüyor)."""
    b = bugun or pt.bugun()
    return pt.hafta_kodu(b - dt.timedelta(days=7)) if b.weekday() <= 1 else pt.hafta_kodu(b)


def _tur(s):
    if s.get("spor") or (s.get("kardiyo") or {}).get("tur"):
        k = s.get("spor") or s["kardiyo"]["tur"]
        return SPOR_AD.get(k, str(k).replace("_", " ").capitalize())
    return TUR_AD.get(s.get("tur"), str(s.get("tur") or "Antrenman").capitalize())


def hikaye(kod=None):
    import pt_saglik
    kod = pt.hafta_gecerli(kod) if kod else varsayilan_hafta()
    bugun = pt.bugun()
    gunler = [g for g in pt.hafta_gunleri(kod)]
    G, seanslar, sabahlar = [], [], []
    adim, uyku, kilo = [], [], []
    yemek = 0
    for g in gunler:
        t = g.isoformat()
        if g > bugun:
            G.append({"gun": GUN[g.weekday()], "tarih": t, "dk": 0, "gelecek": True})
            continue
        d = pt.gun(t)
        b = [s for s in d.get("seanslar") or [] if s.get("bitti")]
        seanslar += [{**s, "tarih": t} for s in b]
        dk = sum(int(s.get("sure_dk") or 0) for s in b)
        G.append({"gun": GUN[g.weekday()], "tarih": t, "dk": dk, "seans": len(b)})
        if d.get("sabah"):
            sabahlar.append(d["sabah"])
        yemek += len(d.get("yemekler") or [])
        sg = pt_saglik.gun(t) or {}
        if sg.get("adim"):
            adim.append(int(sg["adim"]))
        u = sg.get("uyku_saat") or (d.get("sabah") or {}).get("uyku_saat")
        if u:
            uyku.append(float(u))
        k = d.get("kilo") or sg.get("kilo")
        if k:
            kilo.append(float(k))
    toplam = sum(x["dk"] for x in G)
    aktif = sum(1 for x in G if x.get("dk"))
    tur = {}
    for s in seanslar:
        a = _tur(s)
        tur[a] = tur.get(a, 0) + int(s.get("sure_dk") or 0)
    turler = sorted(({"ad": a, "dk": v} for a, v in tur.items() if v), key=lambda x: -x["dk"])
    an = max(seanslar, key=lambda s: (int(s.get("yuk") or 0), int(s.get("sure_dk") or 0)), default=None)
    yukselen = [i for s in seanslar for i in (s.get("ilerleme") or []) if (i.get("tip") or i.get("yon")) in ("yukari", "ust", "basamak", None)]
    try:
        import pt_uzun
        doz = [x for x in (pt_uzun.doz_ozeti(kod).get("satirlar") or []) if x.get("hedef")]
    except Exception:  # noqa: BLE001
        doz = []
    try:
        import pt_oyun
        seri = (pt_oyun.ozet() or {}).get("seri") or 0
    except Exception:  # noqa: BLE001
        seri = 0
    enerji = [int(s["enerji"]) for s in sabahlar if str(s.get("enerji") or "").isdigit()]
    sonraki = pt.hafta_kodu(gunler[0] + dt.timedelta(days=7))
    pl = pt.program(sonraki) if pt.program_yolu(sonraki).exists() else {}
    plan_gun = [x for x in pl.get("gunler") or [] if x.get("tur") not in ("dinlenme", None)]
    mesaj = pt._json(pt.MESAJLAR / f"{kod}.json", {})
    kapanis = (mesaj.get("degisecek") or "").strip() or _kural_kapanis(aktif, toplam, doz, gunler[-1] > bugun)
    return {
        "hafta": kod, "bas": gunler[0].isoformat(), "bit": gunler[-1].isoformat(), "suruyor": gunler[-1] > bugun,
        "bos": not seanslar and not adim and not uyku and not kilo,
        "gunler": G, "aktif": aktif, "dakika": toplam, "seans": len(seanslar), "turler": turler[:5],
        "an": {"baslik": an.get("baslik") or _tur(an), "tur": _tur(an), "dk": int(an.get("sure_dk") or 0), "not": (an.get("not") or "")[:120],
               "gun": GUN[dt.date.fromisoformat(an["tarih"]).weekday()], "zorluk": an.get("zorluk")} if an else None,
        "yukselen": len(yukselen), "doz": doz, "seri": seri,
        "adim": round(statistics.mean(adim)) if adim else None, "adim_gun": len(adim),
        "uyku": round(statistics.mean(uyku), 1) if uyku else None, "uyku_gun": len(uyku),
        "kilo": {"bas": kilo[0], "son": kilo[-1], "fark": round(kilo[-1] - kilo[0], 1)} if len(kilo) >= 2 else ({"son": kilo[0]} if kilo else None),
        "sabah": len(sabahlar), "enerji": round(statistics.mean(enerji), 1) if enerji else None, "yemek": yemek,
        "gelecek": {"seans": len(plan_gun), "ilk": (plan_gun[0].get("baslik") if plan_gun else None), "var": bool(pl)},
        "kapanis": kapanis,
    }


def _kural_kapanis(aktif, dk, doz, suruyor=False):
    eksik = [x["ad"].lower() for x in doz if x.get("yapilan", 0) < x.get("hedef", 0)]
    if suruyor:
        if not aktif:
            return "Bu hafta henüz hareket kaydı yok. Hafta bitmeden tek bir 10 dakikalık seans bile sayılır."
        return f"Şimdiye kadar {aktif} gün hareket ettiniz. Hafta bitmeden bir gün daha ekleyebiliriz" + (f"; en çok {eksik[0]} eksik." if eksik else ".")
    if not aktif:
        return "Bu hafta hareket kaydı yok. Gelecek hafta tek bir 10 dakikalık seansla başlamak yeter."
    if aktif >= 4:
        return "Güçlü bir hafta. Gelecek hafta aynı ritmi koruyun" + (f"; yalnız {eksik[0]} biraz eksik kaldı." if eksik else ".")
    return f"{aktif} gün hareket ettiniz. Gelecek hafta bir gün daha ekleyelim" + (f"; en çok {eksik[0]} eksik kaldı." if eksik else ".")


def bugun_karti():
    """Bugün ekranında hikâye kartı: cumartesi akşamı, pazar ve pazartesi; haftada veri varsa."""
    b = pt.bugun()
    import datetime as _dt
    if not (b.weekday() in (6, 0) or (b.weekday() == 5 and _dt.datetime.now().hour >= 17)):
        return None
    h = hikaye()
    if h["bos"]:
        return None
    return {"hafta": h["hafta"], "aktif": h["aktif"], "dakika": h["dakika"], "suruyor": h["suruyor"]}

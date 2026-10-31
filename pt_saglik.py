"""pt_saglik.py - Apple Sağlık köprüsü (2026-10-25). iPhone Kısayolu ya da Health Auto Export uygulaması verileri `POST /api/pt/saglik?anahtar=...`
adresine gönderir (evde 8771, dışarıda eşleşmiş tünel 8770: anahtar yeterli, çerez gerekmez). Kayıt pt/saglik/<tarih>.json.

Hazır olma (HRV4Training yöntemi, araştırma raporu): son 7 günün HRV ortalaması, son 60 günün ortalaması ± 0,5 standart sapma "normal aralık"la
karşılaştırılır; aralığın altı → toparlanmaya öncelik. Sabah nabzı kendi ortalamasının 5 atım üstündeyse ve uyku 6 saatin altındaysa da işaret.
Apple Watch HRV'yi SDNN ile ve seyrek ölçer; uyanınca 1 dakikalık Nefes/Farkındalık seansı ölçümü zorlar (kullanıcıya önerilir).
"""
import datetime as dt
import json
import secrets
import statistics
import time

import pt

KLASOR = pt.VERI / "saglik"
AYAR = pt.VERI / "ayar.json"
ANTRENMAN_TUR = {"cycling": "bisiklet", "bisiklet": "bisiklet", "outdoor cycle": "bisiklet", "indoor cycle": "bisiklet", "martial arts": "bjj_ders",
                 "dövüş sanatları": "bjj_ders", "functional strength training": "kalistenik", "traditional strength training": "kalistenik",
                 "fonksiyonel kuvvet antrenmanı": "kalistenik", "yoga": "mobilite", "flexibility": "mobilite", "walking": "yuruyus", "yürüyüş": "yuruyus",
                 "running": "kosu", "koşu": "kosu"}


def anahtar():
    a = pt._json(AYAR, {})
    if not a.get("saglik_anahtar"):
        a["saglik_anahtar"] = secrets.token_urlsafe(18)
        pt._yaz(AYAR, a)
    return a["saglik_anahtar"]


def anahtar_gecerli(k):
    return bool(k) and secrets.compare_digest(str(k), anahtar())


def _sayi(v):
    f = pt.sayi(v, -1e6, 1e6)
    return round(f, 2) if f is not None else None


def _gun_yaz(tarih, ek):
    tarih = pt.tarih_gecerli(tarih)
    with pt._kilit:
        p = KLASOR / f"{tarih}.json"
        d = pt._json(p, {"tarih": tarih})
        for k, v in ek.items():
            if k == "antrenmanlar":
                var = {a.get("bas") for a in d.get("antrenmanlar") or []}
                d["antrenmanlar"] = (d.get("antrenmanlar") or []) + [a for a in v if a.get("bas") not in var]
            elif v is not None:
                d[k] = v
        d["guncelleme"] = int(time.time())
        pt._yaz(p, d)
        return d


def _hae(veri):
    """Health Auto Export JSON'u → {tarih: {alan: değer}}."""
    out = {}
    adlar = {"sleep_analysis": "uyku_saat", "resting_heart_rate": "nabiz", "heart_rate_variability": "hrv", "weight_body_mass": "kilo",
             "step_count": "adim", "body_mass": "kilo", "vo2_max": "vo2max", "vo2max": "vo2max",
             "cardio_fitness": "vo2max"}
    for m in (veri.get("data") or {}).get("metrics") or []:
        alan = adlar.get(m.get("name"))
        if not alan:
            continue
        for x in m.get("data") or []:
            t = str(x.get("date") or "")[:10]
            try:
                t = pt.tarih_gecerli(t)
            except ValueError:
                continue
            v = x.get("totalSleep") or x.get("asleep") or x.get("qty") if alan == "uyku_saat" else x.get("qty")
            if t and v is not None:
                if alan == "adim":
                    out.setdefault(t, {})[alan] = (out.get(t, {}).get(alan) or 0) + int(v)
                else:
                    out.setdefault(t, {})[alan] = _sayi(v)
    for w in (veri.get("data") or {}).get("workouts") or []:
        t = str(w.get("start") or "")[:10]
        if t:
            out.setdefault(t, {}).setdefault("antrenmanlar", []).append(_antrenman(w.get("name"), w.get("duration"), w.get("start"),
                                                                                 (w.get("activeEnergyBurned") or {}).get("qty"), (w.get("distance") or {}).get("qty")))
    return out


def _antrenman(ad, sure, bas, kcal=None, mesafe=None):
    s = _sayi(sure) or 0
    if s > 600:                                   # saniye geldiyse
        s = s / 60
    return {"ad": str(ad or "Antrenman")[:60], "tur": ANTRENMAN_TUR.get(str(ad or "").lower().strip(), "diger"), "sure_dk": round(s),
            "bas": str(bas or "")[:25], "kcal": _sayi(kcal), "mesafe_km": _sayi(mesafe)}


def kaydet(veri):
    """Kısayol (düz alanlar) ya da Health Auto Export biçimi. Döner: yazılan günler."""
    if isinstance(veri, dict) and "data" in veri and isinstance(veri["data"], dict):
        gunler = _hae(veri)
    else:
        t = pt.tarih_gecerli((veri or {}).get("tarih") or pt.bugun().isoformat())
        g = {a: _sayi(veri.get(a)) for a in ("uyku_saat", "hrv", "nabiz", "kilo", "adim", "vo2max") if veri.get(a) not in (None, "")}
        if g.get("uyku_saat") and g["uyku_saat"] > 24:      # dakika geldiyse
            g["uyku_saat"] = round(g["uyku_saat"] / 60, 2)
        if veri.get("antrenmanlar"):
            g["antrenmanlar"] = [_antrenman(a.get("ad") or a.get("tur"), a.get("sure_dk") or a.get("sure"), a.get("bas"), a.get("kcal"), a.get("mesafe_km"))
                                 for a in veri["antrenmanlar"] if isinstance(a, dict)]
        gunler = {t: g}
    return _gunleri_yaz(gunler)


def _gunleri_yaz(gunler):
    yazilan = []
    for t, g in gunler.items():
        d = _gun_yaz(t, g)
        yazilan.append(t)
        if g.get("kilo"):
            pt.gun_degistir(t, lambda x, k=g["kilo"]: x.setdefault("kilo", k))
        for a in g.get("antrenmanlar") or []:                # saatle kaydedilen sürüş/ders: günlüğe seans olarak (zorluk bilinmiyorsa 5)
            sid = f"saglik:{a.get('bas')}"

            def ekle(x, a=a, sid=sid):
                if any(s.get("id") == sid for s in x["seanslar"]):
                    return
                if any(s.get("tur") == a["tur"] and abs((s.get("sure_dk") or 0) - a["sure_dk"]) < 10 for s in x["seanslar"] if not str(s.get("id", "")).startswith("saglik:")):
                    return                                     # Health'te zaten kaydedilmiş
                yeni = {"id": sid, "tur": a["tur"], "baslik": a["ad"], "sure_dk": a["sure_dk"], "zorluk": a.get("zorluk") or 5,
                        "yuk": a["sure_dk"] * (a.get("zorluk") or 5), "bitti": True, "kaynak": "Apple Sağlık", "mesafe_km": a.get("mesafe_km")}
                if a.get("yogunluk"):                          # spor ve kardiyo: haftalık sağlık dozuna doğru sayılsın
                    yeni["bisiklet" if a["tur"] == "bisiklet" else "kardiyo"] = {"tur": a.get("spor") or a["tur"], "sure_dk": a["sure_dk"], "yogunluk": a["yogunluk"]}
                x["seanslar"].append(yeni)
            if a["sure_dk"] >= 10:
                pt.gun_degistir(t, ekle)
    a = pt._json(AYAR, {})
    a["saglik_son"] = int(time.time())
    pt._yaz(AYAR, a)
    return sorted(yazilan)


def gun(tarih=None):
    return pt._json(KLASOR / f"{pt.tarih_gecerli(tarih or pt.bugun().isoformat())}.json", {})


def hazirlik(tarih=None):
    """Kişinin kendi ortalamasına göre: hrv (normal|dusuk|yuksek), nabız, uyku → kısa açıklama ve ışığa katkı."""
    son = dt.date.fromisoformat(tarih) if tarih else pt.bugun()
    seri = [pt._json(KLASOR / f"{(son - dt.timedelta(days=i)).isoformat()}.json", {}) for i in range(60)]
    bugun_ = seri[0]
    if not bugun_:
        return {}
    hrv = [x.get("hrv") for x in seri if x.get("hrv")]
    nab = [x.get("nabiz") for x in seri if x.get("nabiz")]
    sonuc = {"uyku_saat": bugun_.get("uyku_saat"), "hrv": bugun_.get("hrv"), "nabiz": bugun_.get("nabiz"), "notlar": [], "dusuk": 0}
    if len(hrv) >= 10:
        ort7 = statistics.mean([x.get("hrv") for x in seri[:7] if x.get("hrv")] or hrv[:1])
        ort, ss = statistics.mean(hrv), statistics.pstdev(hrv)
        alt, ust = ort - 0.5 * ss, ort + 0.5 * ss
        sonuc["hrv_aralik"] = [round(alt), round(ust)]
        sonuc["hrv_7"] = round(ort7)
        if ort7 < alt:
            sonuc["hrv_durum"] = "dusuk"; sonuc["dusuk"] += 1
            sonuc["notlar"].append("Nabız değişkenliğiniz son günlerde kendi aralığınızın altında: toparlanmaya öncelik.")
        else:
            sonuc["hrv_durum"] = "normal" if ort7 <= ust else "yuksek"
    elif hrv:
        sonuc["notlar"].append(f"Nabız değişkenliği için kişisel aralık {10 - len(hrv)} gün sonra oluşur.")
    if len(nab) >= 7 and bugun_.get("nabiz"):
        taban = statistics.median(nab[1:]) if len(nab) > 1 else nab[0]
        if bugun_["nabiz"] >= taban + 5:
            sonuc["dusuk"] += 1
            sonuc["notlar"].append(f"Sabah nabzınız ortalamanızın {round(bugun_['nabiz'] - taban)} atım üstünde.")
    if bugun_.get("uyku_saat") and bugun_["uyku_saat"] < 6:
        sonuc["dusuk"] += 1
        sonuc["notlar"].append(f"Uyku {str(round(bugun_['uyku_saat'], 1)).replace('.', ',')} saat.")
    return sonuc


def durum():
    a = pt._json(AYAR, {})
    son = sorted(KLASOR.glob("*.json"))
    return {"anahtar": anahtar(), "son_gonderim": a.get("saglik_son"), "gun_sayisi": len(son), "son_gun": son[-1].stem if son else None,
            "ice": a.get("ice_aktarma")}


# ----------------------------------------------------------------------------- Apple Sağlık dışa aktarımı (2026-10-31)
# Mac'te Sağlık uygulaması yok; iPhone'da Sağlık → profil resmi → "Tüm sağlık verilerini dışa aktar" bir dışa_aktar.zip üretir (içinde
# apple_health_export/export.xml). Bu dosya AirDrop ile Mac'e gelir, Health'e bırakılır; son N günün uyku, dinlenme nabzı, nabız değişkenliği,
# kilo, adım, VO2max ve antrenmanları okunur (dosya büyük olabilir: akış hâlinde okunur, belleğe alınmaz). Dosya iş bitince silinir.
HK_GUN = {"HKQuantityTypeIdentifierStepCount": ("adim", "topla"), "HKQuantityTypeIdentifierRestingHeartRate": ("nabiz", "ort"),
          "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv", "ort"), "HKQuantityTypeIdentifierBodyMass": ("kilo", "son"),
          "HKQuantityTypeIdentifierVO2Max": ("vo2max", "son")}
HK_ANTRENMAN = {  # tür, ad, spor, yoğunluk, varsayılan zorluk
    "Soccer": ("spor", "Futbol", "futbol", "aralik", 7), "Basketball": ("spor", "Basketbol", "basketbol", "aralik", 7),
    "Tennis": ("spor", "Tenis", "tenis", "orta", 6), "Volleyball": ("spor", "Voleybol", "voleybol", "orta", 6),
    "Paddle": ("spor", "Padel", "padel", "orta", 6), "PickleBall": ("spor", "Pickleball", "padel", "orta", 6),
    "Running": ("kardiyo", "Koşu", "kosu", "orta", 6), "Walking": ("kardiyo", "Yürüyüş", "yuruyus", "kolay", 3),
    "Hiking": ("kardiyo", "Doğa yürüyüşü", "yuruyus", "kolay", 4), "Swimming": ("kardiyo", "Yüzme", "yuzme", "orta", 6),
    "Cycling": ("bisiklet", "Bisiklet", "bisiklet", "kolay", 5), "Rowing": ("kardiyo", "Kürek", "kurek", "orta", 6),
    "Elliptical": ("kardiyo", "Eliptik", "eliptik", "kolay", 5), "StairClimbing": ("kardiyo", "Merdiven", "merdiven", "orta", 6),
    "HighIntensityIntervalTraining": ("kardiyo", "Aralıklı antrenman", "hiit", "aralik", 8), "Dance": ("spor", "Dans", "dans", "orta", 5),
    "MartialArts": ("bjj_ders", "Dövüş sanatları", "jiujitsu", None, 8), "Wrestling": ("bjj_ders", "Güreş", "jiujitsu", None, 8),
    "Yoga": ("mobilite", "Yoga", "yoga", None, 3), "Flexibility": ("mobilite", "Esneme", "yoga", None, 3), "TaiChi": ("mobilite", "Tai chi", "taichi", None, 3),
    "MindAndBody": ("mobilite", "Zihin ve beden", "yoga", None, 3), "Pilates": ("mobilite", "Pilates", "pilates", None, 4),
    "FunctionalStrengthTraining": ("kalistenik", "Kuvvet antrenmanı", "fitness", None, 6),
    "TraditionalStrengthTraining": ("kalistenik", "Kuvvet antrenmanı", "fitness", None, 6), "CoreTraining": ("kalistenik", "Gövde antrenmanı", "fitness", None, 5),
    "CrossTraining": ("kalistenik", "Karma antrenman", "fitness", None, 7)}
ICE = {"durum": None}


def _hk_sayi(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def ice_aktar(dosya, gun=120, sil=True):
    """dışa_aktar.zip ya da export.xml → son `gun` günün verisi günlere yazılır. Döner: özet."""
    import statistics
    import xml.etree.ElementTree as ET
    import zipfile
    from pathlib import Path
    dosya = Path(dosya)
    bas = (pt.bugun() - dt.timedelta(days=gun)).isoformat()
    G, uyku = {}, {}
    sayac = {"kayit": 0, "antrenman": 0}
    try:
        if zipfile.is_zipfile(dosya):
            z = zipfile.ZipFile(dosya)
            ad = next((n for n in z.namelist() if n.endswith("/export.xml") or n == "export.xml"), None)
            if not ad:
                raise ValueError("Bu dosyada export.xml yok. iPhone Sağlık → profil → Tüm sağlık verilerini dışa aktar ile gelen dosyayı bırakın.")
            akis = z.open(ad)
        else:
            akis = open(dosya, "rb")
        for _, el in ET.iterparse(akis, events=("end",)):
            tag = el.tag
            if tag == "Record":
                tip = el.get("type") or ""
                t = (el.get("startDate") or "")[:10]
                if t >= bas and t <= pt.bugun().isoformat():
                    if tip in HK_GUN:
                        alan, nasil = HK_GUN[tip]
                        v = _hk_sayi(el.get("value"))
                        if v is not None:
                            if alan == "kilo" and (el.get("unit") or "").lower() in ("lb", "lbs"):
                                v = v * 0.453592
                            G.setdefault(t, {}).setdefault(alan, []).append(v)
                            sayac["kayit"] += 1
                    elif tip == "HKCategoryTypeIdentifierSleepAnalysis" and "Asleep" in (el.get("value") or ""):
                        try:
                            b = dt.datetime.fromisoformat((el.get("startDate") or "")[:19])
                            e = dt.datetime.fromisoformat((el.get("endDate") or "")[:19])
                            uyku.setdefault((el.get("endDate") or "")[:10], []).append((b, e))
                            sayac["kayit"] += 1
                        except ValueError:
                            pass
                el.clear()
            elif tag == "Workout":
                t = (el.get("startDate") or "")[:10]
                if bas <= t <= pt.bugun().isoformat():
                    tip = (el.get("workoutActivityType") or "").replace("HKWorkoutActivityType", "")
                    tur, ad, spor, yog, zor = HK_ANTRENMAN.get(tip, ("spor", tip or "Antrenman", "diger", "orta", 5))
                    sure = _hk_sayi(el.get("duration")) or 0
                    if (el.get("durationUnit") or "min") == "s":
                        sure /= 60
                    elif (el.get("durationUnit") or "") == "hr":
                        sure *= 60
                    mesafe = _hk_sayi(el.get("totalDistance"))
                    for st in el.findall("WorkoutStatistics"):
                        if "Distance" in (st.get("type") or "") and st.get("sum"):
                            mesafe = _hk_sayi(st.get("sum"))
                    if sure >= 5:
                        G.setdefault(t, {}).setdefault("antrenmanlar", []).append(
                            {"ad": ad, "tur": tur, "sure_dk": round(sure), "bas": (el.get("startDate") or "")[:25], "spor": spor, "yogunluk": yog,
                             "zorluk": zor, "mesafe_km": round(mesafe, 2) if mesafe else None})
                        sayac["antrenman"] += 1
                el.clear()
            elif tag in ("ActivitySummary", "ClinicalRecord", "Correlation"):
                el.clear()
        akis.close()
    finally:
        if sil:
            dosya.unlink(missing_ok=True)
    gunler = {}
    for t, d in G.items():
        g = {}
        for alan, nasil in HK_GUN.values():
            L = d.get(alan)
            if L:
                g[alan] = round(sum(L)) if nasil == "topla" else round(statistics.mean(L), 1) if nasil == "ort" else round(L[-1], 1)
        if d.get("antrenmanlar"):
            g["antrenmanlar"] = d["antrenmanlar"]
        gunler[t] = g
    for t, araliklar in uyku.items():                      # örtüşen uyku parçaları birleştirilir (saat + telefon aynı geceyi iki kez yazar)
        araliklar.sort()
        top, son_e = 0.0, None
        for b, e in araliklar:
            if son_e and b < son_e:
                b = son_e
            if e > b:
                top += (e - b).total_seconds()
                son_e = e if not son_e or e > son_e else son_e
        if top > 1800:
            gunler.setdefault(t, {})["uyku_saat"] = round(top / 3600, 2)
    for g in gunler.values():
        if g.get("kilo"):
            g["kilo"] = round(g["kilo"], 1)
    yazilan = _gunleri_yaz({t: g for t, g in gunler.items() if g})
    a = pt._json(AYAR, {})
    a["ice_aktarma"] = {"t": int(time.time()), "gun": len(yazilan), "antrenman": sayac["antrenman"], "kayit": sayac["kayit"],
                        "ilk": min(yazilan) if yazilan else None, "son": max(yazilan) if yazilan else None}
    pt._yaz(AYAR, a)
    return a["ice_aktarma"]

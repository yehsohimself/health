"""pt_oyun.py - PT'nin seri, koruma ve rozet motoru (2026-10-27; kullanıcı: "Duolingo'nun seri oyunlaştırması çok iyi, iyice düşün").

İlke: seri antrenmanı cezalandırmamalı. Her günün tek bir HEDEFİ var:
  - antrenman günü (planda seans var, sabah ışığı kırmızı değil): bir seans bitirmek (10 dakikalık asgari antrenman, BJJ dersi, saatten gelen
    antrenman da sayılır);
  - dinlenme günü, plansız gün, hasta ya da kırmızı gün: kendini dinlemek, yani sabah kontrolü ya da akşam görüşmesi.
Kaçırılan gün için önce SERİ KORUMASI harcanır (Duolingo'nun "streak freeze"i): ilk gün 1 tane verilir, üst üste her 7 tamam günde bir tane daha
kazanılır, en çok 2 birikir. Koruma yoksa seri kopar; ama iki gün içinde 10 dakikalık TELAFİ antrenmanı yapılırsa (seans kaydında `onarim_icin`)
kopan gün(ler) onarılır ve seri geri gelir.

Durum dosyada TUTULMAZ: her istek günlük kayıtlardan baştan hesaplanır (tekrar oynatma). Böylece telefondan gelen gecikmeli kayıt, geri alınan
seans ya da elle düzeltilen gün durumu kendiliğinden düzeltir; kayan sayaç yoktur. Hesap dosya değişiklik zamanlarıyla önbelleğe alınır.
Yalnız "gösterildi" işaretleri (kutlama bir kez gösterilsin) pt/oyun.json'da.
"""
import datetime as dt
import os
import threading

import pt

OYUN = pt.VERI / "oyun.json"
KORUMA_BAS, KORUMA_EN_COK, KORUMA_ARALIK = 1, 2, 7
ONARIM_GUN = 2
ESIKLER = [3, 7, 14, 21, 30, 50, 75, 100, 150, 200, 250, 365, 500, 730, 1000]
EN_ESKI_GUN = 800
_kilit = threading.Lock()
_onbellek = {}

# Hareket "ilk"leri: bu hareketten ilk kez en az şu kadar yapıldı (tekrar ya da saniye).
ILKLER = [("ilk_barfiks", "İlk barfiks", "barfiks", 1), ("ilk_dips", "İlk dips", "dips", 1), ("ilk_pistol", "İlk pistol squat", "pistol", 1),
          ("ilk_muscle_up", "İlk muscle-up", "muscle_up", 1), ("ilk_amut", "Duvarsız amut", "serbest_amut", 10), ("ilk_lsit", "İlk L-sit", "lsit", 10),
          ("ilk_tek_kol", "Tek kol şınav", "tek_kol_sinav", 1), ("ilk_front_lever", "Front lever yolunda", "adv_tuck_front_lever", 5)]

# Rozet aileleri (Duolingo'nun başarı seviyeleri gibi): her aile bir ölçü, her seviye bir eşik. Eski rozet kimlikleri korunur
# (önek_eşik: seans_10, seri_7...), böylece daha önce gösterilmiş kutlamalar yinelenmez.
# (önek, aile adı, ölçü, simge, [(eşik, rozet adı, açıklama)])
AILELER = [
    ("seans", "Antrenman", "seans", "dambil", [(1, "İlk adım", "İlk antrenmanı bitirin."), (10, "On antrenman", "Toplam 10 antrenman."),
     (25, "Yirmi beş antrenman", "Toplam 25 antrenman."), (50, "Elli antrenman", "Toplam 50 antrenman."), (100, "Yüz antrenman", "Toplam 100 antrenman."),
     (250, "İki yüz elli", "Toplam 250 antrenman.")]),
    ("seri", "Seri", "en_uzun", "alev", [(3, "Üç gün", "3 gün kesintisiz seri."), (7, "Bir hafta", "7 gün kesintisiz seri."),
     (30, "Bir ay", "30 gün kesintisiz seri."), (100, "Yüz gün", "100 gün kesintisiz seri."), (365, "Bir yıl", "365 gün kesintisiz seri.")]),
    ("gorev", "Günün görevleri", "gorev", "hedef", [(1, "Üçte üç", "Bir günün üç görevini de bitirin."), (7, "Görev haftası", "7 gün üç görev."),
     (30, "Görev ayı", "30 gün üç görev."), (100, "Yüz görev günü", "100 gün üç görev.")]),
    ("dk", "Süre", "dk", "saat", [(60, "İlk saat", "Toplam 60 dakika antrenman."), (300, "Beş saat", "Toplam 300 dakika antrenman."),
     (1000, "Bin dakika", "Toplam 1.000 dakika antrenman."), (3000, "Elli saat", "Toplam 3.000 dakika antrenman."),
     (10000, "On bin dakika", "Toplam 10.000 dakika antrenman.")]),
    ("hafta", "Mükemmel hafta", "mukemmel", "yildiz", [(1, "Mükemmel hafta", "Korumasız, eksiksiz bir hafta (Pazartesi-Pazar)."),
     (4, "Dört mükemmel hafta", "Dört kez mükemmel hafta."), (12, "On iki mükemmel hafta", "On iki kez mükemmel hafta.")]),
    ("rekor", "Rekor", "rekor", "ok", [(1, "İlk rekor", "Bir harekette kendi rekorunuzu kırın."), (5, "Beş rekor", "Toplam 5 kişisel rekor."),
     (10, "On rekor", "Toplam 10 kişisel rekor."), (25, "Yirmi beş rekor", "Toplam 25 kişisel rekor.")]),
    ("basamak", "Basamak", "basamak", "merdiven", [(1, "Bir basamak yukarı", "Bir ilerleme zincirinde üst basamağa geçin."),
     (3, "Üç basamak", "Toplam 3 basamak yukarı."), (5, "Beş basamak", "Toplam 5 basamak yukarı."), (10, "On basamak", "Toplam 10 basamak yukarı.")]),
    ("program", "Program", "program", "bayrak", [(1, "İlk program", "Hazır bir programı bitirin."), (3, "Üç program", "Üç programı bitirin.")]),
    ("sabah", "Sabah kontrolü", "sabah", "gunes", [(7, "Bir hafta dinledi", "7 sabah kontrolü."), (30, "Kendini dinleyen", "30 sabah kontrolü."),
     (100, "Yüz sabah", "100 sabah kontrolü.")]),
    ("bjj", "Minder", "bjj", "kusak", [(1, "İlk ders", "İlk BJJ dersini kaydedin."), (10, "Mindere sadık", "10 BJJ dersi."), (50, "Elli ders", "50 BJJ dersi.")]),
]
# (kod, ad, açıklama, ölçü, eşik, simge, aile, seviye)
ROZETLER = [(f"{on}_{e}", ad, ac, olcu, e, ikon, on, i + 1) for on, _, olcu, ikon, L in AILELER for i, (e, ad, ac) in enumerate(L)] + \
    [(k, ad, f"{pt.KATALOG.get(h, {}).get('ad', h)}: ilk kez {e} {'sn' if (pt.KATALOG.get(h) or {}).get('olcu') == 'sure' else 'tekrar'}.",
      "ilk:" + h, e, "kupa", "ilk", 1) for k, ad, h, e in ILKLER]

# Günün görevleri (Duolingo'nun günlük görevleri): her gün üç tane. İlki günün hedefi (antrenman ya da kontrol), diğer ikisi tarihle
# tohumlanmış seçimle havuzdan; aynı gün hep aynı görevler çıkar.
GOREVLER = {
    "seans": ("Bir antrenman bitirin", "dambil"),
    "kontrol": ("Sabah kontrolü", "gunes"),
    "hareket10": ("10 dakika hareket", "saat"),
    "su": ("Su hedefinin dörtte üçünü için", "damla"),
    "protein": ("Protein hedefinin %80'ine ulaşın", "yumurta"),
    "ogun": ("İki öğün kaydedin", "tabak"),
    "aliskanlik": ("Haftanın alışkanlığı", "tik"),
    "aksam": ("Akşam görüşmesi", "ay"),
}

def _imza():
    """Sonucu etkileyen dosyaların değişiklik zamanları: değişmedikçe önbellek kullanılır."""
    en, n = 0, 0
    for klasor in (pt.GUNLUK, pt.PROGRAM):
        try:
            with os.scandir(klasor) as it:
                for e in it:
                    if e.name.endswith(".json"):
                        en = max(en, e.stat().st_mtime_ns)
                        n += 1
        except FileNotFoundError:
            pass
    il = pt.VERI / "ilerleme.json"
    return (pt.bugun().isoformat(), en, n, il.stat().st_mtime_ns if il.exists() else 0)


def _gun_dosyalari():
    try:
        return sorted(f[:-5] for f in os.listdir(pt.GUNLUK) if len(f) == 15 and f.endswith(".json"))
    except FileNotFoundError:
        return []


def _program_gunleri(tarih, onb):
    kod = pt.hafta_kodu(tarih)
    if kod not in onb:
        onb[kod] = {}
        for g in pt.program(kod).get("gunler") or []:
            onb[kod].setdefault(g.get("tarih"), []).append(g)
    return onb[kod].get(tarih.isoformat(), [])


def gun_hedefi(planli, d):
    """'seans' ya da 'kontrol'. Kırmızı ya da hasta günde hedef kendini dinlemek."""
    s = d.get("sabah") or {}
    if any(g.get("tur") not in ("dinlenme",) for g in planli) and s.get("isik") != "kirmizi" and not s.get("hasta"):
        return "seans"
    return "kontrol"


def gun_tamam(hedef, d):
    if any(x.get("bitti") for x in d.get("seanslar") or []) or d.get("bjj") or d.get("_test"):
        return True
    return hedef == "kontrol" and bool(d.get("sabah") or d.get("aksam"))


def _gorev_baglam():
    p = pt.profil()
    try:
        import pt_beslenme
        protein = pt_beslenme.hedefler(p).get("protein")
    except Exception:
        protein = None
    return {"su": pt.su_hedefi(p), "protein": protein, "aliskanlik": bool((p.get("aliskanlik") or {}).get("metin"))}


def _protein(d):
    try:
        import pt_beslenme
        return pt_beslenme.gun_toplam(d)["protein"]
    except Exception:
        return 0


def gun_gorevleri(t, hedef, d, bag):
    """Bir günün üç görevi ve durumu."""
    import random
    havuz = ["su", "ogun", "aksam"] + (["protein"] if bag.get("protein") else []) + (["aliskanlik"] if bag.get("aliskanlik") else []) + \
        (["hareket10"] if hedef == "kontrol" else ["kontrol"])
    out = []
    for k in [hedef] + random.Random("gorev:" + t).sample(havuz, 2):
        ad, ikon = GOREVLER[k]
        deger, hedef_ = 0, 1
        if k == "seans":
            deger = 1 if gun_tamam("seans", {**d, "sabah": None, "aksam": None}) else 0
        elif k == "kontrol":
            deger = 1 if d.get("sabah") else 0
        elif k == "aksam":
            deger = 1 if d.get("aksam") else 0
        elif k == "aliskanlik":
            deger = 1 if (d.get("aliskanlik") or {}).get("tamam") else 0
        elif k == "hareket10":
            deger, hedef_ = sum(int(s.get("sure_dk") or 0) for s in d.get("seanslar") or [] if s.get("bitti")), 10
        elif k == "su":
            hedef_ = max(500, round(bag["su"] * .75 / 50) * 50)
            deger, ad = int(d.get("su_ml") or 0), f"{hedef_:,} ml su için".replace(",", ".")
        elif k == "protein":
            hedef_ = round(bag["protein"] * .8)
            deger, ad = round(_protein(d)), f"{hedef_} g protein alın"
        elif k == "ogun":
            deger, hedef_ = len(d.get("yemekler") or []), 2
        out.append({"kod": k, "ad": ad, "ikon": ikon, "deger": min(deger, hedef_), "hedef": hedef_, "tamam": deger >= hedef_})
    return out


def _hesapla():
    bugun = pt.bugun()
    dosyalar = _gun_dosyalari()
    bas = dt.date.fromisoformat(dosyalar[0]) if dosyalar else bugun
    bas = max(bas, bugun - dt.timedelta(days=EN_ESKI_GUN))
    pl_onb = {}
    gunler, onarilan, var = {}, set(), set(dosyalar)
    test_gunleri = {x.get("tarih") for x in pt.testler().get("kayitlar") or []}
    g_ = bas
    while g_ <= bugun:
        t = g_.isoformat()
        d = pt.gun(t) if t in var else {"tarih": t, "seanslar": [], "yemekler": [], "agri": [], "bjj": []}
        if t in test_gunleri:
            d = {**d, "_test": True}
        gunler[t] = d
        for s in d.get("seanslar") or []:
            if s.get("bitti"):
                for o in s.get("onarim_icin") or []:
                    try:
                        if 0 < (g_ - dt.date.fromisoformat(o)).days <= ONARIM_GUN:
                            onarilan.add(o)
                    except (TypeError, ValueError):
                        pass
        g_ += dt.timedelta(days=1)

    kat = pt.KATALOG
    seri = en_uzun = ardisik = 0
    koruma = KORUMA_BAS
    kayitlar, olaylar, kopus = [], [], None
    sayac = {"seans": 0, "dk": 0, "sabah": 0, "bjj": 0, "rekor": 0, "mukemmel": 0, "en_uzun": 0, "gorev": 0, "program": 0}
    bag = _gorev_baglam()
    biten_prog = sorted((x.get("tarih") or "", x.get("kod")) for x in pt.profil().get("program_biten") or [])
    gorev_gunleri, bugun_gorev = [], []
    rozet_tarih, en_iyi, ilk = {}, {}, {}
    basamak_gunleri = sorted(dt.date.fromtimestamp(x["t"]).isoformat() for x in pt.ilerleme().get("degisiklikler") or []
                             if x.get("tur") == "basamak" and not x.get("geri")
                             and (kat.get(x.get("yeni")) or {}).get("basamak", 0) > (kat.get(x.get("kod")) or {}).get("basamak", 0))
    hafta_tam = []
    basladi = False                                         # Duolingo gibi: seri ilk tamamlanan günle başlar; öncesi sayılmaz
    for t, d in gunler.items():
        g_ = dt.date.fromisoformat(t)
        planli = _program_gunleri(g_, pl_onb)
        hedef = gun_hedefi(planli, d)
        tamam = gun_tamam(hedef, d)
        bugun_mu = g_ == bugun
        basladi = basladi or tamam
        # birikimli sayaçlar (rozetler için)
        for s in d.get("seanslar") or []:
            if not s.get("bitti"):
                continue
            sayac["seans"] += 1
            sayac["dk"] += int(s.get("sure_dk") or 0)
            for h in s.get("hareketler") or []:
                v = [float(x["deger"]) for x in h.get("setler") or [] if isinstance(x.get("deger"), (int, float))]
                if not v:
                    continue
                k, m = h.get("kod"), max(v)
                if k in en_iyi and m > en_iyi[k]:
                    sayac["rekor"] += 1
                    olaylar.append({"id": f"rekor:{k}:{t}", "tarih": t, "tur": "rekor", "kod": k, "deger": m, "onceki": en_iyi[k]})
                en_iyi[k] = max(m, en_iyi.get(k, 0))
                ilk.setdefault(k, {})
                for e in {x[3] for x in ILKLER if x[2] == k}:
                    if m >= e and e not in ilk[k]:
                        ilk[k][e] = t
        sayac["sabah"] += 1 if d.get("sabah") else 0
        sayac["bjj"] += len(d.get("bjj") or [])
        sayac["basamak"] = sum(1 for x in basamak_gunleri if x <= t)
        G = gun_gorevleri(t, hedef, d, bag)
        if bugun_mu:
            bugun_gorev = G
        if all(x["tamam"] for x in G):
            sayac["gorev"] += 1
            gorev_gunleri.append(t)
            olaylar.append({"id": f"gorev:{t}", "tarih": t, "tur": "gorev", "sayi": sayac["gorev"]})
        for pt_, pk in biten_prog:
            if pt_ == t:
                olaylar.append({"id": f"program:{pk}:{t}", "tarih": t, "tur": "program", "kod": pk})
        sayac["program"] = sum(1 for x, _ in biten_prog if x <= t)
        if tamam or t in onarilan:
            durum = "tamam" if tamam else "onarildi"
            seri += 1
            ardisik += 1
            if ardisik % KORUMA_ARALIK == 0 and koruma < KORUMA_EN_COK:
                koruma += 1
                olaylar.append({"id": f"koruma:{t}", "tarih": t, "tur": "koruma", "koruma": koruma})
            if seri in ESIKLER:
                olaylar.append({"id": f"seri:{seri}:{t}", "tarih": t, "tur": "seri", "seri": seri})
        elif bugun_mu:
            durum = "bekliyor"
        elif not basladi:
            durum = "once"
        elif koruma > 0:
            koruma -= 1
            ardisik = 0
            durum = "korundu"
            olaylar.append({"id": f"korundu:{t}", "tarih": t, "tur": "korundu", "seri": seri})
        else:
            durum = "kacti"
            if seri:
                kopus = {"tarih": t, "seri": seri}
            seri = ardisik = 0
        en_uzun = max(en_uzun, seri)
        sayac["en_uzun"] = en_uzun
        kayitlar.append({"tarih": t, "durum": durum, "hedef": hedef, "dk": sum(int(s.get("sure_dk") or 0) for s in d.get("seanslar") or [] if s.get("bitti"))})
        if g_.weekday() == 6 and not bugun_mu:                  # biten hafta: yedi gün de korumasız tamam mı?
            son7 = kayitlar[-7:]
            if len(son7) == 7 and all(x["durum"] == "tamam" for x in son7):
                sayac["mukemmel"] += 1
                hafta_tam.append(t)
                olaylar.append({"id": f"hafta:{t}", "tarih": t, "tur": "mukemmel", "sayi": sayac["mukemmel"]})
        for kod, ad, ac, olcu, esik, ikon, *_ in ROZETLER:
            if kod in rozet_tarih:
                continue
            if olcu.startswith("ilk:"):
                deger = 1 if esik in ilk.get(olcu[4:], {}) else 0
                hedef_ = 1
            else:
                deger, hedef_ = sayac.get(olcu, 0), esik
            if deger >= hedef_:
                rozet_tarih[kod] = t
                olaylar.append({"id": f"rozet:{kod}", "tarih": t, "tur": "rozet", "kod": kod})

    bugun_k = kayitlar[-1] if kayitlar else {"tarih": bugun.isoformat(), "durum": "bekliyor", "hedef": "kontrol", "dk": 0}
    onarim = None
    if kopus:
        kt = dt.date.fromisoformat(kopus["tarih"])
        if 0 < (bugun - kt).days <= ONARIM_GUN and kopus["seri"] >= 2:
            kacan = [x["tarih"] for x in kayitlar if x["durum"] == "kacti" and 0 < (bugun - dt.date.fromisoformat(x["tarih"])).days <= ONARIM_GUN]
            onarim = {"seri": kopus["seri"], "gunler": kacan, "son": (kt + dt.timedelta(days=ONARIM_GUN)).isoformat()}
    rozetler = []
    for kod, ad, ac, olcu, esik, ikon, aile, seviye in ROZETLER:
        if olcu.startswith("ilk:"):
            deger, hedef_ = (1 if esik in ilk.get(olcu[4:], {}) else 0), 1
            en = en_iyi.get(olcu[4:])
        else:
            deger, hedef_, en = sayac.get(olcu, 0), esik, None
        rozetler.append({"kod": kod, "ad": ad, "aciklama": ac, "ikon": ikon, "grup": olcu.split(":")[0], "deger": min(deger, hedef_), "hedef": hedef_,
                         "kazanildi": rozet_tarih.get(kod), "en_iyi": en,
                         "aile": aile, "seviye": seviye})
    sonraki = next((e for e in ESIKLER if e > seri), None)
    return {"seri": seri, "en_uzun": en_uzun, "koruma": koruma, "koruma_en_cok": KORUMA_EN_COK,
            "koruma_sonraki": (KORUMA_ARALIK - ardisik % KORUMA_ARALIK) if koruma < KORUMA_EN_COK else None,
            "bugun": bugun_k, "onarim": onarim, "kopus": kopus, "sonraki_esik": sonraki, "gunler": kayitlar, "olaylar": olaylar,
            "rozetler": rozetler, "aileler": _aileler(rozetler, sayac), "sayac": sayac, "mukemmel_haftalar": hafta_tam,
            "baslangic": bas.isoformat(), "gorevler": bugun_gorev, "gorev_gunleri": gorev_gunleri}


def _aileler(rozetler, sayac):
    """Aile başına seviye: kaç seviye kazanıldı, sıradaki eşik ve ilerleme."""
    out = []
    for on, ad, olcu, ikon, L in AILELER:
        R = [r for r in rozetler if r["aile"] == on]
        k = [r for r in R if r["kazanildi"]]
        sonraki = next((r for r in R if not r["kazanildi"]), None)
        onceki_esik = k[-1]["hedef"] if k else 0
        deger = sayac.get(olcu, 0)
        out.append({"kod": on, "ad": ad, "ikon": ikon, "seviye": len(k), "toplam": len(R), "deger": deger,
                    "son": k[-1]["ad"] if k else None, "son_tarih": k[-1]["kazanildi"] if k else None,
                    "sonraki": {"ad": sonraki["ad"], "aciklama": sonraki["aciklama"], "hedef": sonraki["hedef"],
                                "oran": round(max(0, min(1, (deger - onceki_esik) / max(1, sonraki["hedef"] - onceki_esik))), 3)} if sonraki else None})
    return out


def hesap():
    imza = _imza()
    with _kilit:
        if _onbellek.get("imza") != imza:
            _onbellek.update(imza=imza, veri=_hesapla())
        return _onbellek["veri"]


def seri():
    return hesap()["seri"]


def _hafta(h):
    """Bu haftanın yedi günü: geçmiş günlerin durumu, gelecek günlerin hedefi (plandan)."""
    bugun = pt.bugun()
    gunler = {x["tarih"]: x for x in h["gunler"]}
    pl_onb = {}
    out = []
    for g_ in pt.hafta_gunleri(pt.hafta_kodu(bugun)):
        t = g_.isoformat()
        if t in gunler:
            out.append({k: gunler[t][k] for k in ("tarih", "durum", "hedef", "dk")})
        else:
            planli = _program_gunleri(g_, pl_onb)
            out.append({"tarih": t, "durum": "gelecek" if g_ > bugun else "once",
                        "hedef": "seans" if any(p.get("tur") != "dinlenme" for p in planli) else "kontrol", "dk": 0})
    return out


def hafta_halkasi(h=None):
    """Bu haftanın dakika halkası: yapılan / planlanan dakika ve seans sayısı (Apple Watch halkası gibi)."""
    h = h or hesap()
    bugun = pt.bugun()
    gunler = {x["tarih"]: x for x in h["gunler"]}
    plan_dk = plan_seans = yap_dk = yap_seans = 0
    for g_ in pt.hafta_gunleri(pt.hafta_kodu(bugun)):
        t = g_.isoformat()
        for p in pt.program(pt.hafta_kodu(g_)).get("gunler") or []:
            if p.get("tarih") == t and p.get("tur") != "dinlenme":
                plan_dk += int(p.get("sure_dk") or 0)
                plan_seans += 1
        if t in gunler and g_ <= bugun:
            yap_dk += gunler[t]["dk"]
            yap_seans += len([s for s in pt.gun(t).get("seanslar") or [] if s.get("bitti")]) if gunler[t]["dk"] else 0
    hedef = plan_dk or 90
    return {"dk": yap_dk, "hedef_dk": hedef, "seans": yap_seans, "hedef_seans": plan_seans, "oran": round(min(1.5, yap_dk / hedef), 3)}


def goruldu_listesi():
    return set(pt._json(OYUN, {}).get("goruldu") or [])


def goruldu(idler):
    with _kilit:
        d = pt._json(OYUN, {})
        g = list(dict.fromkeys((d.get("goruldu") or []) + [str(i)[:80] for i in idler]))[-2000:]
        d["goruldu"] = g
        pt._yaz(OYUN, d)


def yeni_olaylar(h=None, gun=1):
    """Henüz gösterilmemiş, son `gun` günün kutlanacak olayları (seri eşiği, rozet, koruma kazanma, mükemmel hafta)."""
    h = h or hesap()
    sinir = (pt.bugun() - dt.timedelta(days=gun)).isoformat()
    g = goruldu_listesi()
    R = {r["kod"]: r for r in h["rozetler"]}
    out = []
    for o in h["olaylar"]:
        if o["tarih"] >= sinir and o["id"] not in g and o["tur"] in ("seri", "rozet", "koruma", "mukemmel", "gorev", "program"):
            if o["tur"] == "rozet" and o["kod"] in R:
                o = {**o, **{k: R[o["kod"]][k] for k in ("ad", "aciklama", "ikon", "seviye", "aile")}}
            if o["tur"] == "program":
                try:
                    import pt_programlar
                    o = {**o, "ad": pt_programlar.P[o["kod"]]["ad"]}
                except Exception:
                    pass
            out.append(o)
    return out


def hedef_metni(hedef, durum):
    if durum == "tamam":
        return "Bugünün hedefi tamam."
    return "Bugün bir antrenman bitirin; 10 dakika da sayılır." if hedef == "seans" else "Bugün dinlenme günü: sabah kontrolünü yapmanız yeterli."


def ozet():
    """Bugün sayfası için kısa durum."""
    h = hesap()
    b = h["bugun"]
    saat = dt.datetime.now().hour
    return {"seri": h["seri"], "en_uzun": h["en_uzun"], "koruma": h["koruma"], "koruma_en_cok": h["koruma_en_cok"],
            "koruma_sonraki": h["koruma_sonraki"], "bugun": {**b, "metin": hedef_metni(b["hedef"], b["durum"])},
            "risk": b["durum"] == "bekliyor" and h["seri"] >= 2 and saat >= 18, "onarim": h["onarim"], "sonraki_esik": h["sonraki_esik"],
            "hafta": _hafta(h), "yeni": yeni_olaylar(h), "rozet_sayi": sum(1 for r in h["rozetler"] if r["kazanildi"]), "rozet_toplam": len(h["rozetler"]),
            "gorevler": h["gorevler"], "gorev_gun": h["sayac"]["gorev"], "halka": hafta_halkasi(h)}


def tam(gun_sayisi=84):
    """Seri sayfası: takvim (son 12 hafta), rozetler, kurallar."""
    h = hesap()
    return {**ozet(), "takvim": h["gunler"][-gun_sayisi:], "rozetler": h["rozetler"], "aileler": h["aileler"], "sayac": h["sayac"],
            "mukemmel_haftalar": h["mukemmel_haftalar"], "baslangic": h["baslangic"],
            "kurallar": [
                "Her günün tek bir hedefi var: antrenman günü bir seans bitirmek (10 dakikalık kısa antrenman da sayılır), dinlenme günü sabah kontrolü.",
                "Hastaysanız ya da sabah ışığınız kırmızıysa o gün hedef antrenman değil, kendinizi dinlemek; seri bozulmaz.",
                f"Bir günü kaçırırsanız seri koruması kendiliğinden harcanır. Üst üste her {KORUMA_ARALIK} tamam günde bir koruma kazanırsınız; en çok {KORUMA_EN_COK} birikir.",
                f"Koruma yokken seri koparsa, {ONARIM_GUN} gün içinde 10 dakikalık telafi antrenmanıyla geri getirebilirsiniz.",
                "Mükemmel hafta: Pazartesi'den Pazar'a korumasız, eksiksiz yedi gün.",
                "Her gün üç görev var; ilki günün hedefi. Üçü de bitince o gün görev günü sayılır; görev rozetleri bunlardan.",
                "Rozetlerin seviyeleri var: her ailede bir sonraki seviye neyi istiyor, rozete dokununca görünür."]}


def onarim_gecerli(gunler):
    """Telafi seansının onarabileceği günler (son iki günde kaçırılmış olanlar)."""
    o = hesap().get("onarim") or {}
    return [g for g in gunler or [] if g in (o.get("gunler") or [])]

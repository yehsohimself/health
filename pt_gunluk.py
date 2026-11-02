"""pt_gunluk.py - Günlük sabit liste + her gün bir sürpriz (2026-11-02; kullanıcı: "günlük default hareket listem olsun, bileyim ki onları yapacağım;
her gün beni şaşırtacak bir ekleme olsun; evde ve aletsiz; ısınma, yürüyüş, test yok; six pack hedefim var").

Eski yol: her "haftayı değiştir" isteği planı yapay zekâya baştan yazdırıyordu ve bir önceki istek unutuluyordu; bilek hazırlığı, kedi-inek, yürüyüş ve
test geri geliyordu. Burada kural kodda: profil `gunluk_liste` doluysa plan Claude'suz kurulur ve kişinin söyledikleri kalıcıdır.

Her günün yapısı aynı: sabit liste + 1 sürpriz. Değişen adetler: hafif / orta / zorlu dalgası (aynı kaslar her gün çalıştığı için). Şınav göğüs için günlere
göre değişir. Hedefler kişinin kaydettiği setlerden ilerler. Sürpriz takvime bağlı bir karışık sıradan gelir: yaklaşık bir ay tekrar etmez, yeniden yazımda değişmez.
"""
import datetime as dt
import hashlib
import random
import time

import pt

VARSAYILAN = ["sinav", "squat", "kalca_kopru", "superman", "duvar_oturus", "cift_baldir", "plank", "dead_bug", "hollow"]

# Orta günde bir setin hedefi (test sonucu yoksa ve kişi başka bir şey söylemediyse). Süreli hareketlerde saniye.
TABAN = {"sinav": 6, "squat": 20, "kalca_kopru": 15, "superman": 20, "duvar_oturus": 30, "cift_baldir": 20, "plank": 25, "dead_bug": 10, "hollow": 15}
TESTTEN = {"sinav": ("sinav_max", .6), "squat": ("squat_max", .45), "plank": ("plank_sn", .85), "hollow": ("hollow_sn", .8)}

# Pazartesiden pazara. Aynı kaslar her gün çalıştığı için yük dalgalanır; iki zorlu gün yan yana gelmez.
DALGA = ["orta", "hafif", "zorlu", "hafif", "orta", "zorlu", "hafif"]
DUZEY = {"hafif": {"kat": .75, "set": 2, "dinlenme": 20, "ad": "Hafif gün"},
         "orta": {"kat": 1.0, "set": 2, "dinlenme": 30, "ad": "Orta gün"},
         "zorlu": {"kat": 1.2, "set": 3, "dinlenme": 25, "ad": "Zorlu gün"}}
# Göğüs: aletsiz en iyi yol şınavı değiştirmek. Düz şınavın hedefinden hesaplanır.
SINAV_DONGU = [("sinav", 1.0), ("genis_sinav", 1.0), ("sinav", 1.0), ("ayak_yuksek_sinav", .8)]

SURPRIZ = {
    "gogus": ("Göğüs", ["elmas_sinav", "yaslanan_sinav", "pike_sinav", "egimli_sinav"]),
    "kol": ("Kol", ["sandalye_dips", "beast", "crab"]),
    "karin": ("Karın", ["yer_bacak_kaldirma", "bisiklet_crunch", "mountain_climber", "yan_plank"]),
    "bjj": ("Jiu-jitsu", ["karides", "ters_karides", "kopru_upa", "sit_out", "sprawl", "teknik_kalkis", "kalca_degistirme", "bacak_pummel", "golge_gures"]),
    "kalistenik": ("Kalistenik", ["bulgar_squat", "ters_lunge", "yan_lunge", "tek_kalca_kopru"]),
    "akis": ("Animal flow", ["ape", "underswitch", "side_kickthrough", "scorpion_reach"]),
    "denge": ("Denge", ["tek_ayak_denge", "yere_otur_kalk"]),
}
SURPRIZ_TABAN = {"elmas_sinav": 5, "egimli_sinav": 12, "yaslanan_sinav": 5, "pike_sinav": 6, "sandalye_dips": 8, "beast": 25, "crab": 20,
                 "yer_bacak_kaldirma": 10, "bisiklet_crunch": 16, "mountain_climber": 25, "yan_plank": 20, "karides": 8, "ters_karides": 6, "kopru_upa": 8,
                 "sit_out": 8, "sprawl": 8, "teknik_kalkis": 6, "kalca_degistirme": 10, "bacak_pummel": 30, "golge_gures": 45, "bulgar_squat": 8,
                 "ters_lunge": 10, "yan_lunge": 8, "tek_kalca_kopru": 8, "ape": 8, "underswitch": 8, "side_kickthrough": 8,
                 "scorpion_reach": 8, "tek_ayak_denge": 30, "yere_otur_kalk": 5}
BASLANGIC = dt.date(2026, 1, 5)    # bir pazartesi; sürpriz sırasının başlangıcı
SN_TEKRAR = 3                      # süre hesabı: tekrar başına saniye


def ayar(p=None):
    """Kişinin listesi. Yoksa None: plan eski yoldan (Claude) yazılır."""
    p = p or pt.profil()
    a = p.get("gunluk_liste")
    return a if isinstance(a, dict) and a.get("sabit") else None


def acik(p=None):
    return bool(ayar(p))


def aletsiz(kod, kat=None):
    h = (kat or pt.katalog()).get(kod) or {}
    return h.get("ekipman") in ("yok", "mat", "duvar") and h.get("tur") not in ("isinma", "mobilite") or h.get("zincir") == "denge"


def kur(sabit=None, surpriz_haric=None, yuruyus_dk=None):
    """Listeyi profile yazar ve bu haftayla gelecek haftanın planını kodla kurar."""
    p = pt.profil()
    a = ayar(p) or {}
    kat = pt.katalog()
    y = dict(a)
    y["sabit"] = [k for k in (sabit if sabit is not None else a.get("sabit") or VARSAYILAN) if aletsiz(k, kat)]
    y["surpriz_haric"] = list(surpriz_haric if surpriz_haric is not None else a.get("surpriz_haric") or [])
    if yuruyus_dk is not None:
        y["yuruyus_dk"] = int(yuruyus_dk)
    pt.profil_kaydet({"gunluk_liste": y})
    hafta_yaz()
    return y


def _seviye_dosya():
    return pt.ilerleme()["hareketler"]


def seviye(kod):
    """Orta günde bir setin hedefi: kayıtlardan ilerlemiş değer > test sonucu > taban."""
    st = _seviye_dosya().get(kod) or {}
    if st.get("gunluk_hedef"):
        return int(st["gunluk_hedef"])
    t = TESTTEN.get(kod)
    if t:
        for k in reversed(pt.testler().get("kayitlar") or []):
            v = pt.sayi((k.get("sonuclar") or {}).get(t[0]), 0, 2000)
            if v:
                adim = 5 if (pt.KATALOG.get(kod) or {}).get("olcu") == "sure" else 1
                return max(adim, int(round(v * t[1] / adim)) * adim)
    return TABAN.get(kod) or 10


def _adet(deger, olcu, kat):
    v = deger * kat
    return max(5, int(round(v / 5)) * 5) if olcu == "sure" else max(1, int(round(v)))


def duzey(tarih, hafif=False):
    d = DALGA[dt.date.fromisoformat(tarih).weekday()]
    return "orta" if hafif and d == "zorlu" else d


def _sinav_turu(tarih):
    n = (dt.date.fromisoformat(tarih) - BASLANGIC).days
    return SINAV_DONGU[n % len(SINAV_DONGU)]


def _hareket(kod, deger, d, kat, baz=None):
    h = kat[kod]
    x = {"kod": kod, "ad": h["ad"], "set": d["set"], "dinlenme_sn": d["dinlenme"]}
    if baz:
        x["baz"] = baz
    a = _adet(deger, h.get("olcu"), d["kat"])
    if h.get("olcu") == "sure":
        x["sure_sn"] = a
    else:
        x["tekrar"] = str(a)
    return x


def surpriz_sirasi(p=None, kat=None):
    """Bütün aday hareketleri karışık bir sıraya dizer; yan yana aynı tür gelmez. Sıra sabit olduğu için plan yeniden yazılsa da sürpriz değişmez."""
    a = ayar(p) or {}
    kat = kat or pt.katalog()
    cikan = set(a.get("surpriz_haric") or []) | set(a.get("sabit") or [])
    gruplar = {g: [k for k in L if k in kat and k not in cikan] for g, (_, L) in SURPRIZ.items()}
    r = random.Random(20261102)
    for L in gruplar.values():
        r.shuffle(L)
    sira = []
    son = None
    while any(gruplar.values()):
        adaylar = [g for g, L in gruplar.items() if L and g != son] or [g for g, L in gruplar.items() if L]
        g = max(adaylar, key=lambda x: (len(gruplar[x]), r.random()))
        sira.append((gruplar[g].pop(), g))
        son = g
    return sira


def gunun_surprizi(tarih, p=None, kat=None):
    sira = surpriz_sirasi(p, kat)
    if not sira:
        return None
    n = (dt.date.fromisoformat(tarih) - BASLANGIC).days
    sapma = int(hashlib.sha1(b"surpriz").hexdigest()[:4], 16)
    return sira[(n + sapma) % len(sira)]


def _sure_dk(bolumler):
    sn = 0
    for b in bolumler:
        for h in b["hareketler"]:
            is_sn = h.get("sure_sn") or int(h.get("tekrar") or 8) * SN_TEKRAR
            sn += h.get("set", 2) * (is_sn + h.get("dinlenme_sn", 20))
    return max(5, int(round(sn / 60)))


def gun_kur(tarih, p=None, kat=None, hafif=False):
    p = p or pt.profil()
    kat = kat or pt.katalog()
    a = ayar(p)
    dz = duzey(tarih, hafif)
    d = DUZEY[dz]
    hs = []
    for kod in a["sabit"]:
        if kod not in kat:
            continue
        if kod == "sinav":
            tur, oran = _sinav_turu(tarih)
            hs.append(_hareket(tur, seviye("sinav") * oran, d, kat, baz="sinav"))
        else:
            hs.append(_hareket(kod, seviye(kod), d, kat))
    bol = [{"ad": "Günlük liste", "bicim": "set", "hareketler": hs}]
    s = gunun_surprizi(tarih, p, kat)
    if s:
        kod, grup = s
        d2 = {**d, "set": 2, "kat": 1.0 if dz != "hafif" else .85}
        bol.append({"ad": "Sürpriz", "bicim": "set", "surpriz": True, "grup": SURPRIZ[grup][0],
                    "hareketler": [_hareket(kod, (_seviye_dosya().get(kod) or {}).get("gunluk_hedef") or SURPRIZ_TABAN.get(kod) or 8, d2, kat)]})
    sinir = int(p.get("gunluk_dk") or 30)
    while _sure_dk(bol) > sinir and hs and hs[0]["dinlenme_sn"] > 15:
        for b in bol:
            for h in b["hareketler"]:
                h["dinlenme_sn"] -= 5
    sure = _sure_dk(bol)
    return {"tarih": tarih, "tur": "kalistenik", "gunluk": True, "duzey": dz, "baslik": f"Günlük liste · {d['ad'].lower()}", "sure_dk": sure, "saat": "",
            "neden": f"{d['ad']}: {d['set']} set. Aynı kaslar her gün çalıştığı için adetler günlere göre değişiyor.",
            "bolumler": bol, "id": f"{tarih}-0"}


def asgari(p=None, kat=None):
    """10 dakikalık kısa antrenman: listenin başı, ısınmasız."""
    p = p or pt.profil()
    kat = kat or pt.katalog()
    a = ayar(p) or {}
    secim = [k for k in ("sinav", "squat", "plank", "hollow") if k in (a.get("sabit") or [])] or (a.get("sabit") or [])[:4]
    return {"tur": "asgari", "baslik": "10 dakikalık kısa antrenman", "sure_dk": 10, "asgari": True,
            "bolumler": [{"ad": "Ana bölüm", "bicim": "tur", "tur_sayisi": 3, "calisma_sn": 35, "dinlenme_sn": 15, "hareketler": [{"kod": k} for k in secim if k in kat]}]}


def hafta_kur(kod=None, istek=""):
    """Haftanın planı, Claude'suz. Geçmiş günlere dokunmaz (bitmiş seanslar eski kimliğiyle eşleşmeye devam eder)."""
    kod = pt.hafta_gecerli(kod or pt.hafta_kodu())
    p = pt.profil()
    kat = pt.katalog()
    bugun = pt.bugun().isoformat()
    eski = pt.program(kod) or {}
    eski_gun = {g.get("tarih"): g for g in eski.get("gunler") or []}
    hafif = pt.yorgunluk_durumu().get("durum") == "yorgun"     # zorlu gün yalnız yorgunluk birikince orta olur
    gunler = []
    for g in pt.hafta_gunleri(kod):
        t = g.isoformat()
        if t < bugun and t in eski_gun:
            gunler.append(eski_gun[t])
        else:
            gunler.append(gun_kur(t, p, kat, hafif))
    return {"gunler": gunler, "asgari": asgari(p, kat), "eger_ise": [], "hafta": kod, "olusturma": int(time.time()), "hafif": hafif, "istek": istek,
            "gunluk": True, "not": "Her gün aynı liste, üstüne bir sürpriz. Adetler günlere göre değişir, siz ilerledikçe artar."}


def hafta_yaz(kodlar=None):
    """Bu hafta ve gelecek hafta. Önceki plan yedeğe gider, Önceki plana dön çalışır."""
    bu = pt.hafta_kodu()
    sonraki = pt.hafta_kodu(pt.hafta_gunleri(bu)[-1] + dt.timedelta(days=1))
    for kod in kodlar or (bu, sonraki):
        pl = hafta_kur(kod)
        pt.plan_yaz(kod, pl)


def ilerle(seans):
    """Planlı günlük seansın kaydından hedefleri güncelle. İki kez bütün setlerde hedefe ulaşınca artar; iki kez çok altında kalınca azalır. Basamak değişmez."""
    g = next((x for x in (pt.program(pt.hafta_kodu(dt.date.fromisoformat(seans["tarih"]))).get("gunler") or []) if x.get("id") == seans.get("plan_id")), None)
    if not g:
        return []
    plan = {h["kod"]: h for b in g.get("bolumler") or [] for h in b.get("hareketler") or []}
    kat = pt.katalog()
    degisen = []
    zor = pt.sayi(seans.get("zorluk"), 0, 10, 7) or 7
    with pt._kilit:
        il = pt.ilerleme()
        H = il["hareketler"]
        for r in seans.get("hareketler") or []:
            kod = r.get("kod")
            ph = plan.get(kod)
            setler = [pt.sayi(s.get("deger"), 0, 2000) for s in r.get("setler") or [] if s.get("deger") is not None]
            setler = [x for x in setler if x is not None]
            if not ph or not setler:
                continue
            anahtar = ph.get("baz") or kod
            st = H.setdefault(anahtar, {})
            st.setdefault("son", {})
            st["son"] = {"tarih": seans.get("tarih"), "setler": setler, "zorluk": r.get("zorluk")}
            hedef_ = ph.get("sure_sn") or int(ph.get("tekrar") or 0)
            if not hedef_:
                continue
            olcu = kat[kod].get("olcu")
            simdi = int(st.get("gunluk_hedef") or (seviye(anahtar) if anahtar in TABAN or anahtar in TESTTEN else (SURPRIZ_TABAN.get(anahtar) or hedef_)))
            adim = 5 if olcu == "sure" else max(1, int(round(simdi * .1)))
            yeni = None
            if len(setler) >= ph.get("set", 1) and min(setler) >= hedef_ and zor <= 8:
                st["gunluk_basari"] = (st.get("gunluk_basari") or 0) + 1
                st["gunluk_dusuk"] = 0
                if st["gunluk_basari"] >= 2:
                    yeni, neden = simdi + adim, "iki seans üst üste bütün setlerde hedefe ulaştınız"
                    st["gunluk_basari"] = 0
            elif min(setler) < hedef_ * .7:
                st["gunluk_dusuk"] = (st.get("gunluk_dusuk") or 0) + 1
                st["gunluk_basari"] = 0
                if st["gunluk_dusuk"] >= 2 and simdi > adim:
                    yeni, neden = simdi - adim, "iki seans üst üste hedefin belirgin altında kaldı"
                    st["gunluk_dusuk"] = 0
            else:
                st["gunluk_basari"] = st["gunluk_dusuk"] = 0
            if yeni and yeni != simdi:
                st["gunluk_hedef"] = yeni
                birim = "sn" if olcu == "sure" else "tekrar"
                ad = kat[anahtar]["ad"] if anahtar in kat else kat[kod]["ad"]
                kayit = {"t": int(time.time()), "id": pt._did(), "kod": anahtar, "tur": "gunluk", "eski": simdi, "yeni_hedef": yeni, "ad": ad,
                         "yeni_ad": f"{yeni} {birim} (orta gün)", "neden": neden}
                il["degisiklikler"].append(kayit)
                degisen.append(kayit)
        il["degisiklikler"] = il["degisiklikler"][-300:]
        pt._ilerleme_yaz(il)
    if degisen:
        bu = pt.bugun().isoformat()
        for kod_ in (pt.hafta_kodu(), pt.hafta_kodu(pt.bugun() + dt.timedelta(days=7))):
            eski = pt.program(kod_)
            if not eski:
                continue
            yeni_pl = hafta_kur(kod_)
            for i, gun in enumerate(yeni_pl["gunler"]):      # bugünkü seans değişmesin; yalnız sonraki günler
                if gun["tarih"] <= bu:
                    k = next((x for x in eski.get("gunler") or [] if x.get("tarih") == gun["tarih"]), None)
                    if k:
                        yeni_pl["gunler"][i] = k
            pt.plan_yaz(kod_, yeni_pl, yedek=False)
    return degisen


def baglam_metni(p=None):
    """Sohbet istemi için: liste ne, bugün ne var, kuralı ne. Gelecek günlerin sürprizi söylenmez."""
    p = p or pt.profil()
    a = ayar(p)
    if not a:
        return "yok"
    kat = pt.katalog()
    bugun = pt.bugun().isoformat()
    g = gun_kur(bugun, p, kat)
    def satir(h):
        return f"{kat[h['kod']]['ad']} {h['set']}×{str(h.get('sure_sn')) + ' sn' if h.get('sure_sn') else h.get('tekrar')}"
    liste = ", ".join(satir(h) for h in g["bolumler"][0]["hareketler"])
    sur = g["bolumler"][1]["hareketler"][0] if len(g["bolumler"]) > 1 else None
    aday = ", ".join(f"{k}: {h['ad']}" for k, h in kat.items() if aletsiz(k, kat))
    return (f"BU KİŞİNİN PLANI KODLA KURULUR, SEN YAZMAZSIN. Her gün aynı sabit liste + 1 sürpriz; ısınma yok, yürüyüş yok (günde {a.get('yuruyus_dk') or 90} dk kendi yürüyor, "
            f"haftalık kardiyoya sayılıyor), test yok; hepsi evde ve aletsiz; günde en çok {p.get('gunluk_dk') or 30} dk. Adetler hafif/orta/zorlu dalgasıyla değişir, kayıtlara göre artar. "
            f"Bugün ({DUZEY[g['duzey']]['ad']}, {g['sure_dk']} dk): {liste}. Bugünün sürprizi: {satir(sur) if sur else 'yok'}. Sonraki günlerin sürprizini söyleme, sürpriz kalsın. "
            f"Sabit liste kodları: {', '.join(a['sabit'])}. Listeyi değiştirmek isterse eylem liste kullan (hafta kullanma). Eklenebilecek aletsiz hareketler (kod: ad): {aday}")


def liste_degistir(e):
    """Sohbetten: {ekle: [kod], cikar: [kod], surpriz_cikar: [kod], seviye: {kod: orta gün hedefi}}. Kısa özet döndürür."""
    p = pt.profil()
    a = ayar(p)
    if not a:
        return "Günlük liste açık değil."
    kat = pt.katalog()
    sabit = list(a["sabit"])
    notlar = []
    for k in e.get("cikar") or []:
        if k in sabit:
            sabit.remove(k)
            notlar.append(f"{kat[k]['ad']} listeden çıktı")
    for k in e.get("ekle") or []:
        if k in kat and aletsiz(k, kat) and k not in sabit:
            sabit.append(k)
            notlar.append(f"{kat[k]['ad']} listeye girdi")
    haric = list(a.get("surpriz_haric") or [])
    for k in e.get("surpriz_cikar") or []:
        if k in kat and k not in haric:
            haric.append(k)
            notlar.append(f"{kat[k]['ad']} sürprizlerden çıktı")
    sev = e.get("seviye") if isinstance(e.get("seviye"), dict) else {}
    if sev:
        with pt._kilit:
            il = pt.ilerleme()
            for k, v in sev.items():
                v = pt.sayi(v, 1, 600)
                if k in kat and v:
                    il["hareketler"].setdefault(k, {})["gunluk_hedef"] = int(v)
                    notlar.append(f"{kat[k]['ad']} orta günde {int(v)}")
            pt._ilerleme_yaz(il)
    kur(sabit, haric)
    return "; ".join(notlar) or "Değişiklik yok."

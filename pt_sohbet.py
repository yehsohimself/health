"""pt_sohbet.py - Health ile konuşma (2026-10-25). "Bugün dizim ağrıyor", "Bu hafta Hamburg'dayım" → Health önce seçenekli sorar (gerekirse), sonra planda
yapacağı değişikliği ÖNERİR; kullanıcı onaylayınca uygulanır (kurallar yine kodda). Geçmiş pt/sohbet.json (son 60 mesaj).

Eylem türleri: bugun (bugünü uyarla: vakit, yer, ışık, ağrı), hafta (haftayı yeniden yaz, istekle), tasi (seansı başka güne), profil (ekipman/sakatlık/
hassasiyet ekle ya da çıkar), not (kalıcı not), dinlenme (bugünü dinlenme yap).

Kayıtlar (2026-10-31; kullanıcı: "dün 25 dk maç yaptım büyük sahada; bu tarz bilgileri girmek isteyebilirim"): kişi yaptığı ya da ölçtüğü bir şeyi
söylerse (spor, yürüyüş, yemek, kilo, uyku, su) onay beklemeden kaydedilir ve geri alınabilir. Spor seansı günlüğe seans olarak yazılır; seri, puan ve
haftalık sağlık dozu (yoğun, kolay kardiyo) buradan sayılır. Yemek BLS tablosuyla tahmin edilir, "kontrol bekliyor" olarak yazılır.
"""
import datetime as dt
import json
import re
import time

import pt

DOSYA = pt.VERI / "sohbet.json"

ISTEM = """Sen Health'sin: kişinin yanındaki sıcak, meraklı ve dürüst bir koçsun (antrenör, diyetisyen, fizyoterapist, uyku ve uzun ömür bilgisiyle).
İnsan gibi konuş: kişinin söylediğine önce gerçekten cevap ver, gerekirse merak et, kısa espri ya da takdir olabilir; kalıp cümle, rapor dili, madde
yığını yok. Türkçe, "siz" dili, çoğunlukla 1-3 cümle (kişi açıklama ya da neden sorarsa 4-6 cümle olabilir; **kalın** ve kısa liste serbest).
Kişi soruya soruyla karşılık verebilir, itiraz edebilir, konu açabilir: hepsine açıksın. Bir şeyi neden yaptığını sorarsa nedenini sade anlat.
Kullanıcı sana bir durum söyledi ya da yaptığı bir şeyi anlattı. YAPTIĞI ya da ÖLÇTÜĞÜ bir şeyi söylüyorsa (maç, yürüyüş, koşu, ders,
yediği yemek, kilo, uyku, içtiği su) onu "kayitlar" listesine yaz: bunlar onay beklemeden kaydedilir; yanıtta kaydettiğini kısa söyle ve
gerekiyorsa tek cümle yorum ekle (ör. maç yoğun çalışma sayılır, yarın hafif tutalım). Yalnız YENİ yapılan işi kayıt aç. Daha önce söylediği bir işin ayrıntısını ya da düzeltmesini
veriyorsa ("tek seferde yaptım", "60 dakikaydı") SON KAYITLAR'daki kimliği "guncelle"ye yaz, yalnız değişen alanları ver. Aynı işi gerçekten bir kez daha yaptıysa ("50 squat daha") "ayri": true yaz.
Soru sorduğu ya da konuştuğu mesajlarda ("ne yapayım?") kayıt açma. Kaydetmediğin ya da güncellemediğin şeyi yaptım deme. Tarihleri {bugun} gününe göre çöz ("dün", "cumartesi").
Süre ya da zorluk söylenmediyse makul tahmin et (zorluk 1-10: halı saha/büyük saha futbol 7-8, tempolu yürüyüş 3-4). Ayrıca görevin: (a) durumu anlamak için gerekiyorsa TEK seçenekli soru sormak, (b) yeterince biliyorsan planda yapacağın
değişikliği önermek. Teşhis koyma. Göğüs ağrısı, baş dönmesi, bayılma, yayılan uyuşma, şişlikle keskin eklem ağrısı gibi uyarı belirtilerinde
antrenmanı durdur ve doktora/112'ye yönlendir (eylem: dinlenme).

KİŞİ: {profil}
BUGÜN ({bugun}): {bugun_plan}
SABAH KONTROLÜ: {sabah}
BU HAFTA: {hafta}
GÜNLÜK LİSTE: {gunluk}
SON KAYITLAR: {son}
APPLE SAĞLIK (son günler): {saglik}
ORUÇ (koddan; oruç, otofaji, açlık, yemek saati sorulursa bunu kullan, saatleri yaklaşık söyle, otofajinin insanlarda başlama saatinin ölçülemediğini açıkça söyle; spor varsa birlikte yorumla): {oruc}
BU HAFTANIN SAĞLIK DOZU: {doz}
MODÜLLER: {moduller}
KURALLAR (kodda, değiştirme): {kurallar}

KONUŞMA:
{gecmis}

JSON döndür:
{{"yanit": "cevabın",
  "oneriler": ["kişinin bundan sonra sana söyleyebileceği 2-3 kısa şey (en çok 5 kelime, onun ağzından): 'Neden test var?', 'Yarına alalım'"],
  "kartlar": ["gerekirse göster: seans (bugünün seansı, başlat düğmesiyle) | doz (haftalık sağlık dozu) | nefes (nefes çalışması başlat) | program (haftalık yapı) | kilo (kilo eğrisi) | hareket:<kod> (hareketin kartı)"],
  "kayitlar": [{{"tur": "aktivite|yemek|kilo|uyku|su", "tarih": "YYYY-MM-DD", "guncelle": "düzeltilen aktivite kaydının id'si, varsa", "ayri": "aynı iş bir kez daha yapıldıysa true",
     "spor": "futbol|basketbol|tenis|voleybol|padel|yuzme|kosu|yuruyus|bisiklet|jiujitsu|yoga|fitness|dans|diger", "ad": "kısa ad: 'Futbol (büyük saha)'",
     "sure_dk": sayı, "zorluk": 1-10, "saat": "aktivite bittiği saat HH:MM, söylendiyse", "not": "...", "metin": "yemek için: yenen her şey miktarıyla", "ogun": "kahvalti|ogle|aksam|ara",
     "kilo_kg": sayı, "bel_cm": sayı, "uyku_saat": sayı, "ml": sayı}}],
  "soru": null ya da {{"soru": "...", "secenekler": ["3-5 kısa, aynı düzeyde seçenek"]}},
  "eylem": null ya da {{"tur": "bugun|hafta|liste|tasi|profil|not|dinlenme", "aciklama": "kullanıcıya tek cümle: ne değişecek",
     "vakit_dk": sayı|null, "nerede": "ev|park|salon|yolda"|null, "isik": "yesil|sari|kirmizi"|null, "agri": [{{"bolge": "{bolgeler}", "puan": 0-10}}],
     "ekle": ["liste için sabit listeye eklenecek kod"], "cikar": ["sabit listeden çıkacak kod"], "surpriz_cikar": ["sürprizlerden çıkacak kod"], "seviye": {{"kod": "orta günde bir setin yeni hedefi"}},
     "istek": "hafta için yönlendirme cümlesi", "id": "taşınacak seans id", "tarih": "YYYY-MM-DD",
     "ekle": {{"ekipman": [], "sakatliklar": [], "hassasiyetler": []}}, "cikar": {{"ekipman": [], "sakatliklar": [], "hassasiyetler": []}}, "not": "..."}}}}
Kayıt yoksa "kayitlar": []. Aynı şey için hem kayıt hem eylem yazma. Soru sorarken eylem null olsun. Değişiklik gerekmiyorsa eylem null, yalnız yanıt.
Yapmadığın ya da yapmayacağın şeyi yaptım deme. GÜNLÜK LİSTE doluysa antrenman planını sen yazmazsın, "hafta" kullanma; listeyle ilgili istek "liste" eylemiyle hemen uygulanır (yalnız yukarıdaki kodlar, aletsiz). Kişi zaten söylediğini tekrar ettirme.
Alanları yalnız ilgili türde doldur: bugun → vakit_dk/nerede/isik/agri; liste → ekle/cikar/surpriz_cikar/seviye; hafta → istek; tasi → id/tarih; profil → ekle/cikar (hassasiyetler = GIDA
hassasiyeti, ağrı ya da sakatlık değil; ağrı sakatliklar'a); not → not."""


SPOR = {"futbol": ("spor", "Futbol"), "basketbol": ("spor", "Basketbol"), "tenis": ("spor", "Tenis"), "voleybol": ("spor", "Voleybol"),
        "padel": ("spor", "Padel"), "dans": ("spor", "Dans"), "diger": ("spor", "Spor"), "yuzme": ("kardiyo", "Yüzme"), "kosu": ("kardiyo", "Koşu"),
        "yuruyus": ("kardiyo", "Yürüyüş"), "bisiklet": ("bisiklet", "Bisiklet"), "jiujitsu": ("bjj_ders", "Jiu-jitsu"), "yoga": ("mobilite", "Yoga"),
        "fitness": ("kalistenik", "Antrenman")}


def _tarih(t):
    """Kayıt tarihi: geçerli, gelecekte değil, en çok 14 gün geriye."""
    bugun = pt.bugun()
    try:
        d = dt.date.fromisoformat(str(t)[:10])
    except ValueError:
        return bugun.isoformat()
    return max(bugun - dt.timedelta(days=14), min(bugun, d)).isoformat()


KAYIT_BIRLESTIR_SN = 600     # aynı işin on dakika içindeki ikinci kaydı ayrıntı ya da düzeltmedir (2026-11-01: yürüyüş, squat, baldır ikişer kez yazıldı)


def _ad_kokleri(ad):
    ad = re.sub(r"\(.*?\)", " ", str(ad or "")).replace("İ", "i").replace("I", "ı").lower()
    return {w[:5] for w in re.findall(r"[a-zçğıöşü]+", ad) if len(w) > 2}


def _ayni_is(a, b):
    A, B = _ad_kokleri(a), _ad_kokleri(b)
    return bool(A and B) and len(A & B) / len(A | B) >= 0.5


def _duzeltilen_seans(k, t, ad):
    """Bu kayıt var olan bir seansın düzeltmesi mi? Modelin verdiği kimlik önce; yoksa az önce yazılmış aynı iş (kod kararı). (tarih, seans) ya da None."""
    if k.get("guncelle"):
        for i in range(0, 15):
            g = (pt.bugun() - dt.timedelta(days=i)).isoformat()
            s = next((x for x in pt.gun(g).get("seanslar") or [] if x.get("id") == k["guncelle"]), None)
            if s:
                return g, s
    if k.get("ayri"):
        return None
    for s in reversed(pt.gun(t).get("seanslar") or []):
        m = re.fullmatch(r"k(\d{13})", str(s.get("id") or ""))
        if m and s.get("kaynak") == "sohbet" and time.time() - int(m.group(1)) / 1000 <= KAYIT_BIRLESTIR_SN and _ayni_is(s.get("baslik"), ad):
            return t, s
    return None


def _seans_bicimle(seans, spor, dk, zor, saat, t):
    st = seans["tur"]
    sa = str(saat or "")
    if len(sa) >= 4 and ":" in sa:                              # "bitti" saati söylendiyse oruç fazına doğru yerleşsin
        try:
            h, m = (int(x) for x in sa.split(":")[:2])
            bt = dt.datetime.combine(dt.date.fromisoformat(t), dt.time(h % 24, m % 60)).timestamp()
            if bt <= time.time() + 60:
                seans["bitis_t"] = int(bt)
        except ValueError:
            pass
    if st in ("spor", "kardiyo", "bisiklet"):
        yog = "aralik" if zor >= 7 else "orta" if zor >= 5 else "kolay"
        seans["bisiklet" if st == "bisiklet" else "kardiyo"] = {"tur": spor, "sure_dk": dk, "yogunluk": yog}
    return seans


AKTIVITE = [("Köpek gezdirme", "yuruyus", 45, 3), ("Yürüyüş", "yuruyus", 30, 3), ("Tempolu yürüyüş", "yuruyus", 30, 5), ("Koşu", "kosu", 30, 6), ("Bisiklet", "bisiklet", 45, 5),
            ("Futbol", "futbol", 60, 7), ("Basketbol", "basketbol", 45, 7), ("Tenis", "tenis", 60, 6), ("Padel", "padel", 60, 6), ("Yüzme", "yuzme", 30, 6), ("Jiu-jitsu", "jiujitsu", 60, 7),
            ("Yoga", "yoga", 30, 3), ("Esneme", "yoga", 15, 2), ("Dans", "dans", 45, 5), ("Merdiven", "kosu", 15, 6), ("Ev antrenmanı", "fitness", 20, 6)]


def aktivite_listesi():
    """Hazır hareketler + son 45 günde sık girilenler önde (son süreyle)."""
    sayac, son = {}, {}
    for i in range(45, -1, -1):
        for s in pt.gun((pt.bugun() - dt.timedelta(days=i)).isoformat()).get("seanslar") or []:
            if s.get("kaynak") == "elle" and s.get("baslik"):
                sayac[s["baslik"]] = sayac.get(s["baslik"], 0) + 1
                son[s["baslik"]] = {"dk": s.get("sure_dk"), "zorluk": s.get("zorluk")}
    L = [{"ad": a, "spor": b, "dk": (son.get(a) or {}).get("dk") or c, "zorluk": (son.get(a) or {}).get("zorluk") or z, "kez": sayac.get(a, 0)} for a, b, c, z in AKTIVITE]
    L.sort(key=lambda x: -x["kez"])
    return L


def aktivite_ekle(ad, spor, dk, zorluk, t=None):
    """Hazır listeden seçilen hareket. t = bittiği an; kayıt o günün. Başlangıcı bilindiği için telefonun ölçtüğü yürüyüşle zamanla eşleşir."""
    spor = spor if spor in SPOR else "diger"
    st, ad0 = SPOR[spor]
    simdi = int(time.time())
    t = max(simdi - 14 * 86400, min(int(pt.sayi(t, 0, 4e9, simdi)), simdi))
    dk, zor = int(pt.sayi(dk, 1, 600, 30)), int(pt.sayi(zorluk, 1, 10, 5))
    tarih = dt.datetime.fromtimestamp(t).date().isoformat()
    seans = {"id": f"e{int(time.time() * 1000)}", "tur": st, "baslik": str(ad or ad0)[:60], "sure_dk": dk, "zorluk": zor, "kaynak": "elle", "spor": spor, "bas_t": t - dk * 60, "bitis_t": t}
    _seans_bicimle(seans, spor, dk, zor, None, tarih)
    return pt.seans_kaydet(tarih, seans) or seans


def aktivite_sil(tarih, sid):
    pt.gun_degistir(tarih, lambda d: d.update(seanslar=[s for s in d.get("seanslar") or [] if not (s.get("id") == sid and s.get("kaynak") == "elle")]))


def kayit_isle(k):
    """Tek kaydı uygular. Döner: {tur, tarih, ozet, geri} (geri: geri almak için gereken bilgi) ya da None."""
    tur = k.get("tur")
    t = _tarih(k.get("tarih"))
    gun_ad = "Bugün" if t == pt.bugun().isoformat() else "Dün" if t == (pt.bugun() - dt.timedelta(days=1)).isoformat() else \
        pt.GUN_AD[dt.date.fromisoformat(t).weekday()]
    if tur == "aktivite":
        ad_k = str(k.get("ad") or "")[:60]
        esle = _duzeltilen_seans(k, t, ad_k or SPOR.get(k.get("spor"), ("", ""))[1])
        if esle:                                                # yeni kayıt açılmaz, var olan güncellenir; söylenmeyen alan olduğu gibi kalır
            t_e, eski = esle
            spor = k.get("spor") if k.get("spor") in SPOR and k.get("spor") != "diger" else eski.get("spor") or "diger"
            dk = int(pt.sayi(k.get("sure_dk"), 1, 600, eski.get("sure_dk") or 30))
            zor = int(pt.sayi(k.get("zorluk"), 1, 10, eski.get("zorluk") or 6))
            ad = ad_k or eski.get("baslik") or ""
            yeni = _seans_bicimle({**eski, "baslik": ad, "sure_dk": dk, "zorluk": zor, "spor": spor, "not": str(k.get("not") or eski.get("not") or "")[:200]}, spor, dk, zor, k.get("saat"), t_e)
            pt.seans_kaydet(t_e, yeni)
            return {"tur": tur, "tarih": t_e, "ozet": f"{gun_ad} · {ad} · {dk} dk · güncellendi", "geri": {"seans_once": eski}}
        spor = k.get("spor") if k.get("spor") in SPOR else "diger"
        st, ad0 = SPOR[spor]
        dk = int(pt.sayi(k.get("sure_dk"), 1, 600, 30))
        zor = int(pt.sayi(k.get("zorluk"), 1, 10, 6))
        ad = ad_k or ad0
        seans = {"id": f"k{int(time.time() * 1000)}", "tur": st, "baslik": ad, "sure_dk": dk, "zorluk": zor, "kaynak": "sohbet", "spor": spor,
                 "not": str(k.get("not") or "")[:200]}
        _seans_bicimle(seans, spor, dk, zor, k.get("saat"), t)
        pt.seans_kaydet(t, seans)
        return {"tur": tur, "tarih": t, "ozet": f"{gun_ad} · {ad} · {dk} dk", "geri": {"seans": seans["id"]}}
    if tur == "yemek" and str(k.get("metin") or "").strip():
        import pt_beslenme
        y = pt_beslenme.disaridan_kaydet([], str(k["metin"])[:400], t)
        top = round(sum(x.get("kcal") or 0 for x in y.get("kalemler") or []))
        return {"tur": tur, "tarih": t, "ozet": f"{gun_ad} · {y.get('ad')} · yaklaşık {top} kcal (kontrol edin)", "geri": {"yemek": y["id"]}}
    if tur == "kilo" and (k.get("kilo_kg") or k.get("bel_cm")):
        ek = {}
        if k.get("kilo_kg") and 30 <= float(k["kilo_kg"]) <= 300:
            ek["kilo"] = round(float(k["kilo_kg"]), 1)
        if k.get("bel_cm") and 40 <= float(k["bel_cm"]) <= 200:
            ek["bel_cm"] = round(float(k["bel_cm"]), 1)
        if not ek:
            return None
        once = {a: pt.gun(t).get(a) for a in ek}
        pt.gun_degistir(t, lambda d: d.update(ek))
        return {"tur": tur, "tarih": t, "ozet": f"{gun_ad} · " + " · ".join(f"{v:g} {'kg' if a == 'kilo' else 'cm bel'}".replace(".", ",") for a, v in ek.items()),
                "geri": {"once": once}}
    if tur == "uyku" and k.get("uyku_saat"):
        u = pt.sayi(k["uyku_saat"], 1, 16, None)
        if not u:
            return None
        import pt_saglik
        once = (pt_saglik.gun(t) or {}).get("uyku_saat")
        pt_saglik.kaydet({"tarih": t, "uyku_saat": u})
        return {"tur": tur, "tarih": t, "ozet": f"{gun_ad} · {u:g} saat uyku".replace(".", ","), "geri": {"uyku_once": once}}
    if tur == "su" and k.get("ml"):
        ml = int(pt.sayi(k["ml"], 50, 5000, 0))
        if not ml:
            return None
        pt.gun_degistir(t, lambda d: d.update(su_ml=(d.get("su_ml") or 0) + ml))
        return {"tur": tur, "tarih": t, "ozet": f"{gun_ad} · {ml} ml su", "geri": {"ml": ml}}
    return None


def kayit_geri(r):
    """kayit_isle sonucunu geri alır."""
    t, g = r["tarih"], r.get("geri") or {}
    if g.get("seans"):
        pt.gun_degistir(t, lambda d: d.update(seanslar=[s for s in d.get("seanslar") or [] if s.get("id") != g["seans"]]))
    elif g.get("seans_once"):
        once = g["seans_once"]
        pt.gun_degistir(t, lambda d: d.update(seanslar=[once if s.get("id") == once.get("id") else s for s in d.get("seanslar") or []]))
    elif g.get("yemek"):
        import pt_beslenme
        pt_beslenme.yemek_sil(t, g["yemek"])
    elif "once" in g:
        def f(d):
            for a, v in g["once"].items():
                if v is None:
                    d.pop(a, None)
                else:
                    d[a] = v
        pt.gun_degistir(t, f)
    elif "uyku_once" in g:
        import pt_saglik
        yol = pt_saglik.KLASOR / f"{t}.json"
        d = pt._json(yol, {})
        if g["uyku_once"] is None:
            d.pop("uyku_saat", None)
        else:
            d["uyku_saat"] = g["uyku_once"]
        pt._yaz(yol, d)
    elif g.get("ml"):
        pt.gun_degistir(t, lambda d: d.update(su_ml=max(0, (d.get("su_ml") or 0) - g["ml"])))


def kayit_geri_al(no, i):
    def al(L):
        x = next((x for x in L if x.get("kayit_no") == no), None)
        if not x or i >= len(x.get("kayitlar") or []) or x["kayitlar"][i].get("geri_alindi"):
            return None
        x["kayitlar"][i]["geri_alindi"] = int(time.time())
        return dict(x["kayitlar"][i])
    r = _degistir(al)
    if r:
        kayit_geri(r)
    return bool(r)


def gecmis():
    return pt._json(DOSYA, {"mesajlar": []})["mesajlar"]


def _yaz(L):
    pt._yaz(DOSYA, {"mesajlar": L[-60:]})


def _degistir(fn):
    """Kilit altında yeniden oku → değiştir → yaz (2026-10-28: Claude yanıtı beklenirken yapılan 'Uygula' eski kopyayla
    siliniyor, aynı öneri iki kez uygulanabiliyordu)."""
    with pt._kilit:
        L = gecmis()
        sonuc = fn(L)
        _yaz(L)
        return sonuc


def baglam():
    p = pt.profil()
    t = pt.bugun().isoformat()
    gs = pt.gun_seansi(t)
    pl = pt.program()
    son = []
    for g in pt.gunler(5):
        for s in g.get("seanslar") or []:
            son.append({"id": s.get("id"), "tarih": g["tarih"], "tur": s.get("tur"), "baslik": s.get("baslik"), "sure_dk": s.get("sure_dk"), "zorluk": s.get("zorluk"), "not": s.get("not")})
        for a in g.get("agri") or []:
            son.append({"tarih": g["tarih"], "agri": a.get("bolge"), "puan": a.get("puan")})
    return dict(
        profil=pt._profil_ozeti(p), bugun=t,
        bugun_plan=json.dumps([{"id": s.get("id"), "tur": s.get("tur"), "baslik": s.get("baslik"), "sure_dk": s.get("sure_dk"), "bitti": s.get("bitti")}
                               for s in gs["seanslar"]], ensure_ascii=False),
        sabah=json.dumps(gs.get("sabah") or {}, ensure_ascii=False)[:600],
        hafta=json.dumps([{"id": g.get("id"), "tarih": g["tarih"], "tur": g["tur"], "baslik": g.get("baslik")} for g in pl.get("gunler") or []], ensure_ascii=False),
        son=json.dumps(son[-30:], ensure_ascii=False), kurallar=" ".join(pt.KURALLAR_METNI), bolgeler="|".join(pt.BOLGELER),
        saglik=_g(_saglik_ozet, "yok"), doz=_g(lambda: json.dumps(__import__("pt_uzun").doz_ozeti().get("satirlar"), ensure_ascii=False), "yok"),
        moduller=_g(lambda: ", ".join(f"{m['ad']}{' (bugün yapıldı)' if m.get('bitti') else ''}" for m in __import__("pt_modul").gunun()) or "yok", "yok"),
        gunluk=_g(lambda: __import__("pt_gunluk").baglam_metni(p), "yok"),
        oruc=_g(lambda: __import__("pt_oruc").anlat(__import__("pt_beslenme").pencere_durumu(p).get("oruc")), "yok"))


def _g(fn, v=""):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return v


def _saglik_ozet():
    import pt_saglik
    L = []
    for i in range(0, 4):
        t = (pt.bugun() - dt.timedelta(days=i)).isoformat()
        g = pt_saglik.gun(t) or {}
        x = {k: g[k] for k in ("uyku_saat", "nabiz", "hrv", "kilo") if g.get(k)}
        ab = pt_saglik.adim_bilgi(g.get("adim"))
        if ab:
            x["adim"] = f"yaklaşık {ab['tahmin']} (telefonun saydığı {ab['sayilan']}; telefon hep üzerinde olmadığı için eksik sayar)" if ab["duzeltildi"] else ab["sayilan"]
        Y = pt_saglik.yuruyusler(t)
        if Y:
            x["adım kayıtlarından ölçülen yürüyüş (yeniden kaydetme)"] = ", ".join(f"{w['ad']} {w['dk']} dk" for w in Y)
        if x:
            L.append(f"{t}: " + ", ".join(f"{k} {v}" for k, v in x.items()))
    return "; ".join(L) or "yok"


def gonder(metin):
    import claude_yaz
    L = _degistir(lambda L: (L.append({"kim": "siz", "metin": str(metin)[:1000], "t": int(time.time())}), list(L))[1])
    son = [m for m in L if time.time() - m["t"] < 6 * 3600][-12:]
    g = "\n".join(f"{'Kullanıcı' if m['kim'] == 'siz' else 'Health'}: {m['metin']}" for m in son)
    c = claude_yaz.sor_json(ISTEM.format(gecmis=g, **baglam()), model_adi="sonnet", zaman_asimi=300)
    cevap = {"kim": "pt", "metin": str(c.get("yanit") or "")[:1600], "t": int(time.time())}
    K = []
    for k in (c.get("kayitlar") or [])[:6]:
        if isinstance(k, dict):
            try:
                r = kayit_isle(k)
            except Exception as e:  # noqa: BLE001
                r = {"tur": k.get("tur"), "tarih": _tarih(k.get("tarih")), "ozet": f"Kaydedilemedi: {str(e)[:80]}", "hata": True}
            if r:
                K.append(r)
    if K:
        cevap["kayitlar"] = K
        cevap["kayit_no"] = f"k{int(time.time() * 1000)}"
    cevap["oneriler"] = [str(x)[:40] for x in (c.get("oneriler") or []) if str(x).strip()][:3]
    KART = ("seans", "doz", "nefes", "program", "kilo")
    cevap["kartlar"] = [str(k)[:40] for k in (c.get("kartlar") or []) if str(k).split(":")[0] in KART or str(k).startswith("hareket:")][:2]
    if c.get("soru") and (c["soru"].get("secenekler") or []):
        cevap["soru"] = {"soru": str(c["soru"].get("soru") or "")[:200], "secenekler": [str(x)[:60] for x in c["soru"]["secenekler"]][:5]}
    e = c.get("eylem")
    import pt_gunluk
    if isinstance(e, dict) and pt_gunluk.acik() and e.get("tur") == "hafta":
        e = None                                     # plan kodla kuruluyor; "yeniden yazdım" denmesin
    if isinstance(e, dict) and e.get("tur") == "liste":
        cevap["sonuc"] = pt_gunluk.liste_degistir(e)  # kişi açıkça istedi, onay beklemez
        cevap["kartlar"] = ["program"]
        e = None
    yeni_eylem = isinstance(e, dict) and e.get("tur") in ("bugun", "hafta", "tasi", "profil", "not", "dinlenme")
    if yeni_eylem:
        cevap["eylem"] = {k: v for k, v in e.items() if v not in (None, "", [], {})}
        cevap["eylem"]["id"] = cevap["eylem"].get("id") or ""
        cevap["eylem_no"] = f"e{int(time.time() * 1000)}"

    def ekle(L):
        if yeni_eylem:
            for eski in L:                                   # yanıtlanmamış eski öneri: yerine yenisi geldi
                if eski.get("eylem") and not eski.get("uygulandi") and not eski.get("uygulaniyor") and not eski.get("vazgecildi"):
                    eski["vazgecildi"] = True
        L.append(cevap)
    _degistir(ekle)
    return cevap


def uygula(eylem_no):
    """Onaylanan öneriyi uygular. Döner: kısa sonuç metni."""
    def al(L):                                               # önce işaretle: iki dokunuş aynı öneriyi iki kez uygulamasın
        x = next((x for x in L if x.get("eylem_no") == eylem_no), None)
        if not x or x.get("uygulandi") or x.get("uygulaniyor"):
            return None
        x["uygulaniyor"] = int(time.time())
        return dict(x)
    m = _degistir(al)
    if not m:
        return None
    e = m["eylem"]
    try:
        t = pt.bugun().isoformat()
        tur, sonuc = e["tur"], ""
        if tur in ("bugun", "dinlenme"):
            def degis(d):
                s = d.get("sabah") or {}
                if tur == "dinlenme":
                    s["isik"], s["neden"] = "kirmizi", ["Health ile konuşma: dinlenme"]
                else:
                    for a in ("vakit_dk", "nerede", "isik"):
                        if e.get(a):
                            s[a] = e[a]
                    if e.get("agri"):
                        s["agri"] = (s.get("agri") or []) + [a for a in e["agri"] if a.get("bolge") in pt.BOLGELER]
                        d["agri"] += [{**a, "t": int(time.time()), "sohbet": True} for a in e["agri"] if a.get("bolge") in pt.BOLGELER]
                        if not e.get("isik"):
                            s["isik"] = pt.sabah_isigi(s)[0]
                    s.setdefault("isik", "yesil")
                    s["neden"] = (s.get("neden") or []) + ["Health ile konuşma"]
                s["t"] = s.get("t") or int(time.time())
                d["sabah"] = s
            pt.gun_degistir(t, degis)
            sonuc = "Bugünkü seans güncellendi."
        elif tur == "hafta":
            pt.program_uret(pt.hafta_kodu(), e.get("istek") or m.get("metin") or "")
            sonuc = "Haftanız yeniden yazıldı."
        elif tur == "tasi" and e.get("id") and e.get("tarih"):
            kod = pt.hafta_kodu(dt.date.fromisoformat(e["tarih"]))
            pt.gun_tasi(kod, e["id"], e["tarih"])
            sonuc = "Seans taşındı."
        elif tur == "profil":
            p = pt.profil()
            ek, cik = e.get("ekle") or {}, e.get("cikar") or {}
            yeni = {"ekipman": [x for x in (p.get("ekipman") or []) if x not in (cik.get("ekipman") or [])] + [x for x in ek.get("ekipman") or [] if x in pt.EKIPMANLAR and x not in (p.get("ekipman") or [])],
                    "sakatliklar": [x for x in (p.get("sakatliklar") or []) if x not in (cik.get("sakatliklar") or [])] + list(ek.get("sakatliklar") or [])}
            b = p["beslenme"]
            b["hassasiyetler"] = [x for x in b.get("hassasiyetler") or [] if x not in (cik.get("hassasiyetler") or [])] + list(ek.get("hassasiyetler") or [])
            yeni["beslenme"] = b
            pt.profil_kaydet(yeni)
            sonuc = "Profiliniz güncellendi; bir sonraki plan buna göre yazılır."
        elif tur == "not":
            p = pt.profil()
            pt.profil_kaydet({"notlar": (p.get("notlar") or []) + [{"soru": "Health ile konuşma", "metin": e.get("not") or m.get("metin")}]})
            sonuc = "Not alındı."
    except Exception:
        def geri(L):
            for x in L:
                if x.get("eylem_no") == eylem_no:
                    x.pop("uygulaniyor", None)
        _degistir(geri)
        raise

    def bitir(L):
        for x in L:
            if x.get("eylem_no") == eylem_no:
                x.pop("uygulaniyor", None)
                x["uygulandi"] = int(time.time())
                x["sonuc"] = sonuc
    _degistir(bitir)
    return sonuc


def vazgec(eylem_no):
    def f(L):
        for x in L:
            if x.get("eylem_no") == eylem_no and not x.get("uygulandi"):
                x["vazgecildi"] = True
    _degistir(f)


# ----------------------------------------------------------------------------- Health önce konuşur (2026-10-31; kullanıcı: "deneyim humanize edilmeli,
# çok kısıtlı hissediyorum"). Bugün ekranının başında, günün durumuna göre kısa, kişisel bir söz; altında kişinin verebileceği cevaplar. Söz sohbet
# geçmişine de yazılır, cevap aynı konuşmanın devamıdır. Günün durumu değişince (sabah kontrolü, seans, kayıt) yeniden yazılır.
SELAM = pt.VERI / "selam.json"
SELAM_ISTEM = """Sen Health'sin: kişinin yanındaki sıcak, meraklı, dürüst koç. Bugün ekranını açtı; ilk sen konuşuyorsun. Şu anki duruma göre
1-2 cümlelik, insan gibi, KİŞİSEL bir söz yaz: dünü ya da son kayıtları (maç, yürüyüş, uyku, adım) fark ettiğini göster, bugün için tek bir şey
öner ya da sor. Selamlama ve ad ekranda zaten yazıyor: "Günaydın/Merhaba/İyi akşamlar" ile ve adla BAŞLAMA, doğrudan konuya gir.
Kayıttaki sayıları ve puanları okur gibi tekrarlama ("7 zorluk girmişsiniz" değil, "dünkü maç zorlu geçmiş"); bir arkadaş gibi söyle.
Rapor dili, "Bugün harika bir gün" gibi kalıp, emoji yok; "siz" dili, Türkçe. Saat {saat}, {dilim}. Veri yoksa uydurma.
KİŞİ: {profil}
BUGÜN ({bugun}): {bugun_plan}
SABAH KONTROLÜ: {sabah}
SON KAYITLAR: {son}
APPLE SAĞLIK: {saglik}
BU HAFTANIN SAĞLIK DOZU: {doz}
MODÜLLER: {moduller}
PROGRAM DURUMU: {durum}
JSON: {{"soz": "1-2 cümle", "cevaplar": ["kişinin buna verebileceği 3 kısa cevap, onun ağzından, en çok 5 kelime"], "kart": "seans|doz|nefes|null"}}"""


def _dilim():
    h = dt.datetime.now().hour
    return "sabah" if h < 12 else "öğleden sonra" if h < 18 else "akşam"


def _selam_imza():
    t = pt.bugun().isoformat()
    d = pt.gun(t)
    return f"{t}|{_dilim()}|{bool(d.get('sabah'))}|{sum(1 for x in d.get('seanslar') or [] if x.get('bitti'))}|{len(d.get('yemekler') or [])}"


def _kural_selam():
    gs = pt.gun_seansi(pt.bugun().isoformat())
    s = next((x for x in gs["seanslar"] if not x.get("bitti") and x.get("tur") != "dinlenme"), None)
    if not gs.get("sabah"):
        return {"soz": "Bugün nasıl hissediyorsunuz? Uykunuza ve enerjinize göre günü ayarlayayım.",
                "cevaplar": ["İyiyim, enerjim yerinde", "Biraz yorgunum", "Vaktim az"], "kart": None}
    if s:
        return {"soz": f"Bugün {s.get('baslik') or 'seansınız'} var, {s.get('sure_dk') or 20} dakika. Hazır olduğunuzda başlayalım.",
                "cevaplar": ["Şimdi başlıyorum", "Akşama bırakayım", "Daha kısa olsun"], "kart": "seans"}
    return {"soz": "Bugünkü işiniz tamam gibi. Yarın için bir isteğiniz var mı?", "cevaplar": ["Yarın daha kolay", "Her şey yolunda", "Bir sorum var"], "kart": None}


def selam(uret=True):
    """Önbellekteki söz (aynı durum için bir kez yazılır). uret=False: yalnız var olanı ya da kural sözünü döndürür."""
    im = _selam_imza()
    d = pt._json(SELAM, {})
    if d.get("imza") == im and d.get("soz"):
        return d
    if not uret:
        return {**_kural_selam(), "imza": im, "eski": True}
    import claude_yaz
    c = {}
    if claude_yaz.hazir():
        try:
            import pt_yeniden
            b = baglam()
            dg = pt_yeniden.durgun()
            c = claude_yaz.sor_json(SELAM_ISTEM.format(saat=dt.datetime.now().strftime("%H:%M"), dilim=_dilim(),
                                                       durum=json.dumps(dg, ensure_ascii=False) if dg else "yolunda", **b), model_adi="sonnet", zaman_asimi=120)
        except Exception:  # noqa: BLE001
            c = {}
    if not c.get("soz"):
        c = _kural_selam()
    out = {"imza": im, "soz": str(c["soz"])[:400], "cevaplar": [str(x)[:40] for x in c.get("cevaplar") or []][:3],
           "kart": c.get("kart") if c.get("kart") in ("seans", "doz", "nefes") else None, "t": int(time.time())}
    pt._yaz(SELAM, out)
    def ekle(L):                                                 # konuşmanın başı olsun: cevap bu sözün devamıdır
        eski = next((m for m in L if m.get("selam") == im), None)
        if eski:                                                 # aynı durumun söz yeniden yazıldı (ör. Claude yokken kural sözü vardı)
            eski.update({"metin": out["soz"], "oneriler": out["cevaplar"]})
        else:
            L.append({"kim": "pt", "metin": out["soz"], "t": out["t"], "selam": im, "oneriler": out["cevaplar"]})
    _degistir(ekle)
    return out

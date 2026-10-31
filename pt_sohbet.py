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
import time

import pt

DOSYA = pt.VERI / "sohbet.json"

ISTEM = """Sen Health'sin: kişisel antrenör + diyetisyen + fizyoterapist bilgisiyle çalışan, kısa ve net konuşan bir koç. Türkçe, "siz" dili, en çok 3 cümle.
Kullanıcı sana bir durum söyledi ya da yaptığı bir şeyi anlattı. YAPTIĞI ya da ÖLÇTÜĞÜ bir şeyi söylüyorsa (maç, yürüyüş, koşu, ders,
yediği yemek, kilo, uyku, içtiği su) onu "kayitlar" listesine yaz: bunlar onay beklemeden kaydedilir; yanıtta kaydettiğini kısa söyle ve
gerekiyorsa tek cümle yorum ekle (ör. maç yoğun çalışma sayılır, yarın hafif tutalım). Tarihleri {bugun} gününe göre çöz ("dün", "cumartesi").
Süre ya da zorluk söylenmediyse makul tahmin et (zorluk 1-10: halı saha/büyük saha futbol 7-8, tempolu yürüyüş 3-4). Ayrıca görevin: (a) durumu anlamak için gerekiyorsa TEK seçenekli soru sormak, (b) yeterince biliyorsan planda yapacağın
değişikliği önermek. Teşhis koyma. Göğüs ağrısı, baş dönmesi, bayılma, yayılan uyuşma, şişlikle keskin eklem ağrısı gibi uyarı belirtilerinde
antrenmanı durdur ve doktora/112'ye yönlendir (eylem: dinlenme).

KİŞİ: {profil}
BUGÜN ({bugun}): {bugun_plan}
SABAH KONTROLÜ: {sabah}
BU HAFTA: {hafta}
SON KAYITLAR: {son}
KURALLAR (kodda, değiştirme): {kurallar}

KONUŞMA:
{gecmis}

JSON döndür:
{{"yanit": "kısa cevap",
  "kayitlar": [{{"tur": "aktivite|yemek|kilo|uyku|su", "tarih": "YYYY-MM-DD",
     "spor": "futbol|basketbol|tenis|voleybol|padel|yuzme|kosu|yuruyus|bisiklet|jiujitsu|yoga|fitness|dans|diger", "ad": "kısa ad: 'Futbol (büyük saha)'",
     "sure_dk": sayı, "zorluk": 1-10, "not": "...", "metin": "yemek için: yenen her şey miktarıyla", "ogun": "kahvalti|ogle|aksam|ara",
     "kilo_kg": sayı, "bel_cm": sayı, "uyku_saat": sayı, "ml": sayı}}],
  "soru": null ya da {{"soru": "...", "secenekler": ["3-5 kısa, aynı düzeyde seçenek"]}},
  "eylem": null ya da {{"tur": "bugun|hafta|tasi|profil|not|dinlenme", "aciklama": "kullanıcıya tek cümle: ne değişecek",
     "vakit_dk": sayı|null, "nerede": "ev|park|salon|yolda"|null, "isik": "yesil|sari|kirmizi"|null, "agri": [{{"bolge": "{bolgeler}", "puan": 0-10}}],
     "istek": "hafta için yönlendirme cümlesi", "id": "taşınacak seans id", "tarih": "YYYY-MM-DD",
     "ekle": {{"ekipman": [], "sakatliklar": [], "hassasiyetler": []}}, "cikar": {{"ekipman": [], "sakatliklar": [], "hassasiyetler": []}}, "not": "..."}}}}
Kayıt yoksa "kayitlar": []. Aynı şey için hem kayıt hem eylem yazma. Soru sorarken eylem null olsun. Değişiklik gerekmiyorsa eylem null, yalnız yanıt.
Alanları yalnız ilgili türde doldur: bugun → vakit_dk/nerede/isik/agri; hafta → istek; tasi → id/tarih; profil → ekle/cikar (hassasiyetler = GIDA
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


def kayit_isle(k):
    """Tek kaydı uygular. Döner: {tur, tarih, ozet, geri} (geri: geri almak için gereken bilgi) ya da None."""
    tur = k.get("tur")
    t = _tarih(k.get("tarih"))
    gun_ad = "Bugün" if t == pt.bugun().isoformat() else "Dün" if t == (pt.bugun() - dt.timedelta(days=1)).isoformat() else \
        pt.GUN_AD[dt.date.fromisoformat(t).weekday()]
    if tur == "aktivite":
        spor = k.get("spor") if k.get("spor") in SPOR else "diger"
        st, ad0 = SPOR[spor]
        dk = int(pt.sayi(k.get("sure_dk"), 1, 600, 30))
        zor = int(pt.sayi(k.get("zorluk"), 1, 10, 6))
        ad = str(k.get("ad") or ad0)[:60]
        seans = {"id": f"k{int(time.time() * 1000)}", "tur": st, "baslik": ad, "sure_dk": dk, "zorluk": zor, "kaynak": "sohbet", "spor": spor,
                 "not": str(k.get("not") or "")[:200]}
        if st in ("spor", "kardiyo", "bisiklet"):
            yog = "aralik" if zor >= 7 else "orta" if zor >= 5 else "kolay"
            seans["bisiklet" if st == "bisiklet" else "kardiyo"] = {"tur": spor, "sure_dk": dk, "yogunluk": yog}
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
            son.append({"tarih": g["tarih"], "tur": s.get("tur"), "zorluk": s.get("zorluk"), "not": s.get("not")})
        for a in g.get("agri") or []:
            son.append({"tarih": g["tarih"], "agri": a.get("bolge"), "puan": a.get("puan")})
    return dict(
        profil=pt._profil_ozeti(p), bugun=t,
        bugun_plan=json.dumps([{"id": s.get("id"), "tur": s.get("tur"), "baslik": s.get("baslik"), "sure_dk": s.get("sure_dk"), "bitti": s.get("bitti")}
                               for s in gs["seanslar"]], ensure_ascii=False),
        sabah=json.dumps(gs.get("sabah") or {}, ensure_ascii=False)[:600],
        hafta=json.dumps([{"id": g.get("id"), "tarih": g["tarih"], "tur": g["tur"], "baslik": g.get("baslik")} for g in pl.get("gunler") or []], ensure_ascii=False),
        son=json.dumps(son[:20], ensure_ascii=False), kurallar=" ".join(pt.KURALLAR_METNI), bolgeler="|".join(pt.BOLGELER))


def gonder(metin):
    import claude_yaz
    L = _degistir(lambda L: (L.append({"kim": "siz", "metin": str(metin)[:1000], "t": int(time.time())}), list(L))[1])
    son = [m for m in L if time.time() - m["t"] < 6 * 3600][-12:]
    g = "\n".join(f"{'Kullanıcı' if m['kim'] == 'siz' else 'Health'}: {m['metin']}" for m in son)
    c = claude_yaz.sor_json(ISTEM.format(gecmis=g, **baglam()), model_adi="sonnet", zaman_asimi=300)
    cevap = {"kim": "pt", "metin": str(c.get("yanit") or "")[:800], "t": int(time.time())}
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
    if c.get("soru") and (c["soru"].get("secenekler") or []):
        cevap["soru"] = {"soru": str(c["soru"].get("soru") or "")[:200], "secenekler": [str(x)[:60] for x in c["soru"]["secenekler"]][:5]}
    e = c.get("eylem")
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

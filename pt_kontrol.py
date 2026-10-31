"""pt_kontrol.py - Değerlendirme ve ara kontroller (2026-10-30; kullanıcı: "gerçek uzmanlarla başlıyormuşum gibi sorular sorsun, cevaplarıma göre
ne tarz bir spor ve beslenme programına ihtiyacım olduğunu belirlesin; ara kontrollerle programı güncellemek gerekip gerekmediğini belirlesin").

İki parça:
1. DEĞERLENDİRME (`degerlendirme`): kurulumdan sonra bir kez (profil değişince yenilenir). Gerçek bir antrenör + diyetisyenin ilk görüşme sonunda
   söylediği şey: "Sizi şöyle gördüm; antrenman yaklaşımınız şu, beslenme yaklaşımınız şu, nedeni şu, dikkat edeceğimiz şu, ilk adımlar bunlar."
   Sayılar koddan gelir (kalori, protein, pencere, testler, basamaklar); Claude yalnızca açıklar. Claude yoksa kural tabanlı metin.
2. ARA KONTROL (`zamani`, `hazirla`, `bitir`): kurulumdan ya da son kontrolden 14 gün sonra (ilk hafta yolu sürerken değil). Kod 14 günlük raporu
   çıkarır (uyum, zorluk, ağrı, uyku, kilo trendi hedef hıza göre, hedef ilerlemesi), Claude 3-4 seçenekli soru sorar, cevaplar + rapor →
   KARAR: "devam" ya da "güncelle" (değişiklikler nedenleriyle). Güvenli alanlar profile uygulanır (günlük dakika, gün sayısı, kilo hızı), plan isteği
   gelecek plana ve isteğe bağlı olarak bu haftanın yeniden yazımına gider. Kayıt pt/kontroller/<tarih>.json.
"""
import datetime as dt
import hashlib
import json
import re
import time

import pt

DEGERLENDIRME = pt.VERI / "degerlendirme.json"
KONTROLLER = pt.VERI / "kontroller"
KONTROL_ARALIK = 14

DEGERLENDIRME_ISTEM = """Sen PT'sin: bir uzman ekibisin (antrenör, dayanıklılık koçu, diyetisyen, fizyoterapist, uyku ve toparlanma koçu, uzun ömür uzmanı,
alışkanlık koçu; kişi jiu-jitsu yapıyorsa jiu-jitsu koçu). Kişinin asıl amacı uzun ve sağlıklı bir ömür olabilir; sorduğun şeyler ihtiyaç ve
şartlardı, programın bileşimine (hangi disiplin, kaç gün) SEN karar verdin ve REÇETE'de yazıyor. İlk görüşme bitti;
şimdi kişiye değerlendirmeni söylüyorsun: onu nasıl gördüğün, hangi antrenman yaklaşımının ve hangi beslenme yaklaşımının ona uyduğu ve NEDEN.
Sayılar aşağıda KODDAN geliyor (kalori, protein, pencere, test sonuçları, basamaklar); onları aynen kullan, yeni sayı uydurma. Teşhis koyma;
sağlık notu varsa saygıyla an ve gerekirse doktora yönlendir. Dil: Türkçe, "siz", sıcak ama net, klişe ve slogan yok, abartı yok, 2-3 cümlelik
paragraflar. Kişi programlama bilmez; teknik terim yok. Adıyla hitap edebilirsin ama "Bey/Hanım" ekleme. "dikkat" ve "ilk_adimlar" maddeleri
en çok 30 kelime.

KİŞİ: {profil}
KODUN HESAPLADIKLARI: {hesap}
KURALLAR (planı bunların içinde yazarım): {kurallar}

JSON:
{{"mesaj": "2-3 cümle: onu nasıl gördüğün ve neyi başarabileceği (gerçekçi, kişisel)",
 "antrenman": {{"yaklasim": "tek cümle ad (ör. 'Kalistenik temelli, haftada 4 kısa seans')", "aciklama": "2-4 cümle: hangi yöntemler, kaç gün, ne kadar, neye odak, nasıl ilerler", "neden": "2 cümle: bu kişi için neden böyle"}},
 "beslenme": {{"yaklasim": "tek cümle ad (ör. 'Hafif açık, yüksek protein, 11-17 penceresi')", "aciklama": "2-4 cümle: kalori, protein, pencere/öğün düzeni, ne yiyeceği", "neden": "2 cümle"}},
 "dikkat": ["en çok 4 madde: ağrı, sağlık notu, risk, alışkanlık"],
 "ilk_adimlar": ["bu hafta yapılacak 3 somut şey"],
 "ekip": [{{"uzman": "Antrenör|Dayanıklılık koçu|Diyetisyen|Fizyoterapist|Uyku ve toparlanma koçu|Uzun ömür uzmanı|Alışkanlık koçu|Jiu-jitsu koçu", "not": "bu kişi için tek cümle, en çok 25 kelime, somut"}}],
 "uzun_omur": {{"ozet": "2 cümle: yıllar sonra güçlü, dengeli ve bağımsız olmak için bu programın neye yatırım yaptığı (göstergelere dayan)", "olcum": "tek cümle: ilk ölçmemiz gerekenler ya da en zayıf gösterge"}},
 "kontrol": "tek cümle: 14 gün sonra neye bakacağız"}}
"antrenman" REÇETE'yi anlatır (disiplinler, kaç gün, neden), başka bir bileşim önerme. "ekip" 5-8 uzman; her biri tekrar etmeyen tek şey söyler.
Uzun ömür göstergelerinde "yok" olanlar henüz ölçülmedi; değer uydurma."""

KONTROL_SORU_ISTEM = """Sen PT'sin. {gun} günlük ara kontrol görüşmesi yapıyorsunuz; amacı programın güncellenip güncellenmeyeceğine karar vermek.
Aşağıdaki RAPOR kodun ölçtüğü gerçeklerdir. Rapora dayanarak 3-4 soru sor: her biri tek konu, 3-4 kısa ve birbirini dışlayan seçenek, gözleme
dayalı ("Seansların yarısı kaçmış, neden?" gibi). Seçenekler en çok 7 kelime. Konular: kaçırılan seansların nedeni, seansların zorluğu, ağrı, açlık/beslenmeye uyum, enerji,
önümüzdeki iki haftada özel durum. Rapor temizse (uyum yüksek, ağrı yok) sorular kısa ve ileriye dönük olsun. Türkçe, "siz" dili.
RAPOR: {rapor}
HEDEFLER: {hedefler}
JSON: {{"giris": "iki cümle: bu iki haftayı nasıl gördün (somut sayılarla)", "sorular": [{{"kod": "kisa_kod", "soru": "...", "secenekler": ["..."]}}]}}"""

KONTROL_KARAR_ISTEM = """Sen PT'sin: antrenör + diyetisyen. {gun} günlük ara kontrol bitti. RAPOR kodun ölçtüğü gerçekler, CEVAPLAR kişinin söyledikleri,
KURAL ÖNERİLERİ kodun kurallarından çıkan değişiklikler (bunlara uy; gerekçesi olmadan ters düşme). Karar ver: program "devam" mı, "guncelle" mi.
Aynı anda en çok 2-3 şeyi değiştir. Değişmeyen şeyleri de söyle ("şu iyi gidiyor, dokunmuyorum"). Teşhis yok; ağrı sürüyorsa doktor/fizyoterapist öner.
Türkçe, "siz" dili, somut, klişe yok.
RAPOR: {rapor}
CEVAPLAR: {cevaplar}
KURAL ÖNERİLERİ: {kural}
HEDEFLER: {hedefler}
JSON: {{"karar": "devam|guncelle", "ozet": "2-3 cümle: iki haftanın değerlendirmesi, sayılarla",
 "degisiklikler": [{{"alan": "antrenman|beslenme|toparlanma|hedef", "ne": "tek cümle", "neden": "tek cümle"}}],
 "ayarlar": {{"gunluk_dk": null, "gun_sayisi": null, "kilo_hizi": null}},
 "plan_istegi": "gelecek haftanın planına verilecek tek cümlelik yönlendirme (devam ise boş olabilir)",
 "hedef_notu": "hedefler hakkında tek cümle (yolunda / değiştirilmeli)",
 "sonraki": "tek cümle: 14 gün sonra neye bakacağız"}}"""


def _profil_ozet(p):
    return json.dumps({k: p.get(k) for k in ("ad", "cinsiyet", "yas", "boy_cm", "kilo_kg", "hedef_kilo_kg", "hedef_turleri", "beceri_hedefleri", "deneyim",
                                             "motivasyon", "yontemler", "bjj_ders", "ekipman", "gunler", "gunluk_dk", "antrenman_saati", "sakatliklar",
                                             "sinirlar", "ek_bilgi", "notlar", "diyet", "beslenme", "beslenme_aliskanlik")}, ensure_ascii=False, default=str)


def _hesap(p):
    import pt_beslenme
    h = {}
    try:
        b = pt_beslenme.hedefler(p)
        pen = b.get("pencere") or {}
        h["beslenme"] = {"kcal": b.get("kcal"), "protein_g": b.get("protein"), "protein_aralik": b.get("protein_aralik"), "harcama": b.get("harcama"),
                         "acik": b.get("acik"), "lif": b.get("lif"), "doymus_ust": b.get("doymus_ust"), "kolesterol_notu": b.get("kolesterol"),
                         "pencere": f"{pen.get('acilis')}-{pen.get('kapanis')}" if pen.get("acilis") and (p.get("beslenme") or {}).get("pencere_saat", 14) < 14 else "saat sınırı yok",
                         "ogun_sayisi": (p.get("beslenme") or {}).get("ogun_sayisi"), "neden": b.get("neden")}
    except Exception:  # noqa: BLE001
        pass
    try:
        bas = pt.baslangic_durumu()
        h["baslangic"] = {"tur": bas.get("tur"), "aciklama": pt._baslangic_metni(bas, p)}
    except Exception:  # noqa: BLE001
        pass
    T = {}
    for k in pt.testler().get("kayitlar") or []:
        T.update(k.get("sonuclar") or {})
    h["testler"] = T or "henüz yok"
    try:
        kat = pt.katalog()
        h["basamaklar"] = pt._basamak_metni(kat)[:1500] or "henüz test yok"
    except Exception:  # noqa: BLE001
        pass
    try:
        import pt_uzun
        rc = pt_uzun.recete_oku()
        rc = rc if rc.get("satirlar") else pt_uzun.recete(p)
        h["recete"] = {"ozet": rc.get("ozet"), "satirlar": [{k: x.get(k) for k in ("ad", "haftada", "dk", "rol")} for x in rc.get("satirlar") or []],
                       "eklemeler": rc.get("eklemeler"), "uyarilar": rc.get("uyarilar")}
        h["uzun_omur_dozu"] = pt_uzun.dozlar(p, rc)
        h["uzun_omur_gostergeleri"] = [{k: g.get(k) for k in ("ad", "deger", "birim", "durum", "kaynak")} for g in pt_uzun.gostergeler(p)]
    except Exception:  # noqa: BLE001
        pass
    try:
        h["su_hedefi_ml"] = pt.su_hedefi(p)
    except Exception:  # noqa: BLE001
        pass
    return h


def _imza(p):
    d = {k: p.get(k) for k in ("hedef_turleri", "beceri_hedefleri", "hedef_kilo_kg", "kilo_kg", "yontemler", "gunler", "gunluk_dk",
                               "ekipman", "sakatliklar", "sinirlar", "beslenme", "diyet")}
    ek = {"sevdikleri": p.get("sevdikleri"), "recete": (pt._json(pt.VERI / "recete.json", {}) or {}).get("zaman")}
    d.update({k: v for k, v in ek.items() if v})          # yeni alanlar yalnız doluysa: eski değerlendirmeler boşuna yeniden yazılmasın
    return hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:10]


def _kural_degerlendirme(p, hesap):
    """Claude yoksa: sayılardan düz, dürüst bir değerlendirme."""
    y = {k: v for k, v in (p.get("yontemler") or {}).items() if v}
    gun = len(p.get("gunler") or []) or 3
    b = hesap.get("beslenme") or {}
    bas = (hesap.get("baslangic") or {}).get("tur")
    yak = ", ".join(f"{v} {pt.YONTEMLER.get(k, k)}" for k, v in y.items()) or "kalistenik"
    rc = hesap.get("recete") or {}
    if rc.get("ozet"):                                       # reçete varsa bileşimi o anlatır (ders günleri dahil)
        gun = int(re.search(r"Haftada (\d+)", rc["ozet"]).group(1)) if re.search(r"Haftada (\d+)", rc["ozet"]) else gun
        yak = rc["ozet"].split(": ", 1)[-1].rstrip(".")
    return {"mesaj": f"Haftada {gun} gün, günde {p.get('gunluk_dk') or 30} dakika ayırabiliyorsunuz; bu düzenli ilerleme için yeterli. "
                     + ("İlk haftalarda kısa seanslarla alışmak, sonra yüklenmek en sağlıklısı." if bas == "alisma" else "Kaldığınız yerden, ölçerek devam edeceğiz."),
            "antrenman": {"yaklasim": f"Haftalık {yak}", "aciklama": f"Her seans ısınma, ana bölüm ve kapanıştan oluşur; hareketler basamak basamak ilerler ve "
                                                                   f"her değişikliğin nedeni yazılır. {'İlk hafta 10-15 dakikalık seanslar.' if bas == 'alisma' else ''}",
                          "neden": "Hedeflerinize ve ekipmanınıza uyan, kaçırılmayacak kadar kısa seanslar."},
            "beslenme": {"yaklasim": f"{b.get('kcal') or '-'} kcal, {b.get('protein_g') or '-'} g protein", "aciklama": f"Yeme düzeni: {b.get('pencere')}, {b.get('ogun_sayisi') or 2} öğün. "
                                                                                                           f"{b.get('neden') or ''}", "neden": "Hedefler tartı ve kayıtlara göre kendini düzeltir."},
            "dikkat": [x for x in (p.get("sinirlar") or []) + (p.get("sakatliklar") or [])][:4],
            "ilk_adimlar": ["Sabah kontrolünü her gün yapın", "İlk antrenmanı bitirin; kısa da olsa sayılır", "Bir öğünü fotoğrafla kaydedin"],
            "ekip": _ekip_notlari(p), "uzun_omur": _kural_uzun_omur(p, hesap),
            "kontrol": "14 gün sonra uyum, zorluk ve ağrıya bakıp programı güncelleyip güncellemeyeceğimize karar veririz."}


def _ekip_notlari(p):
    try:
        return __import__("pt_uzun").uzman_notlari(p)
    except Exception:  # noqa: BLE001
        return []


def _kural_uzun_omur(p, hesap):
    d = hesap.get("uzun_omur_dozu") or {}
    G = hesap.get("uzun_omur_gostergeleri") or []
    eksik = [g["ad"].lower() for g in G if g.get("durum") == "yok"]
    return {"ozet": f"Uzun ve sağlıklı yaşamın üç ayağı kas gücü, kalp-damar kondisyonu ve denge. Haftada {d.get('guc', 2)} güç antrenmanı ve "
                    f"{d.get('kolay_dk', 150)} dakika kolay kardiyo bu üçünü birlikte besler.",
            "olcum": ("İlk ölçeceklerimiz: " + ", ".join(eksik[:3]) + ".") if eksik else "Göstergeleri 5 haftada bir yeniden ölçeriz."}


def degerlendirme(yenile=False):
    import claude_yaz
    p = pt.profil()
    d = pt._json(DEGERLENDIRME, {})
    imza = _imza(p)
    if d.get("mesaj") and d.get("imza") == imza and not yenile:
        return d
    hesap = _hesap(p)
    c = {}
    try:
        if claude_yaz.hazir():
            c = claude_yaz.sor_json(DEGERLENDIRME_ISTEM.format(profil=_profil_ozet(p), hesap=json.dumps(hesap, ensure_ascii=False, default=str),
                                                               kurallar=" ".join(pt.KURALLAR_METNI)), model_adi="opus", zaman_asimi=420)
    except Exception:  # noqa: BLE001
        c = {}
    if not (c.get("mesaj") and isinstance(c.get("antrenman"), dict) and isinstance(c.get("beslenme"), dict)):
        c = _kural_degerlendirme(p, hesap)
        yazan = "kural"
    else:
        yazan = "claude"
    d = {"zaman": int(time.time()), "imza": imza, "yazan": yazan, "mesaj": str(c.get("mesaj"))[:800],
         "antrenman": {k: str((c.get("antrenman") or {}).get(k) or "")[:900] for k in ("yaklasim", "aciklama", "neden")},
         "beslenme": {k: str((c.get("beslenme") or {}).get(k) or "")[:900] for k in ("yaklasim", "aciklama", "neden")},
         "dikkat": [str(x)[:400] for x in c.get("dikkat") or []][:4], "ilk_adimlar": [str(x)[:400] for x in c.get("ilk_adimlar") or []][:4],
         "kontrol": str(c.get("kontrol") or "")[:300], "hesap": hesap, "okundu": False,
         "ekip": [{"uzman": str(x.get("uzman") or "")[:40], "not": str(x.get("not") or "")[:300]} for x in (c.get("ekip") or []) if isinstance(x, dict)
                  and x.get("not")][:8] or _ekip_notlari(p),
         "uzun_omur": {k: str(((c.get("uzun_omur") or {}) if isinstance(c.get("uzun_omur"), dict) else {}).get(k) or "")[:500] for k in ("ozet", "olcum")}}
    if not d["uzun_omur"]["ozet"]:
        d["uzun_omur"] = _kural_uzun_omur(p, hesap)
    pt._yaz(DEGERLENDIRME, d)
    return d


def degerlendirme_oku():
    d = pt._json(DEGERLENDIRME, {})
    if d.get("mesaj"):
        d["eski"] = d.get("imza") != _imza(pt.profil())
    return d


def degerlendirme_isaretle(okundu=True):
    d = pt._json(DEGERLENDIRME, {})
    if d:
        d["okundu"] = bool(okundu)
        pt._yaz(DEGERLENDIRME, d)
    return d

# ----------------------------------------------------------------------------- ara kontrol


def _kontroller():
    KONTROLLER.mkdir(parents=True, exist_ok=True)
    return sorted((pt._json(f, {}) for f in KONTROLLER.glob("*.json")), key=lambda x: x.get("tarih") or "")


def _baslangic_tarihi():
    """Kurulum günü: ilk günlük kaydı, değerlendirme ya da hedef onayı (en eskisi). Profilin `guncelleme`si kullanılmaz: her kayıtta
    yenilendiği için 14 günlük sayacı sıfırlardı."""
    adaylar = []
    d = pt._json(DEGERLENDIRME, {})
    if d.get("zaman"):
        adaylar.append(dt.date.fromtimestamp(d["zaman"]))
    h = pt._json(pt.VERI / "hedefler.json", {})
    if h.get("onaylandi"):
        adaylar.append(dt.date.fromtimestamp(h["onaylandi"]))
    try:
        g = sorted(f.stem for f in pt.GUNLUK.glob("*.json") if len(f.stem) == 10)
        if g:
            adaylar.append(dt.date.fromisoformat(g[0]))
    except Exception:  # noqa: BLE001
        pass
    return min(adaylar) if adaylar else pt.bugun()


def zamani():
    """Kontrol zamanı geldi mi; sıradaki tarih; açık kontrol varsa o."""
    K = _kontroller()
    acik = next((k for k in reversed(K) if k.get("durum") == "acik"), None)
    son = next((k for k in reversed(K) if k.get("durum") == "bitti"), None)
    try:
        import pt_ilk
        ilk = pt_ilk.durum().get("aktif")
    except Exception:  # noqa: BLE001
        ilk = False
    bas = dt.date.fromisoformat(son["tarih"]) if son else _baslangic_tarihi()
    sonraki = bas + dt.timedelta(days=KONTROL_ARALIK)
    gun = (pt.bugun() - bas).days
    return {"zamani": bool(acik) or (gun >= KONTROL_ARALIK and not ilk and pt.profil().get("kuruldu")), "acik": acik, "son": son,
            "sonraki": sonraki.isoformat(), "gun": gun, "kalan": max(0, (sonraki - pt.bugun()).days), "sayi": len([k for k in K if k.get("durum") == "bitti"])}


def rapor(gun=KONTROL_ARALIK):
    """Kodun ölçtükleri (son `gun` gün)."""
    import pt_beslenme
    import pt_hedef
    p = pt.profil()
    bugun = pt.bugun()
    gunler_ = [bugun - dt.timedelta(days=i) for i in range(gun - 1, -1, -1)]
    gunluk = [pt.gun(g.isoformat()) for g in gunler_]
    planli = 0
    pl_onb = {}
    for g in gunler_:
        kod = pt.hafta_kodu(g)
        if kod not in pl_onb:
            pl_onb[kod] = pt.program(kod).get("gunler") or []
        planli += sum(1 for x in pl_onb[kod] if x.get("tarih") == g.isoformat() and x.get("tur") not in ("dinlenme",))
    seanslar = [s for d in gunluk for s in d.get("seanslar") or [] if s.get("bitti")]
    zorluk = [float(s["zorluk"]) for s in seanslar if isinstance(s.get("zorluk"), (int, float))]
    agri = [a for d in gunluk for a in d.get("agri") or [] if (a.get("tur") or "eklem") != "kas" and float(a.get("puan") or 0) >= 3]
    sabah = [d.get("sabah") for d in gunluk if d.get("sabah")]
    uyku = [float(s.get("uyku_saat")) for s in sabah if isinstance(s.get("uyku_saat"), (int, float))]
    isik = {k: sum(1 for s in sabah if s.get("isik") == k) for k in ("yesil", "sari", "kirmizi")}
    tr = [(t, v) for t, _, v in pt_beslenme.trend(gun + 7) if v]
    kilo_delta = round(tr[-1][1] - tr[0][1], 1) if len(tr) >= 2 else None
    hedef_b = {}
    try:
        hedef_b = pt_beslenme.hedefler(p)
    except Exception:  # noqa: BLE001
        pass
    beklenen = None
    if hedef_b.get("kayip") and hedef_b.get("kilo_trend"):
        beklenen = -round(float(hedef_b["kilo_trend"]) * min(0.7, float((p.get("beslenme") or {}).get("kilo_hizi") or 0.5)) / 100 * gun / 7, 1)
    protein_gun = sum(1 for d in gunluk if (d.get("yemekler") and hedef_b.get("protein") and pt_beslenme.gun_toplam(d)["protein"] >= .8 * hedef_b["protein"]))
    kayitli = sum(1 for d in gunluk if d.get("yemekler"))
    kat_ = pt.katalog()
    basamak = [x for x in pt.ilerleme().get("degisiklikler") or [] if x.get("t", 0) >= time.time() - gun * 86400 and not x.get("geri") and x.get("tur") == "basamak"]
    yukari = sum(1 for x in basamak if (kat_.get(x.get("yeni")) or {}).get("basamak", 0) > (kat_.get(x.get("kod")) or {}).get("basamak", 0))
    try:
        import pt_oyun
        oy = pt_oyun.ozet()
        seri = {"seri": oy["seri"], "en_uzun": oy["en_uzun"]}
    except Exception:  # noqa: BLE001
        seri = {}
    doz = {}
    try:
        import pt_uzun
        hd = pt_uzun.dozlar(p)
        kodlar = sorted({pt.hafta_kodu(g) for g in gunler_})
        olc = [pt_uzun.hafta_olcumu(k) for k in kodlar]
        doz = {"hedef_guc": hd["guc"], "hedef_kolay_dk": hd["kolay_dk"], "hafta": len(kodlar),
               "guc_ort": round(sum(o["guc"] for o in olc) / len(olc), 1), "kolay_dk_ort": round(sum(o["kolay_dk"] for o in olc) / len(olc)),
               "tamam_hafta": sum(1 for o in olc if o["guc"] >= hd["guc"] and o["kolay_dk"] >= hd["kolay_dk"])}
    except Exception:  # noqa: BLE001
        pass
    return {"gun": gun, "doz": doz, "planlanan_seans": planli, "yapilan_seans": len(seanslar), "uyum": round(len(seanslar) / planli, 2) if planli else None,
            "toplam_dk": sum(int(s.get("sure_dk") or 0) for s in seanslar), "zorluk_ort": round(sum(zorluk) / len(zorluk), 1) if zorluk else None,
            "zorluk_dagilim": {"kolay(<=4)": sum(1 for z in zorluk if z <= 4), "iyi(5-7)": sum(1 for z in zorluk if 5 <= z <= 7), "zor(>=8)": sum(1 for z in zorluk if z >= 8)},
            "agri": [{"bolge": a.get("bolge"), "puan": a.get("puan")} for a in agri][:8], "korunan": list(pt.koru_bolgeler()),
            "sabah_kontrol": len(sabah), "isik": isik, "uyku_ort": round(sum(uyku) / len(uyku), 1) if uyku else None,
            "kilo_degisim": kilo_delta, "kilo_beklenen": beklenen, "kilo_son": tr[-1][1] if tr else None,
            "beslenme": {"kayitli_gun": kayitli, "protein_hedefli_gun": protein_gun, "protein_hedef": hedef_b.get("protein"), "kcal_hedef": hedef_b.get("kcal")},
            "basamak_yukari": yukari, "basamak_asagi": len(basamak) - yukari,
            "seri": seri, "hedefler": [{k: h.get(k) for k in ("vade", "metin", "oran", "durum_metni", "kalan_gun")} for h in pt_hedef.aktif()],
            "testler_son": {k: v for k, v in (next(iter(reversed(pt.testler().get("kayitlar") or [])), {}) or {}).get("sonuclar", {}).items()}}


def _kural_onerileri(r, cevaplar=None):
    """Kurallardan çıkan değişiklik önerileri (Claude bunlara uyar; Claude yoksa karar bunlardır)."""
    p = pt.profil()
    cevaplar = cevaplar or {}
    L = []
    ayar = {}
    uyum = r.get("uyum")
    gun = len(p.get("gunler") or []) or 3
    dk = int(p.get("gunluk_dk") or 30)
    if uyum is not None and r["planlanan_seans"] >= 4:
        if uyum < 0.5:
            L.append({"alan": "antrenman", "ne": f"Haftalık antrenman günü {gun} → {max(2, gun - 1)}, seans süresi {dk} → {max(10, dk - 10)} dk.",
                      "neden": f"{r['gun']} günde planlanan {r['planlanan_seans']} seanstan {r['yapilan_seans']} tanesi yapıldı; daha küçük bir plan tutar."})
            ayar.update(gun_sayisi=max(2, gun - 1), gunluk_dk=max(10, dk - 10))
        elif uyum >= 0.85 and (r.get("zorluk_ort") or 10) <= 5 and not r.get("agri"):
            L.append({"alan": "antrenman", "ne": f"Seans süresi {dk} → {min(60, dk + 10)} dk; basamaklar kurallara göre ilerlemeye devam.",
                      "neden": f"Uyum %{round(uyum * 100)}, seanslar kolay geldi ({r['zorluk_ort']}/10), ağrı yok."})
            ayar.update(gunluk_dk=min(60, dk + 10))
    if (r.get("zorluk_ort") or 0) >= 8:
        L.append({"alan": "antrenman", "ne": "Önümüzdeki hafta hafif hafta: set sayısı üçte bir az.", "neden": f"Seanslar çok zor geldi (ortalama {r['zorluk_ort']}/10)."})
    if r.get("agri"):
        b = sorted({a.get("bolge") for a in r["agri"] if a.get("bolge")})
        L.append({"alan": "toparlanma", "ne": f"{', '.join(pt.BOLGELER.get(x, x) for x in b)} için yükleyen hareketler kolay basamakta; ağrı sürerse fizyoterapist.",
                  "neden": f"{len(r['agri'])} kez eklem ağrısı kaydedildi."})
    kd, kb = r.get("kilo_degisim"), r.get("kilo_beklenen")
    hiz = min(0.7, float((p.get("beslenme") or {}).get("kilo_hizi") or 0.5))
    if kd is not None and kb is not None and r["beslenme"]["kayitli_gun"] >= 7:
        if kd > kb + 0.6 and hiz >= 0.7:
            L.append({"alan": "beslenme", "ne": "Açık zaten üst sınırda; iki hafta porsiyonları tartarak ve kayıt dışı kalorilere (yağ, içecek) bakarak kaydedin.",
                      "neden": f"Kilo trendi {kd:+g} kg, beklenen {kb:+g} kg; hızı daha da artırmak kas kaybettirir."})
        elif kd > kb + 0.6 and hiz < 0.7:
            L.append({"alan": "beslenme", "ne": f"Günlük açık 100 kcal artar (hız {hiz:g} → {min(0.7, round(hiz + 0.1, 1)):g} %/hafta).",
                      "neden": f"Kilo trendi {kd:+g} kg, beklenen {kb:+g} kg; kayıtlar düzenli olduğu için hedef biraz sıkılaşır."})
            ayar["kilo_hizi"] = min(0.7, round(hiz + 0.1, 1))
        elif kd < kb - 0.8 and hiz > 0.3:
            L.append({"alan": "beslenme", "ne": f"Açık azalır (hız {hiz:g} → {max(0.3, round(hiz - 0.2, 1)):g} %/hafta).",
                      "neden": f"Kilo beklenenden hızlı düştü ({kd:+g} kg); kas ve enerji korunmalı."})
            ayar["kilo_hizi"] = max(0.3, round(hiz - 0.2, 1))
    if r["beslenme"]["kayitli_gun"] and r["beslenme"]["protein_hedefli_gun"] < r["beslenme"]["kayitli_gun"] * 0.5:
        n = r["beslenme"]["protein_hedefli_gun"]
        L.append({"alan": "beslenme", "ne": "Her öğüne bir avuç içi protein; menü buna göre yeniden yazılır.",
                  "neden": f"Kayıtlı {r['beslenme']['kayitli_gun']} günün " + ("hiçbirinde" if not n else f"yalnız {n} tanesinde") + " protein hedefe yaklaştı."})
    dz = r.get("doz") or {}
    if dz.get("hedef_kolay_dk") and dz.get("kolay_dk_ort", 0) < dz["hedef_kolay_dk"] / 2 and r.get("yapilan_seans"):
        L.append({"alan": "uzun_omur", "ne": "Antrenman olmayan günlere 20 dakikalık tempolu yürüyüş; kolay kardiyo dakikaları buradan dolar.",
                  "neden": f"Haftada ortalama {dz['kolay_dk_ort']} dk kolay kardiyo yapıldı, hedef {dz['hedef_kolay_dk']} dk."})
    if dz.get("hedef_guc") and dz.get("guc_ort", 0) < dz["hedef_guc"] - 0.5 and r.get("yapilan_seans"):
        L.append({"alan": "uzun_omur", "ne": "Güç antrenmanları haftanın başına; kaçarsa 20 dakikalık kısa versiyon.",
                  "neden": f"Haftada ortalama {dz['guc_ort']} güç antrenmanı; uzun ömür için en az {dz['hedef_guc']}."})
    if r.get("uyku_ort") and r["uyku_ort"] < 6.5:
        L.append({"alan": "toparlanma", "ne": "Yatış saati 30 dakika öne; zor seanslar iyi uyunan günlere.", "neden": f"Ortalama uyku {r['uyku_ort']} saat."})
    sec = str(cevaplar.get("ozel") or cevaplar.get("onumuzdeki") or "").lower()
    if any(k in sec for k in ("seyahat", "yoğun", "yogun", "hasta")):
        L.append({"alan": "antrenman", "ne": "Önümüzdeki iki hafta kısa, ekipmansız seanslar.", "neden": "Özel bir dönem söylediniz."})
    return L, ayar


def hazirla(yenile=False):
    """Açık kontrol yoksa açar: rapor + sorular."""
    import claude_yaz
    import pt_hedef
    z = zamani()
    if z.get("acik") and not yenile:
        return z["acik"]
    r = rapor()
    c = {}
    try:
        if claude_yaz.hazir():
            c = claude_yaz.sor_json(KONTROL_SORU_ISTEM.format(gun=KONTROL_ARALIK, rapor=json.dumps(r, ensure_ascii=False, default=str),
                                                              hedefler=pt_hedef.istem_metni()), model_adi="sonnet", zaman_asimi=240)
    except Exception:  # noqa: BLE001
        c = {}
    sorular = [{"kod": str(s.get("kod") or f"s{i}")[:24], "soru": str(s.get("soru"))[:220], "secenekler": [str(x)[:90] for x in s.get("secenekler") or []][:5]}
               for i, s in enumerate(c.get("sorular") or []) if s.get("soru") and len(s.get("secenekler") or []) >= 2][:4]
    if not sorular:
        sorular = [{"kod": "uyum", "soru": "Kaçırdığınız seansların asıl nedeni neydi?", "secenekler": ["Kaçırmadım", "Vakit", "Enerji", "Ağrı ya da hastalık"]},
                   {"kod": "zorluk", "soru": "Seanslar nasıl geldi?", "secenekler": ["Kolay", "Tam yerinde", "Zor", "Çok değişken"]},
                   {"kod": "beslenme", "soru": "Beslenme planına uyum?", "secenekler": ["Çoğu gün", "Yarı yarıya", "Az", "Kaydetmedim"]},
                   {"kod": "ozel", "soru": "Önümüzdeki iki haftada özel bir durum var mı?", "secenekler": ["Yok", "Seyahat", "İş yoğun", "Hastalık"]}]
    k = {"tarih": pt.bugun().isoformat(), "zaman": int(time.time()), "durum": "acik", "rapor": r, "giris": str(c.get("giris") or "")[:400], "sorular": sorular}
    KONTROLLER.mkdir(parents=True, exist_ok=True)
    pt._yaz(KONTROLLER / f"{k['tarih']}.json", k)
    return k


def bitir(tarih, cevaplar):
    """Cevaplar → karar. Güvenli ayarlar profile; plan isteği profile (`kontrol_istegi`, bir sonraki planda kullanılır)."""
    import claude_yaz
    import pt_hedef
    yol = KONTROLLER / f"{pt.tarih_gecerli(tarih)}.json"
    k = pt._json(yol, {})
    if not k:
        raise ValueError("Böyle bir kontrol yok.")
    r = k.get("rapor") or rapor()
    cevaplar = {str(a)[:24]: str(b)[:80] for a, b in (cevaplar or {}).items()}
    kural, ayar = _kural_onerileri(r, cevaplar)
    c = {}
    try:
        if claude_yaz.hazir():
            c = claude_yaz.sor_json(KONTROL_KARAR_ISTEM.format(gun=KONTROL_ARALIK, rapor=json.dumps(r, ensure_ascii=False, default=str),
                                                               cevaplar=json.dumps([{"soru": s["soru"], "cevap": cevaplar.get(s["kod"], "")} for s in k.get("sorular") or []], ensure_ascii=False),
                                                               kural=json.dumps(kural, ensure_ascii=False), hedefler=pt_hedef.istem_metni()), model_adi="opus", zaman_asimi=420)
    except Exception:  # noqa: BLE001
        c = {}
    degisiklikler = [{"alan": str(x.get("alan") or "antrenman")[:16], "ne": str(x.get("ne") or "")[:240], "neden": str(x.get("neden") or "")[:240]}
                     for x in c.get("degisiklikler") or [] if x.get("ne")] or kural
    karar = c.get("karar") if c.get("karar") in ("devam", "guncelle") else ("guncelle" if degisiklikler else "devam")
    if karar == "devam" and not c.get("degisiklikler"):
        degisiklikler = [x for x in degisiklikler if x.get("alan") == "toparlanma"]   # devamda yalnız güvenlik notları kalır
    a = c.get("ayarlar") if isinstance(c.get("ayarlar"), dict) else {}
    uygulanan = {}
    p = pt.profil()
    dk = a.get("gunluk_dk", ayar.get("gunluk_dk"))
    if dk is not None:
        v = pt.sayi(dk, 10, 90)
        if v and int(v) != int(p.get("gunluk_dk") or 0):
            uygulanan["gunluk_dk"] = int(v)
    gs = a.get("gun_sayisi", ayar.get("gun_sayisi"))
    if gs is not None:
        v = pt.sayi(gs, 2, 7)
        if v and int(v) != len(p.get("gunler") or []):
            uygulanan["gun_sayisi"] = int(v)
    kh = a.get("kilo_hizi", ayar.get("kilo_hizi"))
    if kh is not None:
        v = pt.sayi(kh, 0.2, 0.7)
        if v and abs(float(v) - float((p.get("beslenme") or {}).get("kilo_hizi") or 0.5)) >= 0.05:
            uygulanan["kilo_hizi"] = round(float(v), 2)
    if karar == "devam":
        uygulanan = {}
    plan_istegi = str(c.get("plan_istegi") or "")[:300]
    if not plan_istegi and karar == "guncelle":
        plan_istegi = " ".join(x["ne"] for x in degisiklikler if x.get("alan") in ("antrenman", "toparlanma"))[:300]
    hedef_notu = str(c.get("hedef_notu") or "")[:300]
    if not hedef_notu:
        H = pt_hedef.aktif()
        geride = [h["metin"] for h in H if h.get("yolda") == "geride"]
        hedef_notu = ("Geride kalan: " + "; ".join(geride) + ".") if geride else ("Hedefler yolunda." if H else "")
    sonuc = {"karar": karar, "ozet": str(c.get("ozet") or "")[:600] or _kural_ozet(r), "degisiklikler": degisiklikler, "uygulanan": uygulanan,
             "plan_istegi": plan_istegi, "hedef_notu": hedef_notu,
             "sonraki": str(c.get("sonraki") or "")[:300] or f"{KONTROL_ARALIK} gün sonra uyum, zorluk, ağrı ve kilo trendine yeniden bakarız.",
             "yazan": "claude" if c.get("karar") else "kural"}
    k.update(durum="bitti", cevaplar=cevaplar, sonuc=sonuc, bitis=int(time.time()))
    pt._yaz(yol, k)
    ek = {}
    if uygulanan.get("gunluk_dk"):
        ek["gunluk_dk"] = uygulanan["gunluk_dk"]
    if uygulanan.get("gun_sayisi"):
        g = list(p.get("gunler") or [0, 1, 2, 3, 4, 5, 6])
        n = uygulanan["gun_sayisi"]
        oncelik = [0, 2, 4, 5, 1, 3, 6]
        ek["gunler"] = sorted(g[:n] if len(g) >= n else sorted(set(g) | set(oncelik))[:n])
    if uygulanan.get("kilo_hizi") is not None:
        ek["beslenme"] = {**(p.get("beslenme") or {}), "kilo_hizi": uygulanan["kilo_hizi"]}
    ek["kontrol_istegi"] = plan_istegi if karar == "guncelle" else ""
    ek["son_kontrol"] = k["tarih"]
    pt.profil_kaydet(ek)
    return k


def _kural_ozet(r):
    u = f"%{round(r['uyum'] * 100)}" if r.get("uyum") is not None else "-"
    return (f"{r['gun']} günde {r['yapilan_seans']} antrenman ({r['planlanan_seans']} planlanmıştı, uyum {u}), toplam {r['toplam_dk']} dakika. "
            + (f"Seans zorluğu ortalama {r['zorluk_ort']}/10. " if r.get("zorluk_ort") else "")
            + (f"Kilo trendi {r['kilo_degisim']:+g} kg." if r.get("kilo_degisim") is not None else ""))


def gecmis():
    return [{k: v for k, v in x.items() if k != "rapor"} | {"rapor_ozet": _kural_ozet(x["rapor"]) if x.get("rapor") else ""} for x in _kontroller()]


def ozet():
    z = zamani()
    d = pt._json(DEGERLENDIRME, {})
    return {"kontrol": {k: v for k, v in z.items() if k != "son"} | {"son": {kk: vv for kk, vv in (z.get("son") or {}).items() if kk in ("tarih", "sonuc")} if z.get("son") else None},
            "degerlendirme": {"var": bool(d.get("mesaj")), "okundu": bool(d.get("okundu")), "eski": bool(d.get("mesaj")) and d.get("imza") != _imza(pt.profil()),
                              "mesaj": d.get("mesaj"), "antrenman": (d.get("antrenman") or {}).get("yaklasim"), "beslenme": (d.get("beslenme") or {}).get("yaklasim")}}


if __name__ == "__main__":
    print(json.dumps({"zamani": zamani(), "rapor": rapor()}, ensure_ascii=False, indent=1, default=str))

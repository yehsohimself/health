"""pt.py - PT (Trainer): kişisel antrenör + diyetisyen çekirdeği (2026-10-25). Site uçları pt_site.py, sayfa static/pt.html (port 8771).

Araştırma: reports/PT özellik araştırması.md. İlke: uzmanların döngüsü (tarama → başlangıç testleri → plan → sabah kontrolü → seans → ağrı →
haftalık koç mesajı). Kurallar KODDA ve görünür (ilerleme, sabah uyarlaması, ağrı izleme); Claude planı bu kuralların verdiği hedeflerle yazar ve
her değişikliği sade dille açıklar. Teşhis koymaz; uyarı belirtilerinde durdurur ve doktora yönlendirir.

Veri pt/ (git dışı): profil.json, program/<hafta>.json (+ gecmis/), gunluk/<tarih>.json (sabah, seanslar, yemekler, kilo, bel, ağrı, bjj),
ilerleme.json (hareket başına durum + değişiklik kaydı), testler.json, mesajlar/<hafta>.json, hareketler/<kod>/ (kendi videolarınız).
"""
import datetime as dt
import json
import os
import re
import threading
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
VERI = KLASOR / "pt"
PROGRAM = VERI / "program"
GUNLUK = VERI / "gunluk"
MESAJLAR = VERI / "mesajlar"
HAREKETLER = VERI / "hareketler"
_kilit = threading.RLock()

# ----------------------------------------------------------------------------- yardımcılar


def _json(p, varsayilan=None):
    """Dosya yoksa varsayılan. Bozuksa (2026-10-28) önce `<ad>.bozuk-<zaman>` kopyası alınır: varsayılanla sonradan üzerine
    yazılsa da kayıt kaybolmaz."""
    p = Path(p)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001
        try:
            if p.exists() and p.stat().st_size and not list(p.parent.glob(p.name + ".bozuk-*")):
                import shutil
                shutil.copy2(p, p.with_name(f"{p.name}.bozuk-{int(time.time())}"))
                print(f"PT: bozuk kayıt yedeklendi: {p.name} ({type(e).__name__})", flush=True)
        except OSError:
            pass
    return {} if varsayilan is None else varsayilan


def _yaz(p, d):
    """Atomik yazım; geçici dosya adı her yazımda tekil (iki yazıcı aynı .yeni dosyasında çakışmasın)."""
    import tempfile
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, ad = tempfile.mkstemp(prefix=p.name + ".", suffix=".yeni", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False, indent=1))
        os.replace(ad, p)
    except BaseException:
        try:
            os.unlink(ad)
        except OSError:
            pass
        raise


def bugun():
    return dt.date.today()


def hafta_kodu(g=None):
    y, w, _ = (g or bugun()).isocalendar()
    return f"{y}-W{w:02d}"


def hafta_gunleri(kod):
    y, w = kod.split("-W")
    pzt = dt.date.fromisocalendar(int(y), int(w), 1)
    return [pzt + dt.timedelta(days=i) for i in range(7)]


GUN_AD = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# ----------------------------------------------------------------------------- katalog
# (kod, ad, tür, ölçü: tekrar|sure, ekipman, bölgeler, zincir, basamak, kısa açıklama)
# Zincir = ilerleme basamakları (kolay → zor). Ekipman: yok | bar | paralel | halka | kettlebell | bant | mat | duvar.
KATALOG_HAM = [
    # itme
    ("duvar_sinav", "Duvar şınavı", "kalistenik", "tekrar", "duvar", "omuz,bilek", "itme", 1, "Eller duvarda, gövde düz."),
    ("egimli_sinav", "Eğimli şınav", "kalistenik", "tekrar", "yok", "omuz,bilek", "itme", 2, "Eller sehpa ya da bankta."),
    ("sinav", "Şınav", "kalistenik", "tekrar", "yok", "omuz,bilek,dirsek", "itme", 3, "Göğüs yere yaklaşana kadar, dirsekler 45°."),
    ("elmas_sinav", "Elmas şınav", "kalistenik", "tekrar", "yok", "dirsek,bilek", "itme", 4, "Eller göğüs altında birleşik."),
    ("yaslanan_sinav", "Öne yaslanan şınav", "kalistenik", "tekrar", "yok", "omuz,bilek", "itme", 5, "Omuzlar ellerin önünde (planche hazırlığı)."),
    ("arcer_sinav", "Okçu şınavı", "kalistenik", "tekrar", "yok", "omuz,dirsek", "itme", 6, "Bir kol bükülür, öbürü yana açık."),
    ("tek_kol_sinav", "Tek kol şınav", "kalistenik", "tekrar", "yok", "omuz,dirsek,bilek", "itme", 7, "Ayaklar açık, kalça dönmeden."),
    ("destek_tutus", "Paralelde destek", "kalistenik", "sure", "paralel", "omuz,dirsek", "dips", 1, "Kollar düz, omuzlar aşağıda."),
    ("negatif_dips", "Negatif dips", "kalistenik", "tekrar", "paralel", "omuz,dirsek", "dips", 2, "3-5 sn'de yavaş iniş."),
    ("dips", "Dips", "kalistenik", "tekrar", "paralel", "omuz,dirsek", "dips", 3, "Omuz dirsek hizasına inene kadar."),
    ("pike_sinav", "Pike şınav", "kalistenik", "tekrar", "yok", "omuz,bilek", "amut_itme", 1, "Kalça yukarıda, baş ellerin önüne."),
    ("yuksek_pike_sinav", "Ayak yüksekte pike şınav", "kalistenik", "tekrar", "yok", "omuz,bilek", "amut_itme", 2, "Ayaklar sandalyede."),
    ("duvar_amut_sinav", "Duvarda amut şınavı", "kalistenik", "tekrar", "duvar", "omuz,boyun,bilek", "amut_itme", 3, "Baş yere hafifçe değer."),
    # çekme
    ("ters_kurek", "Ters kürek", "kalistenik", "tekrar", "bar", "sirt,dirsek", "cekme", 1, "Alçak bar ya da masa; göğüs bara."),
    ("aktif_asilma", "Aktif asılma", "kalistenik", "sure", "bar", "omuz,el", "cekme", 2, "Omuzları kulaklardan uzaklaştır."),
    ("kurek_cekis", "Kürek kemiği çekişi", "kalistenik", "tekrar", "bar", "omuz,sirt", "cekme", 3, "Kollar düz, yalnızca omuzlar."),
    ("negatif_barfiks", "Negatif barfiks", "kalistenik", "tekrar", "bar", "dirsek,omuz", "cekme", 4, "Yukarıdan 3-5 sn'de iniş."),
    ("barfiks", "Barfiks", "kalistenik", "tekrar", "bar", "dirsek,omuz,sirt", "cekme", 5, "Çene barın üstüne, tam açılarak iniş."),
    ("gogse_barfiks", "Göğse barfiks", "kalistenik", "tekrar", "bar", "dirsek,omuz", "cekme", 6, "Göğüs bara değecek kadar patlayıcı."),
    ("arcer_barfiks", "Okçu barfiksi", "kalistenik", "tekrar", "bar", "dirsek,omuz", "cekme", 7, "Bir kol düz kalır."),
    ("muscle_up", "Muscle-up", "kalistenik", "tekrar", "bar", "dirsek,omuz,bilek", "cekme", 8, "Barın üstüne geçiş."),
    ("tuck_front_lever", "Toplu front lever", "kalistenik", "sure", "bar", "omuz,sirt", "front_lever", 1, "Dizler göğüste, sırt yere paralel."),
    ("adv_tuck_front_lever", "Açık toplu front lever", "kalistenik", "sure", "bar", "omuz,sirt", "front_lever", 2, "Sırt düz, dizler 90°."),
    # bacak ve kalça
    ("sandalye_kalkis", "Sandalyeden kalkış", "kalistenik", "tekrar", "yok", "diz,kalca", "bacak", 1, "Elleri kullanmadan."),
    ("squat", "Squat", "kalistenik", "tekrar", "yok", "diz,kalca", "bacak", 2, "Topuklar yerde, kalça diz hizasının altına."),
    ("bulgar_squat", "Bulgar squat", "kalistenik", "tekrar", "yok", "diz,kalca", "bacak", 3, "Arka ayak sandalyede."),
    ("karides_squat", "Karides squat", "kalistenik", "tekrar", "yok", "diz,kalca,ayak_bilegi", "bacak", 4, "Arka ayak elde, diz yere."),
    ("pistol", "Pistol squat", "kalistenik", "tekrar", "yok", "diz,kalca,ayak_bilegi", "bacak", 5, "Tek bacak, öbürü önde düz."),
    ("kalca_kopru", "Kalça köprüsü", "kalistenik", "tekrar", "yok", "kalca,bel", "kalca", 1, "Kalçayı sık, bel boşta değil."),
    ("tek_kalca_kopru", "Tek bacak kalça köprüsü", "kalistenik", "tekrar", "yok", "kalca,bel", "kalca", 2, "Kalça düz kalsın."),
    ("nordic_negatif", "Nordic negatif", "kalistenik", "tekrar", "yok", "diz,kalca", "kalca", 3, "Ayaklar sabit, yavaş öne düşüş."),
    ("kb_swing", "Kettlebell swing", "kalistenik", "tekrar", "kettlebell", "kalca,bel", "kalca_kb", 1, "Kalçadan itiş, kollar ip gibi."),
    ("baldir", "Tek bacak baldır kaldırma", "kalistenik", "tekrar", "yok", "ayak_bilegi", "baldir", 1, "Basamakta tam açıklık."),
    # gövde
    ("dead_bug", "Dead bug", "kalistenik", "tekrar", "mat", "bel", "govde", 1, "Bel yere yapışık."),
    ("tuck_hollow", "Toplu hollow tutuş", "kalistenik", "sure", "mat", "bel", "govde", 2, "Dizler göğse yakın, bel yerde."),
    ("hollow", "Hollow tutuş", "kalistenik", "sure", "mat", "bel", "govde", 3, "Kollar ve bacaklar uzun, bel yerde."),
    ("plank", "Plank", "kalistenik", "sure", "mat", "omuz,bel", "plank", 1, "Kalça ne yukarıda ne aşağıda."),
    ("yan_plank", "Yan plank", "kalistenik", "sure", "mat", "omuz,bel", "plank", 2, "Her iki yan."),
    ("diz_kaldirma", "Asılı diz kaldırma", "kalistenik", "tekrar", "bar", "bel,omuz", "asili_govde", 1, "Sallanmadan."),
    ("bacak_kaldirma", "Asılı bacak kaldırma", "kalistenik", "tekrar", "bar", "bel,omuz", "asili_govde", 2, "Bacaklar düz, en az yere paralel."),
    ("ayak_bara", "Ayaklar bara", "kalistenik", "tekrar", "bar", "bel,omuz", "asili_govde", 3, "Ayak uçları bara değer."),
    ("tuck_lsit", "Toplu L-sit", "kalistenik", "sure", "yok", "bilek,dirsek", "lsit", 1, "Yerde ya da paralelde, dizler göğüste."),
    ("lsit", "L-sit", "kalistenik", "sure", "yok", "bilek,dirsek", "lsit", 2, "Bacaklar düz, yere paralel."),
    # amut
    ("duvar_yuruyus", "Duvara yürüyüş", "kalistenik", "tekrar", "duvar", "omuz,bilek", "amut", 1, "Ayaklarla duvara tırman, eller duvara yaklaşır."),
    ("karin_duvar_amut", "Karın duvara amut", "kalistenik", "sure", "duvar", "omuz,bilek,boyun", "amut", 2, "Vücut düz çizgi."),
    ("amut_dengesi", "Duvardan uzaklaşma (amut dengesi)", "kalistenik", "sure", "duvar", "omuz,bilek", "amut", 3, "Bir ayak, sonra iki ayak duvardan çekilir."),
    ("serbest_amut", "Serbest amut", "kalistenik", "sure", "yok", "omuz,bilek", "amut", 4, "Parmaklarla denge."),
    # BJJ solo
    ("karides", "Karides (shrimp)", "bjj", "tekrar", "mat", "bel,kalca", "bjj_kacis", 1, "Kalçayı geri it, omuz üstünde dön."),
    ("ters_karides", "Ters karides", "bjj", "tekrar", "mat", "bel,kalca", "bjj_kacis", 2, "Baş yönüne kayış."),
    ("kopru_upa", "Köprü (upa)", "bjj", "tekrar", "mat", "boyun,bel", "bjj_kacis", 1, "Omuz üstüne köprü ve dönüş."),
    ("teknik_kalkis", "Teknik ayağa kalkış", "bjj", "tekrar", "yok", "diz,kalca", "bjj_ayakta", 1, "El ve ayak tabanından geriye kalkış."),
    ("sit_out", "Sit-out", "bjj", "tekrar", "mat", "omuz,kalca", "bjj_ayakta", 2, "Dört ayaktan bacağı alttan geçir."),
    ("sprawl", "Sprawl", "bjj", "tekrar", "yok", "kalca,bel", "bjj_ayakta", 2, "Kalçayı yere at, bacaklar geride."),
    ("granby", "Granby rulo", "bjj", "tekrar", "mat", "boyun,omuz", "bjj_rulo", 2, "Omuz üstünden, başa yük bindirmeden."),
    ("one_rulo", "Omuz rulosu", "bjj", "tekrar", "mat", "omuz,boyun", "bjj_rulo", 1, "Çapraz omuzdan yuvarlan."),
    ("kalca_degistirme", "Kalça değiştirme (hip switch)", "bjj", "tekrar", "mat", "kalca", "bjj_kacis", 2, "Otururken kalçayı sağa sola çevir."),
    ("bacak_pummel", "Bacak pummel", "bjj", "sure", "mat", "kalca,diz", "bjj_guard", 1, "Sırt üstü, bacaklarla guard çevirme."),
    ("golge_pas", "Gölge guard geçişi", "bjj", "sure", "yok", "diz,kalca", "bjj_guard", 2, "Hayali guard'ı geçiş akışları."),
    ("golge_gures", "Gölge güreşi", "bjj", "sure", "yok", "kalca,diz", "bjj_akis", 3, "Kalkış, sprawl, karides zinciri."),
    # animal flow
    ("beast", "Beast tutuşu", "flow", "sure", "yok", "bilek,omuz", "flow", 1, "Dizler yerden iki parmak."),
    ("crab", "Crab tutuşu", "flow", "sure", "yok", "bilek,omuz", "flow", 1, "Kalça yukarıda, ters masa."),
    ("ape", "Ape yürüyüşü", "flow", "tekrar", "yok", "kalca,bilek", "flow", 1, "Derin çömelmeden yana geçiş."),
    ("underswitch", "Underswitch", "flow", "tekrar", "yok", "omuz,kalca", "flow", 2, "Beast'ten crab'a alttan geçiş."),
    ("side_kickthrough", "Side kick-through", "flow", "tekrar", "yok", "omuz,kalca", "flow", 2, "Beast'ten bacağı alttan uzat."),
    ("scorpion_reach", "Scorpion reach", "flow", "tekrar", "yok", "bel,omuz", "flow", 2, "Beast'te bacağı çaprazdan geriye uzat."),
    ("front_step", "Front step", "flow", "tekrar", "yok", "kalca,omuz", "flow", 2, "Beast'ten ayağı elin dışına."),
    ("flow_zinciri", "Animal flow akışı", "flow", "sure", "yok", "omuz,bilek,kalca", "flow", 3, "Öğrenilen geçişlerle serbest akış."),
    # mobilite ve ısınma
    ("kedi_inek", "Kedi-inek", "mobilite", "tekrar", "mat", "bel", "mobilite", 1, "Omurgayı yavaşça kıvır ve aç."),
    ("dunya_esneme", "Dünyanın en iyi esnemesi", "mobilite", "tekrar", "yok", "kalca,sirt", "mobilite", 1, "Lunge, dirsek yere, göğüs dönüşü."),
    ("derin_squat_tutus", "Derin squat tutuşu", "mobilite", "sure", "yok", "kalca,diz,ayak_bilegi", "mobilite", 1, "Topuklar yerde, göğüs dik."),
    ("kalca_9090", "90/90 kalça geçişi", "mobilite", "tekrar", "mat", "kalca", "mobilite", 1, "Elsiz dizleri yandan yana çevir."),
    ("gogus_donus", "Göğüs omurgası dönüşü", "mobilite", "tekrar", "mat", "sirt", "mobilite", 1, "Yan yatarak kolu aç."),
    ("bilek_hazirlik", "Bilek hazırlığı", "mobilite", "tekrar", "yok", "bilek", "mobilite", 1, "Dört yöne parmaklar, hafif ağırlık."),
    ("omuz_cevirme", "Omuz çevirme (sopa/bant)", "mobilite", "tekrar", "bant", "omuz", "mobilite", 1, "Geniş tutuşla öne arkaya."),
    ("kanepe_esneme", "Kanepe esnemesi", "mobilite", "sure", "yok", "kalca,diz", "mobilite", 1, "Arka diz duvar dibinde, kalça önde."),
    ("boyun_hazirlik", "Boyun hazırlığı", "mobilite", "tekrar", "yok", "boyun", "mobilite", 1, "Yavaş daireler ve izometrik baskı."),
    ("jumping_jack", "Jumping jack", "isinma", "sure", "yok", "ayak_bilegi", "isinma", 1, "Hafif tempoda."),
    ("ip_atlama", "İp atlama", "isinma", "sure", "ip", "ayak_bilegi", "isinma", 1, "Ayak uçlarında, alçak sıçrama."),
    # denge (2026-10-31, uzun ömür katmanı): güç seanslarının kapanışına, haftada üç gün
    ("tek_ayak_denge", "Tek ayak denge", "mobilite", "sure", "yok", "ayak_bilegi,kalca", "denge", 1, "Bir ayak üstünde, kalça düz; kolaylaşınca gözler kapalı."),
    ("yere_otur_kalk", "Yere oturup kalkma", "mobilite", "tekrar", "yok", "kalca,diz", "denge", 2, "Bağdaş kurup oturun, kalkın; olabildiğince elsiz."),
]
KATALOG = {k: {"kod": k, "ad": a, "tur": t, "olcu": o, "ekipman": e, "bolge": b.split(","), "zincir": z, "basamak": s, "aciklama": ac}
           for k, a, t, o, e, b, z, s, ac in KATALOG_HAM}

EKIPMANLAR = {"bisiklet": "Bisiklet", "bar": "Barfiks demiri", "paralel": "Paralel bar / dips", "halka": "Jimnastik halkası",
              "kettlebell": "Kettlebell", "bant": "Direnç bandı", "mat": "Mat", "ip": "Atlama ipi", "bjj_manken": "BJJ mankeni",
              "trainer": "Bisiklet trainer'ı (evde)"}
YONTEMLER = {"kalistenik": "Kalistenik", "bjj_solo": "Solo BJJ drill", "bjj_ders": "BJJ dersi", "flow": "Animal flow", "bisiklet": "Bisiklet",
             "mobilite": "Mobilite", "kardiyo": "Yürüyüş ve koşu"}
BOLGELER = {"boyun": "Boyun", "omuz": "Omuz", "dirsek": "Dirsek", "bilek": "Bilek", "el": "El/parmak", "sirt": "Sırt", "bel": "Bel",
            "kalca": "Kalça", "diz": "Diz", "ayak_bilegi": "Ayak bileği"}
BJJ_POZISYONLAR = ["Guard", "Yan kontrol", "Diz üstü", "Mount", "Arkadan kontrol", "Kaplumbağa"]
BJJ_BITIRISLER = ["Kol kilidi", "Kimura", "Americana", "Üçgen", "Arkadan boğma", "Guillotine", "Ezekiel", "Ayak kilidi", "Omoplata", "Kafa-kol"]


def katalog():
    """Yerleşik hareketler + kendi eklediğiniz hareketler (videosu olanlar 'video' alanıyla)."""
    k = {x: dict(v) for x, v in KATALOG.items()}
    for p in HAREKETLER.glob("*/bilgi.json"):
        b = _json(p, {})
        kod = b.get("kod") or p.parent.name
        h = k.get(kod) or {"kod": kod, "ad": b.get("ad") or kod, "tur": b.get("tur") or "kalistenik", "olcu": b.get("olcu") or "tekrar",
                           "ekipman": b.get("ekipman") or "yok", "bolge": b.get("bolge") or [], "zincir": b.get("zincir") or "", "basamak": b.get("basamak") or 0,
                           "aciklama": b.get("aciklama") or "", "kendi": True}
        if (p.parent / "video.mp4").exists():
            h["video"] = f"/pt-hareket/{kod}/video.mp4"
            h["kapak"] = f"/pt-hareket/{kod}/kapak.jpg"
            h["video_zaman"] = int((p.parent / "video.mp4").stat().st_mtime)
        for a in ("ad", "aciklama", "ipuclari", "pozisyon"):
            if b.get(a):
                h[a] = b[a]
        k[kod] = h
    for kod, h in k.items():                                   # kendi videosu yoksa yapay zekâ animasyonu (pt_medya)
        if not h.get("video") and (KLASOR / "pt_medya" / kod / "video.mp4").exists() and not (KLASOR / "pt_medya" / kod / "k1.jpg").exists():
            h["video"] = f"/pt-medya/{kod}/video.mp4"
            h["kapak"] = f"/pt-medya/{kod}/kapak.jpg"
            h["video_zaman"] = int((KLASOR / "pt_medya" / kod / "video.mp4").stat().st_mtime)
            h["ornek"] = True
    return k


def zincir_komsu(kod, yon, kat=None):
    """Aynı zincirde bir alt (yon=-1) ya da üst (yon=1) basamak."""
    kat = kat or katalog()
    h = kat.get(kod)
    if not h or not h.get("zincir"):
        return None
    adaylar = sorted([x for x in kat.values() if x.get("zincir") == h["zincir"]], key=lambda x: x.get("basamak") or 0)
    i = next((n for n, x in enumerate(adaylar) if x["kod"] == kod), None)
    if i is None:
        return None
    j = i + yon
    return adaylar[j]["kod"] if 0 <= j < len(adaylar) else None


def ekipmansiz_karsilik(kod, var_olan, kat=None):
    """Yolda/parkta ekipman yoksa aynı zincirde ya da aynı türde ekipmansız bir hareket."""
    kat = kat or katalog()
    h = kat.get(kod)
    if not h or h["ekipman"] in ("yok", "mat", "duvar") or h["ekipman"] in var_olan:
        return kod
    for x in sorted(kat.values(), key=lambda x: -(x.get("basamak") or 0)):
        if x.get("zincir") == h.get("zincir") and x["ekipman"] in ("yok", "mat", "duvar"):
            return x["kod"]
    yedek = {"cekme": "kalca_kopru", "dips": "elmas_sinav", "asili_govde": "hollow", "front_lever": "hollow", "kalca_kb": "tek_kalca_kopru",
             "isinma": "jumping_jack"}
    return yedek.get(h.get("zincir"), "plank")

# ----------------------------------------------------------------------------- profil ve tarama

PROFIL_VARSAYILAN = {
    "ad": "", "cinsiyet": "erkek", "dogum_tarihi": "", "yas": None, "boy_cm": None, "kilo_kg": None, "hedef_kilo_kg": None, "hedef_tarih": "",
    "hedefler": [], "beceri_hedefleri": [], "neden": "", "hedef_turleri": [], "deneyim": "", "motivasyon": "", "diyet": "",
    "ek_bilgi": [], "notlar": [], "gun_duzeni": {}, "beslenme_aliskanlik": {}, "saglik_degerleri": [], "aliskanlik": {}, "ara_cevaplar": {}, "program_aktif": None, "program_biten": [],
    "gorusmeler": {}, "kontrol_istegi": "", "son_kontrol": "", "sevdikleri": [], "kardiyo_tur": "yuruyus",
    "yontemler": {"kalistenik": 2, "bjj_solo": 1, "flow": 1, "bisiklet": 1, "mobilite": 1},
    "bjj_ders": {"gunler": [], "saat": "", "sure_dk": 90},
    "ekipman": ["bisiklet", "bar", "mat"], "gunler": [0, 1, 2, 3, 4, 5, 6], "gunluk_dk": 45, "antrenman_saati": "sabah",
    "sinirlar": [], "sakatliklar": [], "yapamadiklarim": [],
    "beslenme": {"pencere_bas": "12:00", "pencere_saat": 6, "hassasiyetler": [], "sevmedikleri": [], "mutfak": "Türk ev yemekleri",
                 "ogun_sayisi": 2, "kilo_hizi": 0.7},
    "konum": {"ad": "", "lat": None, "lon": None},
    "tarama": {}, "tarama_tarih": "", "doktor_onayi": False,
    "kuruldu": False,
}

TARAMA_SORULARI = [
    ("kalp", "Bir doktor size kalp rahatsızlığı ya da yüksek tansiyon olduğunu söyledi mi?"),
    ("gogus", "Dinlenirken, günlük işlerde ya da spor yaparken göğsünüzde ağrı hissediyor musunuz?"),
    ("bas_donmesi", "Son 12 ayda baş dönmesiyle dengenizi kaybettiniz mi ya da bayıldınız mı?"),
    ("kronik", "Kalp ve tansiyon dışında, doktorun koyduğu süregelen bir hastalığınız var mı (şeker, böbrek, astım gibi)?"),
    ("ilac", "Süregelen bir hastalık için ilaç kullanıyor musunuz?"),
    ("kemik_eklem", "Spor yapınca kötüleşebilecek bir kemik, eklem ya da yumuşak doku sorununuz var mı (son 12 ay)?"),
    ("gozetim", "Bir doktor yalnızca gözetim altında spor yapmanızı söyledi mi?"),
]

UYARI_BELIRTILERI = [
    "Göğüste, boyunda, çenede ya da kolda baskı, sıkışma, yanma ya da ağırlık hissi",
    "Nefes darlığının olağandan çok daha ağır olması, dinlenince geçmemesi",
    "Baş dönmesi, bayılma hissi, ani şiddetli baş ağrısı",
    "Kola ya da bacağa yayılan uyuşma, karıncalanma, güç kaybı",
    "Eklemde şişlikle birlikte keskin ağrı, kilitlenme ya da boşalma hissi",
    "Düşme ya da darbeden sonra hareket ettirememe",
]


def market_notu(p=None):
    """Yemek istemleri için malzeme kaynağı: profildeki konumdan (2026-10-29; açık depoda herkes için, eskiden sabit 'Berlin marketleri')."""
    ad = ((p or profil()).get("konum") or {}).get("ad") or ""
    return f"{ad} çevresindeki sıradan marketlerde bulunan malzemeler" if ad else "sıradan bir markette bulunan malzemeler"


def yas_hesapla(dogum):
    """Doğum tarihinden bugünkü yaş (yaş saklanmaz; her okumada güncel)."""
    try:
        d, b = dt.date.fromisoformat(str(dogum)[:10]), bugun()
        return b.year - d.year - ((b.month, b.day) < (d.month, d.day))
    except ValueError:
        return None


def profil():
    p = {**PROFIL_VARSAYILAN, **_json(VERI / "profil.json", {})}
    p["beslenme"] = {**PROFIL_VARSAYILAN["beslenme"], **(p.get("beslenme") or {})}
    if p.get("dogum_tarihi"):
        p["yas"] = yas_hesapla(p["dogum_tarihi"])
    return p


def profil_kaydet(ek):
    with _kilit:
        p = profil()
        for k, v in (ek or {}).items():
            if k == "beslenme" and isinstance(v, dict):
                p["beslenme"] = {**p["beslenme"], **v}
            elif k in PROFIL_VARSAYILAN or k in ("guncelleme",):
                p[k] = v
        p["guncelleme"] = int(time.time())
        if p.get("dogum_tarihi"):
            p.pop("yas", None)                                 # yaş doğum tarihinden her okumada hesaplanır
        _yaz(VERI / "profil.json", p)
        return p


def tarama_durumu(p=None):
    """PAR-Q+ mantığı (ACSM 2015 karar şeması): 'evet' cevabı otomatik yasak değil ama plan doktor onayına kadar bekler."""
    p = p or profil()
    evetler = [k for k, _ in TARAMA_SORULARI if (p.get("tarama") or {}).get(k)]
    eski = False
    if p.get("tarama_tarih"):
        try:
            eski = (bugun() - dt.date.fromisoformat(p["tarama_tarih"])).days > 365
        except ValueError:
            eski = True
    return {"yapildi": bool(p.get("tarama_tarih")), "evetler": evetler, "bekliyor": bool(evetler) and not p.get("doktor_onayi"),
            "eski": eski}


TANISMA_ISTEM = """Sen PT'sin: kişisel antrenör + diyetisyen. Kullanıcı kendini serbestçe anlattı. Anlattığından profil alanlarını çıkar.
Yalnızca SÖYLENENİ yaz; söylenmeyen alanı boş bırak (tahmin etme). Türkçe yaz.

KULLANICININ ANLATTIĞI:
{metin}

ŞU ANKİ PROFİL (doluysa koru, yenisi söylendiyse değiştir):
{profil}

Alanlar ve izin verilen değerler:
- ad, cinsiyet (erkek|kadin), dogum_tarihi (YYYY-MM-DD; yalnız tarih söylendiyse), yas (sayı), boy_cm, kilo_kg, hedef_kilo_kg, hedef_tarih (YYYY-MM-DD)
- hedefler: kısa cümleler listesi ("3 ayda 5 kilo vermek", "muscle-up")
- beceri_hedefleri: şu kodlardan: {beceriler}
- neden: neden istediği (tek cümle)
- yontemler: haftada kaç seans {{kalistenik, bjj_solo, flow, bisiklet, mobilite}} (sayı)
- bjj_ders: {{gunler: [0=Pazartesi..6=Pazar], saat: "19:00", sure_dk}} (salonda ders varsa)
- ekipman: şu kodlardan: {ekipman}
- gunler: antrenman yapabileceği günler [0..6], gunluk_dk: günde ayırabileceği dakika, antrenman_saati: sabah|ogle|aksam
- sakatliklar: ["sol diz menisküs, derin çömelme ağrıtıyor"] gibi; yapamadiklarim: ["koşu"] gibi; sinirlar: diğer
- beslenme: {{pencere_bas: "12:00", pencere_saat: 6 (18/6 için), hassasiyetler: ["laktoz"], sevmedikleri: [], mutfak, ogun_sayisi}}
- konum: {{ad: "Kreuzberg, Berlin"}} (bisiklet rotası için semt)

JSON döndür: {{"profil": {{...yalnızca çıkarılan alanlar...}}, "eksik": ["sorulması gereken en önemli en çok 4 şey, soru cümlesi olarak"],
"ozet": "anladığını 2 cümleyle, 'siz' diliyle"}}"""


def tanisma_coz(metin):
    import claude_yaz
    p = profil()
    beceriler = ", ".join(sorted({x["zincir"] for x in KATALOG.values() if x["tur"] == "kalistenik"} | {"muscle_up", "serbest_amut", "pistol", "front_lever", "tek_kol_sinav"}))
    gorunen = {k: p.get(k) for k in PROFIL_VARSAYILAN if k not in ("tarama", "tarama_tarih", "doktor_onayi", "kuruldu")}
    c = claude_yaz.sor_json(TANISMA_ISTEM.format(metin=metin[:6000], profil=json.dumps(gorunen, ensure_ascii=False),
                                                 beceriler=beceriler, ekipman=", ".join(EKIPMANLAR)), model_adi="sonnet")
    ek = c.get("profil") or {}
    ek = {k: v for k, v in ek.items() if k in PROFIL_VARSAYILAN and v not in (None, "", [], {})}
    if ek.get("ekipman"):
        ek["ekipman"] = [x for x in ek["ekipman"] if x in EKIPMANLAR]
    return {"profil": ek, "eksik": c.get("eksik") or [], "ozet": c.get("ozet") or ""}

EK_SORU_ISTEM = """Sen PT'sin: kişisel antrenör + diyetisyen + fizyoterapist bilgisiyle çalışıyorsun. Kullanıcı tanışma sorularını seçeneklerle cevapladı,
bazı yerlere kendi notunu yazdı. Türkçe, "siz" dili.

CEVAPLAR (profil):
{profil}

KULLANICININ NOTLARI (hangi soruda yazdığıyla):
{notlar}

ZATEN SORULAN SORULAR (bunları ya da aynı konuyu bir daha SORMA; cevabı "yok/boş" olsa bile cevaplanmış sayılır):
{sorulanlar}

İki iş:
1) Notlarda geçen bilgileri profil alanlarına çevir (yalnızca SÖYLENENİ; tahmin yok). Alanlar: hedefler (YALNIZ amaçlar; hastalık, kolesterol gibi
   sağlık durumları hedef değildir, sinirlar'a yaz), sakatliklar, yapamadiklarim,
   sinirlar, beslenme {{hassasiyetler, sevmedikleri}}, bjj_ders {{gunler [0=Pzt..6=Paz], saat, sure_dk}}, ekipman (kodlar: {ekipman}), konum {{ad}}.
2) İyi bir antrenör ve diyetisyenin ilk görüşmede MUTLAKA soracağı ama henüz cevaplanmamış en önemli 2-4 soruyu seç. Program ve beslenmeyi gerçekten
   değiştirecek sorular olsun (ör. ağrının hangi harekette olduğu, BJJ kuşağı/kaç yıldır, bisiklet türü ve alışık olduğu mesafe, iş gün içinde ayakta mı
   masa başında mı, uyku düzeni, gün içinde ne yediği, alkol, daha önce denediği ve bıraktığı şeyler). Cevaplanmış şeyi tekrar sorma.
   Her soru TEK bir konuyu sorsun (iki şeyi bir soruda birleştirme). Seçenekli: 3-6 kısa seçenek (en çok 5 kelime); tek seçimli sorularda seçenekler
   birbirini dışlasın ve olası cevapların hepsini kapsasın; birden çok seçilebiliyorsa "coklu": true. "alt": neden sorduğun, tek kısa cümle.
   Başlangıç testinde ölçülecek şeyleri (kaç şınav/barfiks/dips) sorma; ilk hafta zaten test var.
   Seçenekler aynı genellik düzeyinde ve aynı biçimde olsun (hepsi kısa ad ya da hepsi kısa cümle; biri genel biri çok özel olmasın).

JSON: {{"profil": {{...}}, "sorular": [{{"soru": "...", "alt": "...", "coklu": false, "secenekler": ["...", "..."]}}]}}"""


def ek_sorular(p_ek=None, notlar=None, sorulanlar=None):
    """Tanışma soruları bitince: notları profile çevirir, cevaplanmamış en önemli 2-4 soruyu seçenekli olarak üretir (sonnet)."""
    import claude_yaz
    p = {**profil(), **(p_ek or {})}
    gorunen = {k: p.get(k) for k in PROFIL_VARSAYILAN if k not in ("tarama", "tarama_tarih", "doktor_onayi", "kuruldu", "notlar")}
    notlar = notlar if notlar is not None else p.get("notlar") or []
    c = claude_yaz.sor_json(EK_SORU_ISTEM.format(profil=json.dumps(gorunen, ensure_ascii=False), ekipman=", ".join(EKIPMANLAR),
                                                 notlar="\n".join(f"- ({n.get('soru')}) {n.get('metin')}" for n in notlar) or "yok",
                                                 sorulanlar="\n".join(f"- {s}" for s in (sorulanlar or [])[:60]) or "yok"),
                            model_adi="sonnet", zaman_asimi=300)
    ek = {k: v for k, v in (c.get("profil") or {}).items() if k in PROFIL_VARSAYILAN and v not in (None, "", [], {})}
    if ek.get("ekipman"):
        ek["ekipman"] = [x for x in ek["ekipman"] if x in EKIPMANLAR]
    sorular = []
    for s in (c.get("sorular") or [])[:4]:
        sec = [str(x)[:60] for x in s.get("secenekler") or [] if str(x).strip()][:6]
        if s.get("soru") and len(sec) >= 2:
            sorular.append({"soru": str(s["soru"])[:200], "alt": str(s.get("alt") or "")[:200], "coklu": bool(s.get("coklu")), "secenekler": sec})
    return {"profil": ek, "sorular": sorular}


# ----------------------------------------------------------------------------- günlük kayıt


HAFTA_RE = re.compile(r"\d{4}-W\d{2}")


def tarih_gecerli(t):
    """'YYYY-MM-DD' ise kendisi, değilse ValueError (2026-10-28: tarih ve hafta değerleri dosya yolu oluyor; '../profil' gibi
    değerler başka dosyalara yazdırabiliyordu)."""
    return dt.date.fromisoformat(str(t)[:10]).isoformat() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(t)) else _hata(t)


def hafta_gecerli(kod):
    if not HAFTA_RE.fullmatch(str(kod)):
        raise ValueError(f"Geçersiz hafta: {str(kod)[:20]}")
    return str(kod)


def _hata(t):
    raise ValueError(f"Geçersiz tarih: {str(t)[:20]}")


def sayi(v, en=None, ust=None, varsayilan=None):
    """Sonlu sayı (NaN/sonsuz değil), aralığa kırpılmış; olmazsa varsayılan."""
    import math
    try:
        f = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return varsayilan
    if not math.isfinite(f):
        return varsayilan
    if en is not None:
        f = max(en, f)
    if ust is not None:
        f = min(ust, f)
    return f


def _dk(v, varsayilan):
    """'45', 45, '45 dk' → 45 (Claude bazen birimle yazar)."""
    m = re.search(r"\d+", str(v or ""))
    return min(600, int(m.group())) if m else varsayilan


def gun_yolu(tarih):
    return GUNLUK / f"{tarih_gecerli(tarih)}.json"


def gun(tarih=None):
    tarih = tarih or bugun().isoformat()
    d = _json(gun_yolu(tarih), {})
    d.setdefault("tarih", tarih)
    for a in ("seanslar", "yemekler", "agri", "bjj"):
        d.setdefault(a, [])
    return d


def gun_degistir(tarih, fn):
    with _kilit:
        d = gun(tarih)
        fn(d)
        _yaz(gun_yolu(tarih), d)
        return d


def gunler(gun_sayisi=28):
    son = bugun()
    return [gun((son - dt.timedelta(days=i)).isoformat()) for i in range(gun_sayisi)]

# ----------------------------------------------------------------------------- başlangıç testleri

TESTLER = [
    ("sinav_max", "En fazla şınav", "tekrar", "sinav", "Göğüs yere yaklaşana kadar, tek seferde, temiz tekrar."),
    ("barfiks_max", "En fazla barfiks", "tekrar", "barfiks", "Kollar tam açık başlangıç. Hiç çıkamıyorsanız 0 yazın."),
    ("dips_max", "En fazla dips", "tekrar", "dips", "Paralel bar yoksa atlayın."),
    ("asilma_sn", "Barda asılı kalma", "sure", "aktif_asilma", "Bıraktığınız ana kadar saniye."),
    ("hollow_sn", "Hollow tutuş", "sure", "hollow", "Bel yerden kalkınca durun."),
    ("plank_sn", "Plank", "sure", "plank", "Kalça düşünce durun."),
    ("squat_max", "En fazla squat", "tekrar", "squat", "Tam derinlik, ara vermeden."),
    ("derin_squat", "Derin squat (topuklar yerde, 30 sn)", "secim", "derin_squat_tutus", "Rahat | Zor | Yapamıyorum"),
    ("omuz_duvar", "Duvarda kollar yukarı (bel duvardan ayrılmadan)", "secim", "", "Başparmaklar duvara değiyor | Değmiyor"),
    ("bel_cm", "Bel çevresi (göbek hizası)", "sayi", "", "Sabah, nefes verince."),
    ("dinlenme_nabzi", "Sabah dinlenme nabzı", "sayi", "", "Uyanınca, yataktan kalkmadan 60 sn."),
    ("tek_ayak_sn", "Tek ayak üstünde durma", "sure", "tek_ayak_denge", "Gözler açık, eller belde. Kaldırdığınız ayak yere değince durun; iki ayağın kısası. En çok 60 sn."),
    ("oturkalk", "Yere oturup kalkma", "secim", "yere_otur_kalk",
     "Ayakta başlayın, bağdaş kurup yere oturun, sonra kalkın. Elinizi, dizinizi ya da bir şeye tutunmayı sayın: her biri bir destek. || "
     "Hiç destek yok | Bir destek | İki destek | Üç-dört destek | Beş ve fazla"),
]


def testler():
    return _json(VERI / "testler.json", {"kayitlar": []})


def test_kaydet(sonuclar, tarih=None):
    with _kilit:
        t = testler()
        tarih = tarih or bugun().isoformat()
        once = next((x.get("sonuclar") or {} for x in t["kayitlar"] if x.get("tarih") == tarih), {})
        sonuclar = {**once, **sonuclar}                      # aynı gün parça parça yapılan testler birleşir
        if isinstance(sonuclar.get("oturkalk"), str):        # yere oturup kalkma: seçenek → 0-10 puan (göstergeler ve hedefler sayıyla çalışır)
            import pt_uzun
            if sonuclar["oturkalk"] in pt_uzun.OTURKALK:
                sonuclar["oturkalk_puan"] = pt_uzun.OTURKALK[sonuclar["oturkalk"]]
        t["kayitlar"] = [x for x in t["kayitlar"] if x.get("tarih") != tarih] + [{"tarih": tarih, "sonuclar": sonuclar}]
        t["kayitlar"].sort(key=lambda x: x["tarih"])
        _yaz(VERI / "testler.json", t)
    if sonuclar.get("bel_cm"):
        gun_degistir(tarih, lambda d: d.update(bel_cm=float(sonuclar["bel_cm"])))
    _testten_baslangic(sonuclar)
    return t


TEMEL_TESTLER = ("sinav_max", "squat_max", "hollow_sn", "plank_sn")


def test_eksikleri(gun=35):
    """Son `gun` günde yapılmamış temel testler (testler parça parça, farklı günlerde yapılabilir)."""
    yapilan = set()
    for x in testler().get("kayitlar") or []:
        try:
            if (bugun() - dt.date.fromisoformat(x["tarih"])).days < gun:
                yapilan |= set((x.get("sonuclar") or {}).keys())
        except (ValueError, KeyError):
            continue
    return [k for k in TEMEL_TESTLER if k not in yapilan]


def test_gerekli():
    """İlk kurulumda ya da son testten 5 hafta geçtiyse yeniden test (temel testlerden biri eksikse)."""
    return bool(test_eksikleri())

# ----------------------------------------------------------------------------- ilerleme kuralları (kodda; Claude açıklar)
# Çift ilerleme: hedef aralığın (ör. 3×6-10) üstüne bütün setlerde yedekte ≥1 tekrar kalarak ulaşınca → zincirde bir üst basamak (tekrar
# aralığın altına döner); üst basamak yoksa aralık 2 tekrar (süre için 5 sn) yükselir. Aralığın altında iki seans üst üste kalınca ya da o hareket
# sırasında ağrı >5 olunca → bir alt basamak. Her değişiklik `degisiklikler`'e yazılır ve geri alınabilir.

KURALLAR_METNI = [
    "Her harekette bir tekrar aralığı var (ör. 3 set 6-10). Bütün setlerde aralığın üstüne çıktığınızda ve zorlanma 8/10'u geçmediğinde bir sonraki basamağa geçersiniz.",
    "Üstünde basamak yoksa aralık 2 tekrar (tutuşlarda 5 saniye) yükselir.",
    "İki seans üst üste aralığın altında kalırsanız ya da hareket sırasında ağrı 5/10'u geçerse bir alt basamağa inersiniz.",
    "Sabah kontrolü sarıysa ana bölümde bir set azalır ve zorluk bir kademe düşer; kırmızıysa gün hareketlilik ya da kolay sürüşe döner.",
    "Ağrı kuralı: hareket sırasında ve sonrasında ağrı en çok 5/10, ertesi sabah eski düzeyine dönmeli, haftadan haftaya artmamalı. Bozulursa o bölgeyi yükleyen hareketler 7 gün kolay basamakta kalır.",
    "Her 5. hafta hafif haftadır: set sayısı yaklaşık üçte bir azalır, basamak değişmez.",
]
ARALIK_TEKRAR = (6, 10)
ARALIK_SURE = (15, 30)


def _did():
    return f"d{time.time_ns()}"


def ilerleme():
    return _json(VERI / "ilerleme.json", {"hareketler": {}, "degisiklikler": []})


def _ilerleme_yaz(d):
    _yaz(VERI / "ilerleme.json", d)


def hedef(kod, kat=None):
    """Hareketin şu anki hedefi: {set, alt, ust, olcu}."""
    kat = kat or katalog()
    h = kat.get(kod) or {}
    s = ilerleme()["hareketler"].get(kod) or {}
    alt, ust = s.get("aralik") or (ARALIK_SURE if h.get("olcu") == "sure" else ARALIK_TEKRAR)
    return {"set": s.get("set") or 3, "alt": alt, "ust": ust, "olcu": h.get("olcu") or "tekrar"}


def _testten_baslangic(sonuclar):
    """Başlangıç testinden zincirde doğru basamağı seç (ör. 0 barfiks → negatif barfiks; 12 şınav → şınav 3×6-10)."""
    with _kilit:
        il = ilerleme()
        H = il["hareketler"]
        def koy(zincir, kod, neden):
            if not any((KATALOG.get(k) or {}).get("zincir") == zincir and v.get("aktif") for k, v in H.items()):
                H.setdefault(kod, {})["aktif"] = True
                il["degisiklikler"].append({"t": int(time.time()), "id": _did(), "kod": kod, "tur": "baslangic", "neden": neden})
        def sayi(a):
            try:
                return float(sonuclar.get(a))
            except (TypeError, ValueError):
                return None
        s = sayi("sinav_max")
        if s is not None:
            koy("itme", "duvar_sinav" if s < 3 else "egimli_sinav" if s < 8 else "sinav" if s < 25 else "elmas_sinav", f"Testte {int(s)} şınav")
        b = sayi("barfiks_max")
        if b is not None:
            koy("cekme", "ters_kurek" if b == 0 and (sayi("asilma_sn") or 0) < 20 else "negatif_barfiks" if b < 3 else "barfiks" if b < 12 else "gogse_barfiks",
                f"Testte {int(b)} barfiks")
        q = sayi("squat_max")
        if q is not None:
            koy("bacak", "sandalye_kalkis" if q < 10 else "squat" if q < 30 else "bulgar_squat", f"Testte {int(q)} squat")
        hs = sayi("hollow_sn")
        if hs is not None:
            koy("govde", "dead_bug" if hs < 10 else "tuck_hollow" if hs < 25 else "hollow", f"Hollow {int(hs)} sn")
        d = sayi("dips_max")
        if d is not None:
            koy("dips", "destek_tutus" if d < 2 else "negatif_dips" if d < 6 else "dips", f"Testte {int(d)} dips")
        _ilerleme_yaz(il)


def aktif_basamak(zincir, kat=None):
    """Zincirde şu an çalışılan hareket (yoksa en kolay basamak)."""
    kat = kat or katalog()
    H = ilerleme()["hareketler"]
    aday = [k for k, v in H.items() if v.get("aktif") and (kat.get(k) or {}).get("zincir") == zincir]
    if aday:
        return aday[-1]
    zs = sorted([x for x in kat.values() if x.get("zincir") == zincir], key=lambda x: x.get("basamak") or 0)
    return zs[0]["kod"] if zs else None


def seans_sonrasi_ilerleme(seans):
    """Kaydedilen setlerden kuralları uygula; değişiklik listesini döndür (koç mesajı ve ekranda gösterilir)."""
    kat = katalog()
    degisen = []
    agrili = {a.get("bolge") for a in seans.get("agri") or [] if a.get("tur") != "kas" and sayi(a.get("puan"), 0, 10, 0) > 5}
    with _kilit:
        il = ilerleme()
        H = il["hareketler"]
        for h in seans.get("hareketler") or []:
            kod = h.get("kod")
            setler = [s for s in h.get("setler") or [] if s.get("deger") is not None]
            if not kod or kod not in kat or not setler:
                continue
            hd = hedef(kod, kat)
            st = H.setdefault(kod, {})
            zincir = kat[kod].get("zincir")
            aktif_kod = aktif_basamak(zincir, kat) if zincir else kod
            if seans.get("deneme", {}).get(kod) and aktif_kod != kod:          # beceri denemesi: bir üst basamakta hedefin altına inmeden yapıldıysa geç
                st["son"] = {"tarih": seans.get("tarih"), "setler": [s.get("deger") for s in setler], "deneme": True}
                if max(float(s["deger"]) for s in setler) >= hd["alt"]:
                    H.setdefault(aktif_kod, {})["aktif"] = False
                    st["aktif"] = True
                    kayit = {"t": int(time.time()), "id": _did(), "kod": aktif_kod, "yeni": kod, "tur": "basamak", "neden": "deneme seansında başarılı"}
                    il["degisiklikler"].append(kayit)
                    degisen.append({**kayit, "ad": kat[aktif_kod]["ad"], "yeni_ad": kat[kod]["ad"]})
                continue
            if zincir and kat[kod]["tur"] == "kalistenik" and aktif_kod != kod:   # ısınmada yapılan başka basamak: yalnız kaydedilir, basamağı değiştirmez
                st["son"] = {"tarih": seans.get("tarih"), "setler": [s.get("deger") for s in setler]}
                continue
            st["aktif"] = True
            st["son"] = {"tarih": seans.get("tarih"), "setler": [s.get("deger") for s in setler], "zorluk": h.get("zorluk")}
            degerler = [float(s["deger"]) for s in setler]
            zor = h.get("zorluk") or 7
            yeni, neden = None, ""
            if agrili & set(kat[kod].get("bolge") or []):
                yeni, neden = zincir_komsu(kod, -1, kat), "hareket sırasında ağrı 5/10'u geçti"
                st["dusuk"] = 0
            elif len(degerler) >= hd["set"] and min(degerler) >= hd["ust"] and zor <= 8:
                ust = zincir_komsu(kod, 1, kat)
                if ust:
                    yeni, neden = ust, f"bütün setlerde {hd['ust']}{' sn' if hd['olcu'] == 'sure' else ''} ve üstü"
                else:
                    adim = 5 if hd["olcu"] == "sure" else 2
                    st["aralik"] = [hd["alt"] + adim, hd["ust"] + adim]
                    kayit = {"t": int(time.time()), "id": _did(), "kod": kod, "tur": "aralik", "eski": [hd["alt"], hd["ust"]], "yeni": st["aralik"], "neden": f"bütün setlerde {hd['ust']} ve üstü"}
                    il["degisiklikler"].append(kayit)
                    degisen.append({**kayit, "yeni_aralik": st["aralik"], "ad": kat[kod]["ad"]})
                st["dusuk"] = 0
            elif min(degerler) < hd["alt"]:
                st["dusuk"] = (st.get("dusuk") or 0) + 1
                if st["dusuk"] >= 2:
                    yeni, neden = zincir_komsu(kod, -1, kat), f"iki seans üst üste {hd['alt']} altında"
                    st["dusuk"] = 0
            else:
                st["dusuk"] = 0
            if yeni and yeni != kod:
                st["aktif"] = False
                H.setdefault(yeni, {})["aktif"] = True
                kayit = {"t": int(time.time()), "id": _did(), "kod": kod, "yeni": yeni, "tur": "basamak", "neden": neden}
                il["degisiklikler"].append(kayit)
                degisen.append({**kayit, "ad": kat[kod]["ad"], "yeni_ad": kat[yeni]["ad"]})
        il["degisiklikler"] = il["degisiklikler"][-300:]
        _ilerleme_yaz(il)
    return degisen


def degisiklik_geri_al(did):
    """Bir basamak/aralık değişikliğini geri al (kimliğiyle; aynı saniyede birden çok değişiklik olabilir)."""
    with _kilit:
        il = ilerleme()
        x = next((d for d in il["degisiklikler"] if (d.get("id") or str(d.get("t"))) == str(did) and not d.get("geri")), None)
        if not x:
            return False
        H = il["hareketler"]
        if x.get("tur") == "basamak":
            H.setdefault(x["yeni"], {})["aktif"] = False
            H.setdefault(x["kod"], {})["aktif"] = True
        elif x.get("tur") == "aralik":
            H.setdefault(x["kod"], {})["aralik"] = x.get("eski")
        x["geri"] = int(time.time())
        _ilerleme_yaz(il)
        return True

# ----------------------------------------------------------------------------- yorgunluk: kondisyon / yorgunluk / form (zorluk × dakika)


def yuk_serisi(gun_sayisi=120):
    """Günlük yük (seans zorluğu × dakika; araştırma: sRPE çok sporda geçerli, BJJ dahil). Kondisyon = 42 günlük, yorgunluk = 7 günlük üstel ortalama,
    form = kondisyon − yorgunluk. Eşikler katı kural değil, yol gösterici (kanıt zayıf)."""
    son = bugun()
    ctl = atl = 0.0
    L = []
    for i in range(gun_sayisi - 1, -1, -1):
        g_ = son - dt.timedelta(days=i)
        d = _json(gun_yolu(g_.isoformat()), {})
        yuk = sum(int(s.get("yuk") or 0) for s in d.get("seanslar") or [] if s.get("bitti"))
        ctl += (yuk - ctl) / 42
        atl += (yuk - atl) / 7
        L.append({"tarih": g_.isoformat(), "yuk": yuk, "kondisyon": round(ctl, 1), "yorgunluk": round(atl, 1), "form": round(ctl - atl, 1)})
    return L


def yorgunluk_durumu():
    L = yuk_serisi(120)
    s = L[-1]
    ctl, form = s["kondisyon"], s["form"]
    if ctl < 15:
        return {**s, "durum": "veri_az", "metin": "Birkaç hafta kayıttan sonra kondisyon ve yorgunluk dengesi burada görünür."}
    oran = form / ctl
    if oran < -0.3:
        return {**s, "durum": "yorgun", "metin": "Yorgunluk kondisyonun belirgin üstünde: birkaç gün hafif gitmek iyi olur."}
    if oran < -0.1:
        return {**s, "durum": "yuklenme", "metin": "Verimli yüklenme aralığındasınız."}
    if oran > 0.15:
        return {**s, "durum": "dinc", "metin": "Dinçsiniz; zorlayıcı bir seans ya da deneme için iyi zaman."}
    return {**s, "durum": "denge", "metin": "Yük ve toparlanma dengede."}

# ----------------------------------------------------------------------------- takvim: toplantıların etrafına antrenman, seyahat günleri

SEYAHAT = re.compile(r"(uçuş|flight|flug|otel|hotel|seyahat|travel|trip|reise|tatil|holiday|urlaub|vacation|konferans|conference|airport|havalimanı|✈)", re.I)


_takvim_onb = {}


def takvim_haftasi(kod):
    """Haftanın günleri için toplantılar (saat aralıkları) ve seyahat işaretleri. Takvim yoksa boş. 10 dk önbellek."""
    anahtar = (kod, int(time.time() // 600))
    if anahtar not in _takvim_onb:
        _takvim_onb.clear()
        _takvim_onb[anahtar] = _takvim_haftasi(kod)
    return _takvim_onb[anahtar]


def _takvim_haftasi(kod):
    try:
        import takvim
        metin = takvim.ics_getir()
        if not metin:
            return {}
        out = {}
        tum = [e for e in takvim.etkinlikler(metin) if not e.get("iptal")]
        for g_ in hafta_gunleri(kod):
            ts = time.mktime(g_.timetuple()) + 12 * 3600
            dolu = [f"{time.strftime('%H:%M', time.localtime(e['bas']))}-{time.strftime('%H:%M', time.localtime(e['bit']))}" for e in takvim.gun(metin, ts)]
            g0 = time.mktime(g_.timetuple())
            seyahat = [e["ad"] for e in tum if SEYAHAT.search(f"{e['ad']} {e.get('konum', '')}") and e["bas"] < g0 + 86400 and e["bit"] > g0]
            if dolu or seyahat:
                out[g_.isoformat()] = {"dolu": dolu, "seyahat": seyahat[:2]}
        return out
    except Exception:  # noqa: BLE001
        return {}


# ----------------------------------------------------------------------------- beceri ağacı
BECERI = {"muscle_up": ("Muscle-up", ["cekme", "dips"]), "barfiks": ("Barfiks", ["cekme"]), "serbest_amut": ("Amut", ["amut", "amut_itme"]),
          "pistol": ("Pistol squat", ["bacak"]), "front_lever": ("Front lever", ["front_lever", "cekme"]), "lsit": ("L-sit", ["lsit", "govde"]),
          "tek_kol_sinav": ("Tek kol şınav", ["itme"])}
ZINCIR_AD = {"itme": "Şınav", "dips": "Dips", "amut_itme": "Amut şınavı", "cekme": "Barfiks", "front_lever": "Front lever", "bacak": "Bacak", "kalca": "Kalça",
             "govde": "Gövde", "plank": "Plank", "asili_govde": "Asılı gövde", "lsit": "L-sit", "amut": "Amut", "kalca_kb": "Kettlebell", "baldir": "Baldır"}


def beceriler():
    """Hedef becerilerin ağacı: her zincirde basamaklar (geçti / şimdi / kilitli), şimdiki basamağın geçme şartı ve son performans."""
    p = profil()
    kat = katalog()
    il = ilerleme()["hareketler"]
    var = set(p.get("ekipman") or []) | {"yok", "mat", "duvar"}
    out = []
    for b in p.get("beceri_hedefleri") or []:
        if b not in BECERI:
            continue
        ad, zincirler = BECERI[b]
        Z = []
        for z in zincirler:
            L = sorted([h for h in kat.values() if h.get("zincir") == z], key=lambda h: h.get("basamak") or 0)
            if not L:
                continue
            ak = aktif_basamak(z, kat)
            i = next((n for n, h in enumerate(L) if h["kod"] == ak), 0)
            hd = hedef(ak, kat)
            son = (il.get(ak) or {}).get("son") or {}
            sonraki = L[i + 1] if i + 1 < len(L) else None
            Z.append({"zincir": z, "ad": ZINCIR_AD.get(z, z), "ilerleme": round(i / max(1, len(L) - 1) * 100),
                      "basamaklar": [{"kod": h["kod"], "ad": h["ad"], "durum": "gecti" if n < i else "simdi" if n == i else "kilitli",
                                      "ekipman_yok": h["ekipman"] not in var} for n, h in enumerate(L)],
                      "simdi": {"kod": ak, "ad": kat[ak]["ad"], "sart": f"{hd['set']} set × {hd['ust']}{' sn' if hd['olcu'] == 'sure' else ' tekrar'}",
                                "son": son.get("setler"), "son_tarih": son.get("tarih")},
                      "sonraki": {"kod": sonraki["kod"], "ad": sonraki["ad"]} if sonraki else None,
                      "hazir": bool(son.get("setler")) and min(float(x) for x in son["setler"]) >= hd["ust"] - (2 if hd["olcu"] == "tekrar" else 5)})
        hedef_kod = b if b in kat else None
        out.append({"kod": b, "ad": ad, "zincirler": Z, "ilerleme": round(sum(z["ilerleme"] for z in Z) / max(1, len(Z))),
                    "tamam": bool(hedef_kod and (il.get(hedef_kod) or {}).get("aktif"))})
    return out


def deneme_seansi(beceri_kod):
    """Bir beceri için deneme: ısınma, her zincirde şimdiki basamak 2 set, sonra bir üst basamağa 2 deneme. Üstte hedefin altına inilmeden
    yapılırsa basamak geçer (seans_sonrasi_ilerleme 'deneme')."""
    kat = katalog()
    B = next((b for b in beceriler() if b["kod"] == beceri_kod), None)
    if not B:
        return None
    ana, deneme = [], {}
    for z in B["zincirler"]:
        ana.append({"kod": z["simdi"]["kod"], "ad": z["simdi"]["ad"], "set": 2, "tekrar": f"{hedef(z['simdi']['kod'], kat)['alt']}-{hedef(z['simdi']['kod'], kat)['ust']}", "dinlenme_sn": 120})
        if z["sonraki"]:
            hd = hedef(z["sonraki"]["kod"], kat)
            ana.append({"kod": z["sonraki"]["kod"], "ad": z["sonraki"]["ad"], "set": 2, "tekrar": f"{hd['alt']}+", "dinlenme_sn": 180, "not": "Deneme: temiz tekrar sayın."})
            deneme[z["sonraki"]["kod"]] = z["simdi"]["kod"]
    return {"tur": "kalistenik", "baslik": f"{B['ad']} denemesi", "sure_dk": 30, "deneme": deneme, "id": f"deneme-{beceri_kod}",
            "bolumler": [{"ad": "Isınma", "bicim": "sure", "hareketler": [{"kod": "bilek_hazirlik", "sure_sn": 60}, {"kod": "kedi_inek", "sure_sn": 45},
                                                                       {"kod": "dunya_esneme", "sure_sn": 60}, {"kod": "jumping_jack", "sure_sn": 60}]},
                         {"ad": "Ana bölüm", "bicim": "set", "hareketler": ana}]}

# ----------------------------------------------------------------------------- jiu-jitsu haritası
BJJ_HARITA = VERI / "bjj_harita.json"


def bjj_harita():
    d = _json(BJJ_HARITA, {})
    o = bjj_ozeti(56)
    zor = dict(o["zorlandigim"])
    kat = katalog()
    out = []
    for poz in BJJ_POZISYONLAR:
        x = d.get(poz) or {}
        out.append({"pozisyon": poz, "zorlanma": zor.get(poz, 0), "notlar": x.get("notlar") or [],
                    "drill": [{"kod": k, "ad": KATALOG[k]["ad"], "video": (kat.get(k) or {}).get("video")} for k in BJJ_DRILL.get(poz, [])],
                    "videolar": [{"kod": h["kod"], "ad": h["ad"], "video": h.get("video"), "kapak": h.get("kapak")} for h in kat.values()
                                 if h.get("pozisyon") == poz and h.get("video")]})
    return out


def bjj_not(poz, metin, sil=None):
    if poz not in BJJ_POZISYONLAR:
        return None
    with _kilit:
        d = _json(BJJ_HARITA, {})
        x = d.setdefault(poz, {"notlar": []})
        if sil is not None:
            x["notlar"] = [n for n in x["notlar"] if str(n.get("t")) != str(sil)]
        elif metin:
            x["notlar"].append({"t": int(time.time()), "metin": str(metin)[:600], "tarih": bugun().isoformat()})
        _yaz(BJJ_HARITA, d)
        return x


# ----------------------------------------------------------------------------- sabah kontrolü ve günün uyarlanması


def sabah_isigi(s):
    """4 soru → yeşil / sarı / kırmızı (Juggernaut ve TrainerRoad ışıklarının basit hali; kurallar görünür)."""
    uyku, enerji = s.get("uyku") or "iyi", int(sayi(s.get("enerji"), 1, 5, 3))
    agri = int(max([sayi(a.get("puan"), 0, 10, 0) for a in s.get("agri") or [] if isinstance(a, dict)] or [0]))
    neden = []
    if s.get("hasta"):
        return "kirmizi", ["kendinizi hasta hissediyorsunuz"]
    kotu = 0
    if uyku == "kotu":
        kotu += 1; neden.append("uyku kötü")
    if enerji <= 2:
        kotu += 1; neden.append("enerji düşük")
    if agri >= 6:
        return "kirmizi", [f"ağrı {agri}/10"]
    if agri >= 4:
        kotu += 1; neden.append(f"ağrı {agri}/10")
    if any(a.get("durum") == "artti" for a in s.get("dunku_agri") or []):
        kotu += 1; neden.append("dünkü ağrı arttı")
    hz = s.get("saglik") or {}
    if hz.get("dusuk"):                                    # Apple Sağlık: HRV kendi aralığının altı, sabah nabzı yüksek ya da kısa uyku
        kotu += 1; neden.append("saat verileri toparlanmanın eksik olduğunu gösteriyor")
    if kotu >= 2:
        return "kirmizi", neden
    if kotu == 1 or uyku == "orta" and enerji <= 3:
        return "sari", neden or ["uyku orta, enerji orta"]
    return "yesil", ["her şey yolunda"]


def agri_takip_bekleyen(tarih=None):
    """Dün antrenmanda kaydedilen eklem/keskin ağrı (≥3) bugün henüz sorulmadıysa: [{bolge, ad, puan}] (2026-10-28).
    Bugün ekranı tek dokunuşla sorar; sabah kontrolü de aynı bölgeleri tekrar sormaz."""
    t = dt.date.fromisoformat(tarih) if tarih else bugun()
    dun, bu = gun((t - dt.timedelta(days=1)).isoformat()), gun(t.isoformat())
    cevap = {a.get("bolge") for a in ((bu.get("sabah") or {}).get("dunku_agri") or []) + (bu.get("agri_takip") or [])}
    en = {}
    for a in dun.get("agri") or []:
        b, p = a.get("bolge"), sayi(a.get("puan"), 0, 10, 0)
        if a.get("tur") == "kas" or b not in BOLGELER or p < 3 or b in cevap or a.get("sabah"):
            continue
        en[b] = max(en.get(b, 0), p)
    return [{"bolge": b, "ad": BOLGELER[b], "puan": int(p)} for b, p in en.items()]


def agri_takip_kaydet(tarih, bolge, durum):
    bek = {x["bolge"]: x for x in agri_takip_bekleyen(tarih)}
    if bolge not in bek or durum not in ("gecti", "ayni", "artti"):
        raise ValueError("Bu bölge için bekleyen soru yok.")
    gun_degistir(tarih, lambda d: d.setdefault("agri_takip", []).append({"bolge": bolge, "durum": durum, "puan": bek[bolge]["puan"],
                                                                       "t": int(time.time())}))
    return {"koru": bolge in koru_bolgeler(), "bekleyen": agri_takip_bekleyen(tarih)}


def koru_bolgeler(gun_sayisi=7):
    """Ağrı kuralı bozulan bölgeler (son 7 gün): hareket sırasında >5, ertesi sabah eski düzeye dönmedi."""
    koru = {}
    for g in gunler(gun_sayisi):
        for a in g.get("agri") or []:
            if a.get("tur") != "kas" and sayi(a.get("puan"), 0, 10, 0) > 5:      # kas yanması/tutulma kural bozmaz
                koru[a.get("bolge")] = g["tarih"]
        for a in ((g.get("sabah") or {}).get("dunku_agri") or []) + (g.get("agri_takip") or []):
            if a.get("durum") in ("ayni", "artti") and sayi(a.get("puan"), 0, 10, 0) >= 3:
                koru[a.get("bolge")] = g["tarih"]
    return koru


def seansi_uyarla(seans, isik="yesil", vakit_dk=None, nerede="ev", p=None):
    """Planlanan seansı günün durumuna göre değiştirir (kodla, deterministik). Değişiklikleri 'uyarlama' listesine yazar."""
    p = p or profil()
    kat = katalog()
    s = json.loads(json.dumps(seans))
    notlar = []
    if isik == "kirmizi" and s.get("tur") not in ("dinlenme",):
        return {**kirmizi_seans(s), "uyarlama": ["Sabah kontrolü kırmızı: bugün yük yok, yalnızca hareketlilik ve isterseniz kolay sürüş."]}
    var_olan = set(p.get("ekipman") or [])
    if nerede in ("yolda", "otel"):
        var_olan = set()
    elif nerede == "park":
        var_olan = var_olan | {"bar", "paralel"}
    koru = koru_bolgeler()
    for b in s.get("bolumler") or []:
        for h in b.get("hareketler") or []:
            kod = h.get("kod")
            if kod not in kat:
                continue
            k2 = ekipmansiz_karsilik(kod, var_olan, kat)
            if k2 != kod:
                notlar.append(f"{kat[kod]['ad']} yerine {kat[k2]['ad']} (ekipman yok)")
                h["kod"], h["ad"] = k2, kat[k2]["ad"]
                kod = k2
            if set(kat[kod].get("bolge") or []) & set(koru):
                alt = zincir_komsu(kod, -1, kat)
                if alt:
                    notlar.append(f"{kat[kod]['ad']} yerine {kat[alt]['ad']} ({', '.join(BOLGELER.get(x, x) for x in set(kat[kod]['bolge']) & set(koru))} korunuyor)")
                    h["kod"], h["ad"] = alt, kat[alt]["ad"]
            if isik == "sari" and b.get("ad") == "Ana bölüm":
                if (h.get("set") or 3) > 2:
                    h["set"] = (h.get("set") or 3) - 1
                h["rir"] = (h.get("rir") or 2) + 1
        if isik == "sari" and b.get("bicim") in ("tur", "tabata", "emom"):
            b["tur_sayisi"] = max(1, int((b.get("tur_sayisi") or 3) * 2 / 3))
    if isik == "sari":
        notlar.insert(0, "Sabah kontrolü sarı: ana bölümde bir set az, zorluk bir kademe düşük.")
        if s.get("bisiklet") and s["bisiklet"].get("yogunluk") in ("aralik", "tempo"):
            s["bisiklet"]["yogunluk"] = "kolay"
            notlar.append("Bisikletteki aralıklar kolay tempoya döndü.")
        if s.get("kardiyo") and s["kardiyo"].get("yogunluk") in ("aralik", "orta"):
            s["kardiyo"]["yogunluk"] = "kolay"
            notlar.append("Aralıklar kolay tempoya döndü.")
    if vakit_dk and (s.get("sure_dk") or 0) > vakit_dk + 5:
        s = kisalt(s, vakit_dk)
        notlar.append(f"Vaktiniz {vakit_dk} dk: seans kısaltıldı.")
    s["uyarlama"] = notlar
    return s


def kisalt(s, dk):
    """Önce ısınma ve kapanışı kısalt, sonra ana bölümün sonundaki hareketleri at; en az asgari antrenman kalır."""
    if dk <= 12:
        return asgari_seans(s)
    s = json.loads(json.dumps(s))
    oran = dk / max(1, s.get("sure_dk") or dk)
    for b in s.get("bolumler") or []:
        hs = b.get("hareketler") or []
        if b.get("ad") != "Ana bölüm":
            b["hareketler"] = hs[:max(1, round(len(hs) * oran))]
        else:
            b["hareketler"] = hs[:max(2, round(len(hs) * min(1, oran + .15)))]
    s["sure_dk"] = dk
    return s


def asgari_seans(s=None):
    """Kötü günler için 10 dakika: seri bozulmasın ("iki kez kaçırma")."""
    il = [aktif_basamak("itme"), aktif_basamak("bacak"), aktif_basamak("govde")]
    return {"tur": "asgari", "baslik": "10 dakikalık kısa antrenman", "sure_dk": 10, "asgari": True,
            "bolumler": [
                {"ad": "Isınma", "bicim": "sure", "hareketler": [{"kod": "kedi_inek", "sure_sn": 40}, {"kod": "dunya_esneme", "sure_sn": 60}]},
                {"ad": "Ana bölüm", "bicim": "tur", "tur_sayisi": 3, "calisma_sn": 40, "dinlenme_sn": 20,
                 "hareketler": [{"kod": k} for k in il if k]},
            ]}


def kirmizi_seans(s=None):
    return {"tur": "mobilite", "baslik": "Toparlanma: hareketlilik", "sure_dk": 20, "toparlanma": True,
            "bolumler": [{"ad": "Hareketlilik", "bicim": "sure", "hareketler": [
                {"kod": "kedi_inek", "sure_sn": 60}, {"kod": "dunya_esneme", "sure_sn": 90}, {"kod": "kalca_9090", "sure_sn": 90},
                {"kod": "gogus_donus", "sure_sn": 90}, {"kod": "derin_squat_tutus", "sure_sn": 60}, {"kod": "kanepe_esneme", "sure_sn": 90}]}],
            **({"bisiklet": {"sure_dk": 30, "yogunluk": "kolay", "aciklama": "İsterseniz en çok 45 dk çok kolay sürüş (konuşabileceğiniz tempo)."}}
               if "bisiklet" in (profil().get("ekipman") or []) else
               {"kardiyo": {"tur": "yuruyus", "sure_dk": 20, "yogunluk": "kolay", "aciklama": "İsterseniz 20-30 dakika sakin yürüyüş."}})}

# ----------------------------------------------------------------------------- haftalık plan (Claude yazar, kurallar kodda)

PLAN_ISTEM = """Sen PT'sin: deneyimli bir kişisel antrenör, kuvvet-kondisyon koçu, BJJ hocası ve fizyoterapistin bilgisiyle çalışıyorsun.
{hafta_ad} için haftalık antrenman planı yaz. Türkçe, "siz" dili.

KİŞİ:
{profil}

BU HAFTANIN KOŞULLARI:
- Tarihler: {tarihler}
- Hafif hafta mı: {hafif}
- Başlangıç testi gerekiyor mu: {test} (gerekiyorsa ilk uygun güne "Başlangıç testleri" seansı koy: tur "test", bölüm yok)
- Korunan bölgeler (ağrı kuralı bozuldu, bu bölgeleri yükleyen hareketlerde kolay basamak): {koru}
- Geçen haftanın özeti: {gecen}
- Kullanıcının bu hafta için söyledikleri: {istek}
- Takvim (bu saatler dolu; seansları boş saatlere koy ve "saat" alanına HH:MM yaz; seyahat günlerinde kısa ve ekipmansız): {takvim}
- Yorgunluk durumu: {yorgunluk}
- Kullanıcının onayladığı güncel bulgular (kurallara ek olarak uygula): {bulgular}
- Programlama bloğu: {blok}. Bloğun amacına göre yaz; 5. hafta hafif hafta ve yeniden test.
- Başlangıç durumu (ÖNCELİKLİ; profildeki gün/dakika tercihinden önce gelir): {baslangic}
- Gün düzeni: {gun_duzeni} (antrenmanı kalkış/iş saatlerine ve yoğun günlere göre yerleştir; "saat" alanına HH:MM yaz).
- Jiu-jitsu: son 8 haftada derslerde en çok zorlandığı pozisyonlar: {bjj_zor}. Solo BJJ seansında bu pozisyonların drillerini öne al: {bjj_drill}
- Birlikte belirlenen hedefler (planı bunlara doğru kur; kısa vadeli hedef bu haftanın odağına girsin): {hedefler}
- Son ara kontrolün kararı (uygula): {kontrol}
- Haftalık reçete ve uzun ömür dozu (KODDA, kişi onayladı; gün türlerini ve sayılarını buna göre dağıt): {recete}

İLERLEME KURALLARI (KODDA; sen hedefleri değiştirme, aynen kullan). Her zincirde ŞU AN çalışılan hareket ve hedefi:
{basamaklar}

KULLANABİLECEĞİN HAREKETLER (YALNIZCA bu kodlar; 'video' olanlar kişinin kendi videosu var, onları tercih et):
{katalog}

KURALLAR:
- Yöntem dağılımı kişinin istediği gibi; BJJ dersi günleri sabit (tur "bjj_ders", hareket yok, sure_dk ders süresi).
- BJJ dersinden ÖNCEKİ gün ağır bacak ya da kavrama (barfiks, asılma) yok; ders günü başka seans yok; dersten sonraki gün hafif ya da hareketlilik.
- Ağır bacak çalışmasını uzun/sert bisiklet ile aynı güne koyma; bisikletin çoğu kolay tempoda; BJJ dersini zor seans say.
- Kalistenik seansta: Isınma (5-8 dk, mobilite/ısınma hareketleri) → Ana bölüm (zincir hareketleri, yukarıdaki hedeflerle: set, tekrar aralığı
  "alt-ust", rir 1-3, dinlenme_sn 60-150) → isteğe bağlı Bitiriş (tur/emom/tabata) → Kapanış (2-4 dk esneme).
- Solo BJJ: drill hareketleri, bicim "tur" (ör. 5 tur, calisma_sn 30-45, dinlenme_sn 15-30). Animal flow: önce tutuşlar, sonra geçişler, sonra
  flow_zinciri. Mobilite seansı 15-25 dk.
- Bisiklet günü: "bisiklet": {{sure_dk, yogunluk: kolay|orta|aralik, aciklama (aralıksa tarif: "3×8 dk orta-zor, araları 4 dk kolay")}}.
- Yürüyüş/koşu günü (tur "kardiyo"): "kardiyo": {{tur: yuruyus|kosu, sure_dk, yogunluk: kolay|orta|aralik, aciklama ("konuşabileceğiniz tempoda" ya da
  aralık tarifi "5 kez 2 dk hızlı yürüyüş / 2 dk yavaş")}}; bölüm yok ya da yalnız kısa Kapanış. Kolay tempo = konuşabileceğiniz hız.
- Günlük süre kişinin dakikasını geçmesin. Dinlenme günü de olabilir (tur "dinlenme").
- Her güne "neden" (tek cümle: bu seans neden bugün) yaz.
- Hafif haftada set sayısını üçte bir azalt.
- "asgari": kötü bir gün için 10 dakikalık ortak seans (bolumler).
- "eger_ise": 3-4 önceden bağlanmış plan ("BJJ dersi iptal olursa: 20 dk solo drill" gibi), kişinin düzenine göre.
- "not": haftanın tek cümlelik odağı.

JSON: {{"gunler": [{{"tarih": "YYYY-MM-DD", "tur": "kalistenik|bjj_solo|bjj_ders|flow|bisiklet|kardiyo|mobilite|test|dinlenme", "baslik", "sure_dk", "saat": "sabah|ogle|aksam",
"neden", "bolumler": [{{"ad": "Isınma|Ana bölüm|Bitiriş|Kapanış|Drill|Akış", "bicim": "set|sure|tur|emom|tabata|akis", "tur_sayisi", "calisma_sn",
"dinlenme_sn", "hareketler": [{{"kod", "set", "tekrar": "6-10" (ya da "sure_sn": 30), "rir", "dinlenme_sn", "not"}}]}}], "bisiklet": {{...}}, "kardiyo": {{...}} }}],
"asgari": {{"bolumler": [...]}}, "eger_ise": ["..."], "not": "..."}}"""


def program_yolu(kod):
    return PROGRAM / f"{hafta_gecerli(kod)}.json"


def program(kod=None):
    return _json(program_yolu(kod or hafta_kodu()), {})


def _profil_ozeti(p):
    gorunen = {k: p.get(k) for k in ("cinsiyet", "yas", "boy_cm", "kilo_kg", "hedef_kilo_kg", "hedefler", "hedef_turleri", "beceri_hedefleri", "deneyim",
                                     "motivasyon", "yontemler", "bjj_ders", "ekipman", "gunler", "gunluk_dk", "antrenman_saati", "sakatliklar",
                                     "yapamadiklarim", "sinirlar", "ek_bilgi", "notlar", "gun_duzeni", "beslenme_aliskanlik", "aliskanlik", "sevdikleri", "kardiyo_tur")}
    gorunen["gunler"] = [GUN_AD[i] for i in p.get("gunler") or []]
    if p.get("bjj_ders", {}).get("gunler"):
        gorunen["bjj_ders"] = {**p["bjj_ders"], "gunler": [GUN_AD[i] for i in p["bjj_ders"]["gunler"]]}
    return json.dumps(gorunen, ensure_ascii=False)


def _katalog_metni(p, kat):
    var = set(p.get("ekipman") or []) | {"yok", "mat", "duvar"}
    L = []
    for h in kat.values():
        if h["ekipman"] not in var:
            continue
        L.append(f"{h['kod']}: {h['ad']} [{h['tur']}, {h['olcu']}{', zincir ' + h['zincir'] + ' #' + str(h['basamak']) if h.get('zincir') else ''}"
                 f"{', VIDEO' if h.get('video') else ''}]")
    return "\n".join(L)


def _basamak_metni(kat):
    L = []
    for z in sorted({x["zincir"] for x in kat.values() if x.get("zincir") and x["tur"] == "kalistenik"}):
        k = aktif_basamak(z, kat)
        if k:
            hd = hedef(k, kat)
            L.append(f"{z}: {k} ({kat[k]['ad']}) → {hd['set']} set {hd['alt']}-{hd['ust']}{' sn' if hd['olcu'] == 'sure' else ' tekrar'}")
    return "\n".join(L)


def _gecen_hafta_ozeti(kod):
    gun_list = hafta_gunleri(kod)
    once = [g - dt.timedelta(days=7) for g in gun_list]
    pl = program(hafta_kodu(once[0]))
    planlanan = len([g for g in pl.get("gunler") or [] if g.get("tur") not in ("dinlenme",)])
    yapilan, notlar = 0, []
    for g in once:
        d = gun(g.isoformat())
        yapilan += len([s for s in d["seanslar"] if s.get("bitti")])
        for s in d["seanslar"]:
            if s.get("not"):
                notlar.append(s["not"][:120])
    return f"planlanan {planlanan} seans, yapılan {yapilan}. Notlar: {'; '.join(notlar[:5]) or 'yok'}"


def _hafta_no(kod):
    """Kurulumdan bu yana kaçıncı hafta (her 5. hafta hafif)."""
    ilk = sorted(PROGRAM.glob("*-W*.json"))
    if not ilk:
        return 1
    try:
        return 1 + max(0, (hafta_gunleri(kod)[0] - hafta_gunleri(ilk[0].stem)[0]).days // 7)
    except Exception:  # noqa: BLE001
        return 1


def baslangic_durumu():
    """Alışma ya da dönüş haftası mı (2026-10-28: ilk planda her gün 30 dk vardı, kullanıcı ilk seansta bıraktı).
    alisma: toplam biten seans < 6. donus: daha önce en az 6 seans ama son 10 günde hiç yok."""
    gunler_ = sorted(GUNLUK.glob("*.json"))
    toplam, son = 0, None
    for f in gunler_:
        n = sum(1 for x in _json(f, {}).get("seanslar") or [] if x.get("bitti"))
        toplam += n
        if n:
            son = f.stem
    if toplam < 6:
        return {"tur": "alisma", "toplam": toplam, "en_cok_gun": 5, "en_cok_dk": 20}
    if son and (bugun() - dt.date.fromisoformat(son)).days >= 10:
        return {"tur": "donus", "toplam": toplam, "en_cok_gun": 4, "en_cok_dk": 20}
    return {"tur": "normal", "toplam": toplam}


def _baslangic_metni(b, p):
    if b["tur"] == "normal":
        return "yok (alışmış kullanıcı; normal plan)"
    beceri = p.get("beceri_hedefleri") or []
    return (("ALIŞMA HAFTASI: kullanıcı henüz " + str(b["toplam"]) + " seans tamamladı. " if b["tur"] == "alisma"
             else "DÖNÜŞ HAFTASI: 10 günden uzun ara verildi. ")
            + f"En çok {b['en_cok_gun']} antrenman günü, her biri 10-{b['en_cok_dk']} dakika; kalan günler dinlenme. En kolay basamaklar, "
            "zorluk en çok 6/10. Başlangıç testi gerekiyorsa tek seansa değil, 5'er dakikalık parçalar halinde ilk 2-3 güne dağıt "
            "(test seansının sure_dk'si 10). Hedef becerilerden en çok 2'sine odaklan; ekipman gerektirenleri (bar, paralel) ekipman yoksa bu hafta koyma."
            + (f" Kullanıcının hedef becerileri: {', '.join(map(str, beceri))}." if beceri else ""))


def _g_metin(fn, varsayilan=""):
    try:
        return fn() or varsayilan
    except Exception:  # noqa: BLE001
        return varsayilan


def program_uret(kod=None, istek=""):
    """Haftanın planı: Claude yazar, sonra kodla doğrulanır (bilinmeyen hareket atılır, hedefler kurallardan, ekipman denetimi)."""
    import claude_yaz
    kod = kod or hafta_kodu()
    p = profil()
    kat = katalog()
    tarihler = [g.isoformat() for g in hafta_gunleri(kod)]
    bugun_s = bugun().isoformat()
    tarihler_metin = ", ".join(f"{t} {GUN_AD[i]}" + (" (geçti)" if t < bugun_s else "") for i, t in enumerate(tarihler))
    hafif = _hafta_no(kod) % 5 == 0 or yorgunluk_durumu().get("durum") == "yorgun"      # her 5. hafta ya da yorgunluk birikmişse (pt_koc.blok ile aynı)
    koru = koru_bolgeler()
    bas_d = baslangic_durumu()
    istem = PLAN_ISTEM.format(baslangic=_baslangic_metni(bas_d, p),
        hafta_ad=kod, profil=_profil_ozeti(p), tarihler=tarihler_metin, hafif="evet" if hafif else "hayır",
        test="evet" if test_gerekli() else "hayır", koru=", ".join(BOLGELER.get(k, k) for k in koru) or "yok",
        gecen=_gecen_hafta_ozeti(kod), istek=" ".join(x for x in (istek, __import__("pt_programlar").plan_notu(kod)) if x) or "yok", basamaklar=_basamak_metni(kat) or "henüz test yok; en kolay basamaklardan başla",
        takvim=json.dumps(takvim_haftasi(kod), ensure_ascii=False) or "bilgi yok", yorgunluk=yorgunluk_durumu().get("metin", ""),
        bulgular=__import__("pt_kanit").onayli_metin(),
        blok=json.dumps(__import__("pt_koc").blok(kod, p), ensure_ascii=False), gun_duzeni=json.dumps(__import__("pt_koc").gun_duzeni(p), ensure_ascii=False),
        katalog=_katalog_metni(p, kat), bjj_zor=", ".join(f"{a} ({n})" for a, n in bjj_ozeti(56)["zorlandigim"][:3]) or "kayıt yok",
        bjj_drill=", ".join(sorted({k for a, _ in bjj_ozeti(56)["zorlandigim"][:3] for k in BJJ_DRILL.get(a, [])})) or "-",
        hedefler=_g_metin(lambda: __import__("pt_hedef").istem_metni(), "henüz belirlenmedi"),
        kontrol=p.get("kontrol_istegi") or "yok", recete=_g_metin(lambda: __import__("pt_uzun").recete_metni(), "yok"))
    c = claude_yaz.sor_json(istem, model_adi="opus", zaman_asimi=900)
    pl = plani_dogrula(c, tarihler, p, kat)
    bjj_ders_isle(pl, p)
    if bas_d["tur"] != "normal":                                   # kural kodda: modelin uyması beklenmez
        aktif = [g for g in pl.get("gunler") or [] if g.get("tur") not in ("dinlenme", "bjj_ders")]
        for g in aktif:
            g["sure_dk"] = min(g.get("sure_dk") or bas_d["en_cok_dk"], bas_d["en_cok_dk"] if g.get("tur") != "test" else 10)
        for g in aktif[bas_d["en_cok_gun"]:]:
            g.update(tur="dinlenme", baslik="Dinlenme", sure_dk=0, bolumler=[], neden="Alışma haftası: günde bir kısa seans yeter.")
        pl["baslangic"] = bas_d["tur"]
    pl.update(hafta=kod, olusturma=int(time.time()), hafif=hafif, istek=istek)
    with _kilit:
        eski = program(kod)
        if eski:
            _yaz(PROGRAM / "gecmis" / f"{kod}_{eski.get('olusturma', 0)}.json", eski)
        _yaz(program_yolu(kod), pl)
    return pl


def _hareket_dogrula(h, kat, var_olan):
    kod = h.get("kod")
    if kod not in kat:
        return None
    if kat[kod]["ekipman"] not in var_olan:
        kod = ekipmansiz_karsilik(kod, var_olan, kat)
    x = {"kod": kod, "ad": kat[kod]["ad"]}
    for a in ("set", "rir", "dinlenme_sn", "sure_sn"):
        try:
            if h.get(a) is not None:
                x[a] = int(h[a])
        except (TypeError, ValueError):
            pass
    if h.get("tekrar"):
        x["tekrar"] = str(h["tekrar"])[:12]
    if h.get("not"):
        x["not"] = str(h["not"])[:160]
    if kat[kod].get("zincir") and kat[kod]["tur"] == "kalistenik" and kat[kod]["olcu"] == "tekrar" and not x.get("sure_sn"):
        hd = hedef(kod, kat)
        x["tekrar"] = f"{hd['alt']}-{hd['ust']}"
    return x


def bjj_ders_isle(pl, p=None):
    """Salondaki jiu-jitsu dersleri kodla sabitlenir (2026-10-28): ders günü o gün yalnız ders olur, ders günü olmayan
    'bjj_ders' dinlenmeye döner. Claude'un yazdığı plana ve profil değişince var olan plana uygulanır. Döner: değişen gün sayısı."""
    p = p or profil()
    b = p.get("bjj_ders") or {}
    dg = {int(x) for x in b.get("gunler") or [] if str(x).isdigit() and 0 <= int(x) <= 6}
    gunler_ = pl.setdefault("gunler", [])
    var = {g.get("tarih"): g for g in gunler_}
    degisen = 0
    if pl.get("hafta"):
        for t in (x.isoformat() for x in hafta_gunleri(pl["hafta"])):
            if t not in var and dt.date.fromisoformat(t).weekday() in dg:
                g = {"tarih": t, "tur": "dinlenme", "bolumler": [], "id": f"{t}-b"}
                gunler_.append(g)
                var[t] = g
    for g in gunler_:
        try:
            wd = dt.date.fromisoformat(g["tarih"]).weekday()
        except (KeyError, ValueError):
            continue
        if g["tarih"] < bugun().isoformat():
            continue                                            # geçmiş günlere dokunulmaz (seri hesabı geçmiş planı okur)
        if wd in dg and not g.get("bitti"):
            degisen += g.get("tur") != "bjj_ders"
            g.update(tur="bjj_ders", baslik="Jiu-jitsu dersi", sure_dk=int(b.get("sure_dk") or 90), saat=b.get("saat") or g.get("saat") or "aksam",
                     bolumler=[], neden="Salondaki dersiniz; bugün başka antrenman yok.")
            g.pop("bisiklet", None)
            g.pop("kardiyo", None)
        elif g.get("tur") == "bjj_ders" and wd not in dg and not g.get("bitti"):
            g.update(tur="dinlenme", baslik="Dinlenme", sure_dk=0, bolumler=[], neden="Bu gün ders yok.")
            degisen += 1
    gunler_.sort(key=lambda g: g.get("tarih") or "")
    return degisen


def bjj_dersleri_kaydet(gunler, saat="", sure_dk=90):
    """Profil + bu haftanın ve (varsa) gelecek haftanın planına anında işler (Claude çağrısı yok)."""
    gunler = sorted({int(x) for x in gunler or [] if str(x).isdigit() and 0 <= int(x) <= 6})
    saat = saat if re.fullmatch(r"\d{2}:\d{2}", str(saat or "")) else ""
    p = profil_kaydet({"bjj_ders": {"gunler": gunler, "saat": saat, "sure_dk": int(sayi(sure_dk, 30, 240, 90)), "soruldu": True}})
    toplam = 0
    with _kilit:
        for kod in (hafta_kodu(), hafta_kodu(bugun() + dt.timedelta(days=7))):
            pl = program(kod) if program_yolu(kod).exists() else None
            if pl:
                pl.setdefault("hafta", kod)
                n = bjj_ders_isle(pl, p)
                if n:
                    _yaz(program_yolu(kod), pl)
                    toplam += n
    return {"profil": p, "degisen": toplam}


def plani_dogrula(c, tarihler, p, kat):
    var_olan = set(p.get("ekipman") or []) | {"yok", "mat", "duvar"}
    gunler_ = {}
    for g in c.get("gunler") or []:
        t = str(g.get("tarih") or "")
        if t not in tarihler:
            continue
        g2 = {"tarih": t, "tur": g.get("tur") or "dinlenme", "baslik": str(g.get("baslik") or "")[:80], "sure_dk": _dk(g.get("sure_dk"), 0),
              "saat": g.get("saat") or "", "neden": str(g.get("neden") or "")[:240], "bolumler": [], "id": f"{t}-{len(gunler_)}"}
        for b in g.get("bolumler") or []:
            hs = [x for x in (_hareket_dogrula(h, kat, var_olan) for h in b.get("hareketler") or []) if x]
            if hs:
                g2["bolumler"].append({"ad": str(b.get("ad") or "Ana bölüm")[:30], "bicim": b.get("bicim") or "set",
                                       **{a: int(b[a]) for a in ("tur_sayisi", "calisma_sn", "dinlenme_sn") if isinstance(b.get(a), (int, float))},
                                       "hareketler": hs})
        if g.get("bisiklet") and "bisiklet" in (p.get("ekipman") or []):
            bs = g["bisiklet"]
            g2["bisiklet"] = {"sure_dk": _dk(bs.get("sure_dk"), 60), "yogunluk": bs.get("yogunluk") or "kolay", "aciklama": str(bs.get("aciklama") or "")[:240]}
        elif g.get("bisiklet") or g.get("kardiyo") or g2["tur"] == "kardiyo":   # bisikleti yoksa aynı gün yürüyüş olur
            bs = g.get("kardiyo") or g.get("bisiklet") or {}
            ktur = bs.get("tur") if bs.get("tur") in ("yuruyus", "kosu", "merdiven", "yuzme") else (p.get("kardiyo_tur") or "yuruyus")
            g2["kardiyo"] = {"tur": ktur, "sure_dk": _dk(bs.get("sure_dk"), g2["sure_dk"] or 30), "yogunluk": bs.get("yogunluk") if bs.get("yogunluk") in ("kolay", "orta", "aralik") else "kolay",
                             "aciklama": str(bs.get("aciklama") or "")[:240]}
            if g2["tur"] == "bisiklet":
                g2["tur"] = "kardiyo"
            g2["sure_dk"] = g2["sure_dk"] or g2["kardiyo"]["sure_dk"]
        gunler_.setdefault(t, []).append(g2)
    gunler_l = []
    for t in tarihler:
        gunler_l += gunler_.get(t) or [{"tarih": t, "tur": "dinlenme", "baslik": "Dinlenme", "sure_dk": 0, "bolumler": [], "id": f"{t}-0",
                                         "neden": "Toparlanma günü."}]
    asg = c.get("asgari") or {}
    asgari = asgari_seans()
    if asg.get("bolumler"):
        bl = [{"ad": b.get("ad") or "Ana bölüm", "bicim": b.get("bicim") or "tur", **{a: int(b[a]) for a in ("tur_sayisi", "calisma_sn", "dinlenme_sn") if isinstance(b.get(a), (int, float))},
               "hareketler": [x for x in (_hareket_dogrula(h, kat, var_olan) for h in b.get("hareketler") or []) if x]} for b in asg["bolumler"]]
        if any(b["hareketler"] for b in bl):
            asgari["bolumler"] = [b for b in bl if b["hareketler"]]
    return {"gunler": gunler_l, "asgari": asgari, "eger_ise": [str(x)[:200] for x in (c.get("eger_ise") or [])][:5], "not": str(c.get("not") or "")[:240]}


def program_geri_al(kod=None):
    kod = kod or hafta_kodu()
    eskiler = sorted((PROGRAM / "gecmis").glob(f"{hafta_gecerli(kod)}_*.json"))
    if not eskiler:
        return None
    with _kilit:
        simdiki = program(kod)
        _yaz(PROGRAM / "gecmis" / f"{kod}_{simdiki.get('olusturma', 0)}_geri.json", simdiki)
        pl = _json(eskiler[-1], {})
        eskiler[-1].unlink()
        _yaz(program_yolu(kod), pl)
    return pl


def gun_tasi(kod, gid, yeni_tarih):
    """Esneklik: seansı başka güne taşı (kilitli antrenman yok)."""
    with _kilit:
        pl = program(kod)
        for g in pl.get("gunler") or []:
            if g.get("id") == gid:
                g["tarih"] = yeni_tarih
                g["tasindi"] = True
        pl["gunler"].sort(key=lambda g: (g["tarih"], g.get("tur") == "dinlenme"))
        _yaz(program_yolu(kod), pl)
        return pl


def gun_seansi(tarih=None):
    """Bugünün seansları (dinlenme dahil) + sabah kontrolüne göre uyarlanmış hali."""
    tarih = tarih or bugun().isoformat()
    g_ = dt.date.fromisoformat(tarih)
    pl = program(hafta_kodu(g_))
    plan = [g for g in pl.get("gunler") or [] if g.get("tarih") == tarih]
    d = gun(tarih)
    s = d.get("sabah") or {}
    isik = s.get("isik")
    out = []
    for g in plan:
        nerede = s.get("nerede") or ("yolda" if (takvim_haftasi(hafta_kodu(g_)).get(tarih) or {}).get("seyahat") else "ev")
        u = seansi_uyarla(g, isik or "yesil", s.get("vakit_dk"), nerede) if g.get("bolumler") or g.get("bisiklet") or g.get("kardiyo") else dict(g)
        u["id"] = g.get("id")
        u["bitti"] = any(x.get("plan_id") == g.get("id") and x.get("bitti") for x in d["seanslar"])
        out.append(u)
    return {"tarih": tarih, "seanslar": out, "sabah": s, "asgari": pl.get("asgari") or asgari_seans()}

# ----------------------------------------------------------------------------- seans kaydı


def seans_kaydet(tarih, seans):
    """Oynatıcıdan gelen kayıt: hareketler[{kod, setler[{deger}], zorluk}], sure_dk, zorluk (1-10), agri[{bolge, puan}], not."""
    seans = dict(seans)
    seans["tarih"] = tarih
    seans.setdefault("id", f"s{int(time.time() * 1000)}")
    seans["bitti"] = True
    try:
        seans["yuk"] = int(float(seans.get("zorluk") or 0) * float(seans.get("sure_dk") or 0))   # seans zorluğu × dakika
    except (TypeError, ValueError):
        seans["yuk"] = 0
    degisen = seans_sonrasi_ilerleme(seans) if seans.get("hareketler") else []
    seans["ilerleme"] = degisen

    def ekle(d):
        d["seanslar"] = [x for x in d["seanslar"] if x.get("id") != seans["id"]] + [seans]
        for a in seans.get("agri") or []:
            d["agri"].append({**a, "seans": seans["id"], "t": int(time.time())})
    gun_degistir(tarih, ekle)
    return seans


def seri(gun_sayisi=60):
    """Güncel seri (pt_oyun: günün hedefi, seri koruması, telafi). `gun_sayisi` eski çağrılarla uyum için."""
    import pt_oyun
    return pt_oyun.seri()


def yillik_takvim(gun_sayisi=182):
    son = bugun()
    L = []
    for i in range(gun_sayisi - 1, -1, -1):
        g_ = son - dt.timedelta(days=i)
        p = gun_yolu(g_.isoformat())
        n = 0
        if p.exists():
            d = _json(p, {})
            n = sum(int(s.get("sure_dk") or 0) for s in d.get("seanslar") or [] if s.get("bitti"))
        L.append([g_.isoformat(), n])
    return L

# ----------------------------------------------------------------------------- BJJ günlüğü


def bjj_kaydet(tarih, k):
    k = {"t": int(time.time()), "sure_dk": int(k.get("sure_dk") or 0), "zorluk": int(k.get("zorluk") or 0),
         "zorlandigim": [x for x in k.get("zorlandigim") or [] if x in BJJ_POZISYONLAR],
         "yakalandigim": [x for x in k.get("yakalandigim") or [] if x in BJJ_BITIRISLER],
         "bitirdigim": [x for x in k.get("bitirdigim") or [] if x in BJJ_BITIRISLER],
         "teknik": str(k.get("teknik") or "")[:300], "not": str(k.get("not") or "")[:500]}

    def ekle(d):
        d["bjj"].append(k)
        if k["sure_dk"] and k["zorluk"]:
            d["seanslar"].append({"id": f"bjj{k['t']}", "tur": "bjj_ders", "baslik": "BJJ dersi", "bitti": True, "sure_dk": k["sure_dk"],
                                  "zorluk": k["zorluk"], "yuk": k["sure_dk"] * k["zorluk"], "plan_id": k.get("plan_id")})
    gun_degistir(tarih, ekle)
    return k


def bjj_ozeti(gun_sayisi=28):
    from collections import Counter
    z, y, b, n = Counter(), Counter(), Counter(), 0
    for g in gunler(gun_sayisi):
        for k in g.get("bjj") or []:
            n += 1
            z.update(k.get("zorlandigim") or []); y.update(k.get("yakalandigim") or []); b.update(k.get("bitirdigim") or [])
    return {"ders": n, "zorlandigim": z.most_common(6), "yakalandigim": y.most_common(6), "bitirdigim": b.most_common(6)}


BJJ_DRILL = {"Guard": ["bacak_pummel", "kalca_degistirme", "karides"], "Yan kontrol": ["karides", "ters_karides", "kopru_upa"],
             "Diz üstü": ["karides", "kopru_upa"], "Mount": ["kopru_upa", "karides"], "Arkadan kontrol": ["granby", "ters_karides"],
             "Kaplumbağa": ["sit_out", "granby", "teknik_kalkis"]}

# ----------------------------------------------------------------------------- haftalık koç mesajı

KOC_ISTEM = """Sen PT'sin: kişisel antrenör + diyetisyen + alışkanlık koçu. {hafta} haftası için haftalık kontrol mesajını yaz.
Ton: sıcak ama net, "siz" dili, Türkçe, klişe ve slogan yok, abartı yok. Kayıtlara SOMUT atıf yap (sayı, gün). Uydurma yok: veride olmayanı yazma.
Tartı tek ölçü değil: tekrar sayıları, bel, uyku gibi tartı dışı kazanımları öne çıkar. Kişinin motivasyonunu ve notlarını (veri.kisi) hatırla. "İki kez kaçırma" ilkesi: bir kaçırma sorun değil.
Aynı anda en çok bir-iki şeyi değiştir. Teşhis koyma; ağrı ya da belirti kuralı bozulduysa açıkça söyle, gerekiyorsa doktora yönlendir.
18/6 bir uyum aracı: protein hedefi ya da antrenman kalitesi bozuluyorsa 16/8'e ya da esnek günlere geçmeyi öner.

VERİ:
{veri}

Markdown ile şu başlıklar (her biri 1-4 kısa satır; veri yoksa başlığı atla):
## Neler iyi gitti
## Seanslar
## Performans
## Vücut
## Toparlanma
## Beslenme
## Önümüzdeki hafta
(engelleri tahmin et ve her biri için bir "eğer ... olursa ..." planı)
## Değişecek tek şey
(tek cümle)

Sonra ayrı satırda JSON: {{"degisecek": "tek cümle", "plan_istegi": "gelecek haftanın planına verilecek tek cümlelik yönlendirme"}}"""


def hafta_verisi(kod):
    import pt_beslenme
    gl = hafta_gunleri(kod)
    pr = profil()
    pl = program(kod)
    planlanan = [g for g in pl.get("gunler") or [] if g.get("tur") not in ("dinlenme",)]
    gunluk = [gun(g.isoformat()) for g in gl]
    seanslar = [s for d in gunluk for s in d["seanslar"] if s.get("bitti")]
    sabah = [d.get("sabah") for d in gunluk if d.get("sabah")]
    agri = [a for d in gunluk for a in d["agri"]]
    ilerl = [x for s in seanslar for x in s.get("ilerleme") or []]
    enler = {}
    for s in seanslar:
        for h in s.get("hareketler") or []:
            v = [x.get("deger") for x in h.get("setler") or [] if x.get("deger") is not None]
            if v:
                enler[h.get("ad") or h.get("kod")] = max(max(v), enler.get(h.get("ad") or h.get("kod"), 0))
    return {
        "kisi": {k: pr.get(k) for k in ("hedefler", "beceri_hedefleri", "motivasyon", "sakatliklar", "ek_bilgi", "notlar")},
        "planlanan_seans": len(planlanan), "yapilan_seans": len(seanslar), "seri_gun": seri(),
        "seanslar": [{"tarih": s.get("tarih"), "tur": s.get("tur"), "sure_dk": s.get("sure_dk"), "zorluk": s.get("zorluk"), "not": s.get("not")} for s in seanslar],
        "en_iyi": enler, "basamak_degisiklikleri": [{k: x.get(k) for k in ("ad", "yeni_ad", "neden")} for x in ilerl],
        "sabah": [{"tarih": d["tarih"], "isik": (d.get("sabah") or {}).get("isik"), "uyku": (d.get("sabah") or {}).get("uyku"),
                   "uyku_saat": (d.get("sabah") or {}).get("uyku_saat"), "enerji": (d.get("sabah") or {}).get("enerji")} for d in gunluk if d.get("sabah")],
        "agri": [{"bolge": a.get("bolge"), "puan": a.get("puan")} for a in agri],
        "korunan_bolgeler": list(koru_bolgeler()), "bjj": bjj_ozeti(7),
        "bel_cm": [{"tarih": d["tarih"], "bel": d["bel_cm"]} for d in gunler(35) if d.get("bel_cm")][:4],
        "testler_bu_hafta": [x for x in testler().get("kayitlar") or [] if x.get("tarih", "") >= gl[0].isoformat()],
        "gorusme": {k: v for k, v in _json(MESAJLAR / f"{hafta_gecerli(kod)}.gorusme.json", {}).items() if k in ("sorular", "cevaplar", "aliskanlik")},
        "aksamlar": [{"tarih": d["tarih"], **{k: (d.get("aksam") or {}).get(k) for k in ("antrenman", "beslenme", "aclik", "enerji")}} for d in gunluk if d.get("aksam")],
        "beslenme": pt_beslenme.hafta_ozeti(gl), "uyku_ortalama": round(sum(float(x.get("uyku_saat") or 0) for x in sabah) / len(sabah), 1) if sabah else None,
        "hedefler": _g_metin(lambda: __import__("pt_hedef").istem_metni(), "henüz belirlenmedi"),
    }


def koc_mesaji(kod=None):
    import claude_yaz
    kod = kod or hafta_kodu()
    v = hafta_verisi(kod)
    yanit = claude_yaz.sor(KOC_ISTEM.format(hafta=kod, veri=json.dumps(v, ensure_ascii=False, default=str)), model_adi="opus", zaman_asimi=600)
    j = claude_yaz.json_coz(yanit[yanit.rfind("{", 0, yanit.rfind('"degisecek"')) if '"degisecek"' in yanit else len(yanit):])
    metin = yanit
    if '"degisecek"' in yanit:
        metin = yanit[:yanit.rfind("{", 0, yanit.rfind('"degisecek"'))].strip().rstrip("`").rstrip()
        metin = re.sub(r"```(json)?\s*$", "", metin).strip()
    m = {"hafta": kod, "zaman": int(time.time()), "metin": metin, "degisecek": j.get("degisecek") or "", "plan_istegi": j.get("plan_istegi") or "",
         "veri": v}
    _yaz(MESAJLAR / f"{hafta_gecerli(kod)}.json", m)
    return m


def mesaj(kod):
    return _json(MESAJLAR / f"{hafta_gecerli(kod)}.json", {})


def son_mesaj():
    L = sorted(MESAJLAR.glob("*.json"))
    return _json(L[-1], {}) if L else {}

# ----------------------------------------------------------------------------- nabız bölgeleri, su, kafein, sesli mesaj, takvim dosyası


def nabiz_bolgeleri(p=None):
    """Tanaka (208 − 0,7 × yaş) en yüksek nabız; sabah nabzı biliniyorsa (Apple Sağlık, son 14 gün ortanca) Karvonen yöntemi."""
    p = p or profil()
    yas = p.get("yas")
    if not yas:
        return None
    mx = round(208 - 0.7 * yas)
    dinlenme = None
    try:
        import statistics
        import pt_saglik
        L = [x.get("nabiz") for x in (pt_saglik.gun((bugun() - dt.timedelta(days=i)).isoformat()) for i in range(14)) if x.get("nabiz")]
        dinlenme = round(statistics.median(L)) if len(L) >= 3 else None
    except Exception:  # noqa: BLE001
        pass
    def n(y):
        return round(dinlenme + y * (mx - dinlenme)) if dinlenme else round(y * mx)
    B = [("Z1", "Çok kolay", .5, .6), ("Z2", "Kolay · sohbet temposu", .6, .7), ("Z3", "Orta", .7, .8), ("Z4", "Zor · eşik", .8, .9), ("Z5", "Çok zor", .9, 1.0)]
    return {"en_yuksek": mx, "dinlenme": dinlenme, "yontem": "Karvonen" if dinlenme else "Tanaka",
            "bolgeler": [{"kod": k, "ad": a, "alt": n(lo), "ust": n(hi)} for k, a, lo, hi in B],
            "tempo": {"kolay": "Z2", "orta": "Z3", "aralik": "Z4", "tempo": "Z3"}}


def su_hedefi(p=None):
    p = p or profil()
    return min(3500, round(35 * float(p.get("kilo_kg") or 75) / 50) * 50)


def su_ekle(tarih, ml):
    return gun_degistir(tarih, lambda d: d.update(su_ml=max(0, int(d.get("su_ml") or 0) + int(ml))))


def kafein_ekle(tarih):
    return gun_degistir(tarih, lambda d: d.update(kafein=(d.get("kafein") or []) + [int(time.time())]))


def _md_duz(m):
    return re.sub(r"[#*_`>|]", "", re.sub(r"^\s*[-•]\s+", "", m or "", flags=re.M))


def mesaj_sesi(kod):
    """Haftalık mesajı koçun doğal Türkçe sesiyle (pt_ses, sinir ağı) m4a'ya çevirir; eski robotik 'say' sesi kullanılmaz."""
    import pt_ses
    m = mesaj(kod)
    if not m.get("metin"):
        return None
    return pt_ses.uzun_metin(_md_duz(m["metin"])[:8000], MESAJLAR / f"{kod}.m4a")


SAAT_VARSAYILAN = {"sabah": "07:30", "ogle": "12:30", "aksam": "18:30"}


def takvim_dosyasi(kod):
    """Haftanın planı .ics (iPhone takvimine eklemek için). Saat yoksa sabah/öğle/akşam varsayılanı."""
    pl = program(kod)
    p = profil()
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Video Hub//PT//TR", "CALSCALE:GREGORIAN", "X-WR-CALNAME:PT"]
    simdi = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for g in pl.get("gunler") or []:
        if g.get("tur") == "dinlenme":
            continue
        s = str(g.get("saat") or "")
        if not re.match(r"^\d\d:\d\d$", s):
            s = (p.get("bjj_ders") or {}).get("saat") if g.get("tur") == "bjj_ders" else SAAT_VARSAYILAN.get(s or p.get("antrenman_saati") or "sabah", "07:30")
        bas = dt.datetime.combine(dt.date.fromisoformat(g["tarih"]), dt.time.fromisoformat(s or "07:30"))
        bit = bas + dt.timedelta(minutes=int(g.get("sure_dk") or 45))
        aciklama = "\\n".join(f"{b.get('ad')}: " + ", ".join(h.get("ad") or h.get("kod") for h in b.get("hareketler") or []) for b in g.get("bolumler") or [])
        L += ["BEGIN:VEVENT", f"UID:pt-{g.get('id')}@videohub", f"DTSTAMP:{simdi}", f"DTSTART:{bas.strftime('%Y%m%dT%H%M%S')}",
              f"DTEND:{bit.strftime('%Y%m%dT%H%M%S')}", f"SUMMARY:PT · {(g.get('baslik') or g.get('tur') or '').replace(',', '\\,')}",
              f"DESCRIPTION:{aciklama[:900].replace(',', '\\,')}", "BEGIN:VALARM", "TRIGGER:-PT10M", "ACTION:DISPLAY", "DESCRIPTION:PT", "END:VALARM", "END:VEVENT"]
    L.append("END:VCALENDAR")
    return "\r\n".join(L) + "\r\n"


# ----------------------------------------------------------------------------- dışa aktarma


def disa_aktar():
    """Bütün PT verisi tek JSON (videolar hariç)."""
    d = {"surum": "pt@1", "zaman": int(time.time()), "profil": profil(), "testler": testler(), "ilerleme": ilerleme(),
         "program": {p.stem: _json(p, {}) for p in sorted(PROGRAM.glob("*.json"))},
         "gunluk": {p.stem: _json(p, {}) for p in sorted(GUNLUK.glob("*.json"))},
         "mesajlar": {p.stem: _json(p, {}) for p in sorted(MESAJLAR.glob("*.json"))},
         "hareketler": {p.parent.name: _json(p, {}) for p in sorted(HAREKETLER.glob("*/bilgi.json"))}}
    try:
        import pt_beslenme
        d["beslenme"] = pt_beslenme.durum_dosyasi()
    except Exception:  # noqa: BLE001
        pass
    return d


if __name__ == "__main__":
    import sys
    a = sys.argv[1:]
    if a[:1] == ["plan"]:
        print(json.dumps(program_uret(a[1] if len(a) > 1 else None), ensure_ascii=False, indent=1)[:3000])
    elif a[:1] == ["mesaj"]:
        print(koc_mesaji(a[1] if len(a) > 1 else None)["metin"])
    else:
        print(json.dumps({"profil": profil(), "tarama": tarama_durumu(), "katalog": len(katalog())}, ensure_ascii=False, indent=1))

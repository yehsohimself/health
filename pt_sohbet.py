"""pt_sohbet.py - PT ile konuşma (2026-10-25). "Bugün dizim ağrıyor", "Bu hafta Hamburg'dayım" → PT önce seçenekli sorar (gerekirse), sonra planda
yapacağı değişikliği ÖNERİR; kullanıcı onaylayınca uygulanır (kurallar yine kodda). Geçmiş pt/sohbet.json (son 60 mesaj).

Eylem türleri: bugun (bugünü uyarla: vakit, yer, ışık, ağrı), hafta (haftayı yeniden yaz, istekle), tasi (seansı başka güne), profil (ekipman/sakatlık/
hassasiyet ekle ya da çıkar), not (kalıcı not), dinlenme (bugünü dinlenme yap).
"""
import datetime as dt
import json
import time

import pt

DOSYA = pt.VERI / "sohbet.json"

ISTEM = """Sen PT'sin: kişisel antrenör + diyetisyen + fizyoterapist bilgisiyle çalışan, kısa ve net konuşan bir koç. Türkçe, "siz" dili, en çok 3 cümle.
Kullanıcı sana bir durum söyledi. Görevin: (a) durumu anlamak için gerekiyorsa TEK seçenekli soru sormak, (b) yeterince biliyorsan planda yapacağın
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
  "soru": null ya da {{"soru": "...", "secenekler": ["3-5 kısa, aynı düzeyde seçenek"]}},
  "eylem": null ya da {{"tur": "bugun|hafta|tasi|profil|not|dinlenme", "aciklama": "kullanıcıya tek cümle: ne değişecek",
     "vakit_dk": sayı|null, "nerede": "ev|park|salon|yolda"|null, "isik": "yesil|sari|kirmizi"|null, "agri": [{{"bolge": "{bolgeler}", "puan": 0-10}}],
     "istek": "hafta için yönlendirme cümlesi", "id": "taşınacak seans id", "tarih": "YYYY-MM-DD",
     "ekle": {{"ekipman": [], "sakatliklar": [], "hassasiyetler": []}}, "cikar": {{"ekipman": [], "sakatliklar": [], "hassasiyetler": []}}, "not": "..."}}}}
Soru sorarken eylem null olsun. Değişiklik gerekmiyorsa eylem null, yalnız yanıt.
Alanları yalnız ilgili türde doldur: bugun → vakit_dk/nerede/isik/agri; hafta → istek; tasi → id/tarih; profil → ekle/cikar (hassasiyetler = GIDA
hassasiyeti, ağrı ya da sakatlık değil; ağrı sakatliklar'a); not → not."""


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
    g = "\n".join(f"{'Kullanıcı' if m['kim'] == 'siz' else 'PT'}: {m['metin']}" for m in son)
    c = claude_yaz.sor_json(ISTEM.format(gecmis=g, **baglam()), model_adi="sonnet", zaman_asimi=300)
    cevap = {"kim": "pt", "metin": str(c.get("yanit") or "")[:800], "t": int(time.time())}
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
                    s["isik"], s["neden"] = "kirmizi", ["PT ile konuşma: dinlenme"]
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
                    s["neden"] = (s.get("neden") or []) + ["PT ile konuşma"]
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
            pt.profil_kaydet({"notlar": (p.get("notlar") or []) + [{"soru": "PT ile konuşma", "metin": e.get("not") or m.get("metin")}]})
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

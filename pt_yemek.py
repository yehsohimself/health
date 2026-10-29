"""pt_yemek.py - Haftalık menü, alışveriş listesi, ürünler (barkod ve etiket) (2026-10-25).

- Menü (`plan_uret`, sonnet ~1 dk): 7 gün × öğün sayısı, yeme penceresine sığar; antrenman günleri biraz daha fazla, dinlenme günleri daha az kalori;
  her öğünde protein; hassasiyetler kesin hariç (kodla ikinci kontrol), sevmedikleri yok, beslenme tarzı (vejetaryen...) uyulur; Türk ev yemekleri +
  kişinin konumundaki marketler; aile boyu pişen yemeğin kalanı ertesi günün öğünü (artan). Alışveriş listesi reyon sırasıyla; işaretlenenler dosyada.
  pt/yemek_plani/<hafta>.json.
- Ürünler (pt/urunler.json): barkod → Open Food Facts v3 (100 g değerleri, kaynak "barkod"); etiket fotoğrafı → Claude besin tablosunu okur (kaynak
  "etiket"); fotoğrafta yalnız barkod rakamları varsa onları okuyup barkoda gider.
"""
import json
import re
import time

import requests

import pt
import pt_beslenme

KLASOR = pt.VERI / "yemek_plani"
URUNLER = pt.VERI / "urunler.json"
REYONLAR = ["Meyve ve sebze", "Et, tavuk, balık", "Süt ürünleri ve yumurta", "Ekmek ve fırın", "Kuru gıda, bakliyat, tahıl", "Konserve ve sos",
            "Donuk", "Yağ, baharat", "İçecek", "Diğer"]

PLAN_ISTEM = """Sen bir spor diyetisyenisin. {hafta} haftası için gün gün yemek planı yaz. Türkçe.

KİŞİ: {kisi}
GÜNLÜK HEDEF: yaklaşık {kcal} kcal, en az {protein} g protein. Antrenman günlerinde +%10 kalori (fazlası karbonhidrattan), dinlenme günlerinde -%10.
YEME PENCERESİ: {pencere}. Öğün sayısı: {ogun}. Orucu proteinli bir öğünle açtır; antrenman pencere içindeyse sonraki öğün en proteinli olsun.
ANTRENMAN GÜNLERİ: {antrenman}
HASSASİYETLER (KESİNLİKLE kullanma, içinde geçen ürünler dahil): {hassasiyet}
SEVMEDİKLERİ (kullanma): {sevmedik}
BESLENME TARZI: {diyet}
ALIŞKANLIKLARI (kahvaltı, öğle, akşam, atıştırma, içecek, alkol, pişirme, dışarıda yeme, sevdikleri): {aliskanlik}
SAĞLIK NOTLARI (teşhis koyma; yalnız beslenmeyi buna uygun kur, ör. kolesterol yüksekse lif ve doymamış yağ artsın, doymuş/trans yağ azalsın): {saglik}
Kişinin alıştığı yemeklerden uzaklaşma; tanıdık yemekleri daha dengeli yap. Hafta içi hazırlık süresi ALIŞKANLIKLARI'ndaki pişirme süresini geçmesin.
MUTFAK: Türk ev yemekleri ağırlıklı, {market}. Hafta içi hazırlık ≤30 dk; hafta sonu daha uzun olabilir.
AKILLI PLAN: aile boyu pişen bir yemeğin kalanı ertesi günün bir öğünü olsun ("artan": true); aynı malzemeler hafta içinde tekrar kullanılsın (israf az);
aynı yemek haftada en çok 2 kez.

JSON:
{{"gunler": [{{"tarih": "YYYY-MM-DD", "antrenman": true|false, "ogunler": [{{"saat": "12:00", "ad": "...", "malzemeler": [{{"ad": "tavuk göğsü", "miktar": 150, "birim": "g"}}],
  "kcal": 0, "protein": 0, "yag": 0, "karb": 0, "hazirlik_dk": 0, "tarif": "1-3 cümle", "artan": false}}]}}],
 "alisveris": [{{"reyon": "{reyonlar}", "kalemler": [{{"ad": "...", "miktar": "..."}}]}}],
 "hazirlik": ["pazar günü önceden yapılabilecek 3-6 hazırlık işi (ör. 1 kg tavuğu marine et, bulguru haşla)"],
 "ipucu": "haftanın tek pratik ipucu"}}"""


def plan(kod=None):
    return pt._json(KLASOR / f"{pt.hafta_gecerli(kod or pt.hafta_kodu())}.json", {})


def plan_uret(kod=None):
    import claude_yaz
    kod = kod or pt.hafta_kodu()
    p = pt.profil()
    h = pt_beslenme.hedefler(p)
    b = p.get("beslenme") or {}
    pl = pt.program(kod)
    antr = ", ".join(f"{g['tarih']} {g.get('tur')}" + (f" ({g.get('saat')})" if g.get("saat") else "") for g in pl.get("gunler") or [] if g.get("tur") not in ("dinlenme",)) or "bilinmiyor"
    pen = f"{h['pencere']['acilis']}-{h['pencere']['kapanis']}" if float(b.get("pencere_saat") or 14) < 14 else "pencere yok"
    c = claude_yaz.sor_json(PLAN_ISTEM.format(market=pt.market_notu(p),
        hafta=kod, kisi=json.dumps({k: p.get(k) for k in ("cinsiyet", "yas", "kilo_kg", "hedef_kilo_kg", "hedefler", "ek_bilgi")}, ensure_ascii=False),
        kcal=h["kcal"] or 2000, protein=h["protein"] or 140, pencere=pen, ogun=b.get("ogun_sayisi") or 2, antrenman=antr,
        hassasiyet=", ".join(b.get("hassasiyetler") or []) or "yok", sevmedik=", ".join(b.get("sevmedikleri") or []) or "yok",
        diyet=pt_beslenme.DIYET_AD.get(p.get("diyet") or "", "kısıtlama yok"), reyonlar="|".join(REYONLAR),
        aliskanlik=json.dumps(p.get("beslenme_aliskanlik") or {}, ensure_ascii=False) or "bilinmiyor",
        saglik="; ".join([*(p.get("sinirlar") or []), *[f"{x.get('ad')}: {x.get('deger')} {x.get('birim', '')}" for x in p.get("saglik_degerleri") or []]]) or "yok"),
        model_adi="sonnet", zaman_asimi=600)
    hass = [x.lower() for x in b.get("hassasiyetler") or [] if x]
    for g in c.get("gunler") or []:
        for o in g.get("ogunler") or []:
            o["uyari"] = [m.get("ad") for m in o.get("malzemeler") or [] if any(x in str(m.get("ad", "")).lower() for x in hass)]
    for r in c.get("alisveris") or []:
        for k in r.get("kalemler") or []:
            k["id"] = re.sub(r"\W+", "_", f"{r.get('reyon')}_{k.get('ad')}".lower())[:60]
    c["alisveris"] = sorted(c.get("alisveris") or [], key=lambda r: REYONLAR.index(r["reyon"]) if r.get("reyon") in REYONLAR else 99)
    d = {"hafta": kod, "zaman": int(time.time()), "hedef": {"kcal": h["kcal"], "protein": h["protein"]}, **c, "alindi": []}
    pt._yaz(KLASOR / f"{pt.hafta_gecerli(kod)}.json", d)
    return d


def alindi(kod, kid, durum):
    with pt._kilit:
        d = plan(kod)
        s = set(d.get("alindi") or [])
        (s.add if durum else s.discard)(kid)
        d["alindi"] = sorted(s)
        pt._yaz(KLASOR / f"{pt.hafta_gecerli(kod)}.json", d)
        return d["alindi"]


def ogun_kalemleri(o):
    """Plandaki öğünü 'yedim' kaydına çevirir (toplamı tek kalem; malzemeler not olarak)."""
    return [{"ad": o.get("ad") or "Öğün", "miktar_g": 0, **{a: float(o.get(a) or 0) for a in ("kcal", "protein", "yag", "karb")},
             "kaynak": "menü", "not": ", ".join(f"{m.get('miktar', '')} {m.get('birim', '')} {m.get('ad', '')}".strip() for m in o.get("malzemeler") or [])}]

# ----------------------------------------------------------------------------- ürünler


def urunler():
    return pt._json(URUNLER, {"liste": []})["liste"]


def _urun_kaydet(u):
    with pt._kilit:
        d = pt._json(URUNLER, {"liste": []})
        d["liste"] = [x for x in d["liste"] if not (x.get("barkod") and x.get("barkod") == u.get("barkod")) and x.get("ad") != u.get("ad")] + [u]
        pt._yaz(URUNLER, d)
    return u


def barkod(kod):
    kod = re.sub(r"\D", "", str(kod))
    if len(kod) < 8:
        raise ValueError("Barkod 8-14 rakam olmalı.")
    r = requests.get(f"https://world.openfoodfacts.org/api/v3/product/{kod}.json",
                     params={"fields": "product_name,product_name_de,product_name_tr,brands,nutriments,serving_size,allergens_tags"},
                     headers={"User-Agent": "VideoHub-PT/1.0 (kisisel kullanim)"}, timeout=20)
    d = r.json()
    p = d.get("product") or {}
    n = p.get("nutriments") or {}
    if not p or not n.get("energy-kcal_100g") and not n.get("proteins_100g"):
        return None
    u = {"ad": (p.get("product_name_tr") or p.get("product_name") or p.get("product_name_de") or kod)[:60], "marka": (p.get("brands") or "")[:40],
         "barkod": kod, "kaynak": "barkod (Open Food Facts)",
         "100g": {"kcal": n.get("energy-kcal_100g"), "protein": n.get("proteins_100g"), "yag": n.get("fat_100g"), "karb": n.get("carbohydrates_100g")},
         "alerjen": [a.split(":")[-1] for a in p.get("allergens_tags") or []], "t": int(time.time())}
    return _urun_kaydet(u)


ETIKET_ISTEM = """Bu bir gıda ambalajının fotoğrafı. İki şeyden birini oku:
(1) Besin değerleri tablosu varsa 100 g (ya da 100 ml) başına değerleri ve ürünün adını; içindekiler listesi görünüyorsa alerjenleri.
(2) Tablo yoksa ve barkod rakamları okunuyorsa yalnızca barkodu.
Uydurma: okuyamadığın değeri null yaz.
JSON: {"ad": "...", "marka": "...", "100g": {"kcal": null, "protein": null, "yag": null, "karb": null}, "alerjen": [], "barkod": null}"""


def etiket(resim):
    import claude_yaz
    c = claude_yaz.json_coz(claude_yaz.sor_gorsel(ETIKET_ISTEM, [resim], model_adi="sonnet", zaman_asimi=300))
    if not c:
        raise ValueError("Etiket okunamadı.")
    yuz = c.get("100g") or {}
    if not any(yuz.get(a) for a in ("kcal", "protein")) and c.get("barkod"):
        u = barkod(c["barkod"])
        if u:
            return u
        raise ValueError("Barkod okundu ama Open Food Facts'te yok; besin tablosunun fotoğrafını çekin.")
    u = {"ad": str(c.get("ad") or "Ürün")[:60], "marka": str(c.get("marka") or "")[:40], "barkod": c.get("barkod"), "kaynak": "etiket fotoğrafı",
         "100g": {a: yuz.get(a) for a in ("kcal", "protein", "yag", "karb")}, "alerjen": c.get("alerjen") or [], "t": int(time.time())}
    return _urun_kaydet(u)


def urun_kalemi(u, gram):
    g = float(gram or 100)
    return {"ad": u["ad"], "miktar_g": g, **{a: round(float((u.get("100g") or {}).get(a) or 0) * g / 100, 1) for a in ("kcal", "protein", "yag", "karb")},
            "kaynak": u.get("kaynak")}


def hassasiyet_uyarisi(u):
    hass = [x.lower() for x in (pt.profil().get("beslenme") or {}).get("hassasiyetler") or []]
    es = {"laktoz": ["milk", "süt", "lactose", "laktoz"], "gluten": ["gluten", "wheat", "buğday"], "fıstık": ["peanuts", "fıstık"],
          "kuruyemiş": ["nuts", "kuruyemiş", "fındık"], "yumurta": ["eggs", "yumurta"], "deniz ürünü": ["fish", "crustaceans", "molluscs", "balık"],
          "soya": ["soybeans", "soya"]}
    al = " ".join(u.get("alerjen") or []).lower()
    return [h for h in hass if any(k in al for k in es.get(h, [h]))]


DEGISTIR_ISTEM = """Sen bir diyetisyensin. Bu öğünü aynı kalori (±%10) ve protein (±10 g) değerinde başka bir öğünle değiştir. Kişinin isteği: {istek}.
Hassasiyetler (KULLANMA): {hassasiyet}. Beslenme tarzı: {diyet}. Türk ev yemekleri, {market}.
ESKİ ÖĞÜN: {eski}
JSON: {{"saat": "...", "ad": "...", "malzemeler": [{{"ad", "miktar", "birim"}}], "kcal", "protein", "yag", "karb", "hazirlik_dk", "tarif": "1-3 cümle", "artan": false}}"""


def ogun_degistir(kod, tarih, i, istek=""):
    import claude_yaz
    p = pt.profil()
    with pt._kilit:
        d = plan(kod)
        g = next((x for x in d.get("gunler") or [] if x.get("tarih") == tarih), None)
        eski = (g or {}).get("ogunler", [])[int(i)]
    c = claude_yaz.sor_json(DEGISTIR_ISTEM.format(market=pt.market_notu(p), istek=istek or "başka bir şey", hassasiyet=", ".join((p.get("beslenme") or {}).get("hassasiyetler") or []) or "yok",
                                                  diyet=pt_beslenme.DIYET_AD.get(p.get("diyet") or "", "kısıtlama yok"), eski=json.dumps(eski, ensure_ascii=False)),
                            model_adi="sonnet", zaman_asimi=180)
    if not c.get("ad"):
        raise ValueError("Yeni öğün yazılamadı.")
    hass = [x.lower() for x in (p.get("beslenme") or {}).get("hassasiyetler") or [] if x]
    c["uyari"] = [m.get("ad") for m in c.get("malzemeler") or [] if any(x in str(m.get("ad", "")).lower() for x in hass)]
    c["saat"] = c.get("saat") or eski.get("saat")
    with pt._kilit:
        d = plan(kod)
        g = next((x for x in d.get("gunler") or [] if x.get("tarih") == tarih), None)
        g["ogunler"][int(i)] = {**c, "degisti": True}
        pt._yaz(KLASOR / f"{pt.hafta_gecerli(kod)}.json", d)
    return c

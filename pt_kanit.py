"""pt_kanit.py - PT'nin kanıt dosyası ve aylık güncelleme önerisi (2026-10-25). Video Hub'ın gelişim deseni: sistem kendini DEĞİŞTİRMEZ, öneri getirir.

- KANIT: her kuralın dayanağı, yılı ve güven derecesi (araştırma raporu reports/PT özellik araştırması.md; "doğrulanmadı" olanlar düşük).
- Aylık tarama: PubMed E-utilities (anahtarsız; son 35 gün, konu başına en çok 8 makale, özetler) → Claude (sonnet) hangisinin bir kuralı değiştirmesi
  gerektiğini söyler (en çok 5 öneri, PMID ile). Kullanıcı onaylarsa öneri "onaylanan bulgu" olarak plan ve koç istemlerine girer.
  pt/kanit.json: {oneriler: [{id, kanit, oneri, neden, guven, pmid, baslik, durum}], son_tarama}.
"""
import json
import time

import requests

import pt

DOSYA = pt.VERI / "kanit.json"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

KANIT = [
    {"id": "protein", "kural": "Protein kilo başına 1,6-2,2 g (fazla kiloluysa hedef kiloya göre); günlük toplam, dağılımdan önemli.", "kaynak": "ISSN görüş bildirgesi (Aragon ve ark.)", "yil": 2026, "guven": "orta", "not": "Makalenin kendisi değil haber özeti okundu."},
    {"id": "tre", "kural": "18/6 bir uyum aracı; kalori eşitken sürekli kısıtlamadan üstün değil. Kuvvet antrenmanıyla yağsız kütle korunuyor.", "kaynak": "Meta-analiz, PubMed 41687432", "yil": 2026, "guven": "orta", "not": "18/6'ya özel deney yok; 16/8 ve 20/4'ten aktarım."},
    {"id": "tre_protein", "kural": "Asıl risk proteini eksik yemek; orucu proteinle açmak.", "kaynak": "TREAT deneyi (Lowe ve ark.)", "yil": 2020, "guven": "orta", "not": "Antrenmansız 16:8'de kaybın %65'i yağsız kütle."},
    {"id": "kilo_hizi", "kural": "Haftada vücut ağırlığının %0,5-1'i; yağ oranı düştükçe yavaş.", "kaynak": "Helms ve ark.", "yil": 2014, "guven": "dusuk", "not": "Bu oturumda yeniden doğrulanmadı."},
    {"id": "rir", "kural": "Yükü RIR/RPE ile ayarlamak sabit yüzdelerden belirgin üstün değil; vücut ağırlığında pratik ölçü.", "kaynak": "Sports Med Open", "yil": 2021, "guven": "orta", "not": "Kanıt çelişkili."},
    {"id": "deload", "kural": "Hafif hafta: yorgunluğu atmak için bilerek azaltılmış dönem; sıklığı bilinmiyor (PT: 5. hafta ya da yorgunluk).", "kaynak": "Delphi uzlaşısı (Bell ve ark.)", "yil": 2023, "guven": "dusuk", "not": "Sıklık koç alışkanlığı."},
    {"id": "agri", "kural": "Ağrı izleme: hareket sırasında ≤5/10, ertesi sabah eski düzey, haftadan haftaya artmıyor.", "kaynak": "Aşil tendinopatisi çalışması (Silbernagel)", "yil": 2007, "guven": "orta", "not": "Klinik muayenenin yerini tutmaz."},
    {"id": "fms", "kural": "Hareket taraması sakatlık öngörmez; başlangıç basamağını seçmek için kullanılır.", "kaynak": "Dorrel ve ark.", "yil": 2015, "guven": "yuksek", "not": "Duyarlılık %24,7."},
    {"id": "eger_ise", "kural": "Eğer-ise planları fiziksel aktiviteyi küçük ama güvenilir biçimde artırır (0,24-0,31).", "kaynak": "Meta-analiz (McMaster özeti)", "yil": 2014, "guven": "orta", "not": ""},
    {"id": "aliskanlik", "kural": "Alışkanlık ortanca 59-66 günde oturur (aralık 4-335).", "kaynak": "Singh ve ark.", "yil": 2024, "guven": "orta", "not": ""},
    {"id": "tarti", "kural": "Haftada bir tartılmak her gün tartılmak kadar etkili; hesap sorma etkiyi artırır.", "kaynak": "Madigan ve ark.", "yil": 2016, "guven": "orta", "not": ""},
    {"id": "uyku", "kural": "En etkili uyku müdahalesi uykuyu uzatmak.", "kaynak": "Lang ve ark.", "yil": 2022, "guven": "dusuk", "not": "İncelemeye 2 çalışma girebilmiş."},
    {"id": "srpe", "kural": "Seans zorluğu × dakika (sRPE) farklı sporlarda yükü ölçmek için geçerli, BJJ dahil.", "kaynak": "Haddad ve ark.", "yil": 2017, "guven": "yuksek", "not": ""},
    {"id": "birlikte", "kural": "Kuvvet + dayanıklılık birlikte: yalnız erkeklerde alt vücut kuvvetinde küçük kayıp.", "kaynak": "Schumann ve ark. (59 çalışma)", "yil": 2024, "guven": "orta", "not": "Ağır bacak ile uzun/sert bisikleti ayır."},
    {"id": "hrv", "kural": "Hazır olma: 7 günlük HRV ortalaması, 60 günlük ortalama ± 0,5 SS aralığının altındaysa toparlanma.", "kaynak": "HRV4Training", "yil": 2024, "guven": "dusuk", "not": "Üretici yöntemi."},
    {"id": "foto", "kural": "Fotoğrafla kalori tahmini yaklaşık üçte bir eksik, en çok yağı kaçırır; fotoğraf + cümle + yağ sorusu.", "kaynak": "Bağımsız test, 102 öğün", "yil": 2026, "guven": "orta", "not": ""},
]
SORGULAR = ["resistance training hypertrophy trained", "time-restricted eating resistance training lean mass", "protein intake muscle energy deficit",
            "concurrent training interference cycling", "tendinopathy load management pain monitoring", "calisthenics bodyweight training",
            "Brazilian jiu-jitsu training load", "sleep extension athletes performance", "deload resistance training", "heart rate variability guided training"]

ISTEM = """Sen spor bilimi kanıtlarını izleyen bir editörsün. PT'nin kuralları ve dayanakları aşağıda. Son ayın PubMed makaleleri (başlık + özet) ekte.
Görev: yalnızca bir kuralı DEĞİŞTİRMEYİ, inceltmeyi ya da güvenini yükseltip düşürmeyi gerektiren makaleleri seç. Tek küçük çalışma, hayvan ya da
hücre çalışması, kullanıcıyla ilgisiz popülasyon (hastalar, yaşlılar, elit kadın kürekçiler...) tek başına kural değiştirmez; sistematik derleme,
meta-analiz, görüş bildirgesi, büyük RKÇ ağırlıklı. Hiçbiri yeterli değilse boş liste. Türkçe, sade dil.

KURALLAR:
{kurallar}

ONAYLANMIŞ ÖNCEKİ GÜNCELLEMELER:
{onayli}

MAKALELER:
{makaleler}

JSON: {{"oneriler": [{{"kanit": "kural id ya da yeni", "oneri": "kural şöyle değişsin (tek cümle)", "neden": "makale ne buldu (tek cümle)",
"guven": "yuksek|orta|dusuk", "pmid": "...", "baslik": "..."}}]}}  (en çok 5)"""


def durum():
    return pt._json(DOSYA, {"oneriler": [], "son_tarama": 0})


def _yaz(d):
    pt._yaz(DOSYA, d)


def onayli_bulgular():
    return [o for o in durum()["oneriler"] if o.get("durum") == "kabul"]


def onayli_metin():
    L = onayli_bulgular()
    return "\n".join(f"- {o['oneri']} ({o.get('baslik', '')[:80]}, PMID {o.get('pmid')})" for o in L[-10:]) or "yok"


def _pubmed(sorgu, gun=35, n=8):
    r = requests.get(f"{EUTILS}/esearch.fcgi", params={"db": "pubmed", "term": sorgu, "reldate": gun, "datetype": "edat", "retmax": n, "retmode": "json",
                                                        "sort": "relevance", "tool": "videohub-pt"}, timeout=30)
    return r.json().get("esearchresult", {}).get("idlist", [])


def _ozetler(idler):
    if not idler:
        return []
    r = requests.get(f"{EUTILS}/efetch.fcgi", params={"db": "pubmed", "id": ",".join(idler), "rettype": "abstract", "retmode": "xml", "tool": "videohub-pt"}, timeout=60)
    import xml.etree.ElementTree as ET
    out = []
    for a in ET.fromstring(r.content).iter("PubmedArticle"):
        pmid = a.findtext(".//PMID")
        baslik = "".join(a.find(".//ArticleTitle").itertext()) if a.find(".//ArticleTitle") is not None else ""
        ozet = " ".join("".join(x.itertext()) for x in a.iter("AbstractText"))
        tur = [x.text for x in a.iter("PublicationType")]
        out.append({"pmid": pmid, "baslik": baslik[:300], "tur": tur, "ozet": ozet[:1400]})
    return out


def tara():
    import claude_yaz
    idler = []
    for s in SORGULAR:
        try:
            idler += [i for i in _pubmed(s) if i not in idler]
        except Exception:  # noqa: BLE001
            continue
        time.sleep(0.4)                                      # NCBI: anahtarsız saniyede 3 istek
    makaleler = []
    for i in range(0, len(idler), 20):
        try:
            makaleler += _ozetler(idler[i:i + 20])
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.4)
    with pt._kilit:                                          # önce yaz: Claude düşse de ay dolmadan yeniden denenmez
        d = durum()
        d["son_tarama"] = int(time.time())
        d["son_makale"] = len(makaleler)
        _yaz(d)
    c = {}
    if makaleler:
        c = claude_yaz.sor_json(ISTEM.format(kurallar="\n".join(f"- {k['id']}: {k['kural']} [{k['kaynak']} {k['yil']}, güven {k['guven']}]" for k in KANIT),
                                             onayli=onayli_metin(),
                                             makaleler="\n\n".join(f"PMID {m['pmid']} ({', '.join(m['tur'][:2])}): {m['baslik']}\n{m['ozet']}" for m in makaleler)),
                                model_adi="sonnet", zaman_asimi=600)
    with pt._kilit:                                          # uzun çağrı sırasında verilen kararlar kaybolmasın: yeniden oku
        d = durum()
        var = {o.get("pmid") for o in d["oneriler"]}
        for o in (c.get("oneriler") or [])[:5]:
            if o.get("pmid") in var or not o.get("oneri"):
                continue
            d["oneriler"].append({**{k: str(o.get(k) or "")[:400] for k in ("kanit", "oneri", "neden", "guven", "pmid", "baslik")},
                                  "id": f"k{int(time.time() * 1000)}{len(d['oneriler'])}", "durum": "bekliyor", "tarih": pt.bugun().isoformat()})
        _yaz(d)
    return d


def karar(oid, kabul):
    d = durum()
    for o in d["oneriler"]:
        if o["id"] == oid:
            o["durum"] = "kabul" if kabul else "red"
            o["karar_tarih"] = pt.bugun().isoformat()
    _yaz(d)
    return d

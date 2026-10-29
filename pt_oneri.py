"""pt_oneri.py - PT'nin önerileri: sıradaki program ve "şuna ihtiyacınız var" (2026-10-27; kullanıcı: "spor programı önerme, ihtiyaç önerme, tüm
tarafları geliştir"; araştırma: reports/PT yeni özellik taraması.md).

İlkeler (araştırmadan): tek seferde tek öneri ve tek cümlelik neden (rakipler çoğunlukla yalnız puan ya da ısı haritası gösteriyor); program yalnız
karar anlarında önerilir (etkin program yokken, program bitince, yeni test sonucunda); ihtiyaçlar kurallarla ve kişinin kendi kayıtlarından çıkar,
günde en çok bir tanesi Bugün'de görünür; "Sonra" 7 gün, "Bana göre değil" kalıcı susturur. Sıklık kişinin elinde (her gün | haftada bir | kapalı).
Ekipman satış önerisi değil, "bu, yolunuzdaki şu basamağı açar" diye söylenir. Teşhis yok: ağrı ve tahlil önerileri yalnız "uzmana / doktora danışın".
Kayıt pt/oneriler.json {gizli: {kod: bitiş_ts | 0=kalıcı}, ret: [{kod, neden, t}], siklik, son_gosterim: {tarih: kod}}.
"""
import datetime as dt
import statistics
import time

import pt

DOSYA = pt.VERI / "oneriler.json"
SONRA_GUN = 7


def _durum():
    return pt._json(DOSYA, {"gizli": {}, "ret": [], "siklik": "gunluk", "son_gosterim": {}})


def _yaz(d):
    pt._yaz(DOSYA, d)


def gizli_mi(kod, d=None):
    d = d or _durum()
    g = (d.get("gizli") or {}).get(kod)
    return g is not None and (g == 0 or g > time.time())


def kapat(kod, nasil="sonra", neden=""):
    with pt._kilit:
        d = _durum()
        d.setdefault("gizli", {})[kod] = 0 if nasil == "kalici" else int(time.time() + SONRA_GUN * 86400)
        if nasil == "kalici":
            d["ret"] = (d.get("ret") or [])[-60:] + [{"kod": kod, "neden": neden, "t": int(time.time())}]
        _yaz(d)


def siklik_ayarla(s):
    if s not in ("gunluk", "haftalik", "kapali"):
        raise ValueError("Sıklık gunluk, haftalik ya da kapali olmalı.")
    with pt._kilit:
        d = _durum()
        d["siklik"] = s
        _yaz(d)

# ----------------------------------------------------------------------------- program önerisi


def _son_test():
    k = pt.testler().get("kayitlar") or []
    return k[-1]["sonuclar"] if k else {}


def _ek(p, kelime):
    return any(kelime in (str(x.get("cevap") or "") + " " + str(x.get("soru") or "")).lower() for x in p.get("ek_bilgi") or [])


def program_onerileri(n=3):
    """Her programa puan ve gerekçe: hedef beceriler, test sonuçları, hedef türleri, yöntemler, iş düzeni. Etkin olan ve son 60 günde biten çıkar."""
    import pt_programlar as PR
    p = pt.profil()
    t = _son_test()
    beceri = set(p.get("beceri_hedefleri") or [])
    tur = set(p.get("hedef_turleri") or [])
    yon = p.get("yontemler") or {}
    var = set(p.get("ekipman") or [])
    a = PR.aktif()
    biten = {x.get("kod"): x.get("tarih") for x in p.get("program_biten") or []}
    bugun = pt.bugun()

    def sayi(k):
        try:
            return float(t.get(k))
        except (TypeError, ValueError):
            return None
    barfiks, hollow = sayi("barfiks_max"), sayi("hollow_sn")
    derin, omuz = str(t.get("derin_squat") or ""), str(t.get("omuz_duvar") or "")
    out = []
    for x in PR.PROGRAMLAR:
        k = x["kod"]
        if a and a["kod"] == k:
            continue
        if biten.get(k) and (bugun - dt.date.fromisoformat(biten[k])).days < 60:
            continue
        puan, neden = 0, []
        if k == "ilk_barfiks" and beceri & {"barfiks", "muscle_up", "front_lever"}:
            puan += 3
            if barfiks is not None and barfiks < 3:
                puan += 3; neden.append(f"testte {int(barfiks)} barfiks çıktınız; muscle-up ve front lever yolu da buradan geçiyor")
            else:
                neden.append("barfiks, muscle-up ve front lever hedeflerinizin temeli")
        if k == "amut_yolu" and "serbest_amut" in beceri:
            puan += 4; neden.append("serbest amut hedefiniz var")
            if "Değmiyor" in omuz:
                puan -= 2; neden.append("ama önce omuz açıklığı gerekiyor (duvar testi)")
        if k == "pistol_yolu" and "pistol" in beceri:
            puan += 4; neden.append("pistol squat hedefiniz var")
            if derin in ("Zor", "Yapamıyorum"):
                puan -= 2; neden.append("derin squat testi zorlanıyor; hareketlilik önce")
        if k == "guclu_govde" and (beceri & {"lsit", "front_lever"} or (hollow is not None and hollow < 30)):
            puan += 3; neden.append(f"hollow tutuşunuz {int(hollow)} sn; L-sit ve front lever güçlü gövde ister" if hollow is not None else "L-sit ve front lever güçlü gövde ister")
        if k == "hareketlilik_14":
            if derin in ("Zor", "Yapamıyorum"):
                puan += 3; neden.append("derin squat testinde zorlandınız")
            if "Değmiyor" in omuz:
                puan += 3; neden.append("duvarda kollar testinde başparmaklar değmedi; amut için omuz açılmalı")
            if "hareket" in tur:
                puan += 1; neden.append("esneklik hedeflerinizden biri")
        if k == "temel" and (p.get("deneyim") in ("yeni", "baslangic") or not t):
            puan += 3; neden.append("dört temel zinciri sağlam kurmak sonraki her hedefi hızlandırır")
        if k == "minder_kondisyonu" and (yon.get("bjj_solo") or (p.get("bjj_ders") or {}).get("gunler")):
            puan += 3; neden.append("jiu-jitsu yapıyorsunuz; raunt kondisyonu ve kaçışlar")
        if k == "masa_basi" and _ek(p, "masa"):
            puan += 2; neden.append("gününüzün çoğu masa başında geçiyor")
        eksik = [e for e in x["ekipman"] if e not in var]
        if eksik:
            puan -= 1
        if puan <= 0:
            continue
        out.append({"kod": k, "ad": x["ad"], "alt": x["alt"], "hafta": x["hafta"], "gun": x["gun"], "puan": puan,
                    "neden": "; ".join(neden[:2]).capitalize() + ".", "eksik_ekipman": [pt.EKIPMANLAR.get(e, e) for e in eksik]})
    out.sort(key=lambda o: -o["puan"])
    return out[:n]

# ----------------------------------------------------------------------------- ihtiyaçlar


def _gunluk(n):
    return pt.gunler(n)


def _ekipman_ihtiyaci(p):
    """Hedef becerilerin şimdiki ve sonraki iki basamağında eksik ekipman → hangi yolları açtığı."""
    kat = pt.katalog()
    acar = {}
    for b in pt.beceriler():
        for z in b["zincirler"]:
            B = z["basamaklar"]
            i = next((n for n, s in enumerate(B) if s["durum"] == "simdi"), 0)
            for s in B[i:i + 3]:
                if s["ekipman_yok"]:
                    acar.setdefault(kat[s["kod"]]["ekipman"], set()).add(b["ad"])
    out = []
    for e, hedefler in acar.items():
        ad = pt.EKIPMANLAR.get(e, e)
        out.append({"kod": f"ekipman_{e}", "tur": "ekipman", "oncelik": 70 + 5 * len(hedefler), "baslik": ad,
                    "neden": f"{', '.join(sorted(hedefler))} yolunuzun sıradaki basamakları {ad.lower()} ister; şimdilik ekipmansız karşılıklarıyla ilerliyorsunuz.",
                    "eylem": {"tur": "ekipman", "kod": e, "ad": "Bende var"}})
    return out


def _protein_lif(p, G):
    import pt_beslenme
    h = pt_beslenme.hedefler(p)
    kayitli = [g for g in G[:7] if len(g.get("yemekler") or []) >= 1 and not g.get("eksik_kayit") and g["tarih"] != pt.bugun().isoformat()]
    if len(kayitli) < 3:
        return []
    T = [pt_beslenme.gun_toplam(g) for g in kayitli]
    out = []
    pr = statistics.mean(x["protein"] for x in T)
    if h.get("protein") and pr < 0.8 * h["protein"]:
        out.append({"kod": "protein", "tur": "beslenme", "oncelik": 60, "baslik": "Protein az",
                    "neden": f"Son {len(T)} günün ortalaması {round(pr)} g, hedefiniz {h['protein']} g. Kas tutmak için orucu proteinle açın.",
                    "eylem": {"tur": "oneri", "ad": "Bugün ne yesem?"}})
    lifler = [x["lif"] for x in T if x.get("lif")]
    if h.get("kolesterol") and len(lifler) >= 3 and statistics.mean(lifler) < 0.7 * h["lif"]:
        out.append({"kod": "lif", "tur": "beslenme", "oncelik": 55, "baslik": "Lif az",
                    "neden": f"Ortalama {round(statistics.mean(lifler))} g lif, en az {h['lif']} g olmalı. Kolesterol için yulaf, baklagil ve sebze lifi en etkili adım.",
                    "eylem": {"tur": "oneri", "ad": "Lifli öneri al"}})
    return out


def _uyku(G):
    import pt_saglik
    deg = []
    for i in range(7):
        g = (pt.bugun() - dt.timedelta(days=i)).isoformat()
        u = pt._json(pt_saglik.KLASOR / f"{g}.json", {}).get("uyku_saat")
        if not u:
            u = next((((x.get("sabah") or {}).get("uyku_saat")) for x in G if x["tarih"] == g), None)
        if u:
            deg.append(float(u))
    if len(deg) >= 4 and statistics.mean(deg) < 6.5:
        return [{"kod": "uyku", "tur": "toparlanma", "oncelik": 75, "baslik": "Uyku kısa",
                 "neden": f"Son {len(deg)} gecenin ortalaması {str(round(statistics.mean(deg), 1)).replace('.', ',')} saat. 7 saatin altı güç artışını ve iştahı bozar; "
                          "bu hafta yatış saatini 30 dakika öne alın.", "eylem": {"tur": "sohbet", "ad": "Uyku düzenimi konuşalım"}}]
    return []


def _agri(G):
    from collections import Counter
    c = Counter()
    for g in G[:14]:
        bol = {a.get("bolge") for a in (g.get("agri") or []) if (a.get("puan") or 0) >= 3}
        bol |= {a.get("bolge") for a in ((g.get("sabah") or {}).get("agri") or []) if (a.get("puan") or 0) >= 3}
        c.update(b for b in bol if b)
    return [{"kod": f"agri_{b}", "tur": "saglik", "oncelik": 90, "baslik": f"{b.capitalize()} ağrısı tekrarlıyor",
             "neden": f"Son iki haftada {n} gün {b} ağrısı kaydettiniz. PT o bölgeyi kolay basamakta tutuyor; geçmiyorsa bir fizyoterapiste görünün.",
             "eylem": {"tur": "sohbet", "ad": "PT'ye anlat"}} for b, n in c.items() if n >= 3]


def ihtiyaclar():
    """Kurallarla bulunan ihtiyaçlar, önceliğe göre. Susturulanlar hariç."""
    p = pt.profil()
    G = _gunluk(21)
    out = []
    out += _agri(G)
    try:
        y = pt.yorgunluk_durumu()
        if y.get("durum") == "yorgun":
            out.append({"kod": "hafif_hafta", "tur": "toparlanma", "oncelik": 85, "baslik": "Hafif hafta zamanı",
                        "neden": y.get("metin") or "Yorgunluk kondisyonunuzun belirgin üstünde.", "eylem": {"tur": "plan", "ad": "Bu haftayı hafiflet",
                                                                                                               "istek": "Bu hafta hafif hafta olsun."}})
    except Exception:  # noqa: BLE001
        pass
    out += _uyku(G)
    gunler_ = [g["tarih"] for g in G if any(x.get("bitti") for x in g.get("seanslar") or [])]
    if gunler_ and (pt.bugun() - dt.date.fromisoformat(max(gunler_))).days >= 10:
        ara = (pt.bugun() - dt.date.fromisoformat(max(gunler_))).days
        out.append({"kod": "geri_donus", "tur": "toparlanma", "oncelik": 88, "baslik": f"{ara} gündür antrenman yok",
                    "neden": "Aradan sonra ilk hafta yaklaşık yarı yükle, ikinci hafta üçte iki yükle dönmek sakatlığı önler. Kaçırılanı telafi etmeye çalışmayın.",
                    "eylem": {"tur": "plan", "ad": "Dönüş haftası yaz", "istek": f"{ara} günlük aradan dönüyorum; bu hafta yarı yükle başlat."}})
    if pt.test_gerekli():
        ilk = not pt.testler().get("kayitlar")
        out.append({"kod": "test", "tur": "olcum", "oncelik": 95 if ilk else 65, "baslik": "Başlangıç testi" if ilk else "Yeniden test zamanı",
                    "neden": "Her yolda hangi basamaktan başlayacağınızı test belirler." if ilk else "Son testten 5 hafta geçti; ilerlemenizi görmek ve basamakları güncellemek için.",
                    "eylem": {"tur": "test", "ad": "Teste başla"}})
    t = _son_test()
    if "Değmiyor" in str(t.get("omuz_duvar") or "") and "serbest_amut" in (p.get("beceri_hedefleri") or []):
        out.append({"kod": "omuz_acikligi", "tur": "hareketlilik", "oncelik": 58, "baslik": "Omuz açıklığı amutu kısıtlıyor",
                    "neden": "Duvar testinde kollar duvara değmedi; amutta bel çukurlaşır. Günde 5 dakika omuz açılımı birkaç haftada farkı kapatır.",
                    "eylem": {"tur": "hizli", "odak": "mobilite", "dk": 10, "ad": "10 dk omuz ve göğüs açılımı"}})
    if str(t.get("derin_squat") or "") in ("Zor", "Yapamıyorum") and (p.get("beceri_hedefleri") or []):
        out.append({"kod": "kalca_bilek", "tur": "hareketlilik", "oncelik": 54, "baslik": "Derin squat zorlanıyor",
                    "neden": "Topuklar yerde derin squat pistol ve bacak zincirinin anahtarı; ayak bileği ve kalça açılımı ekleyin.",
                    "eylem": {"tur": "hizli", "odak": "mobilite", "dk": 10, "ad": "10 dk kalça ve ayak bileği"}})
    out += _ekipman_ihtiyaci(p)
    out += _protein_lif(p, G)
    if p.get("hedef_kilo_kg") and not any(g.get("kilo") for g in G[:7]):
        out.append({"kod": "tarti", "tur": "olcum", "oncelik": 40, "baslik": "Bir haftadır tartılmadınız",
                    "neden": "Hedefiniz, kilo ortalamanızın gidişine göre ayarlanıyor; haftada 3-4 sabah tartılmak yeter.", "eylem": {"tur": "kilo", "ad": "Kilomu gir"}})
    metin = " ".join(p.get("sinirlar") or []).lower()
    sd = p.get("saglik_degerleri") or {}
    if "kolesterol" in metin and not sd:
        out.append({"kod": "tahlil_lipid", "tur": "saglik", "oncelik": 35, "baslik": "Kolesterol değerleriniz",
                    "neden": "Kolesterolünüzün yüksek olduğunu yazdınız ama değerler PT'de yok. Son tahlil değerlerini girerseniz menü ona göre ayarlanır; "
                             "uzun süredir bakılmadıysa doktorunuza sorun.", "eylem": {"tur": "diyetisyen", "ad": "Değerleri gir"}})
    d = _durum()
    out = [o for o in out if not gizli_mi(o["kod"], d)]
    out.sort(key=lambda o: -o["oncelik"])
    return out


def bugun_icin():
    """Bugün'de gösterilecek tek öneri: önce ihtiyaç; etkin program yoksa en uygun program. Sıklık ayarına uyar."""
    d = _durum()
    s = d.get("siklik") or "gunluk"
    if s == "kapali":
        return None
    t = pt.bugun().isoformat()
    if s == "haftalik":
        son = [g for g in (d.get("son_gosterim") or {}) if g != t]
        if son and (pt.bugun() - dt.date.fromisoformat(max(son))).days < 7:
            return None
    I = ihtiyaclar()
    sec = None
    if I:
        sec = {"tip": "ihtiyac", **I[0]}
    else:
        import pt_programlar as PR
        if not PR.aktif():
            P = [x for x in program_onerileri(3) if not gizli_mi("program_" + x["kod"], d)]
            if P:
                sec = {"tip": "program", "kod": "program_" + P[0]["kod"], "program": P[0], "alternatif": P[1:3]}
    if sec and (d.get("son_gosterim") or {}).get(t) != sec["kod"]:
        with pt._kilit:
            d = _durum()
            d.setdefault("son_gosterim", {})[t] = sec["kod"]
            d["son_gosterim"] = dict(sorted(d["son_gosterim"].items())[-30:])
            _yaz(d)
    return sec


def hepsi():
    return {"ihtiyaclar": ihtiyaclar(), "programlar": program_onerileri(3), "siklik": _durum().get("siklik") or "gunluk"}


if __name__ == "__main__":
    import json
    print(json.dumps(hepsi(), ensure_ascii=False, indent=1))

"""pt_programlar.py - hazır çok haftalı programlar (2026-10-27; Nike Training Club'ın programları gibi: "İlk barfiks · 6 hafta").

Program bir hedef ve hafta hafta odak demektir; seansın kendisi kodla kurulur (pt_hizli, kişinin şu anki basamakları ve ekipmanıyla), program
zincirleri vurgulanır (öne alınır, bir set fazlası). Etkin program haftalık plana da not olarak girer (pt.program_uret → `plan_notu`), Claude
programın günlerini haftaya yerleştirir. İlerleme günlüklerden sayılır: `program` alanı bu programın kodu olan biten seanslar, katılma anından beri.
Etkin program profilde: `program_aktif` {kod, bas}; bitenler `program_biten` [{kod, tarih}].
"""
import datetime as dt

import pt

# hafta: (başlık, hızlı antrenman odağı, dakika, vurgulanan zincirler, not)
PROGRAMLAR = [
    {"kod": "ilk_barfiks", "ad": "İlk barfiks", "alt": "Ters kürekten tam barfikse", "hafta": 6, "gun": 3, "seviye": "Başlangıç", "gorsel": "barfiks",
     "ekipman": ["bar"], "hedef": "Tek seferde en az bir temiz barfiks.",
     "haftalar": [("Asılma ve kürek", "ust", 25, ["cekme"], "Aktif asılma ve ters kürekle kavrama ve kürek kemiği gücü."),
                  ("Negatife giriş", "ust", 25, ["cekme"], "Yavaş iniş: 3-5 saniyede in."),
                  ("Hacim", "ust", 30, ["cekme", "govde"], "Setler artar, dinlenme kısalır."),
                  ("Güç", "ust", 30, ["cekme"], "Negatifler 5 saniye, ilk tam deneme."),
                  ("Hafif hafta", "ust", 20, ["cekme"], "Toparlanma; teknik temiz kalsın."),
                  ("Deneme haftası", "ust", 30, ["cekme"], "Haftanın son seansında barfiks testi.")]},
    {"kod": "amut_yolu", "ad": "Amut yolu", "alt": "Duvar yürüyüşünden serbest amuta", "hafta": 6, "gun": 3, "seviye": "Orta", "gorsel": "duvar_yuruyus",
     "ekipman": [], "hedef": "Duvara dayanmadan 10 saniye amut.",
     "haftalar": [("Bilek ve omuz", "ust", 20, ["amut", "amut_itme"], "Bilek hazırlığı ve pike şınav."),
                  ("Duvarda süre", "ust", 25, ["amut"], "Karın duvara amutta süreyi uzat."),
                  ("Denge", "ust", 25, ["amut", "govde"], "Duvardan ayağı kaldırma denemeleri."),
                  ("İtme gücü", "ust", 25, ["amut_itme", "amut"], "Duvarda amut şınavına giriş."),
                  ("Hafif hafta", "mobilite", 15, [], "Omuz ve bilek açılımı."),
                  ("Serbest denemeler", "ust", 25, ["amut"], "Her seansta kısa serbest denemeler.")]},
    {"kod": "temel", "ad": "Kalistenik temeli", "alt": "İtme, çekme, bacak ve gövde", "hafta": 4, "gun": 3, "seviye": "Başlangıç", "gorsel": "squat",
     "ekipman": [], "hedef": "Dört temel zincirde birer basamak yukarı.",
     "haftalar": [("Hareketleri öğren", "tum", 25, ["itme", "bacak"], "Form önce; zorluk 6-7."),
                  ("Hacim", "tum", 30, ["itme", "cekme", "bacak"], "Setler artar."),
                  ("Yoğunluk", "tum", 35, ["itme", "bacak", "govde"], "Aralığın üstüne çık, basamak atla."),
                  ("Toparla ve ölç", "tum", 25, [], "Hafif hafta; sonunda testleri yenile.")]},
    {"kod": "pistol_yolu", "ad": "Pistol yolu", "alt": "Squattan tek bacak squata", "hafta": 6, "gun": 2, "seviye": "Orta", "gorsel": "pistol",
     "ekipman": [], "hedef": "Her bacakta bir pistol squat.",
     "haftalar": [("Bilek ve kalça", "alt", 25, ["bacak"], "Derin squat tutuşu ve squat hacmi."),
                  ("Tek bacak", "alt", 25, ["bacak", "kalca"], "Bulgar squat."),
                  ("Kontrol", "alt", 30, ["bacak"], "Karides squat'a giriş."),
                  ("Güç", "alt", 30, ["bacak", "kalca"], "Karides squat hacmi."),
                  ("Hafif hafta", "mobilite", 15, [], "Ayak bileği ve kalça."),
                  ("Deneme", "alt", 30, ["bacak"], "Destekli ve serbest pistol denemeleri.")]},
    {"kod": "guclu_govde", "ad": "Güçlü gövde", "alt": "Hollow, plank ve asılı gövde", "hafta": 4, "gun": 3, "seviye": "Herkes için", "gorsel": "hollow",
     "ekipman": [], "hedef": "Hollow tutuşta 30 saniye.",
     "haftalar": [("Temel", "govde", 15, ["govde", "plank"], "Dead bug ve plank."), ("Süre", "govde", 15, ["govde"], "Tutuş süreleri uzar."),
                  ("Asılı gövde", "govde", 20, ["asili_govde", "govde"], "Barın varsa diz kaldırma."), ("L-sit'e giriş", "govde", 20, ["lsit", "govde"], "Tuck L-sit.")]},
    {"kod": "hareketlilik_14", "ad": "14 günlük hareketlilik", "alt": "Her gün 10 dakika", "hafta": 2, "gun": 7, "seviye": "Herkes için",
     "gorsel": "dunya_esneme", "ekipman": [], "hedef": "Derin squatta rahat oturmak, omuzlar serbest.",
     "haftalar": [("Kalça ve omurga", "mobilite", 10, [], "Her gün aynı saatte."), ("Omuz ve bilek", "mobilite", 10, [], "Süreler uzar.")]},
    {"kod": "minder_kondisyonu", "ad": "Minder kondisyonu", "alt": "BJJ için kondisyon ve kaçışlar", "hafta": 4, "gun": 2, "seviye": "Orta",
     "gorsel": "sprawl", "ekipman": [], "hedef": "Altı dakikalık rauntlarda nefes kesilmesin.",
     "haftalar": [("Kaçışlar", "bjj", 20, [], "Karides ve köprü."), ("Tabata", "kondisyon", 20, [], "20/10 aralıklar."),
                  ("Akış", "bjj", 25, [], "Gölge güreş ve kalkış."), ("Raunt", "kondisyon", 25, [], "Daha uzun bloklar.")]},
    {"kod": "masa_basi", "ad": "Masa başı sırt ve kalça", "alt": "Uzun oturmaya karşı 15 dakika", "hafta": 3, "gun": 4, "seviye": "Herkes için",
     "gorsel": "kalca_kopru", "ekipman": [], "hedef": "Sırtı ve kalçayı rahatlatmak.",
     "haftalar": [("Açılım", "mobilite", 15, [], "Kalça ve göğüs omurgası."), ("Kalça gücü", "alt", 15, ["kalca"], "Kalça köprüsü."),
                  ("Duruş", "tum", 15, ["kalca", "cekme"], "Kürek kemiği ve kalça birlikte.")]},
]
P = {p["kod"]: p for p in PROGRAMLAR}


def aktif():
    a = pt.profil().get("program_aktif") or {}
    return a if a.get("kod") in P else None


def _seanslar(kod, bas):
    out = []
    for f in sorted(pt.GUNLUK.glob("*.json")):
        if f.stem < bas:
            continue
        for s in pt._json(f, {}).get("seanslar") or []:
            if s.get("bitti") and s.get("program") == kod:
                out.append({"tarih": f.stem, "sure_dk": s.get("sure_dk"), "hafta": s.get("program_hafta")})
    return out


def durum(kod, a=None):
    p = P[kod]
    a = a or {}
    bas = a.get("bas") or pt.bugun().isoformat()
    S = _seanslar(kod, bas) if a else []
    toplam = p["hafta"] * p["gun"]
    yapilan = min(len(S), toplam)
    hafta_i = min(p["hafta"] - 1, yapilan // p["gun"]) if a else 0
    gecen_gun = (pt.bugun() - dt.date.fromisoformat(bas)).days if a else 0
    return {"yapilan": yapilan, "toplam": toplam, "hafta": hafta_i + 1, "bu_hafta": yapilan - hafta_i * p["gun"] if a else 0,
            "gecen_gun": gecen_gun, "bitti": yapilan >= toplam, "seanslar": S[-12:]}


def liste():
    p = pt.profil()
    a = aktif()
    var = set(p.get("ekipman") or [])
    biten = {x.get("kod"): x.get("tarih") for x in p.get("program_biten") or []}
    out = []
    for x in PROGRAMLAR:
        d = {k: x[k] for k in ("kod", "ad", "alt", "hafta", "gun", "seviye", "gorsel", "hedef")}
        d["haftalar"] = [{"baslik": h[0], "odak": h[1], "dk": h[2], "not": h[4]} for h in x["haftalar"]]
        d["eksik_ekipman"] = [e for e in x["ekipman"] if e not in var]
        d["biten"] = biten.get(x["kod"])
        if a and a["kod"] == x["kod"]:
            d["aktif"] = True
            d["bas"] = a.get("bas")
            d["durum"] = durum(x["kod"], a)
        out.append(d)
    return {"programlar": out, "aktif": a["kod"] if a else None}


def sec(kod):
    if kod not in P:
        raise ValueError("Böyle bir program yok.")
    pt.profil_kaydet({"program_aktif": {"kod": kod, "bas": pt.bugun().isoformat()}})
    return liste()


def birak():
    pt.profil_kaydet({"program_aktif": None})
    return liste()


def bugunku_seans(nerede="ev"):
    """Etkin programın bu haftaki seansı (pt_hizli ile, program zincirleri vurgulu)."""
    import pt_hizli
    a = aktif()
    if not a:
        raise ValueError("Etkin program yok.")
    p, d = P[a["kod"]], durum(a["kod"], a)
    baslik, odak, dk, vurgu, notu = p["haftalar"][d["hafta"] - 1]
    s = pt_hizli.olustur(dk, odak, nerede, tohum=d["yapilan"] + 1, vurgu=vurgu)
    s.update(baslik=f"{p['ad']} · {d['hafta']}. hafta", aciklama=f"{baslik}. {notu}", program=p["kod"], program_hafta=d["hafta"],
             neden=f"{d['yapilan'] + 1}. seans / {d['toplam']}", hizli=False, id=f"program_{p['kod']}")
    return s


def tamamla_kontrol():
    """Seans kaydından sonra: program bittiyse bitenlere yazar ve etkin programı kapatır. Döner: biten programın adı ya da None."""
    a = aktif()
    if not a or not durum(a["kod"], a)["bitti"]:
        return None
    p = pt.profil()
    biten = [x for x in p.get("program_biten") or [] if x.get("kod") != a["kod"]] + [{"kod": a["kod"], "tarih": pt.bugun().isoformat()}]
    pt.profil_kaydet({"program_biten": biten, "program_aktif": None})
    return P[a["kod"]]["ad"]


def plan_notu(hafta_kodu=None):
    """Haftalık plan istemine: etkin program ve bu haftanın odağı."""
    a = aktif()
    if not a:
        return ""
    p, d = P[a["kod"]], durum(a["kod"], a)
    baslik, odak, dk, vurgu, notu = p["haftalar"][d["hafta"] - 1]
    return (f"Kullanıcı '{p['ad']}' programında ({d['hafta']}/{p['hafta']}. hafta: {baslik}; {notu}). Bu hafta {p['gun']} gün programın seansını "
            f"(yaklaşık {dk} dk, vurgu: {', '.join(vurgu) or odak}) diğer antrenmanlarla çakışmayacak günlere koy; hedef: {p['hedef']}")

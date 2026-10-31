"""pt_yeniden.py - Programı bugünden baştan başlatmak (2026-10-31; kullanıcı: "programa baştan başlamak da isteyebilirim. Şu an bir program
öyle başlamış gidiyor; ben onu yapmıyorum, öyle devam ediyor").

Baştan başlamak hiçbir kaydı silmez (günlükler, testler, seri geçmişi kalır). Değişen yalnız "saatler": bugünden itibaren
- ilk hafta yolu birinci adımdan,
- etkin hedeflerin süresi (4 hafta / 3 ay / 1 yıl) ve başlangıç ölçümü bugünden,
- 14 günlük ara kontrol sayacı bugünden (`program_baslangic`),
- etkin hazır program bugünden,
- bu haftanın planı bugünden itibaren yeniden yazılır (eski plan geçmişe kaldırılır), gelecek haftanın planı sıfırlanır.
Önceki durumun kopyası pt/.yedek/bastan_<zaman>/ altına alınır. Program ilerlemiyorsa (`durgun`) Bugün'de kendisi önerir.
"""
import datetime as dt
import shutil
import time

import pt

KAYIT = pt.VERI / "yeniden.json"


def son_baslangic():
    """Programın sayılmaya başladığı gün: son 'baştan başla' ya da kurulum."""
    t = pt.profil().get("program_baslangic")
    try:
        return dt.date.fromisoformat(t) if t else None
    except ValueError:
        return None


def _yedekle():
    hedef = pt.VERI / ".yedek" / f"bastan_{time.strftime('%Y%m%d_%H%M%S')}"
    hedef.mkdir(parents=True, exist_ok=True)
    for ad in ("profil.json", "ilk_hafta.json", "hedefler.json", "recete.json"):
        if (pt.VERI / ad).exists():
            shutil.copy2(pt.VERI / ad, hedef / ad)
    if pt.PROGRAM.exists():
        (hedef / "program").mkdir(exist_ok=True)
        for f in pt.PROGRAM.glob("*.json"):
            shutil.copy2(f, hedef / "program" / f.name)
    return hedef


def _hedefleri_kaydir(bugun):
    import pt_hedef
    d = pt_hedef._oku()
    n = 0
    T = pt_hedef._son_test()
    for h in d.get("hedefler") or []:
        if h.get("durum") != "aktif":
            continue
        h["bas"] = bugun.isoformat()
        h["son"] = (bugun + dt.timedelta(days=pt_hedef.VADE_GUN.get(h.get("vade"), 28))).isoformat()
        o = h.get("olcu") or {}
        if o.get("tur") == "kilo":
            k = pt_hedef._kilo(pt.profil())
            if k:
                o["baslangic"] = round(k, 1)
        elif o.get("tur") == "test" and o.get("kod") in T:
            o["baslangic"] = T[o["kod"]][1]
        elif o.get("tur") in ("seans", "seri", "dk", "doz"):
            o["baslangic"] = 0
        h["yeniden"] = bugun.isoformat()
        n += 1
    pt_hedef._yaz(d)
    return n


def _planlari_kaldir(bugun):
    """Bu ve gelecek haftanın planını geçmişe kaldırır (geri alınabilir); bugünden önceki günler zaten geçmişte kalır."""
    (pt.PROGRAM / "gecmis").mkdir(parents=True, exist_ok=True)
    kodlar = [pt.hafta_kodu(bugun), pt.hafta_kodu(bugun + dt.timedelta(days=7))]
    for kod in kodlar:
        yol = pt.program_yolu(kod)
        if yol.exists():
            eski = pt._json(yol, {})
            shutil.move(str(yol), str(pt.PROGRAM / "gecmis" / f"{kod}_{eski.get('olusturma', int(time.time()))}_bastan.json"))
    return kodlar[0]


def yeniden_basla(neden=""):
    """Programı bugünden baştan başlatır. Döner: {tarih, yedek, hedef, hafta}. Planı yazmayı çağıran başlatır (Claude, arka planda)."""
    bugun = pt.bugun()
    yedek = _yedekle()
    pt.profil_kaydet({"program_baslangic": bugun.isoformat()})
    ilk = pt.baslangic_durumu().get("tur") in ("alisma", "donus")
    if ilk:                                                      # henüz alışmamış ya da uzun ara vermiş: ilk hafta yolu birinci adımdan
        pt._yaz(pt.VERI / "ilk_hafta.json", {"bas": bugun.isoformat(), "tamam": [], "birakti": False})
    hedef = _hedefleri_kaydir(bugun)
    a = pt.profil().get("program_aktif")
    if isinstance(a, dict) and a.get("kod"):
        pt.profil_kaydet({"program_aktif": {**a, "bas": bugun.isoformat()}})
    hafta = _planlari_kaldir(bugun)
    k = pt._json(KAYIT, {"olaylar": []})
    k["olaylar"] = ([{"tarih": bugun.isoformat(), "t": int(time.time()), "yedek": yedek.name, "neden": str(neden)[:200]}] + k["olaylar"])[:20]
    k.pop("ertele", None)
    pt._yaz(KAYIT, k)
    return {"tarih": bugun.isoformat(), "yedek": yedek.name, "hedef": hedef, "hafta": hafta, "ilk_hafta": ilk}


def durgun():
    """Program ilerlemiyor mu? Kurulumdan (ya da son baştan başlamadan) en az 4 gün geçmiş, son 5 günde hiç seans bitmemiş,
    bu sürede en az 2 plan günü geçip gitmişse önerilir. Kişi 'kaldığım yerden' derse 7 gün sorulmaz."""
    p = pt.profil()
    if not p.get("kuruldu"):
        return None
    bugun = pt.bugun()
    k = pt._json(KAYIT, {"olaylar": []})
    try:
        if k.get("ertele") and dt.date.fromisoformat(k["ertele"]) > bugun:
            return None
    except ValueError:
        pass
    bas = son_baslangic()
    if not bas:
        g = sorted(f.stem for f in pt.GUNLUK.glob("*.json") if len(f.stem) == 10)
        try:
            bas = dt.date.fromisoformat(g[0]) if g else None
        except ValueError:
            bas = None
    if not bas or (bugun - bas).days < 4:
        return None
    son_seans = None
    for d in pt.gunler(60):
        if any(s.get("bitti") for s in d.get("seanslar") or []):
            son_seans = d.get("tarih")
            break
    if son_seans and (bugun - dt.date.fromisoformat(son_seans)).days < 5:
        return None
    kacan = 0
    for i in range(1, 8):
        g = bugun - dt.timedelta(days=i)
        if g < bas:
            break
        pl = pt.program(pt.hafta_kodu(g))
        kacan += sum(1 for x in pl.get("gunler") or [] if x.get("tarih") == g.isoformat() and x.get("tur") not in ("dinlenme",) and not x.get("bitti"))
    if kacan < 2:
        return None
    gun = (bugun - (dt.date.fromisoformat(son_seans) if son_seans else bas)).days
    return {"gun": gun, "kacan": kacan, "hic": son_seans is None, "bas": bas.isoformat()}


def ertele(gun=7):
    k = pt._json(KAYIT, {"olaylar": []})
    k["ertele"] = (pt.bugun() + dt.timedelta(days=gun)).isoformat()
    pt._yaz(KAYIT, k)

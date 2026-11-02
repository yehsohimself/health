"""pt_site.py - Health'in site uçları (2026-10-25). sunucu/10_sayfalar.py'den `pt_site.kaydet(app)`; sayfa static/pt.html (port 8771).

Uzun işler (haftalık plan, koç mesajı, video işleme) iş parçacığında; durum `calisan` içinde (yeniden başlatma bekler: mesgul()).
Arka plan döngüsü (10 dk): pazar 18.00'den sonra haftanın koç mesajı + gelecek haftanın planı; yeni haftaya plansız girilmişse plan; her gün harcama
tahmini güncellenir.
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path

from flask import Response, abort, jsonify, request, send_file

import pt
import pt_beslenme
import pt_hareket
import pt_koc
import pt_oyun
import pt_rota

calisan = {}
sonuclar = {}
_kilit = threading.Lock()


def mesgul():
    return [f"Health: {a}" for k, a in list(calisan.items()) if k != "selam"]       # ilk söz kısa ve yeniden yazılabilir; beklenmez


def _arka(anahtar, ad, fn, *arg):
    def kos():
        try:
            sonuclar[anahtar] = {"ok": True, "sonuc": fn(*arg), "t": int(time.time())}
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            sonuclar[anahtar] = {"ok": False, "hata": str(e)[:300], "t": int(time.time())}
        finally:
            with _kilit:
                calisan.pop(anahtar, None)
    with _kilit:
        if anahtar in calisan:
            return False
        calisan[anahtar] = ad
        sonuclar.pop(anahtar, None)
    threading.Thread(target=kos, daemon=True).start()
    return True


def _yakinda_basarisiz(anahtar, saat=6):
    """Bu iş son `saat` saatte başarısız olduysa arka plan yeniden denemesin (2026-10-28: başarısız plan her 10 dk'da
    yeniden opus çağrısı başlatıyordu)."""
    r = sonuclar.get(anahtar) or {}
    return r.get("ok") is False and time.time() - (r.get("t") or 0) < saat * 3600


def _hafta_veri_var(kod):
    """Haftada en az bir biten seans ya da üç sabah kontrolü var mı (yoksa koç mesajı yazmaya değmez)."""
    seans = sabah = 0
    for g in pt.hafta_gunleri(kod):
        d = pt._json(pt.gun_yolu(g.isoformat()), {})
        seans += sum(1 for x in d.get("seanslar") or [] if x.get("bitti"))
        sabah += 1 if d.get("sabah") else 0
    return seans >= 1 or sabah >= 3


def _govde():
    return request.get_json(silent=True) or {}


def _tarih(t=None):
    """Verilmediyse bugün; verilmiş ama okunamıyorsa hata (2026-10-28: eskiden sessizce bugüne dönüyordu)."""
    t = t or request.args.get("tarih") or _govde().get("tarih")
    if not t:
        return pt.bugun().isoformat()
    return pt.tarih_gecerli(t)


def _sabah_temizle(s):
    """Sabah kontrolündeki sayılar sayı olsun (metin '5' ağrı puanı bir hafta boyunca /api/pt'yi çökertiyordu)."""
    s["enerji"] = pt.sayi(s.get("enerji"), 1, 5, 3)
    s["uyku_saat"] = pt.sayi(s.get("uyku_saat"), 0, 16)
    s["vakit_dk"] = pt.sayi(s.get("vakit_dk"), 0, 240)
    if s["vakit_dk"] is not None:
        s["vakit_dk"] = int(s["vakit_dk"])
    for k in ("agri", "dunku_agri"):
        L = s.get(k) if isinstance(s.get(k), list) else []
        s[k] = [{**a, "puan": int(pt.sayi(a.get("puan"), 0, 10, 0))} for a in L if isinstance(a, dict)]
    return s


def _program_ozet():
    """Bugün kartı için etkin programın kısa durumu."""
    import pt_programlar
    a = pt_programlar.aktif()
    if not a:
        return None
    p, d = pt_programlar.P[a["kod"]], pt_programlar.durum(a["kod"], a)
    h = p["haftalar"][d["hafta"] - 1]
    bugun_yapildi = any(x["tarih"] == pt.bugun().isoformat() for x in d["seanslar"])
    return {"kod": p["kod"], "ad": p["ad"], "gorsel": p["gorsel"], "hafta": d["hafta"], "hafta_toplam": p["hafta"], "yapilan": d["yapilan"],
            "toplam": d["toplam"], "bu_hafta": d["bu_hafta"], "gun": p["gun"], "baslik": h[0], "dk": h[2], "not": h[4], "bugun_yapildi": bugun_yapildi}


def _kas_ikonlari():
    import pt_kitaplik
    out = {}
    for k in pt_kart_kaslar():
        try:
            f = pt_kitaplik.kas_ikon(k)
        except Exception:  # noqa: BLE001
            f = None
        if f:
            out[k] = int(f.stat().st_mtime)
    return out


def pt_kart_kaslar():
    import pt_kart
    return pt_kart.KASLAR


def _g(fn, varsayilan=None):
    """Ana ekranın yan parçası hata verirse sayfanın tamamı düşmesin; hata kayda yazılır (2026-10-28)."""
    try:
        return fn()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return varsayilan


def _ilk_durum():
    import pt_ilk
    return pt_ilk.durum()


def pt_uzun_recete():
    import pt_uzun
    return pt_uzun.recete_oku()


def ozet():
    p = pt.profil()
    t = pt.bugun().isoformat()
    d = pt.gun(t)
    h = _g(lambda: pt_beslenme.hedefler(p), {})
    kod = pt.hafta_kodu()
    pl = pt.program(kod)
    return {
        "profil": p, "tarama": pt.tarama_durumu(p), "kurulu": bool(p.get("kuruldu")),
        "bugun": pt.gun_seansi(t), "gunluk": d, "beslenme": {"hedef": h, "toplam": pt_beslenme.gun_toplam(d), "son": pt_beslenme.son_ogunler(),
                                                             "oneri_pencere": pt_beslenme.pencere_onerisi(t)},
        "hafta": {"kod": kod, "gunler": [{k: g.get(k) for k in ("tarih", "tur", "baslik", "sure_dk", "id", "neden", "saat", "tasindi")} for g in pl.get("gunler") or []],
                  "not": pl.get("not"), "eger_ise": pl.get("eger_ise") or [], "hafif": pl.get("hafif"), "var": bool(pl),
                  "sonraki": pt.hafta_kodu(pt.hafta_gunleri(kod)[0] + dt.timedelta(days=7))},
        "seri": _g(pt.seri, 0), "test_gerekli": _g(pt.test_gerekli, False), "oneri": _oneri_guvenli(),
        "mesaj": _g(lambda: {k: v for k, v in pt.son_mesaj().items() if k != "veri"}, {}),
        "eksik_video": _g(lambda: pt_hareket.eksik_videolar()[:8], []), "calisan": dict(calisan), "koru": _g(pt.koru_bolgeler, []),
        "trend": _g(lambda: pt_beslenme.trend(60), []), "kurallar": pt.KURALLAR_METNI,
        "nabiz": _g(lambda: pt.nabiz_bolgeleri(p)), "su_hedef": _g(lambda: pt.su_hedefi(p), 2500),
        "oyun": _g(pt_oyun.ozet), "program_aktif": _g(_program_ozet), "baslangic": _g(pt.baslangic_durumu, {}), "ilk": _g(_ilk_durum, {}), "dun_ogun": _g(lambda: len(pt_beslenme.dunku_yemekler(t)["liste"]), 0), "agri_takip": _g(lambda: pt.agri_takip_bekleyen(t), []),
        "blok": _g(lambda: pt_koc.blok(kod, p)), "aliskanlik": _g(lambda: pt_koc.aliskanlik_bugun(t)), "ara_soru": _g(pt_koc.ara_soru),
        "kutlama": _g(lambda: pt_koc.kutlamalar(t), []),
        "gorusme_eksik": [g for g, alan in (("diyet", "beslenme_aliskanlik"), ("gun", "gun_duzeni")) if not p.get(alan)],
        "hedefler": _g(lambda: __import__("pt_hedef").ozet(), {"aktif": [], "var": False}),
        "kontrol": _g(lambda: __import__("pt_kontrol").ozet()["kontrol"], {}),
        "degerlendirme": _g(lambda: {**__import__("pt_kontrol").ozet()["degerlendirme"], "hazirlaniyor": "degerlendirme" in calisan}, {}),
        "akis": _g(lambda: pt_koc.gun_akisi(t)["akis"], []),
        "recete_var": _g(lambda: bool((__import__("pt_uzun").recete_oku() or {}).get("satirlar")), False),
        "durgun": _g(lambda: __import__("pt_yeniden").durgun()), "program_baslangic": p.get("program_baslangic"),
        "moduller": _g(lambda: __import__("pt_modul").gunun(t), []), "modul_olay": _g(lambda: __import__("pt_modul").son_olay()),
        "doz": _g(lambda: __import__("pt_uzun").doz_ozeti(kod), {}),
        "selam": _g(_selam),
        "hikaye": _g(lambda: __import__("pt_hikaye").bugun_karti()),
        "haftalik_gorusme": pt.bugun().weekday() >= 5 and pt._hafta_no(kod) > 1 and not (pt._json(pt.MESAJLAR / f"{kod}.gorusme.json", {}).get("cevaplar")),
    }


def _selam():
    """Health'in Bugün'deki ilk sözü. Önbellekte yoksa kural sözü döner ve Claude ile yazımı arka planda başlar."""
    import pt_sohbet
    s = pt_sohbet.selam(uret=False)
    if s.get("eski"):
        if not _yakinda_basarisiz("selam", 1):
            _arka("selam", "Health'in sözü yazılıyor", pt_sohbet.selam)
        s["yaziliyor"] = "selam" in calisan
    return s


GONDERILEN = pt.VERI / "push_gonderilen.json"
SABAH_SAAT = {"sabah": "07:30", "ogle": "10:30", "aksam": "15:00", "degisir": "08:30"}


def _bildirim_kontrol():
    """Hatırlatma (zil, varsa telefon): sabah kontrolü, pencere kapanmadan 30 dk, saati belli antrenmandan 10 dk önce. Gün başına tür başına bir kez."""
    import pt_push
    p = pt.profil()
    if not p.get("kuruldu"):
        return
    t = pt.bugun().isoformat()
    g = pt._json(GONDERILEN, {})
    gonderilen = set(g.get(t) or [])
    simdi = dt.datetime.now()
    hhmm = simdi.strftime("%H:%M")

    def gonder(tur, baslik, metin):
        if tur in gonderilen:
            return
        pt_push.gonder(baslik, metin, "/?u=pt", f"pt-{tur}")
        gonderilen.add(tur)
        pt._yaz(GONDERILEN, {t: sorted(gonderilen)})
    gs = pt.gun_seansi(t)
    planli = [s for s in gs["seanslar"] if s.get("tur") != "dinlenme" and not s.get("bitti")]
    if planli and not gs.get("sabah") and hhmm >= SABAH_SAAT.get(p.get("antrenman_saati") or "sabah", "07:30") and simdi.hour < 14:
        gonder("sabah", "Günaydın", f"Bugün: {planli[0].get('baslik') or 'antrenman'}. Dört kısa soruyla seansı size göre ayarlayayım.")
    pen = pt_beslenme.pencere_durumu(p, t)
    if pen["durum"] == "acik" and 0 < pen["kapanis_t"] - time.time() <= 1800:
        h = pt_beslenme.hedefler(p)
        top = pt_beslenme.gun_toplam(pt.gun(t))
        eksik = (h.get("protein") or 0) - top["protein"]
        gonder("pencere", "Yeme pencereniz 30 dakika sonra kapanıyor", f"Bugün {top['protein']} g protein kaydedildi" + (f"; {eksik} g eksik." if eksik > 10 else "."))
    gd = pt_koc.gun_duzeni(p)
    if not pt.gun(t).get("aksam") and hhmm >= pt_koc._saat(pt_koc._dk(gd["yatis"], "23:00") - 120) and simdi.hour >= 17:
        gonder("aksam", "Bugün nasıl geçti?", "Bir dakikalık akşam görüşmesi; yarını birlikte hazırlayalım.")
    if simdi.weekday() == 6 and simdi.hour >= 17 and not pt._json(pt.MESAJLAR / f"{pt.hafta_kodu()}.gorusme.json", {}).get("cevaplar"):
        gonder("pazar", "Haftalık görüşme", "Beş dakika: haftayı değerlendirelim, gelecek haftayı birlikte kuralım.")
    oy = pt_oyun.ozet()
    if oy["bugun"]["durum"] == "bekliyor" and oy["seri"] >= 2 and hhmm >= "20:30" and simdi.hour < 23:
        gonder("seri", f"Seriniz {oy['seri']} gün", ("Bugün 10 dakikalık kısa antrenman yeter." if oy["bugun"]["hedef"] == "seans"
                                                    else "Bugün dinlenme günü: bir dakikalık kontrol yeter.")
               + (f" Koruma: {oy['koruma']}." if oy["koruma"] else ""))
    for s in planli:
        if re.match(r"^\d\d:\d\d$", str(s.get("saat") or "")):
            bas = dt.datetime.combine(simdi.date(), dt.time.fromisoformat(s["saat"]))
            if 0 < (bas - simdi).total_seconds() <= 600:
                gonder(f"seans-{s.get('id')}", s.get("baslik") or "Antrenman", f"10 dakika sonra başlıyor ({s.get('sure_dk') or '?'} dk). Su ve havlu hazır mı?")


def _dongu():
    time.sleep(90)
    son_agir = 0
    while True:
        try:
            _bildirim_kontrol()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        if time.time() - son_agir < 600:
            time.sleep(120)
            continue
        son_agir = time.time()
        try:
            p = pt.profil()
            if p.get("kuruldu") and not pt.tarama_durumu(p)["bekliyor"]:
                simdi = dt.datetime.now()
                kod = pt.hafta_kodu()
                try:                                                            # Apple Sağlık: iCloud Drive'daki yeni dosyalar (10 dk'da bir)
                    import pt_saglik
                    pt_saglik.icloud_tara()
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
                if sonuclar.get("modul_gun") != pt.bugun().isoformat():         # modüller gidişata göre, günde bir (Claude gerekmez)
                    sonuclar["modul_gun"] = pt.bugun().isoformat()
                    try:
                        import pt_modul
                        pt_modul.guncelle()
                    except Exception:  # noqa: BLE001
                        traceback.print_exc()
                import claude_yaz
                if claude_yaz.hazir():
                    if not pt.program(kod) and "plan" not in calisan and not _yakinda_basarisiz("plan"):
                        _arka("plan", "haftalık plan yazılıyor", pt.program_uret, kod, "")
                    elif simdi.weekday() == 6 and simdi.hour >= 21 and not pt.mesaj(kod) and "mesaj" not in calisan \
                            and not _yakinda_basarisiz("mesaj") and not _hafta_veri_var(kod) and not sonuclar.get("bos_hafta_" + kod):
                        sonuclar["bos_hafta_" + kod] = {"ok": True, "t": int(time.time())}       # veri yoksa uzun mesaj yok; tek nazik cümle
                        sonraki = pt.hafta_kodu(pt.bugun() + dt.timedelta(days=1))
                        if not pt.program(sonraki):
                            _arka("plan", "gelecek hafta yazılıyor", pt.program_uret, sonraki,
                                  "Geçen hafta hiç antrenman kaydı yok. Bu hafta yeniden başlangıç: en çok 4 gün, her biri 10-15 dakika, kolay basamaklar.")
                        try:
                            import pt_push
                            pt_push.gonder("Bu hafta sizi görmedim", "Yarın 10 dakika deneyelim mi? Plan kısa seanslarla yeniden yazıldı.", "/?u=pt", "pt-mesaj")
                        except Exception:  # noqa: BLE001
                            pass
                    elif simdi.weekday() == 6 and simdi.hour >= 21 and not pt.mesaj(kod) and "mesaj" not in calisan \
                            and not _yakinda_basarisiz("mesaj") and _hafta_veri_var(kod):     # pazar görüşmesi yapılmadıysa
                        def hafta_sonu():
                            m = pt.koc_mesaji(kod)
                            sonraki = pt.hafta_kodu(pt.bugun() + dt.timedelta(days=1))
                            if not pt.program(sonraki):
                                pt.program_uret(sonraki, m.get("plan_istegi") or "")
                            try:
                                pt.mesaj_sesi(kod)
                            except Exception:  # noqa: BLE001
                                pass
                            try:
                                import pt_push
                                pt_push.gonder("Haftalık mesajınız hazır", m.get("degisecek") or "Geçen haftanın değerlendirmesi ve gelecek haftanın planı.", "/?u=pt", "pt-mesaj")
                            except Exception:  # noqa: BLE001
                                pass
                            return m
                        _arka("mesaj", "haftalık koç mesajı ve gelecek hafta", hafta_sonu)
                import pt_kontrol
                if claude_yaz.hazir():
                    if not pt_kontrol.degerlendirme_oku().get("mesaj") and "degerlendirme" not in calisan and not _yakinda_basarisiz("degerlendirme"):
                        _degerlendirme_baslat()                                              # kurulmuş ama değerlendirmesi hiç yazılmamış
                    z = pt_kontrol.zamani()
                    if z.get("zamani") and not z.get("acik") and "kontrol" not in calisan and not _yakinda_basarisiz("kontrol"):
                        def kontrol_hazirla():
                            k = pt_kontrol.hazirla()
                            try:
                                import pt_push
                                pt_push.gonder("Ara kontrol zamanı", "İki hafta doldu: üç dakikada programı gözden geçirelim.", "/?u=pt", "pt-kontrol")
                            except Exception:  # noqa: BLE001
                                pass
                            return {"tarih": k.get("tarih")}
                        _arka("kontrol", "ara kontrol hazırlanıyor", kontrol_hazirla)
                try:
                    import pt_hedef
                    pt_hedef.kendiliginden_tamamla()
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
                import pt_kanit
                if time.time() - (pt_kanit.durum().get("son_tarama") or 0) > 30 * 86400 and claude_yaz.arka_plan_uygun() and "kanit" not in calisan \
                        and not _yakinda_basarisiz("kanit", 72):
                    _arka("kanit", "yeni araştırmalar taranıyor", pt_kanit.tara)          # ayda bir
                b = pt_beslenme.durum_dosyasi()
                if not any(x.get("tarih") == pt.bugun().isoformat() for x in b.get("harcama_gecmis") or []):
                    pt_beslenme.harcama_guncelle()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        time.sleep(120)


def _degerlendirme_baslat(yenile=False):
    """Kurulumdan sonra: Health'in değerlendirmesi + üç vade için hedef önerisi (arka planda, tek iş)."""
    def kos():
        import pt_hedef
        import pt_kontrol
        d = pt_kontrol.degerlendirme(yenile=yenile)
        try:
            pt_hedef.oner(yenile=yenile)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        try:
            import pt_push
            pt_push.gonder("Değerlendirmeniz hazır", (d.get("antrenman") or {}).get("yaklasim") or "Sizi nasıl gördüğümü ve planı yazdım.", "/?u=pt", "pt-degerlendirme")
        except Exception:  # noqa: BLE001
            pass
        return {"zaman": d.get("zaman")}
    return _arka("degerlendirme", "değerlendirme yazılıyor", kos)


def _oneri_guvenli():
    try:
        import pt_oneri
        return pt_oneri.bugun_icin()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return None


def kaydet(app):
    for k in (pt.VERI, pt.PROGRAM, pt.GUNLUK, pt.MESAJLAR, pt.HAREKETLER):
        k.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=_dongu, daemon=True).start()

    @app.get("/api/pt")
    def pt_ozet():
        return jsonify(ozet())

    @app.get("/api/pt/katalog")
    def pt_katalog():
        kat = pt.katalog()
        il = pt.ilerleme()["hareketler"]
        import pt_kart
        import pt_youtube
        kartlar, yt = pt_kart.kartlar(), pt._json(pt_youtube.YOUTUBE, {})
        medya = pt.KLASOR / "pt_medya"
        for k, h in kat.items():
            h["hedef"] = pt.hedef(k, kat)
            h["aktif"] = bool((il.get(k) or {}).get("aktif"))
            if k in kartlar:
                h["kart"] = {a: kartlar[k].get(a) for a in ("adimlar", "hatalar", "hisset", "nefes", "kaslar")}
            kr = [n for n in (1, 2, 3) if (medya / k / f"k{n}.jpg").exists()]
            if kr:
                t = int((medya / k / "k1.jpg").stat().st_mtime)
                h["kareler"] = [{"b": f"/pt-medya/{k}/k{n}.jpg?t={t}", "k": f"/pt-medya/{k}/k{n}_k.jpg?t={t}"} for n in kr]
            if (medya / k / "anatomi.jpg").exists():
                t = int((medya / k / "anatomi.jpg").stat().st_mtime)
                h["anatomi"] = {"b": f"/pt-medya/{k}/anatomi.jpg?t={t}", "k": f"/pt-medya/{k}/anatomi_k.jpg?t={t}"}
            if k in yt:
                h["youtube"] = {a: yt[k].get(a) for a in ("id", "baslik", "kanal", "sure")}
        return jsonify({"katalog": kat, "ekipman": pt.EKIPMANLAR, "yontemler": pt.YONTEMLER, "bolgeler": pt.BOLGELER,
                        "bjj_pozisyon": pt.BJJ_POZISYONLAR, "bjj_bitiris": pt.BJJ_BITIRISLER, "testler": pt.TESTLER,
                        "tarama": pt.TARAMA_SORULARI, "uyari": pt.UYARI_BELIRTILERI, "bjj_drill": pt.BJJ_DRILL,
                        "form_hareketleri": list(__import__("pt_form").TUR), "kas_ad": pt_kart.KAS_AD,
                        "kas_gorsel": {f.stem: int(f.stat().st_mtime) for f in (medya / "_kas").glob("*.jpg")
                                       if not f.stem.endswith(("_ikon", "_govde", "_govde_k"))},
                        "kas_ikon": _kas_ikonlari(),
                        "kas_govde": {f.stem[:-8]: int(f.stat().st_mtime) for f in (medya / "_kas").glob("*_govde_k.jpg")}, "kaslar": pt_kart.KASLAR,
                        "ara_sorular": [k for k, _, _ in pt_koc.ARA_SORULAR]})

    # ---------------------------------------------------------------- tanışma, profil, tarama
    @app.post("/api/pt/tanisma")
    def pt_tanisma():
        metin = str(_govde().get("metin") or "").strip()
        if len(metin) < 20:
            return jsonify({"hata": "Biraz daha anlatın: hedefiniz, yaptığınız sporlar, ekipmanınız, sakatlıklar, beslenme."}), 400
        try:
            return jsonify(pt.tanisma_coz(metin))
        except Exception as e:  # noqa: BLE001
            return jsonify({"hata": f"Okuyamadım: {str(e)[:160]}"}), 502

    @app.post("/api/pt/ek-sorular")
    def pt_ek_sorular():
        g = _govde()
        try:
            return jsonify(pt.ek_sorular(g.get("profil") or {}, g.get("notlar") or [], [str(x)[:200] for x in g.get("sorulanlar") or []]))
        except Exception as e:  # noqa: BLE001
            return jsonify({"profil": {}, "sorular": [], "hata": str(e)[:160]})

    @app.post("/api/pt/profil")
    def pt_profil():
        g = _govde()
        p = pt.profil_kaydet(g)
        if g.get("konum_ad") and not (g.get("konum") or {}).get("lat"):
            try:
                k = pt_rota.konum_bul(g["konum_ad"])
                if k:
                    p = pt.profil_kaydet({"konum": k})
            except Exception:  # noqa: BLE001
                pass
        return jsonify({"profil": p, "tarama": pt.tarama_durumu(p)})

    @app.post("/api/pt/tarama")
    def pt_tarama():
        g = _govde()
        ek = {}
        if "cevaplar" in g:
            ek["tarama"] = {k: bool(v) for k, v in (g.get("cevaplar") or {}).items() if k in dict(pt.TARAMA_SORULARI)}
            ek["tarama_tarih"] = pt.bugun().isoformat()
            if not any(ek["tarama"].values()):
                ek["doktor_onayi"] = False
        if "doktor_onayi" in g:
            ek["doktor_onayi"] = bool(g["doktor_onayi"])
        p = pt.profil_kaydet(ek)
        return jsonify({"tarama": pt.tarama_durumu(p)})

    # ---------------------------------------------------------------- testler
    @app.get("/api/pt/testler")
    def pt_testler():
        return jsonify({**pt.testler(), "gerekli": pt.test_gerekli()})

    @app.post("/api/pt/test")
    def pt_test():
        s = {k: v for k, v in (_govde().get("sonuclar") or {}).items() if v not in (None, "")}
        if not s:
            return jsonify({"hata": "Sonuç yok."}), 400
        return jsonify(pt.test_kaydet(s, _tarih()))

    # ---------------------------------------------------------------- program
    @app.get("/api/pt/program")
    def pt_program():
        kod = request.args.get("hafta") or pt.hafta_kodu()
        kat = pt.katalog()
        pl = pt.program(kod)
        bu = pt.hafta_kodu()
        sonraki = pt.hafta_kodu(pt.hafta_gunleri(bu)[0] + dt.timedelta(days=7))
        return jsonify({"program": pl, "hafta": kod, "gunler": [g.isoformat() for g in pt.hafta_gunleri(kod)], "bu": bu, "sonraki": sonraki,
                        "sonraki_var": bool(pt.program(sonraki)),
                        "geri_var": bool(list((pt.PROGRAM / "gecmis").glob(f"{kod}_*.json"))),
                        "video": {k: h.get("video") for k, h in kat.items() if h.get("video")}})

    @app.post("/api/pt/program/uret")
    def pt_program_uret():
        g = _govde()
        if pt.tarama_durumu()["bekliyor"]:
            return jsonify({"hata": "Sağlık sorularından birine 'evet' dediniz. Planı doktorunuzun onayından sonra başlatın."}), 409
        kod = g.get("hafta") or pt.hafta_kodu()
        istek = str(g.get("istek") or "")[:600]

        def yaz():
            pl = pt.program_uret(kod, istek)
            if g.get("ilk") and pt.bugun().weekday() >= 4:          # kurulum hafta sonuna denk geldiyse gelecek hafta da hemen hazır olsun
                sonraki = pt.hafta_kodu(pt.bugun() + dt.timedelta(days=7 - pt.bugun().weekday()))
                pt.program_uret(sonraki, istek)
            return pl
        if not _arka("plan", "haftalık plan yazılıyor", yaz):
            return jsonify({"hata": "Plan zaten yazılıyor."}), 409
        if g.get("ilk") or g.get("degerlendirme"):
            _degerlendirme_baslat(yenile=bool(g.get("degerlendirme")))
        return jsonify({"ok": True})

    # ---------------------------------------------------------------- değerlendirme, hedefler, ara kontrol (2026-10-30)
    @app.get("/api/pt/degerlendirme")
    def pt_degerlendirme():
        import pt_kontrol
        if request.args.get("yenile"):
            _degerlendirme_baslat(yenile=True)
        d = pt_kontrol.degerlendirme_oku()
        return jsonify({"degerlendirme": {k: v for k, v in d.items() if k != "hesap"}, "hazirlaniyor": "degerlendirme" in calisan,
                        "hata": (sonuclar.get("degerlendirme") or {}).get("hata")})

    @app.post("/api/pt/degerlendirme")
    def pt_degerlendirme_isaretle():
        import pt_kontrol
        g = _govde()
        if g.get("yenile"):
            return jsonify({"ok": _degerlendirme_baslat(yenile=True)})
        pt_kontrol.degerlendirme_isaretle(bool(g.get("okundu", True)))
        return jsonify({"ok": True})

    @app.get("/api/pt/hedefler")
    def pt_hedefler():
        import pt_hedef
        d = pt_hedef._oku()
        return jsonify({"aktif": pt_hedef.aktif(), "hepsi": pt_hedef.hepsi(), "oneri": {k: v for k, v in (d.get("oneri") or {}).items() if k != "adaylar"},
                        "adaylar": (d.get("oneri") or {}).get("adaylar") or [], "vadeler": [{"kod": k, "ad": a, "gun": g_, "sure": s} for k, a, g_, s in pt_hedef.VADELER],
                        "hazirlaniyor": "hedef_oneri" in calisan})

    @app.post("/api/pt/hedefler")
    def pt_hedefler_islem():
        import pt_hedef
        g = _govde()
        islem = g.get("islem")
        if islem == "oner":
            if g.get("hemen"):
                return jsonify({"oneri": pt_hedef.oner(yenile=bool(g.get("yenile")))})
            return jsonify({"ok": _arka("hedef_oneri", "hedefler öneriliyor", pt_hedef.oner, bool(g.get("yenile")))})
        if islem == "kaydet":
            L = g.get("hedefler")
            if not isinstance(L, list) or not L:
                return jsonify({"hata": "En az bir hedef seçin."}), 400
            return jsonify({"aktif": pt_hedef.kaydet(L[:6])})
        if islem == "degistir":
            h = pt_hedef.degistir(str(g.get("id") or ""), g.get("metin"), g.get("durum"))
            if not h:
                return jsonify({"hata": "Hedef bulunamadı."}), 404
            with _kilit:
                pt_oyun._onbellek.clear()
            return jsonify({"hedef": h, "aktif": pt_hedef.aktif()})
        return jsonify({"hata": "islem: oner | kaydet | degistir"}), 400

    # ---------------------------------------------------------------- reçete ve uzun ömür (2026-10-31)
    @app.get("/api/pt/recete")
    def pt_recete():
        import pt_uzun
        p = pt.profil()
        kayit = pt_uzun.recete_oku()
        return jsonify({"kayitli": kayit if kayit.get("satirlar") else None, "oneri": pt_uzun.recete(p),
                        "uzmanlar": [{"kod": k, "ad": a, "ne": n} for k, a, n in pt_uzun.UZMANLAR]
                        + ([{"kod": "bjj", "ad": "Jiu-jitsu koçu", "ne": "Derslerinize göre haftayı dizer; zorlandığınız pozisyonları evde çalıştırır."}]
                           if "jiujitsu" in (p.get("sevdikleri") or []) or (p.get("bjj_ders") or {}).get("gunler") or (p.get("yontemler") or {}).get("bjj_solo") else []),
                        "kardiyo_turleri": pt_uzun.KARDIYO_TUR, "sevdikleri": pt_uzun.SEVDIKLERI,
                        "profil": {k: p.get(k) for k in ("sevdikleri", "ekipman", "bjj_ders", "hedef_turleri", "stres", "uyku_kalite", "is_duzeni")}})

    @app.post("/api/pt/recete")
    def pt_recete_islem():
        import pt_uzun
        g = _govde()
        say = g.get("sayilar") if isinstance(g.get("sayilar"), dict) else None
        if g.get("islem") == "onizle":
            return jsonify({"recete": pt_uzun.recete(pt.profil(), say, g.get("kardiyo_tur"))})
        if g.get("islem") != "uygula":
            return jsonify({"hata": "islem: onizle | uygula"}), 400
        if g.get("uzun_omur"):                                   # kişi asıl hedefinin uzun ve sağlıklı yaşam olduğunu söyledi
            H = list(pt.profil().get("hedef_turleri") or [])
            if "uzun_omur" not in H:
                pt.profil_kaydet({"hedef_turleri": H + ["uzun_omur"]})
        kayit = pt_uzun.recete_kaydet(say, g.get("kardiyo_tur"))
        if g.get("ilk"):                                         # kurulum: planı ve değerlendirmeyi kurulumun kendi akışı başlatır
            return jsonify({"recete": kayit})
        if not pt.tarama_durumu()["bekliyor"]:
            kod = pt.hafta_kodu()
            istek = "Haftalık reçete değişti; bu haftanın kalan günlerini yeni reçeteye göre yaz, bitmiş günlere dokunma."
            if pt.profil().get("program_baslangic") == pt.bugun().isoformat():
                istek += " PROGRAM BUGÜN BAŞTAN BAŞLADI: geçen günlere seans koyma (dinlenme yaz), bugünden pazara kadar kısa ve kolay başla."

            def yaz():
                pl = pt.program_uret(kod, istek)
                sonraki = pt.hafta_kodu(pt.bugun() + dt.timedelta(days=7 - pt.bugun().weekday()))
                if pt.program(sonraki):
                    pt.program_uret(sonraki, "Haftalık reçete değişti; yeni reçeteye göre yaz.")
                return pl
            _arka("plan", "haftalık plan yeniden yazılıyor", yaz)
            _degerlendirme_baslat(yenile=True)
        return jsonify({"recete": kayit, "plan": "plan" in calisan})

    # ---------------------------------------------------------------- bugünden baştan başla (2026-10-31)
    @app.post("/api/pt/yeniden-basla")
    def pt_yeniden_basla():
        import pt_yeniden
        g = _govde()
        if "plan" in calisan:
            return jsonify({"hata": "Plan şu an yazılıyor; bir dakika sonra yeniden deneyin."}), 409
        r = pt_yeniden.yeniden_basla(g.get("neden") or "")
        with _kilit:
            pt_oyun._onbellek.clear()
        if not pt.tarama_durumu()["bekliyor"] and g.get("plan_yaz", True):   # reçete ekranı ardından gelecekse planı o yazar
            gun = pt.GUN_AD[pt.bugun().weekday()] if hasattr(pt, "GUN_AD") else ""
            istek = (f"PROGRAM BUGÜN ({pt.bugun().isoformat()} {gun}) BAŞTAN BAŞLIYOR: önceki günler geçti, onlara seans koyma (dinlenme yaz). "
                     "Bugünden pazara kadar, kişinin kaldırabileceği kadar kısa ve kolay yaz; ilk gün özellikle kolay olsun. " + str(g.get("istek") or "")[:300])
            _arka("plan", "haftalık plan bugünden yazılıyor", pt.program_uret, r["hafta"], istek)
        return jsonify({**r, "plan": "plan" in calisan})

    @app.post("/api/pt/yeniden-ertele")
    def pt_yeniden_ertele():
        import pt_yeniden
        pt_yeniden.ertele(int(_govde().get("gun") or 7))
        return jsonify({"ok": True})

    @app.get("/api/pt/moduller")
    def pt_moduller():
        import pt_modul
        return jsonify({"bugun": pt_modul.gunun(), "olay": pt_modul.son_olay(), "katalog": pt_modul.MODULLER,
                        "cikan": pt_uzun_recete().get("modul_cikan") or []})

    @app.post("/api/pt/modul")
    def pt_modul_islem():
        import pt_modul
        g = _govde()
        kod = str(g.get("kod") or "")
        if kod not in pt_modul.MODULLER:
            return jsonify({"hata": "Bilinmeyen modül."}), 400
        islem = g.get("islem") or "yap"
        if islem in ("yap", "geri"):
            L = pt_modul.isaretle(kod, g.get("tarih"), geri=islem == "geri")
            with _kilit:
                pt_oyun._onbellek.clear()
            return jsonify({"bugun": L})
        if islem in ("cikar", "ekle"):
            return jsonify({"moduller": pt_modul.cikar(kod, geri=islem == "ekle")})
        return jsonify({"hata": "islem: yap | geri | cikar | ekle"}), 400

    @app.post("/api/pt/modul/olay")
    def pt_modul_olay():
        import pt_modul
        g = _govde()
        pt_modul.olay_isaretle(int(g.get("t") or 0), geri=bool(g.get("geri")))
        return jsonify({"ok": True})

    @app.get("/api/pt/modul/video/<kod>")
    def pt_modul_video(kod):
        import pt_modul
        if kod not in pt_modul.MODULLER:
            return jsonify({"hata": "Bilinmeyen modül."}), 404
        return jsonify({"video": pt_modul.video(kod)})

    @app.get("/api/pt/uzun")
    def pt_uzun_omur():
        import pt_uzun
        p = pt.profil()
        return jsonify({"gostergeler": pt_uzun.gostergeler(p), "doz": pt_uzun.doz_ozeti(), "dozlar": pt_uzun.dozlar(p),
                        "recete": bool((pt_uzun.recete_oku() or {}).get("satirlar"))})

    @app.get("/api/pt/kontrol")
    def pt_kontrol_durum():
        import pt_kontrol
        z = pt_kontrol.zamani()
        return jsonify({**z, "gecmis": pt_kontrol.gecmis()[-12:], "hazirlaniyor": "kontrol" in calisan})

    @app.post("/api/pt/kontrol")
    def pt_kontrol_islem():
        import pt_kontrol
        g = _govde()
        islem = g.get("islem")
        if islem == "baslat":
            return jsonify({"kontrol": pt_kontrol.hazirla(yenile=bool(g.get("yenile")))})
        if islem == "bitir":
            cev = g.get("cevaplar") if isinstance(g.get("cevaplar"), dict) else {}
            k = pt_kontrol.bitir(_tarih(g.get("tarih")), cev)
            if g.get("yeniden_yaz") and (k.get("sonuc") or {}).get("karar") == "guncelle":
                _arka("plan", "plan güncelleniyor", pt.program_uret, pt.hafta_kodu(), (k["sonuc"].get("plan_istegi") or ""))
            return jsonify({"kontrol": k, "plan_yaziliyor": "plan" in calisan})
        return jsonify({"hata": "islem: baslat | bitir"}), 400

    @app.post("/api/pt/ek-gorev")
    def pt_ek_gorev():
        g = _govde()
        t = _tarih(g.get("tarih"))
        try:
            e = pt_oyun.ek_gorev_isaretle(t, str(g.get("kod") or ""), bool(g.get("tamam", True)))
        except ValueError as er:
            return jsonify({"hata": str(er)}), 400
        return jsonify({"ek_gorev": e, "oyun": pt_oyun.ozet()})

    @app.post("/api/pt/program/geri-al")
    def pt_program_geri():
        pl = pt.program_geri_al(_govde().get("hafta"))
        return jsonify({"ok": bool(pl)}) if pl else (jsonify({"hata": "Geri alınacak eski plan yok."}), 404)

    @app.post("/api/pt/program/tasi")
    def pt_program_tasi():
        g = _govde()
        return jsonify(pt.gun_tasi(g.get("hafta") or pt.hafta_kodu(), g.get("id"), _tarih(g.get("yeni"))))

    @app.get("/api/pt/is/<anahtar>")
    def pt_is(anahtar):
        return jsonify({"calisiyor": anahtar in calisan, "ad": calisan.get(anahtar), **(sonuclar.get(anahtar) or {})})

    # ---------------------------------------------------------------- gün: sabah, seans, ağrı, kilo
    @app.get("/api/pt/gun")
    def pt_gun():
        t = _tarih()
        import pt_saglik
        return jsonify({**pt.gun_seansi(t), "gunluk": pt.gun(t), "saglik": pt_saglik.hazirlik(t)})

    @app.post("/api/pt/sabah")
    def pt_sabah():
        g = _govde()
        t = _tarih()
        if g.get("uyari_belirti"):
            return jsonify({"dur": True, "uyari": pt.UYARI_BELIRTILERI})
        s = {k: g.get(k) for k in ("uyku", "uyku_saat", "enerji", "agri", "dunku_agri", "vakit_dk", "nerede", "hasta", "not")}
        s = _sabah_temizle(s)
        s["agri"] = [a for a in s.get("agri") or [] if a.get("bolge") in pt.BOLGELER]
        s["dunku_agri"] = (s.get("dunku_agri") or []) + [x for x in pt.gun(t).get("agri_takip") or []
                                                         if x.get("bolge") not in {y.get("bolge") for y in s.get("dunku_agri") or []}]
        import pt_saglik
        hz = pt_saglik.hazirlik(t)
        if hz:
            s["saglik"] = hz
            if not s.get("uyku_saat") and hz.get("uyku_saat"):
                s["uyku_saat"] = hz["uyku_saat"]
        isik, neden = pt.sabah_isigi(s)
        s.update(isik=isik, neden=neden, t=int(time.time()))

        def yaz(d):
            d["sabah"] = s
            for a in s["agri"]:
                d["agri"].append({**a, "sabah": True, "t": int(time.time())})
        pt.gun_degistir(t, yaz)
        return jsonify({"isik": isik, "neden": neden, **pt.gun_seansi(t)})

    @app.post("/api/pt/seans")
    def pt_seans():
        g = _govde()
        seans = dict(g.get("seans") or {})
        onceki = pt_oyun.hesap()
        seans["onarim_icin"] = pt_oyun.onarim_gecerli(seans.get("onarim_icin"))     # telafi yalnız gerçekten kopan son iki gün için
        if not seans["onarim_icin"]:
            seans.pop("onarim_icin")
        seans["t"] = int(time.time())
        seans["sure_dk"] = int(pt.sayi(seans.get("sure_dk"), 0, 600, 0))
        if seans.get("zorluk") is not None:
            seans["zorluk"] = int(pt.sayi(seans.get("zorluk"), 1, 10, 5))
        seans["agri"] = [{"bolge": a.get("bolge"), "puan": int(pt.sayi(a.get("puan"), 0, 10, 0)), "tur": "kas" if a.get("tur") == "kas" else "eklem"}
                         for a in seans.get("agri") or [] if isinstance(a, dict) and a.get("bolge") in pt.BOLGELER]
        for h in seans.get("hareketler") or []:
            if isinstance(h, dict):
                h["setler"] = [{k: (pt.sayi(v, 0, 3600, 0) if k in ("deger", "tekrar", "sure_sn", "rir", "zorluk", "kg") else v) for k, v in x.items()}
                               for x in h.get("setler") or [] if isinstance(x, dict)]
        import pt_programlar
        if seans.get("program") not in pt_programlar.P or (pt_programlar.aktif() or {}).get("kod") != seans.get("program"):
            seans.pop("program", None)                                  # yalnız etkin programın seansı programa sayılır
            seans.pop("program_hafta", None)
        try:
            ilk = int(seans.get("ilk_adim")) if seans.get("ilk_adim") is not None else None
        except (TypeError, ValueError):
            ilk = None
        seans.pop("ilk_adim", None)
        if ilk is not None:
            seans["ilk_adim"] = ilk
        s = pt.seans_kaydet(_tarih(), seans)
        if ilk is not None and not seans.get("yarim"):
            import pt_ilk
            pt_ilk.tamamla(ilk)
        biten = pt_programlar.tamamla_kontrol() if seans.get("program") else None
        return jsonify({"seans": s, "ilerleme": s.get("ilerleme") or [], "oyun": pt_oyun.ozet(), "onceki_seri": onceki["seri"],
                        "onceki_bugun": onceki["bugun"]["durum"], "program_bitti": biten})

    # ---------------------------------------------------------------- ilk hafta yolu (pt_ilk)
    @app.post("/api/pt/ilk")
    def pt_ilk_islem():
        import pt_ilk
        g = _govde()
        if "birak" in g:
            pt_ilk.birak(geri=not g.get("birak"))
        elif g.get("tamam") is not None:
            pt_ilk.tamamla(int(pt.sayi(g.get("tamam"), 0, 6, 0)))
        return jsonify({"ilk": pt_ilk.durum()})

    # ---------------------------------------------------------------- hazır programlar (Nike Training Club'daki gibi)
    @app.get("/api/pt/programlar")
    def pt_programlar_liste():
        import pt_oneri
        import pt_programlar
        return jsonify({**pt_programlar.liste(), "oneriler": pt_oneri.program_onerileri(3)})

    @app.get("/api/pt/oneriler")
    def pt_oneriler():
        import pt_oneri
        return jsonify(pt_oneri.hepsi())

    @app.post("/api/pt/oneri/kapat")
    def pt_oneri_kapat():
        import pt_oneri
        g = _govde()
        pt_oneri.kapat(str(g.get("kod") or ""), "kalici" if g.get("nasil") == "kalici" else "sonra", str(g.get("neden") or "")[:200])
        return jsonify({"ok": True, "oneri": _oneri_guvenli()})

    @app.post("/api/pt/oneri/siklik")
    def pt_oneri_siklik():
        import pt_oneri
        pt_oneri.siklik_ayarla(_govde().get("siklik"))
        return jsonify({"ok": True})

    @app.post("/api/pt/ekipman")
    def pt_ekipman_ekle():
        kod = _govde().get("kod")
        if kod not in pt.EKIPMANLAR:
            return jsonify({"hata": "Bilinmeyen ekipman."}), 400
        var = list(pt.profil().get("ekipman") or [])
        pt.profil_kaydet({"ekipman": var + ([kod] if kod not in var else [])})
        return jsonify({"ok": True, "oneri": _oneri_guvenli()})

    @app.post("/api/pt/program-sec")
    def pt_program_sec():
        import pt_programlar
        g = _govde()
        try:
            return jsonify(pt_programlar.birak() if g.get("birak") else pt_programlar.sec(str(g.get("kod") or "")))
        except ValueError as e:
            return jsonify({"hata": str(e)}), 400

    @app.post("/api/pt/program-antrenman")
    def pt_program_antrenman():
        import pt_programlar
        g = _govde()
        try:
            return jsonify(pt_programlar.bugunku_seans(g.get("nerede") if g.get("nerede") in ("ev", "park", "yolda") else "ev"))
        except ValueError as e:
            return jsonify({"hata": str(e)}), 400

    # ---------------------------------------------------------------- seri, rozetler, kitaplık, hızlı antrenman (2026-10-27)
    @app.get("/api/pt/oyun")
    def pt_oyun_tam():
        return jsonify(pt_oyun.tam())

    @app.post("/api/pt/oyun/goruldu")
    def pt_oyun_goruldu():
        idler = _govde().get("idler") or []
        if not isinstance(idler, list):
            return jsonify({"hata": "Liste bekleniyor."}), 400
        pt_oyun.goruldu(idler[:50])
        return jsonify({"ok": True})

    @app.get("/api/pt/kitaplik")
    def pt_kitaplik_ozet():
        import pt_kitaplik
        return jsonify({"kaydedilen": pt_kitaplik.kaydedilenler(), "ozet": pt_kitaplik.hareket_ozet(), "kas": pt_kitaplik.kas_durumu()})

    @app.post("/api/pt/kaydedilen")
    def pt_kaydedilen():
        import pt_kitaplik
        g = _govde()
        try:
            return jsonify({"kaydedilen": pt_kitaplik.kaydet(str(g.get("kod") or ""), bool(g.get("kayitli", True)))})
        except ValueError as e:
            return jsonify({"hata": str(e)}), 400

    @app.get("/api/pt/hareket-gecmis/<kod>")
    def pt_hareket_gecmis(kod):
        import pt_kitaplik
        try:
            return jsonify(pt_kitaplik.hareket_gecmis(kod))
        except ValueError as e:
            return jsonify({"hata": str(e)}), 404

    @app.get("/api/pt/hizli")
    def pt_hizli_secenek():
        import pt_hizli
        return jsonify(pt_hizli.secenekler())

    @app.post("/api/pt/hizli")
    def pt_hizli_olustur():
        import pt_hizli
        g = _govde()
        nerede = g.get("nerede") if g.get("nerede") in ("ev", "park", "yolda") else "ev"
        try:
            return jsonify(pt_hizli.olustur(g.get("sure") or 20, str(g.get("odak") or "onerilen"), nerede,
                                            tohum=g.get("tohum") if isinstance(g.get("tohum"), int) else None, kod=g.get("kod") or None))
        except ValueError as e:
            return jsonify({"hata": str(e)}), 400

    @app.post("/api/pt/agri-takip")
    def pt_agri_takip():
        g = _govde()
        try:
            return jsonify(pt.agri_takip_kaydet(_tarih(), str(g.get("bolge") or ""), str(g.get("durum") or "")))
        except ValueError as e:
            return jsonify({"hata": str(e)}), 400

    @app.post("/api/pt/agri")
    def pt_agri():
        g = _govde()
        a = {"bolge": g.get("bolge"), "puan": int(pt.sayi(g.get("puan"), 0, 10, 0)), "t": int(time.time()), "not": str(g.get("not") or "")[:200]}
        if a["bolge"] not in pt.BOLGELER:
            return jsonify({"hata": "Bölge yok."}), 400
        pt.gun_degistir(_tarih(), lambda d: d["agri"].append(a))
        return jsonify({"ok": True, "koru": pt.koru_bolgeler()})

    @app.post("/api/pt/kilo")
    def pt_kilo():
        g = _govde()
        ek = {}
        for a, b, en, ust in (("kilo", "kilo", 30, 300), ("bel", "bel_cm", 40, 200)):
            if g.get(a) not in (None, ""):
                v = pt.sayi(g[a])
                if v is None or not en <= v <= ust:
                    return jsonify({"hata": f"{'Kilo' if a == 'kilo' else 'Bel'} {en}-{ust} arasında olmalı."}), 400
                ek[b] = round(v, 1)
        pt.gun_degistir(_tarih(), lambda d: d.update(ek))
        return jsonify({"ok": True, "trend": pt_beslenme.trend(60)})

    @app.get("/api/pt/ilerleme")
    def pt_ilerleme():
        kat = pt.katalog()
        il = pt.ilerleme()
        for d in il["degisiklikler"]:
            d["ad"] = (kat.get(d.get("kod")) or {}).get("ad")
            d["yeni_ad"] = (kat.get(d.get("yeni")) or {}).get("ad")
        return jsonify({**il, "kurallar": pt.KURALLAR_METNI, "takvim": pt.yillik_takvim(), "seri": pt.seri(), "testler": pt.testler()})

    @app.get("/api/pt/yorgunluk")
    def pt_yorgunluk():
        return jsonify({"seri": pt.yuk_serisi(120)[-90:], "durum": pt.yorgunluk_durumu()})

    @app.post("/api/pt/ilerleme/geri-al")
    def pt_ilerleme_geri():
        return jsonify({"ok": pt.degisiklik_geri_al(_govde().get("id") or _govde().get("t") or "")})

    # ---------------------------------------------------------------- beslenme
    def _yemek_fotolari(td):
        """İstekteki 'foto' dosyaları (en çok 3) → 1280 px jpg yolları."""
        yollar = []
        for i, f in enumerate(request.files.getlist("foto")[:3]):
            ham = Path(td) / f"ham{i}"
            f.save(ham)
            yol = Path(td) / f"foto{i}.jpg"
            subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "1280", str(ham), "--out", str(yol)], capture_output=True, timeout=60)
            yollar.append(yol if yol.exists() else ham)
        return yollar

    @app.post("/api/pt/yemek/coz")
    def pt_yemek_coz():
        metin = (request.form.get("metin") or "").strip()
        if not metin and not request.files.get("foto"):
            return jsonify({"hata": "Fotoğraf ya da bir cümle gerekli."}), 400
        try:
            cevap = json.loads(request.form.get("cevap") or "null")
        except ValueError:
            cevap = None
        with tempfile.TemporaryDirectory() as td:
            try:
                fotolar = _yemek_fotolari(td)
                y = pt_beslenme.yemek_coz(metin, resimler=fotolar, cevap=cevap)
                if fotolar:                                           # kaydedilirse günlükte görünecek küçük kopya
                    fid = f"y{int(time.time() * 1000)}{uuid.uuid4().hex[:4]}"
                    if pt_beslenme.foto_kaydet(fid, fotolar[0]):
                        y["foto_id"] = fid
                return jsonify(y)
            except Exception as e:  # noqa: BLE001
                return jsonify({"hata": f"Tahmin yapılamadı: {str(e)[:160]}"}), 502

    @app.post("/api/pt/yemek/paylas")
    def pt_yemek_paylas():
        """iPhone Paylaş menüsündeki Kısayol: fotoğraf(lar) gelir, tahmin edilip 'kontrol bekliyor' olarak kaydedilir. Anahtarla (Apple Sağlık'ınki)."""
        import pt_saglik
        if not pt_saglik.anahtar_gecerli(request.args.get("anahtar") or request.headers.get("X-PT-Anahtar")):
            return jsonify({"hata": "Anahtar geçersiz."}), 403
        if not request.files.get("foto"):
            return jsonify({"hata": "Fotoğraf gelmedi."}), 400
        with tempfile.TemporaryDirectory() as td:
            try:
                y = pt_beslenme.disaridan_kaydet(_yemek_fotolari(td), (request.form.get("metin") or "").strip())
            except Exception as e:  # noqa: BLE001
                return jsonify({"hata": f"Tahmin yapılamadı: {str(e)[:160]}"}), 502
        k = round(sum(x.get("kcal") or 0 for x in y["kalemler"]))
        p_ = round(sum(x.get("protein") or 0 for x in y["kalemler"]))
        return jsonify({"ok": True, "mesaj": f"{y['ad']}: yaklaşık {k} kcal, {p_} g protein. Health'te kontrol edebilirsiniz.", "yemek": y})

    @app.get("/pt-yemek-foto/<yid>.jpg")
    def pt_yemek_foto(yid):
        if not re.fullmatch(r"y\d{10,18}[0-9a-f]{0,4}", yid):
            abort(404)
        p_ = pt_beslenme.FOTO / f"{yid}.jpg"
        if not p_.exists():
            abort(404)
        return send_file(p_, mimetype="image/jpeg", max_age=86400)

    @app.post("/api/pt/yemek")
    def pt_yemek():
        g = _govde()
        y = pt_beslenme.yemek_kaydet(_tarih(), g.get("yemek") or {})
        d = pt.gun(_tarih())
        return jsonify({"yemek": y, "toplam": pt_beslenme.gun_toplam(d), "pencere": pt_beslenme.pencere_durumu(tarih=_tarih())})

    @app.delete("/api/pt/yemek/<tarih>/<yid>")
    def pt_yemek_sil(tarih, yid):
        pt_beslenme.yemek_sil(_tarih(tarih), yid)
        return jsonify({"ok": True})

    @app.get("/api/pt/yemek/dun")
    def pt_yemek_dun():
        return jsonify(pt_beslenme.dunku_yemekler(_tarih()))

    @app.post("/api/pt/yemek/kopyala")
    def pt_yemek_kopyala():
        g = _govde()
        kaynak = pt.tarih_gecerli(g.get("kaynak") or (pt.bugun() - pt.dt.timedelta(days=1)).isoformat())
        idler = [str(x)[:40] for x in g.get("idler") or []][:20] or None
        y = pt_beslenme.yemek_kopyala(_tarih(), kaynak, idler)
        d = pt.gun(_tarih())
        return jsonify({"eklenen": len(y), "toplam": pt_beslenme.gun_toplam(d), "pencere": pt_beslenme.pencere_durumu(tarih=_tarih())})

    @app.post("/api/pt/oruc")
    def pt_oruc():
        g = _govde()
        ne = g.get("ne")
        if ne not in ("ac", "kapat"):
            return jsonify({"hata": "ne: ac ya da kapat"}), 400
        t = g.get("t")
        if t is not None:
            t = pt.sayi(t, 0, 4e9)
            if t is None:
                return jsonify({"hata": "Saat okunamadı."}), 400
        try:
            gun = pt_beslenme.oruc_isaretle(_tarih(), ne, bool(g.get("geri")), t)
        except ValueError as e:
            return jsonify({"hata": str(e)}), 400
        return jsonify({**pt_beslenme.pencere_durumu(tarih=_tarih()), "gun": gun})

    @app.post("/api/pt/bjj-dersleri")
    def pt_bjj_dersleri():
        g = _govde()
        r = pt.bjj_dersleri_kaydet(g.get("gunler") or [], str(g.get("saat") or ""), g.get("sure_dk") or 90)
        return jsonify({"bjj_ders": r["profil"].get("bjj_ders"), "degisen": r["degisen"]})

    @app.post("/api/pt/pencere")
    def pt_pencere():
        g = _govde()
        pt_beslenme.pencere_kaydir(_tarih(), str(g.get("bas") or "")[:5] or None)
        return jsonify(pt_beslenme.pencere_durumu(tarih=_tarih()))

    @app.post("/api/pt/yemek-onerisi")
    def pt_yemek_onerisi():
        try:
            return jsonify(pt_beslenme.gunluk_oneri(_tarih()))
        except Exception as e:  # noqa: BLE001
            return jsonify({"hata": f"Öneri yazılamadı: {str(e)[:160]}"}), 502

    @app.post("/api/pt/eksik-kayit")
    def pt_eksik():
        v = bool(_govde().get("eksik"))
        pt.gun_degistir(_tarih(), lambda d: d.update(eksik_kayit=v))
        return jsonify({"ok": True})

    # ---------------------------------------------------------------- Apple Sağlık köprüsü (Kısayol / Health Auto Export)
    @app.post("/api/pt/saglik")
    def pt_saglik_al():
        import pt_saglik
        if not pt_saglik.anahtar_gecerli(request.args.get("anahtar") or request.headers.get("X-PT-Anahtar")):
            return jsonify({"hata": "Anahtar geçersiz."}), 403
        veri = request.get_json(silent=True)
        if veri is None:
            veri = {k: v for k, v in request.form.items()}
            if not veri:
                try:
                    veri = json.loads(request.get_data(as_text=True) or "{}")
                except ValueError:
                    return jsonify({"hata": "Veri okunamadı."}), 400
        return jsonify({"ok": True, "gunler": pt_saglik.kaydet(veri)})

    @app.get("/api/pt/saglik/durum")
    def pt_saglik_durum():
        import pt_saglik
        return jsonify({**pt_saglik.durum(), "bugun": pt_saglik.hazirlik()})

    @app.post("/api/pt/saglik/icloud")
    def pt_saglik_icloud():
        import pt_saglik
        r = pt_saglik.icloud_tara()
        with _kilit:
            pt_oyun._onbellek.clear()
        return jsonify({**r, "durum": pt_saglik.durum()})

    @app.post("/api/pt/saglik/ice-aktar")
    def pt_saglik_ice_aktar():
        """iPhone Sağlık 'Tüm sağlık verilerini dışa aktar' dosyası (zip ya da export.xml): diske alınır, arka planda okunur, sonra silinir."""
        import pt_saglik
        f = request.files.get("dosya")
        if not f or not f.filename:
            return jsonify({"hata": "Dosya gelmedi."}), 400
        if not f.filename.lower().endswith((".zip", ".xml")):
            return jsonify({"hata": "dışa_aktar.zip ya da export.xml bekleniyor."}), 400
        if "saglik_ice" in calisan:
            return jsonify({"hata": "Bir dosya zaten okunuyor."}), 409
        gecici = pt.VERI / ".gecici"
        gecici.mkdir(parents=True, exist_ok=True)
        yol = gecici / f"saglik_{uuid.uuid4().hex[:8]}{'.zip' if f.filename.lower().endswith('.zip') else '.xml'}"
        f.save(yol)
        _arka("saglik_ice", "Apple Sağlık verisi okunuyor", pt_saglik.ice_aktar, yol)
        return jsonify({"ok": True})

    # ---------------------------------------------------------------- Health ile konuşma
    @app.get("/api/pt/sohbet")
    def pt_sohbet_gecmis():
        import pt_sohbet
        return jsonify({"mesajlar": [m for m in pt_sohbet.gecmis() if time.time() - m["t"] < 3 * 86400][-30:]})

    @app.post("/api/pt/sohbet")
    def pt_sohbet_gonder():
        import pt_sohbet
        metin = str(_govde().get("metin") or "").strip()
        if not metin:
            return jsonify({"hata": "Boş mesaj."}), 400
        try:
            c = pt_sohbet.gonder(metin)
        except Exception as e:  # noqa: BLE001
            return jsonify({"hata": f"Health cevap veremedi: {str(e)[:160]}"}), 502
        if c.get("kayitlar"):
            with _kilit:
                pt_oyun._onbellek.clear()
        return jsonify(c)

    @app.get("/api/pt/hikaye")
    def pt_hikaye_al():
        import pt_hikaye
        kod = request.args.get("hafta")
        if kod and not pt.hafta_gecerli(kod):
            return jsonify({"hata": "Hafta geçersiz."}), 400
        return jsonify(pt_hikaye.hikaye(kod or None))

    @app.get("/api/pt/selam")
    def pt_selam_al():
        return jsonify(_selam())

    @app.post("/api/pt/ses-yazi")
    def pt_ses_yazi():
        """Mikrofondan gelen kısa ses → yazı (bilgisayardaki ses modeliyle; ses dışarı gitmez)."""
        f = request.files.get("dosya")
        if not f:
            return jsonify({"hata": "Ses gelmedi."}), 400
        import subprocess
        import tempfile
        d = tempfile.mkdtemp(prefix="pt_ses_")
        yol = os.path.join(d, "ses" + (os.path.splitext(f.filename or "")[1] or ".webm"))
        f.save(yol)
        try:
            r = subprocess.run([sys.executable, str(pt.KLASOR / "sesnot.py"), yol, "tr"], capture_output=True, text=True, timeout=180)
            if r.returncode != 0 and "mlx" in (r.stderr or ""):        # bu kurulumda ses modeli yok: tarayıcının ses tanımasına geçilir
                return jsonify({"hata": "Ses modeli kurulu değil."}), 501
            j = json.loads((r.stdout or "").strip().splitlines()[-1]) if r.stdout.strip() else {}
        except Exception as e:  # noqa: BLE001
            j = {"hata": str(e)[:160]}
        finally:
            shutil.rmtree(d, ignore_errors=True)
        if not (j.get("metin") or "").strip():
            return jsonify({"hata": j.get("hata") or "Sesi anlayamadım; yeniden deneyin."}), 422
        return jsonify({"metin": j["metin"].strip()})

    @app.post("/api/pt/sohbet/geri")
    def pt_sohbet_geri():
        import pt_sohbet
        g = _govde()
        ok = pt_sohbet.kayit_geri_al(str(g.get("no") or ""), int(g.get("i") or 0))
        with _kilit:
            pt_oyun._onbellek.clear()
        return jsonify({"ok": ok})

    @app.post("/api/pt/sohbet/onay")
    def pt_sohbet_onay():
        import pt_sohbet
        g = _govde()
        no = str(g.get("no") or "")
        if not g.get("onay"):
            pt_sohbet.vazgec(no)
            return jsonify({"ok": True})
        m = next((x for x in pt_sohbet.gecmis() if x.get("eylem_no") == no), None)
        if m and (m.get("eylem") or {}).get("tur") == "hafta":
            if not _arka("plan", "haftalık plan yeniden yazılıyor", pt_sohbet.uygula, no):
                return jsonify({"hata": "Haftanız şu an zaten yazılıyor; bitince yeniden deneyin."}), 409
            return jsonify({"ok": True, "sonuc": "Haftanızı yeniden yazıyorum; bir iki dakika sürer."})
        return jsonify({"ok": True, "sonuc": pt_sohbet.uygula(no) or "Zaten uygulanmış."})

    # ---------------------------------------------------------------- haftalık menü, alışveriş listesi, ürünler
    @app.get("/api/pt/menu")
    def pt_menu():
        import pt_yemek
        kod = request.args.get("hafta") or pt.hafta_kodu()
        sonraki = pt.hafta_kodu(pt.bugun() + dt.timedelta(days=7 - pt.bugun().weekday()))
        return jsonify({"menu": pt_yemek.plan(kod), "hafta": kod, "calisiyor": "menu" in calisan,
                        "sonraki": {"hafta": sonraki, "menu": pt_yemek.plan(sonraki)} if pt.bugun().weekday() >= 5 and pt_yemek.plan(sonraki) else None})

    @app.post("/api/pt/menu/uret")
    def pt_menu_uret():
        import pt_yemek
        kod = _govde().get("hafta") or pt.hafta_kodu()

        def yap():
            d = pt_yemek.plan_uret(kod)
            if pt.bugun().weekday() >= 5 and kod == pt.hafta_kodu():          # hafta sonu: gelecek haftanın menüsü ve alışverişi de hazır olsun
                pt_yemek.plan_uret(pt.hafta_kodu(pt.bugun() + dt.timedelta(days=7 - pt.bugun().weekday())))
            return d
        if not _arka("menu", "haftalık menü hazırlanıyor", yap):
            return jsonify({"hata": "Menü zaten hazırlanıyor."}), 409
        return jsonify({"ok": True})

    @app.post("/api/pt/menu/alindi")
    def pt_menu_alindi():
        import pt_yemek
        g = _govde()
        return jsonify({"alindi": pt_yemek.alindi(g.get("hafta") or pt.hafta_kodu(), str(g.get("id") or ""), bool(g.get("durum")))})

    @app.post("/api/pt/menu/yedim")
    def pt_menu_yedim():
        import pt_yemek
        g = _govde()
        d = pt_yemek.plan(g.get("hafta") or pt.hafta_kodu())
        gun_ = next((x for x in d.get("gunler") or [] if x.get("tarih") == g.get("tarih")), None)
        try:
            o = (gun_ or {}).get("ogunler", [])[int(g.get("i"))]
        except (TypeError, ValueError, IndexError):
            return jsonify({"hata": "Öğün yok."}), 404
        y = pt_beslenme.yemek_kaydet(_tarih(), {"ad": o.get("ad"), "kalemler": pt_yemek.ogun_kalemleri(o), "menu": True})
        return jsonify({"yemek": y, "toplam": pt_beslenme.gun_toplam(pt.gun(_tarih()))})

    @app.get("/api/pt/urunler")
    def pt_urunler():
        import pt_yemek
        return jsonify({"urunler": pt_yemek.urunler()[::-1]})

    @app.post("/api/pt/urun/barkod")
    def pt_urun_barkod():
        import pt_yemek
        try:
            u = pt_yemek.barkod(_govde().get("barkod"))
        except Exception as e:  # noqa: BLE001
            return jsonify({"hata": str(e)[:160]}), 400
        if not u:
            return jsonify({"hata": "Bu barkod Open Food Facts'te yok. Besin tablosunun fotoğrafını çekin."}), 404
        return jsonify({**u, "uyari": pt_yemek.hassasiyet_uyarisi(u)})

    @app.post("/api/pt/urun/etiket")
    def pt_urun_etiket():
        import pt_yemek
        f = request.files.get("foto")
        if not f:
            return jsonify({"hata": "Fotoğraf yok."}), 400
        with tempfile.TemporaryDirectory() as td:
            ham = Path(td) / "ham"; f.save(ham)
            yol = Path(td) / "e.jpg"
            subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "1600", str(ham), "--out", str(yol)], capture_output=True, timeout=60)
            try:
                u = pt_yemek.etiket(yol if yol.exists() else ham)
            except Exception as e:  # noqa: BLE001
                return jsonify({"hata": str(e)[:160]}), 400
        return jsonify({**u, "uyari": pt_yemek.hassasiyet_uyarisi(u)})

    # ---------------------------------------------------------------- set sonrası form raporu (Vision)
    @app.get("/api/pt/form")
    def pt_form_liste():
        import pt_form
        return jsonify({"raporlar": [{k: v for k, v in r.items() if k != "seri"} for r in pt_form.liste()]})

    @app.post("/api/pt/form")
    def pt_form_yukle():
        import pt_form
        f = request.files.get("video")
        if not f:
            return jsonify({"hata": "Video yok."}), 400
        gecici = Path(tempfile.mkdtemp(prefix="pt_form_")) / "v.mov"
        f.save(gecici)
        kod = request.form.get("kod") or "sinav"
        anahtar = f"form:{int(time.time() * 1000)}"

        def isle():
            try:
                return pt_form.rapor(gecici, kod)
            finally:
                shutil.rmtree(gecici.parent, ignore_errors=True)            # video saklanmaz
        _arka(anahtar, "form raporu hazırlanıyor", isle)
        return jsonify({"ok": True, "is": anahtar})

    # ---------------------------------------------------------------- beceri ağacı ve jiu-jitsu haritası
    @app.get("/api/pt/beceriler")
    def pt_beceriler():
        return jsonify({"beceriler": pt.beceriler()})

    @app.get("/api/pt/beceri/<kod>/deneme")
    def pt_beceri_deneme(kod):
        s = pt.deneme_seansi(kod)
        return jsonify(s) if s else (jsonify({"hata": "Beceri yok."}), 404)

    @app.get("/api/pt/bjj/harita")
    def pt_bjj_harita():
        return jsonify({"harita": pt.bjj_harita()})

    @app.post("/api/pt/bjj/not")
    def pt_bjj_not():
        g = _govde()
        x = pt.bjj_not(g.get("pozisyon"), g.get("metin"), g.get("sil"))
        return jsonify(x) if x is not None else (jsonify({"hata": "Pozisyon yok."}), 400)

    # ---------------------------------------------------------------- kanıt dosyası ve aylık güncelleme önerisi
    @app.get("/api/pt/kanit")
    def pt_kanit_al():
        import pt_kanit
        return jsonify({"kanit": pt_kanit.KANIT, **pt_kanit.durum(), "calisiyor": "kanit" in calisan})

    @app.post("/api/pt/kanit/tara")
    def pt_kanit_tara():
        import pt_kanit
        if not _arka("kanit", "yeni araştırmalar taranıyor", pt_kanit.tara):
            return jsonify({"hata": "Tarama sürüyor."}), 409
        return jsonify({"ok": True})

    @app.post("/api/pt/kanit/karar")
    def pt_kanit_karar():
        import pt_kanit
        g = _govde()
        return jsonify(pt_kanit.karar(str(g.get("id") or ""), bool(g.get("kabul"))))

    # ---------------------------------------------------------------- telefon bildirimleri (pt_push; couple_push'un eşi)
    @app.get("/api/pt/push/anahtar")
    def pt_push_anahtar():
        import pt_push
        try:
            return jsonify({"anahtar": pt_push.acik_anahtar(), "cihaz": len(pt_push.aboneler())})
        except Exception as e:  # noqa: BLE001
            return jsonify({"hata": f"Bildirim anahtarı hazırlanamadı: {str(e)[:120]}"}), 500

    @app.post("/api/pt/push/abone")
    def pt_push_abone():
        import pt_push
        v = _govde()
        try:
            n = pt_push.abone_ol(v.get("sub") or {}, str(v.get("cihaz") or "")[:120])
        except ValueError as e:
            return jsonify({"hata": str(e)}), 400
        pt_push.gonder("Health", "Bildirimler açık: sabah soruları, yeme penceresi ve antrenman saati buraya gelecek.", "/?u=pt", "pt-acildi")
        return jsonify({"ok": True, "cihaz": n})

    @app.post("/api/pt/push/sil")
    def pt_push_sil():
        import pt_push
        return jsonify({"ok": True, "cihaz": pt_push.abonelik_sil(str(_govde().get("endpoint") or ""))})

    @app.post("/api/pt/push/dene")
    def pt_push_dene():
        import pt_push
        return jsonify({"ok": True, "cihaz": pt_push.gonder("Health", "Deneme bildirimi.", "/?u=pt", "pt-deneme")})

    # ---------------------------------------------------------------- su, kafein, sesli mesaj, takvim dosyası
    @app.post("/api/pt/su")
    def pt_su():
        d = pt.su_ekle(_tarih(), int(pt.sayi(_govde().get("ml"), -1000, 2000, 250)))
        return jsonify({"su_ml": d.get("su_ml"), "hedef": pt.su_hedefi()})

    @app.post("/api/pt/kafein")
    def pt_kafein():
        d = pt.kafein_ekle(_tarih())
        saat = dt.datetime.now().hour
        return jsonify({"kafein": d.get("kafein"), "uyari": "Bu saatten sonraki kafein uykunuzu bozabilir; yarın daha erken deneyin." if saat >= 15 else ""})

    @app.post("/api/pt/mesaj/ses")
    def pt_mesaj_ses():
        kod = _govde().get("hafta") or (pt.son_mesaj() or {}).get("hafta")
        if not kod:
            return jsonify({"hata": "Mesaj yok."}), 404
        y = pt.mesaj_sesi(kod)
        return jsonify({"url": f"/pt-mesaj-ses/{kod}.m4a"}) if y else (jsonify({"hata": "Ses üretilemedi."}), 500)

    @app.get("/pt-mesaj-ses/<kod>.m4a")
    def pt_mesaj_ses_dosya(kod):
        p_ = pt.MESAJLAR / f"{kod}.m4a"
        if not re.match(r"^\d{4}-W\d\d$", kod) or not p_.exists():
            abort(404)
        return send_file(p_, mimetype="audio/mp4", conditional=True)

    @app.get("/api/pt/takvim.ics")
    def pt_takvim_ics():
        kod = request.args.get("hafta") or pt.hafta_kodu()
        return Response(pt.takvim_dosyasi(kod), mimetype="text/calendar", headers={"Content-Disposition": f'attachment; filename="Health {kod}.ics"'})

    # ---------------------------------------------------------------- koç akışı: gün akışı, akşam ve pazar görüşmeleri, alışkanlık, ara soru
    @app.get("/api/pt/akis")
    def pt_akis():
        return jsonify(pt_koc.gun_akisi(_tarih()))

    @app.post("/api/pt/aksam")
    def pt_aksam():
        return jsonify(pt_koc.aksam_kaydet(_tarih(), _govde()))

    @app.get("/api/pt/haftalik-gorusme")
    def pt_haftalik_gorusme():
        kod = request.args.get("hafta") or pt.hafta_kodu()
        d = pt_koc.haftalik_sorular(kod)
        return jsonify({**d, "veri": {k: v for k, v in pt.hafta_verisi(kod).items() if k in ("planlanan_seans", "yapilan_seans", "en_iyi", "basamak_degisiklikleri", "seri_gun")}})

    @app.post("/api/pt/haftalik-gorusme")
    def pt_haftalik_kaydet():
        g = _govde()
        kod = g.get("hafta") or pt.hafta_kodu()
        istek = pt_koc.haftalik_kaydet(kod, g.get("cevaplar") or {}, g.get("aliskanlik"), g.get("kilo"), g.get("bel"))

        def is_():
            m = pt.koc_mesaji(kod)
            sonraki = pt.hafta_kodu(pt.hafta_gunleri(kod)[0] + dt.timedelta(days=7))
            pt.program_uret(sonraki, " ".join(x for x in (istek, m.get("plan_istegi") or "") if x))
            try:
                pt.mesaj_sesi(kod)
            except Exception:  # noqa: BLE001
                pass
            return m
        if not _arka("mesaj", "haftalık görüşme değerlendiriliyor, gelecek hafta yazılıyor", is_):
            return jsonify({"hata": "Haftalık değerlendirme zaten hazırlanıyor."}), 409
        return jsonify({"ok": True})

    @app.post("/api/pt/aliskanlik")
    def pt_aliskanlik():
        v = bool(_govde().get("tamam"))
        pt.gun_degistir(_tarih(), lambda d: d.update(aliskanlik={"tamam": v, "t": int(time.time())}))
        return jsonify(pt_koc.aliskanlik_bugun(_tarih()) or {})

    @app.post("/api/pt/ara-soru")
    def pt_ara_soru():
        g = _govde()
        r = pt_koc.ara_cevap(str(g.get("kod") or ""), g.get("cevap"))
        return jsonify({"ok": bool(r), "sonraki": pt_koc.ara_soru()})

    @app.post("/api/pt/menu/degistir")
    def pt_menu_degistir():
        import pt_yemek
        g = _govde()
        try:
            return jsonify(pt_yemek.ogun_degistir(g.get("hafta") or pt.hafta_kodu(), _tarih(g.get("tarih")), int(g.get("i") or 0), str(g.get("istek") or "")[:200]))
        except Exception as e:  # noqa: BLE001
            return jsonify({"hata": str(e)[:160]}), 400

    # ---------------------------------------------------------------- hareket görselleri (pt_medya: yapay zekâ animasyonları)
    @app.get("/pt-medya/<kod>/<ad>")
    def pt_medya_dosya(kod, ad):
        if ad not in ("video.mp4", "kapak.jpg", "bas.png", "bit.png", "k1.jpg", "k2.jpg", "k3.jpg", "k1_k.jpg", "k2_k.jpg", "k3_k.jpg",
                      "anatomi.jpg", "anatomi_k.jpg") or "/" in kod or ".." in kod:
            abort(404)
        p_ = pt.KLASOR / "pt_medya" / kod / ad
        if not p_.exists():
            abort(404)
        r = send_file(p_, conditional=True, max_age=86400)
        r.headers["Cache-Control"] = "public, max-age=86400"
        return r

    # ---------------------------------------------------------------- koçun sesi (pt_ses: önceden üretilmiş doğal Türkçe parçalar)
    @app.get("/api/pt/ses")
    def pt_ses_liste():
        import pt_ses
        return jsonify({"hazir": {m: f"/pt-ses/{k}.m4a" for m, k in pt_ses.hazir().items()}, "bekleyen": pt_ses.bekleyen()})

    @app.post("/api/pt/ses")
    def pt_ses_iste():
        import pt_ses
        n = pt_ses.iste([str(x)[:400] for x in (_govde().get("metinler") or [])][:400])
        if pt_ses.bekleyen() and "ses" not in calisan:
            def is_():
                while pt_ses.bekleyen() and pt_ses.calistir(log=lambda s: None):
                    pass
            _arka("ses", "koçun sesi hazırlanıyor", is_)
        return jsonify({"eklendi": n, "bekleyen": pt_ses.bekleyen()})

    @app.get("/pt-ses/<k>.m4a")
    def pt_ses_dosya(k):
        p_ = pt.KLASOR / "pt_medya" / "_ses" / f"{k}.m4a"
        if not re.match(r"^[0-9a-f]{16}$", k) or not p_.exists():
            abort(404)
        r = send_file(p_, mimetype="audio/mp4", conditional=True, max_age=31536000)
        r.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return r

    @app.get("/pt-kas/<kod>.jpg")
    def pt_kas_dosya(kod):
        p_ = pt.KLASOR / "pt_medya" / "_kas" / f"{kod}.jpg"
        if not re.match(r"^[a-z_]{2,20}$", kod) or not p_.exists():
            abort(404)
        r = send_file(p_, conditional=True, max_age=86400)
        r.headers["Cache-Control"] = "public, max-age=86400"
        return r

    @app.get("/api/pt/gorsel/durum")
    def pt_gorsel_durum():
        import pt_storyboard
        return jsonify(pt_storyboard.durum())


    # ---------------------------------------------------------------- BJJ
    @app.post("/api/pt/bjj")
    def pt_bjj():
        return jsonify({"kayit": pt.bjj_kaydet(_tarih(), _govde()), "ozet": pt.bjj_ozeti()})

    @app.get("/api/pt/bjj")
    def pt_bjj_ozet():
        o = pt.bjj_ozeti()
        o["oneri"] = []
        for poz, _ in o["zorlandigim"][:2]:
            o["oneri"].append({"pozisyon": poz, "drill": [{"kod": k, "ad": pt.KATALOG[k]["ad"]} for k in pt.BJJ_DRILL.get(poz, [])]})
        return jsonify(o)

    # ---------------------------------------------------------------- koç mesajı
    @app.get("/api/pt/mesaj")
    def pt_mesaj():
        kod = request.args.get("hafta")
        return jsonify(pt.mesaj(kod) if kod else pt.son_mesaj())

    @app.post("/api/pt/mesaj/uret")
    def pt_mesaj_uret():
        kod = _govde().get("hafta") or pt.hafta_kodu()
        if not _arka("mesaj", "haftalık koç mesajı yazılıyor", pt.koc_mesaji, kod):
            return jsonify({"hata": "Mesaj zaten yazılıyor."}), 409
        return jsonify({"ok": True})

    # ---------------------------------------------------------------- hareket videoları
    @app.post("/api/pt/hareket")
    def pt_hareket_ekle():
        f = request.files.get("video")
        if not f:
            return jsonify({"hata": "Video yok."}), 400
        gecici = Path(tempfile.mkdtemp(prefix="pt_video_")) / (Path(f.filename or "v.mov").name or "v.mov")
        f.save(gecici)
        if gecici.stat().st_size > 600 * 1024 * 1024:
            shutil.rmtree(gecici.parent, ignore_errors=True)
            return jsonify({"hata": "Video 600 MB'tan büyük; kısa bir kesit yükleyin."}), 400
        if shutil.disk_usage(pt.VERI).free < 2 * 1024 ** 3:
            shutil.rmtree(gecici.parent, ignore_errors=True)
            return jsonify({"hata": "Diskte yer az (2 GB'ın altında)."}), 507
        kod = request.form.get("kod") or None
        ipucu, bas, bit = request.form.get("ipucu") or "", request.form.get("bas") or None, request.form.get("bit") or None
        request_pozisyon = request.form.get("pozisyon") or None
        anahtar = f"video:{int(time.time() * 1000)}"

        def isle():
            try:
                return pt_hareket.ekle(gecici, kod, ipucu, bas, bit, request_pozisyon)
            finally:
                shutil.rmtree(gecici.parent, ignore_errors=True)
        _arka(anahtar, "hareket videosu işleniyor", isle)
        return jsonify({"ok": True, "is": anahtar})

    @app.post("/api/pt/hareket/<kod>")
    def pt_hareket_duzenle(kod):
        b = pt_hareket.duzenle(kod, _govde())
        return jsonify(b) if b else (jsonify({"hata": "Yok."}), 404)

    @app.delete("/api/pt/hareket/<kod>")
    def pt_hareket_sil(kod):
        return jsonify({"ok": pt_hareket.sil(kod)})

    @app.get("/pt-hareket/<kod>/<ad>")
    def pt_hareket_dosya(kod, ad):
        if ad not in ("video.mp4", "kapak.jpg") or "/" in kod or ".." in kod:
            abort(404)
        p = pt.HAREKETLER / kod / ad
        if not p.exists():
            abort(404)
        r = send_file(p, conditional=True, max_age=3600)
        r.headers["Cache-Control"] = "public, max-age=3600"
        return r

    # ---------------------------------------------------------------- bisiklet rotası
    @app.post("/api/pt/rota")
    def pt_rota_oner():
        g = _govde()
        lat, lon = g.get("lat"), g.get("lon")
        if lat is None:
            k = pt.profil().get("konum") or {}
            lat, lon = k.get("lat"), k.get("lon")
        if lat is None:
            return jsonify({"hata": "Konum yok. Ayarlar'da semtinizi yazın ya da konum izni verin."}), 400
        try:
            return jsonify(pt_rota.oner(float(lat), float(lon), int(g.get("sure_dk") or 60), g.get("yogunluk") or "kolay"))
        except Exception as e:  # noqa: BLE001
            return jsonify({"hata": f"Rota hesaplanamadı: {str(e)[:160]}"}), 502

    @app.get("/pt-rota/<rid>/<int:no>.gpx")
    def pt_rota_gpx(rid, no):
        if not rid.startswith("r") or not rid[1:].isdigit():
            abort(404)
        x = pt_rota.gpx(rid, no)
        if not x:
            abort(404)
        metin, ad = x
        return Response(metin, mimetype="application/gpx+xml", headers={"Content-Disposition": f'attachment; filename="{ad}.gpx"'.encode("utf-8").decode("latin-1", "ignore")})

    @app.post("/api/pt/konum")
    def pt_konum():
        ad = str(_govde().get("ad") or "").strip()
        k = pt_rota.konum_bul(ad) if ad else None
        if not k:
            return jsonify({"hata": "Bu adres bulunamadı."}), 404
        pt.profil_kaydet({"konum": k})
        return jsonify(k)

    # ---------------------------------------------------------------- erişim, dışa aktarma, çevrimdışı
    # /api/pt/erisim ve /api/pt/esles: sunucu/26_pt_uzak.py (Meet'in eşleştirilmiş telefon yolu)
    @app.get("/api/pt/disa-aktar")
    def pt_disa():
        return Response(json.dumps(pt.disa_aktar(), ensure_ascii=False, indent=1), mimetype="application/json",
                        headers={"Content-Disposition": f"attachment; filename=Health {pt.bugun().isoformat()}.json"})

    @app.get("/pt-sw.js")
    def pt_sw():
        r = send_file(Path(app.static_folder) / "pt-sw.js", mimetype="text/javascript", max_age=0)
        r.headers["Service-Worker-Allowed"] = "/"
        r.headers["Cache-Control"] = "no-cache"
        return r

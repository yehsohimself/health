"""PT hedefler, ara kontrol ve puan (2026-10-30). Claude kapalı: öneri ve karar kural tabanlı."""
import datetime as dt
import json

import pytest

BUGUN = dt.date(2026, 10, 30)


@pytest.fixture
def ptv(kok, tmp_path, monkeypatch):
    import pt
    import pt_hedef
    import pt_kontrol
    import pt_oyun
    v = tmp_path / "pt"
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program"), ("MESAJLAR", v / "mesajlar"), ("HAREKETLER", v / "hareketler")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pt, "bugun", lambda: BUGUN)
    monkeypatch.setattr(pt_oyun, "OYUN", v / "oyun.json")
    monkeypatch.setattr(pt_hedef, "HEDEFLER", v / "hedefler.json")
    monkeypatch.setattr(pt_kontrol, "DEGERLENDIRME", v / "degerlendirme.json")
    monkeypatch.setattr(pt_kontrol, "KONTROLLER", v / "kontroller")
    monkeypatch.setenv("VH_CLAUDE_YOK", "1")
    pt_oyun._onbellek.clear()
    pt.profil_kaydet({"ad": "Test", "kilo_kg": 90, "hedef_kilo_kg": 80, "boy_cm": 180, "dogum_tarihi": "1990-01-01", "hedef_turleri": ["kilo", "beceri"],
                      "beceri_hedefleri": ["barfiks"], "gunler": [0, 2, 4], "gunluk_dk": 30, "kuruldu": True, "ekipman": ["mat"]})
    return pt


def _gun(pt, fark, **alan):
    t = (BUGUN - dt.timedelta(days=fark)).isoformat()
    d = {"tarih": t, "seanslar": [], "yemekler": [], "agri": [], "bjj": [], **alan}
    (pt.GUNLUK / f"{t}.json").write_text(json.dumps(d), encoding="utf-8")
    return t


def _plan(pt, gun_farklari):
    haftalar = {}
    for f in gun_farklari:
        g = BUGUN - dt.timedelta(days=f)
        haftalar.setdefault(pt.hafta_kodu(g), []).append(g.isoformat())
    for kod, gunler in haftalar.items():
        pt._yaz(pt.program_yolu(kod), {"hafta": kod, "gunler": [{"tarih": t, "tur": "kalistenik", "baslik": "Tüm vücut", "sure_dk": 20, "id": t, "bolumler": []} for t in gunler]})


def test_hedef_adaylari_olculebilir_ve_tekil(ptv):
    import pt_hedef
    ptv.test_kaydet({"sinav_max": 10, "squat_max": 15, "plank_sn": 30, "hollow_sn": 15}, (BUGUN - dt.timedelta(days=1)).isoformat())
    A = pt_hedef.adaylar()
    assert A and all(a["olcu"]["tur"] in ("kilo", "bel", "seans", "seri", "test", "basamak") for a in A)
    assert any(a["olcu"]["tur"] == "kilo" and a["vade"] == "uzun" and a["olcu"]["hedef"] == 80 for a in A)
    anahtar = [(a["vade"], a["olcu"]["tur"], a["olcu"].get("kod"), a["olcu"].get("hedef")) for a in A]
    assert len(anahtar) == len(set(anahtar))
    assert "(trend)" not in json.dumps(A)
    o = pt_hedef.oner()
    assert [h["vade"] for h in o["hedefler"]] == ["kisa", "orta", "uzun"]
    assert len({(h["olcu"]["tur"], h["olcu"].get("beceri")) for h in o["hedefler"]}) == 3      # üç vade üç ayrı ölçü
    secili = {h["aday"] for h in o["hedefler"]}
    assert not any(s["aday"] in secili for s in o["secenekler"])


def test_hedef_kaydet_ve_kodla_ilerleme(ptv):
    import pt_hedef
    _gun(ptv, 3, kilo=90)
    kaydet = pt_hedef.kaydet([{"vade": "kisa", "metin": "4 haftada 10 antrenman", "olcu": {"tur": "seans", "hedef": 10, "baslangic": 0}},
                              {"vade": "orta", "metin": "88 kg", "olcu": {"tur": "kilo", "hedef": 88, "baslangic": 90, "yon": "azalis", "birim": "kg"}},
                              {"vade": "uzun", "metin": "İlk BJJ turnuvam", "kendi": True}])
    assert [h["vade"] for h in kaydet] == ["kisa", "orta", "uzun"]
    serbest = next(h for h in kaydet if h["vade"] == "uzun")
    assert serbest["olcu"]["tur"] == "serbest" and serbest["yolda"] == "elle" and serbest["kaynak"] == "kendi"
    for f in (0, 1):
        _gun(ptv, f, seanslar=[{"bitti": True, "sure_dk": 20, "tur": "kalistenik"}], kilo=89.6 if f else 89.4)
    L = {h["vade"]: h for h in pt_hedef.aktif()}
    assert L["kisa"]["simdi"] == 1 and L["kisa"]["oran"] == 0.1 and L["kisa"]["yolda"] == "yolunda"      # hedef bugün başladı; dünkü seans sayılmaz
    assert L["orta"]["simdi"] < 90 and 0 < L["orta"]["oran"] < 1 and "kg" in L["orta"]["simdi_metni"]
    # aynı vadede yeni hedef eskisini "degisti" yapar
    pt_hedef.kaydet([{"vade": "kisa", "metin": "14 gün seri", "olcu": {"tur": "seri", "hedef": 14}}])
    assert [h["metin"] for h in pt_hedef.aktif() if h["vade"] == "kisa"] == ["14 gün seri"]
    assert pt_hedef.istem_metni().startswith("Kısa vade")
    # hedefe ulaşınca kendiliğinden tamam ve puan
    for f in range(2, 12):
        _gun(ptv, f, seanslar=[{"bitti": True, "sure_dk": 20, "tur": "kalistenik"}])
    pt_hedef.kaydet([{"vade": "kisa", "metin": "4 haftada 5 antrenman", "olcu": {"tur": "seans", "hedef": 5, "baslangic": 0}}])
    d = pt_hedef._oku()
    d["hedefler"][-1]["bas"] = (BUGUN - dt.timedelta(days=20)).isoformat()
    pt_hedef._yaz(d)
    olaylar = pt_hedef.kendiliginden_tamamla()
    assert olaylar and olaylar[0]["tur"] == "hedef"
    assert any(h["durum"] == "tamam" for h in pt_hedef.hepsi())


def test_kontrol_zamani_rapor_ve_kural_karari(ptv):
    import pt_kontrol
    import pt_hedef
    z = pt_kontrol.zamani()
    assert not z["zamani"] and z["kalan"] == 14                          # kurulum bugün: 14 gün sonra
    _plan(ptv, [1, 3, 5, 7, 9, 11, 13, 15])
    for f in (1, 5, 9):                                                  # 8 planlı seansın 3'ü yapıldı, hepsi kolay
        _gun(ptv, f, seanslar=[{"bitti": True, "sure_dk": 20, "tur": "kalistenik", "zorluk": 3}], sabah={"isik": "yesil", "uyku_saat": 6})
    _gun(ptv, 2, agri=[{"bolge": "diz", "puan": 5, "tur": "eklem"}], sabah={"isik": "sari", "uyku_saat": 5.5})
    _gun(ptv, 15, sabah={"isik": "yesil"})
    ptv._yaz(ptv.VERI / "ilk_hafta.json", {"bas": None, "tamam": [], "birakti": True})      # ilk hafta yolu sürerken kontrol açılmaz
    z = pt_kontrol.zamani()
    assert z["zamani"] and z["gun"] >= 14
    r = pt_kontrol.rapor()
    assert r["planlanan_seans"] == 7 and r["yapilan_seans"] == 3 and r["uyum"] == 0.43 and r["zorluk_ort"] == 3.0   # 15 gün önceki plan pencere dışı
    assert r["agri"] and r["uyku_ort"] < 6.5
    k = pt_kontrol.hazirla()
    assert k["durum"] == "acik" and len(k["sorular"]) >= 3 and pt_kontrol.zamani()["acik"]
    pt_hedef.kaydet([{"vade": "kisa", "metin": "4 haftada 12 antrenman", "olcu": {"tur": "seans", "hedef": 12, "baslangic": 0}}])
    k2 = pt_kontrol.bitir(k["tarih"], {"uyum": "Vakit", "zorluk": "Kolay", "beslenme": "Az", "ozel": "Seyahat"})
    s = k2["sonuc"]
    assert s["karar"] == "guncelle" and s["yazan"] == "kural"
    alanlar = {x["alan"] for x in s["degisiklikler"]}
    assert {"antrenman", "toparlanma"} <= alanlar
    assert s["uygulanan"]["gunluk_dk"] == 20 and s["uygulanan"]["gun_sayisi"] == 2       # uyum düşük: daha küçük plan
    p = ptv.profil()
    assert p["gunluk_dk"] == 20 and len(p["gunler"]) == 2 and p["kontrol_istegi"] and p["son_kontrol"] == k["tarih"]
    assert s["hedef_notu"] and s["sonraki"]
    z = pt_kontrol.zamani()
    assert not z["zamani"] and z["sayi"] == 1 and z["kalan"] == 14
    assert pt_kontrol.gecmis()[-1]["durum"] == "bitti"
    with pytest.raises(ValueError):
        pt_kontrol.bitir("2020-01-01", {})


def test_degerlendirme_kural_tabanli_ve_imza(ptv):
    import pt_kontrol
    d = pt_kontrol.degerlendirme()
    assert d["yazan"] == "kural" and d["mesaj"] and d["antrenman"]["yaklasim"] and d["beslenme"]["yaklasim"] and not d["okundu"]
    assert pt_kontrol.degerlendirme()["zaman"] == d["zaman"]            # önbellek
    pt_kontrol.degerlendirme_isaretle(True)
    assert pt_kontrol.degerlendirme_oku()["okundu"] and not pt_kontrol.degerlendirme_oku()["eski"]
    ptv.profil_kaydet({"gunluk_dk": 45})
    assert pt_kontrol.degerlendirme_oku()["eski"]
    o = pt_kontrol.ozet()
    assert o["degerlendirme"]["var"] and o["degerlendirme"]["eski"] and "kontrol" in o


def test_puan_seviye_ve_ek_gorevler(ptv):
    import pt_oyun
    t = _gun(ptv, 0, sabah={"isik": "yesil"}, seanslar=[{"bitti": True, "sure_dk": 25, "tur": "kalistenik"}], yemekler=[{"id": "a"}, {"id": "b"}], su_ml=5000)
    o = pt_oyun.ozet()
    P = o["puan"]
    assert P["bugun"] >= pt_oyun.PUAN["seans"] + 25 + pt_oyun.PUAN["sabah"] + 2 * pt_oyun.PUAN["ogun"] + pt_oyun.PUAN["su"]
    assert P["hedef"] == pt_oyun.GUNLUK_PUAN_HEDEF and P["seviye"]["no"] == 1 and P["seviye"]["sonraki"]
    assert len(P["ek_gorevler"]) == 3 and not any(g["tamam"] for g in P["ek_gorevler"])
    kod = P["ek_gorevler"][0]["kod"]
    pt_oyun.ek_gorev_isaretle(t, kod, True)
    P2 = pt_oyun.ozet()["puan"]
    assert P2["bugun"] == P["bugun"] + P["ek_gorevler"][0]["puan"] and next(g for g in P2["ek_gorevler"] if g["kod"] == kod)["tamam"]
    pt_oyun.ek_gorev_isaretle(t, kod, False)
    assert pt_oyun.ozet()["puan"]["bugun"] == P["bugun"]
    with pytest.raises(ValueError):
        pt_oyun.ek_gorev_isaretle(t, "yok_boyle", True)
    assert pt_oyun.ek_gorevler_gun(t, {"masa": False}) == pt_oyun.ek_gorevler_gun(t, {"masa": False})     # aynı gün aynı görevler
    assert "mola" not in pt_oyun.ek_gorevler_gun(t, {"masa": False})
    assert pt_oyun.seviye_bul(0)["ad"] == "Başlangıç" and pt_oyun.seviye_bul(1600)["no"] == 5 and pt_oyun.seviye_bul(99999)["oran"] == 1.0

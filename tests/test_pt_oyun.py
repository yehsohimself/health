"""PT seri motoru, hızlı antrenman ve kitaplık uçları (2026-10-27)."""
import datetime as dt
import json

import pytest

BUGUN = dt.date(2026, 10, 28)                      # Çarşamba


@pytest.fixture
def ptv(kok, tmp_path, monkeypatch):
    """pt modülünü boş, geçici bir veri klasörüne ve sabit bir güne bağlar."""
    import pt
    import pt_oyun
    import pt_kitaplik
    v = tmp_path / "pt"
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program"), ("MESAJLAR", v / "mesajlar"), ("HAREKETLER", v / "hareketler")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pt, "bugun", lambda: BUGUN)
    monkeypatch.setattr(pt_oyun, "OYUN", v / "oyun.json")
    monkeypatch.setattr(pt_kitaplik, "KAYDEDILENLER", v / "kaydedilenler.json")
    pt_oyun._onbellek.clear()
    pt_kitaplik._onbellek.clear()
    return pt


def _gun(pt, fark, **alan):
    t = (BUGUN - dt.timedelta(days=fark)).isoformat()
    d = {"tarih": t, "seanslar": [], "yemekler": [], "agri": [], "bjj": [], **alan}
    (pt.GUNLUK / f"{t}.json").write_text(json.dumps(d), encoding="utf-8")
    return t


def _seans(**ek):
    return {"bitti": True, "sure_dk": 20, "tur": "kalistenik", **ek}


def _plan(pt, gunler):
    """{fark: tur} → ilgili haftaların program dosyaları."""
    hafta = {}
    for fark, tur in gunler.items():
        g = BUGUN - dt.timedelta(days=fark)
        hafta.setdefault(pt.hafta_kodu(g), []).append({"tarih": g.isoformat(), "tur": tur, "id": f"g{fark}"})
    for kod, L in hafta.items():
        (pt.PROGRAM / f"{kod}.json").write_text(json.dumps({"gunler": L}), encoding="utf-8")


def test_seri_ilk_tamam_gunle_baslar_ve_bugun_bekler(ptv):
    import pt_oyun
    _plan(ptv, {i: "kalistenik" for i in range(6)})
    _gun(ptv, 5)                                    # hiçbir şey yapılmamış ilk gün: seri henüz başlamadı, kopmuş sayılmaz
    _gun(ptv, 2, seanslar=[_seans()])
    _gun(ptv, 1, seanslar=[_seans()])
    h = pt_oyun.hesap()
    assert h["seri"] == 2 and h["kopus"] is None
    assert [x["durum"] for x in h["gunler"]][:3] == ["once", "once", "once"]
    assert h["bugun"]["durum"] == "bekliyor" and h["bugun"]["hedef"] == "seans"


def test_koruma_harcanir_sonra_kopar_ve_telafiyle_doner(ptv):
    import pt_oyun
    _plan(ptv, {i: "kalistenik" for i in range(8)})
    for f in (7, 6, 5, 4):
        _gun(ptv, f, seanslar=[_seans()])
    _gun(ptv, 3)                                    # koruma (başta 1) harcanır
    _gun(ptv, 2)                                    # koruma yok: seri 4'te koptu
    h = pt_oyun.hesap()
    assert [x["durum"] for x in h["gunler"] if x["tarih"] >= (BUGUN - dt.timedelta(days=3)).isoformat()][:2] == ["korundu", "kacti"]
    assert h["seri"] == 0 and h["kopus"]["seri"] == 4
    o = pt_oyun.ozet()["onarim"]
    assert o and o["seri"] == 4 and o["gunler"] == [(BUGUN - dt.timedelta(days=d)).isoformat() for d in (2, 1)]   # dün de kaçtı
    pt_oyun._onbellek.clear()
    assert pt_oyun.onarim_gecerli([(BUGUN - dt.timedelta(days=9)).isoformat()]) == []   # pencere dışı reddedilir
    gecerli = pt_oyun.onarim_gecerli([(BUGUN - dt.timedelta(days=d)).isoformat() for d in (2, 1)])
    assert len(gecerli) == 2
    (ptv.GUNLUK / f"{BUGUN.isoformat()}.json").write_text(json.dumps({"tarih": BUGUN.isoformat(), "seanslar": [_seans(onarim_icin=gecerli)]}), encoding="utf-8")
    pt_oyun._onbellek.clear()
    h = pt_oyun.hesap()
    assert h["seri"] == 7 and h["onarim"] is None   # 4 + 2 onarılan + bugün


def test_dinlenme_ve_kirmizi_gun_kontrolle_tamam(ptv):
    import pt_oyun
    _plan(ptv, {3: "kalistenik", 2: "dinlenme", 1: "kalistenik"})
    _gun(ptv, 3, seanslar=[_seans()])
    _gun(ptv, 2, sabah={"isik": "yesil"})           # dinlenme günü: kontrol yeter
    _gun(ptv, 1, sabah={"isik": "kirmizi", "hasta": True})  # hasta: antrenman hedefi kalkar
    h = pt_oyun.hesap()
    assert h["seri"] == 3 and h["koruma"] == 1
    assert [x["hedef"] for x in h["gunler"][-4:-1]] == ["seans", "kontrol", "kontrol"]


def test_yedi_gunde_koruma_kazanilir_en_cok_iki(ptv):
    import pt_oyun
    for f in range(15, 0, -1):
        _gun(ptv, f, seanslar=[_seans()])
    h = pt_oyun.hesap()
    assert h["seri"] == 15 and h["koruma"] == 2 and h["koruma_sonraki"] is None
    assert any(o["tur"] == "koruma" for o in h["olaylar"])
    assert {r["kod"] for r in h["rozetler"] if r["kazanildi"]} >= {"seans_1", "seri_7", "seans_10"}
    yeni = pt_oyun.yeni_olaylar(h, gun=30)
    pt_oyun.goruldu([o["id"] for o in yeni])
    assert pt_oyun.yeni_olaylar(h, gun=30) == []


def test_hizli_antrenman_sureye_ve_ekipmana_uyar(ptv, monkeypatch):
    import pt_hizli
    p = {"ekipman": ["bar", "mat"]}
    for odak in ("tum", "ust", "alt", "govde", "kondisyon", "flow", "bjj", "mobilite"):
        for dk in (10, 20, 30):
            s = pt_hizli.olustur(dk, odak, "ev", tohum=1, p=p)
            assert s["bolumler"] and abs(s["sure_dk"] - dk) <= max(4, dk * .4), (odak, dk, s["sure_dk"])
    kat = ptv.katalog()
    s = pt_hizli.olustur(20, "ust", "yolda", tohum=2, p=p)
    assert all(kat[h["kod"]]["ekipman"] in ("yok", "mat", "duvar") for b in s["bolumler"] for h in b["hareketler"])
    assert all(kat[h["kod"]]["zincir"] not in ("kalca", "bacak") for b in s["bolumler"] if b["ad"] == "Ana bölüm" for h in b["hareketler"])
    t = pt_hizli.olustur(kod="sinav", p=p)
    assert t["tek"] == "sinav" and any(h["kod"] == "sinav" for b in t["bolumler"] for h in b["hareketler"])
    with pytest.raises(ValueError):
        pt_hizli.olustur(kod="yok_boyle", p=p)


def test_api_seans_telafiyi_suzer_ve_oyun_doner(ptv, istemci):
    import pt_oyun
    eski = (BUGUN - dt.timedelta(days=20)).isoformat()
    r = istemci.post("/api/pt/seans", json={"seans": {"tur": "asgari", "sure_dk": 10, "onarim_icin": [eski]}})
    j = r.get_json()
    assert r.status_code == 200 and "onarim_icin" not in j["seans"] and j["oyun"]["seri"] == 1 and j["onceki_seri"] == 0
    assert pt_oyun.hesap()["bugun"]["durum"] == "tamam"
    assert istemci.post("/api/pt/kaydedilen", json={"kod": "yok_boyle"}).status_code == 400
    assert istemci.post("/api/pt/kaydedilen", json={"kod": "sinav"}).get_json()["kaydedilen"] == ["sinav"]
    assert istemci.post("/api/pt/hizli", json={"sure": 10, "odak": "govde"}).get_json()["bolumler"]
    g = istemci.get("/api/pt/hareket-gecmis/sinav").get_json()
    assert g["kod"] == "sinav" and g["kayitlar"] == []


def test_gorevler_halka_ve_rozet_seviyeleri(ptv):
    import pt_oyun
    _plan(ptv, {0: "kalistenik", 1: "dinlenme"})
    _gun(ptv, 1, sabah={"isik": "yesil"})
    _gun(ptv, 0, seanslar=[_seans(sure_dk=25)], sabah={"isik": "yesil"}, aksam={"puan": 3}, su_ml=5000,
         yemekler=[{"ad": "a", "protein": 200, "kcal": 900}, {"ad": "b", "protein": 100, "kcal": 900}], aliskanlik={"tamam": True})
    o = pt_oyun.ozet()
    assert len(o["gorevler"]) == 3 and o["gorevler"][0]["kod"] == "seans" and len({g["kod"] for g in o["gorevler"]}) == 3
    assert all(g["tamam"] for g in o["gorevler"]) and o["gorev_gun"] == 1
    assert pt_oyun.ozet()["gorevler"] == o["gorevler"]                       # aynı gün hep aynı görevler
    assert o["halka"]["dk"] == 25 and o["halka"]["hedef_dk"] == 90 and o["halka"]["seans"] == 1   # planda süre yoksa 90 dk
    t = pt_oyun.tam()
    a = {x["kod"]: x for x in t["aileler"]}
    assert a["seans"]["seviye"] == 1 and a["seans"]["sonraki"]["hedef"] == 10 and a["gorev"]["seviye"] == 1
    assert {r["kod"] for r in t["rozetler"]} >= {"seans_1", "seans_10", "seri_7", "hafta_1", "sabah_30", "bjj_10"}   # eski kimlikler korunur
    assert any(x["tur"] == "gorev" for x in pt_oyun.yeni_olaylar())


def test_program_secilir_seans_sayilir_ve_biter(ptv, istemci, monkeypatch):
    import pt_programlar
    monkeypatch.setitem(pt_programlar.P, "deneme", {**pt_programlar.P["guclu_govde"], "kod": "deneme", "hafta": 1, "gun": 2})
    assert istemci.post("/api/pt/program-sec", json={"kod": "yok"}).status_code == 400
    assert istemci.post("/api/pt/program-sec", json={"kod": "deneme"}).get_json()["aktif"] == "deneme"
    s = istemci.post("/api/pt/program-antrenman", json={"nerede": "ev"}).get_json()
    assert s["program"] == "deneme" and s["program_hafta"] == 1 and s["bolumler"]
    r = istemci.post("/api/pt/seans", json={"seans": {"tur": "kalistenik", "sure_dk": 15, "program": "baska_program"}}).get_json()
    assert "program" not in r["seans"] and r["program_bitti"] is None                # etkin olmayan program sayılmaz
    for _ in range(2):
        r = istemci.post("/api/pt/seans", json={"seans": {"tur": "kalistenik", "sure_dk": 15, "program": "deneme", "program_hafta": 1}}).get_json()
    assert r["program_bitti"] == pt_programlar.P["deneme"]["ad"]
    assert pt_programlar.aktif() is None and ptv.profil()["program_biten"][0]["kod"] == "deneme"

def _beslenme_yollari(pt, monkeypatch):
    import pt_beslenme
    import pt_oneri
    for ad, yol in (("DOSYA", pt.VERI / "beslenme.json"), ("FAVORI", pt.VERI / "favoriler.json"), ("DUZELTME", pt.VERI / "yemek_duzeltme.json"),
                    ("FOTO", pt.VERI / "yemek_foto")):
        monkeypatch.setattr(pt_beslenme, ad, yol)
    monkeypatch.setattr(pt_oneri, "DOSYA", pt.VERI / "oneriler.json")
    return pt_beslenme, pt_oneri


def test_gramdan_hesap_atwater_ve_duzeltme_ogrenme(ptv, monkeypatch):
    B, _ = _beslenme_yollari(ptv, monkeypatch)
    y = B._atwater({"kcal": 50, "protein": 10, "yag": 10, "karb": 10})     # 4·10+4·10+9·10 = 170: tutarsız kcal makrolardan
    assert y["kcal"] == 170
    k = B.kalem_hesapla({"ad": "Pilav", "miktar_g": 200, "yuz": {"kcal": 130, "protein": 2.7, "yag": 0.3, "karb": 28, "lif": 0.4, "doymus": 0.1}})
    assert k["kcal"] == 260 and k["protein"] == 5.4 and k["lif"] == 0.8
    for _ in range(2):                                                    # iki kez pilavı tahminin 1,5 katına çıkarıp yağ ekledi
        B.duzeltme_kaydet({"kalemler": [{"ad": "Pilav", "miktar_g": 180}]},
                          {"ad": "Öğle", "kalemler": [{"ad": "Pilav", "miktar_g": 270}, {"ad": "Tereyağı", "miktar_g": 10}]})
    n = B._duzeltme_notu()
    assert "pilav" in n and "1.5" in n and "tereyağı" in n
    t = ptv.bugun().isoformat()
    B.yemek_kaydet(t, {"ad": "Öğle", "kalemler": [k], "tahmin": {"kalemler": [{"ad": "Pilav", "miktar_g": 200}]}})
    assert "tahmin" not in ptv.gun(t)["yemekler"][0]
    assert B.gun_toplam(ptv.gun(t))["lif"] == 1


def test_oneri_ekipman_test_ve_susturma(ptv, monkeypatch):
    _, O = _beslenme_yollari(ptv, monkeypatch)
    ptv.profil_kaydet({"beceri_hedefleri": ["barfiks"], "ekipman": ["mat"], "kuruldu": True})
    I = O.ihtiyaclar()
    kod = [x["kod"] for x in I]
    assert kod[0] == "test" and "ekipman_bar" in kod
    O.kapat("ekipman_bar", "kalici", "almayacağım")
    assert "ekipman_bar" not in [x["kod"] for x in O.ihtiyaclar()]
    assert json.loads((ptv.VERI / "oneriler.json").read_text())["ret"][0]["neden"] == "almayacağım"
    assert "ilk_barfiks" in [x["kod"] for x in O.program_onerileri()]
    O.siklik_ayarla("kapali")
    assert O.bugun_icin() is None


def test_oneri_aradan_donus_ve_protein(ptv, monkeypatch):
    B, O = _beslenme_yollari(ptv, monkeypatch)
    ptv.profil_kaydet({"kilo_kg": 90, "boy_cm": 180, "kuruldu": True})
    _gun(ptv, 14, seanslar=[_seans()])
    for f in (1, 2, 3):
        _gun(ptv, f, yemekler=[{"ad": "x", "kalemler": [{"ad": "x", "kcal": 1200, "protein": 40}]}])
    kod = [x["kod"] for x in O.ihtiyaclar()]
    assert "geri_donus" in kod and "protein" in kod


def test_bls_kalem_dogrudan_ve_tariften():
    """BLS seçimi kalemin 100 g değerini değiştirir; tariften gelen değer gram ağırlıklı ortalamadır."""
    import pt_beslenme
    yuz = lambda kcal, p: {"kcal": kcal, "protein": p, "yag": 0, "karb": 0, "lif": 0, "doymus": 0}
    secim = {"0": {"kod": "X820162", "de": "Reis gekocht", "en": "Rice boiled", "yuz": yuz(112, 2.5)},
             "1.0": {"kod": "A", "de": "Mehl", "en": "Flour", "yuz": yuz(350, 10)},
             "1.1": {"kod": "B", "de": "Sesam", "en": "Sesame", "yuz": yuz(600, 20)}}
    k0 = {"ad": "Pilav", "miktar_g": 200}
    assert pt_beslenme._bls_uygula(k0, 0, secim) and k0["bls"] == "X820162"
    assert pt_beslenme.kalem_hesapla(k0)["kcal"] == 224
    k1 = {"ad": "Simit", "miktar_g": 100, "tarif_ham": [{"ad": "un", "g": 80}, {"ad": "susam", "g": 20}]}
    assert pt_beslenme._bls_uygula(k1, 1, secim) and k1["yuz"]["kcal"] == 400 and k1["bls"] == "tarif"
    k2 = {"ad": "Mantı", "miktar_g": 100, "tarif_ham": [{"ad": "un", "g": 30}, {"ad": "kıyma", "g": 70}]}
    assert not pt_beslenme._bls_uygula(k2, 2, secim)          # malzemelerin çoğu eşleşmedi: tahmin kalır


def test_yol_kacisi_ve_tarih_hafta_dogrulama(ptv, istemci):
    """2026-10-28 güvenlik turu: '..' hareket kodu pt/ klasörünü taşıyordu; tarih/hafta değerleri dosya yolu oluyordu."""
    import pt_hareket
    (ptv.VERI / "profil.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        pt_hareket.sil("..")
    assert ptv.VERI.exists()
    assert istemci.delete("/api/pt/hareket/%2e%2e").status_code in (400, 404)
    assert ptv.VERI.exists() and (ptv.VERI / "profil.json").exists()
    with pytest.raises(ValueError):
        ptv.gun_yolu("../profil")
    with pytest.raises(ValueError):
        ptv.program_yolu("../../x")
    assert istemci.post("/api/pt/menu/alindi", json={"hafta": "../profil", "id": "a", "durum": True}).status_code == 400
    assert istemci.post("/api/pt/kilo", json={"kilo": "nan", "tarih": BUGUN.isoformat()}).status_code == 400
    assert istemci.post("/api/pt/kilo", json={"kilo": 900}).status_code == 400
    assert istemci.post("/api/pt/kilo", json={"kilo": "82,4"}).status_code == 200
    assert istemci.delete("/api/pt/yemek/bozuk-tarih/y1").status_code == 400


def test_sabah_metin_sayilar_ve_ana_ekran_dayanikli(ptv, istemci):
    r = istemci.post("/api/pt/sabah", json={"enerji": "2", "uyku": "kotu", "agri": [{"bolge": "omuz", "puan": "7"}], "vakit_dk": "15"})
    assert r.status_code == 200 and r.get_json()["isik"] == "kirmizi"
    d = ptv.gun(BUGUN.isoformat())
    assert d["sabah"]["agri"][0]["puan"] == 7 and d["sabah"]["vakit_dk"] == 15 and d["sabah"]["enerji"] == 2
    assert istemci.get("/api/pt").status_code == 200


def test_testler_parca_parca_birlesir(ptv):
    assert ptv.test_gerekli() and ptv.test_eksikleri() == list(ptv.TEMEL_TESTLER)
    ptv.test_kaydet({"sinav_max": 6})
    ptv.test_kaydet({"squat_max": 20})
    k = ptv.testler()["kayitlar"]
    assert len(k) == 1 and k[0]["sonuclar"] == {"sinav_max": 6, "squat_max": 20}
    assert ptv.test_gerekli()
    ptv.test_kaydet({"hollow_sn": 20, "plank_sn": 45})
    assert not ptv.test_gerekli()


def test_kalori_hedefi_yapilmayan_antrenmani_saymaz(ptv, monkeypatch):
    import pt_beslenme
    monkeypatch.setattr(pt_beslenme, "DOSYA", ptv.VERI / "beslenme.json")
    p = {"cinsiyet": "erkek", "yas": 40, "boy_cm": 180, "kilo_kg": 100, "hedef_kilo_kg": 85, "beslenme": {"kilo_hizi": 1.0},
         "ek_bilgi": [{"soru": "İş", "cevap": "Masa başı"}]}
    h = pt_beslenme.hedefler(p)
    bmr = pt_beslenme.bmr(p)
    assert pt_beslenme.etkinlik_carpani(p) == 1.25                   # antrenman yapılmadıysa masa başı tabanı
    assert h["acik"] == round(100 * 0.7 / 100 * 7700 / 7)            # en çok %0,7/hafta
    assert h["kcal"] >= round(bmr * 1.1)                             # dinlenme metabolizmasının altına inmez
    _gun(ptv, 1, seanslar=[_seans(sure_dk=60)])
    assert pt_beslenme.etkinlik_carpani(p) > 1.25


def test_alisma_haftasi_kodla_sinirlanir(ptv, monkeypatch):
    import claude_yaz
    gunler = [g.isoformat() for g in ptv.hafta_gunleri(ptv.hafta_kodu())]
    plan = {"gunler": [{"tarih": t, "tur": "kalistenik", "baslik": "K", "sure_dk": "45 dk", "bolumler": []} for t in gunler]}
    monkeypatch.setattr(claude_yaz, "sor_json", lambda *a, **k: plan)
    assert ptv.baslangic_durumu()["tur"] == "alisma"
    pl = ptv.program_uret(ptv.hafta_kodu())
    aktif = [g for g in pl["gunler"] if g["tur"] != "dinlenme"]
    assert len(aktif) <= 5 and all(g["sure_dk"] <= 20 for g in aktif) and pl["baslangic"] == "alisma"


def test_bozuk_kayit_yedeklenir(ptv):
    f = ptv.VERI / "profil.json"
    f.write_text('{"ad": "x"', encoding="utf-8")
    assert ptv._json(f, {"bos": 1}) == {"bos": 1}
    assert list(ptv.VERI.glob("profil.json.bozuk-*"))
    ptv._yaz(f, {"a": 1})
    assert ptv._json(f) == {"a": 1} and not list(ptv.VERI.glob("*.yeni"))


def test_ilk_hafta_yolu_sirayla_ilerler_ve_biter(ptv, istemci):
    """İlk hafta: tek adım, kaçırılan gün ceza değil (sıra), test adımı yapılmış testlerde atlanır, yarım seans saymaz, atlanabilir."""
    import pt_ilk
    d = pt_ilk.durum()
    assert d["aktif"] and d["adim"] == 0 and d["simdi"]["tur"] == "test" and d["simdi"]["testler"] == pt_ilk.TEST_1
    istemci.post("/api/pt/ilk", json={"tamam": 0})
    d = pt_ilk.durum()
    assert d["adim"] == 1 and d["bugun_tamam"] and d["simdi"]["seans"]["ilk_adim"] == 1 and d["simdi"]["seans"]["bolumler"]
    r = istemci.post("/api/pt/seans", json={"seans": {"tur": "kalistenik", "sure_dk": 6, "ilk_adim": 1, "yarim": True}})
    assert r.status_code == 200 and pt_ilk.durum()["adim"] == 1             # yarım bırakılan adım saymaz
    istemci.post("/api/pt/seans", json={"seans": {"tur": "kalistenik", "sure_dk": 10, "ilk_adim": 1}})
    istemci.post("/api/pt/seans", json={"seans": {"tur": "kalistenik", "sure_dk": 10, "ilk_adim": 1}})   # ikinci kez sayılmaz
    assert pt_ilk.durum()["adim"] == 2
    ptv.test_kaydet({k: 10 for k in pt_ilk.TEST_2})                         # ikinci testler zaten yapılmış → adım geçer
    assert pt_ilk.durum()["adim"] == 3
    for i in range(3, 7):
        pt_ilk.tamamla(i)
    d = pt_ilk.durum()
    assert not d["aktif"] and d["bitti"] and d["kutla"]
    j = istemci.get("/api/pt").get_json()
    assert j["ilk"]["bitti"]


def test_ilk_hafta_alismis_kullaniciya_acilmaz_ve_atlanir(ptv, istemci):
    import pt_ilk
    for i in range(6):
        _gun(ptv, i + 1, seanslar=[_seans()])
    assert not pt_ilk.durum()["aktif"]
    for f in ptv.GUNLUK.glob("*.json"):
        f.unlink()
    assert pt_ilk.durum()["aktif"]
    assert not istemci.post("/api/pt/ilk", json={"birak": True}).get_json()["ilk"]["aktif"]
    assert istemci.post("/api/pt/ilk", json={"birak": False}).get_json()["ilk"]["aktif"]


def test_dunku_gibi_ve_oruc_dokunuslari(ptv, istemci, monkeypatch):
    import time as _t
    import pt_beslenme
    kalem = {"ad": "Yumurta", "miktar_g": 120, "kcal": 170, "protein": 15}
    dun = _gun(ptv, 1, yemekler=[{"id": "y1", "t": 1000, "ad": "Kahvaltı", "kalemler": [kalem]},
                                 {"id": "y2", "t": 2000, "ad": "Akşam", "kalemler": [{**kalem, "ad": "Tavuk", "kcal": 300}]}],
                oruc_kapandi=int(_t.time()) - 15 * 3600)
    r = istemci.get("/api/pt/yemek/dun").get_json()
    assert r["tarih"] == dun and [y["ad"] for y in r["liste"]] == ["Kahvaltı", "Akşam"] and r["liste"][0]["kcal"] == 170
    assert istemci.get("/api/pt").get_json()["dun_ogun"] == 2
    pen = pt_beslenme.pencere_durumu()
    assert pen["oruc_bas_t"] and 14.9 * 3600 < _t.time() - pen["oruc_bas_t"] < 15.1 * 3600   # dünkü kapanıştan sayılır
    j = istemci.post("/api/pt/yemek/kopyala", json={"kaynak": dun, "idler": ["y1"]}).get_json()
    assert j["eklenen"] == 1 and j["toplam"]["kcal"] == 170
    j = istemci.post("/api/pt/yemek/kopyala", json={"kaynak": dun}).get_json()
    assert j["eklenen"] == 2 and j["toplam"]["kcal"] == 640
    assert len({y["id"] for y in ptv.gun(BUGUN.isoformat())["yemekler"]}) == 3          # kopyalar yeni kimlikle
    assert istemci.post("/api/pt/yemek/kopyala", json={"kaynak": "../profil"}).status_code == 400
    p = istemci.post("/api/pt/oruc", json={"ne": "kapat"}).get_json()
    assert p["kapattim"] and p["durum"] == "kapandi"
    p = istemci.post("/api/pt/oruc", json={"ne": "kapat", "geri": True}).get_json()
    assert not p["kapattim"]
    p = istemci.post("/api/pt/oruc", json={"ne": "ac"}).get_json()
    assert p["acildi"] and abs(p["acilis_t"] - _t.time()) < 5 and p["durum"] == "acik"
    assert istemci.post("/api/pt/oruc", json={"ne": "x"}).status_code == 400


def test_jiujitsu_ders_gunleri_plana_kodla_islenir(ptv, istemci):
    kod = ptv.hafta_kodu()
    tarihler = [g.isoformat() for g in ptv.hafta_gunleri(kod)]
    pl = {"hafta": kod, "gunler": [{"tarih": t, "tur": "kalistenik", "baslik": "Kuvvet", "sure_dk": 20, "bolumler": [{"ad": "x"}], "id": t}
                                   for t in tarihler[:6]]}
    pl["gunler"][4]["tur"] = "bjj_ders"                                         # Cuma'ya uydurulmuş ders
    ptv._yaz(ptv.program_yolu(kod), pl)
    j = istemci.post("/api/pt/bjj-dersleri", json={"gunler": [1, 3, 6, 9, "x"], "saat": "19:30", "sure_dk": 75}).get_json()
    assert j["bjj_ders"] == {"gunler": [1, 3, 6], "saat": "19:30", "sure_dk": 75, "soruldu": True}
    g = {x["tarih"]: x for x in ptv.program(kod)["gunler"]}
    # Salı geçti (bugün Çarşamba): dokunulmaz
    assert [g[tarihler[i]]["tur"] for i in range(7)] == ["kalistenik", "kalistenik", "kalistenik", "bjj_ders", "dinlenme", "kalistenik", "bjj_ders"]
    assert g[tarihler[3]]["saat"] == "19:30" and g[tarihler[3]]["sure_dk"] == 75 and not g[tarihler[3]]["bolumler"]
    assert j["degisen"] == 3                                                     # Perşembe, eklenen Pazar, Cuma geri
    j = istemci.post("/api/pt/bjj-dersleri", json={"gunler": []}).get_json()
    assert j["bjj_ders"]["soruldu"] and not j["bjj_ders"]["gunler"]
    assert all(x["tur"] != "bjj_ders" for x in ptv.program(kod)["gunler"])


def test_antrenman_sonu_agri_turu_ve_ertesi_gun_takibi(ptv, istemci):
    dun = (BUGUN - dt.timedelta(days=1)).isoformat()
    r = istemci.post("/api/pt/seans", json={"tarih": dun, "seans": {"tur": "kalistenik", "sure_dk": 20, "agri": [
        {"bolge": "diz", "puan": 7, "tur": "eklem"}, {"bolge": "omuz", "puan": 8, "tur": "kas"}, {"bolge": "kafa", "puan": 9}]}})
    assert r.status_code == 200
    assert {a["bolge"]: a["tur"] for a in ptv.gun(dun)["agri"]} == {"diz": "eklem", "omuz": "kas"}       # bilinmeyen bölge atılır
    assert set(ptv.koru_bolgeler()) == {"diz"}                                                           # kas yanması kural bozmaz
    bek = istemci.get("/api/pt").get_json()["agri_takip"]
    assert bek == [{"bolge": "diz", "ad": "Diz", "puan": 7}]
    assert istemci.post("/api/pt/agri-takip", json={"bolge": "omuz", "durum": "ayni"}).status_code == 400
    j = istemci.post("/api/pt/agri-takip", json={"bolge": "diz", "durum": "artti"}).get_json()
    assert j["koru"] and j["bekleyen"] == []
    s = istemci.post("/api/pt/sabah", json={"uyku": "iyi", "enerji": 4}).get_json()
    assert s["isik"] != "yesil"                                                                           # kartta "arttı" sabah ışığına girer

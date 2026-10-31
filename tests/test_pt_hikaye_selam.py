"""Health: Bugün'deki ilk söz (Claude yokken kural sözü, önbellek, sohbet geçmişine tek kez) ve haftanın hikâyesi (2026-10-31)."""
import datetime as dt

import pytest

BUGUN = dt.date(2026, 10, 31)          # cumartesi; hafta 2026-W44 sürüyor


@pytest.fixture
def ptv(kok, tmp_path, monkeypatch):
    import pt
    import pt_oyun
    import pt_saglik
    import pt_sohbet
    v = tmp_path / "pt"
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program"), ("MESAJLAR", v / "mesajlar"), ("HAREKETLER", v / "hareketler")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pt, "bugun", lambda: BUGUN)
    monkeypatch.setattr(pt_oyun, "OYUN", v / "oyun.json")
    monkeypatch.setattr(pt_saglik, "KLASOR", v / "saglik")
    monkeypatch.setattr(pt_sohbet, "DOSYA", v / "sohbet.json")
    monkeypatch.setattr(pt_sohbet, "SELAM", v / "selam.json")
    (v / "saglik").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VH_CLAUDE_YOK", "1")
    pt.profil_kaydet({"ad": "Test", "kilo_kg": 90, "kuruldu": True})
    return pt


def test_selam_kural_sozu_onbellek_ve_gecmis(ptv):
    import pt_sohbet
    s0 = pt_sohbet.selam(uret=False)
    assert s0["eski"] and s0["soz"] and len(s0["cevaplar"]) == 3
    assert not s0["soz"].startswith(("Günaydın", "Merhaba"))          # selamlama ekranda zaten yazıyor
    s1 = pt_sohbet.selam()
    assert s1["imza"] == s0["imza"] and not s1.get("eski")
    assert pt_sohbet.selam(uret=False)["soz"] == s1["soz"]            # aynı durumda yeniden yazılmaz
    pt_sohbet.selam()
    L = [m for m in pt_sohbet.gecmis() if m.get("selam")]
    assert len(L) == 1 and L[0]["metin"] == s1["soz"]                 # konuşmanın başına tek kez


def test_selam_durum_degisince_yenilenir(ptv):
    import pt_sohbet
    im = pt_sohbet.selam()["imza"]
    ptv.seans_kaydet(BUGUN.isoformat(), {"tur": "kalistenik", "baslik": "Tüm vücut", "sure_dk": 20, "zorluk": 6})
    assert pt_sohbet.selam(uret=False)["imza"] != im


def test_hikaye_sayilar_koddan(ptv):
    import pt_hikaye
    ptv.seans_kaydet("2026-10-28", {"tur": "kalistenik", "baslik": "Tüm vücut", "sure_dk": 20, "zorluk": 6})
    ptv.seans_kaydet("2026-10-30", {"tur": "spor", "spor": "futbol", "baslik": "Futbol", "sure_dk": 25, "zorluk": 8, "not": "lig maçı",
                                    "kardiyo": {"tur": "futbol", "sure_dk": 25, "yogunluk": "aralik"}})
    h = pt_hikaye.hikaye()
    assert h["hafta"] == "2026-W44" and h["suruyor"] and not h["bos"]
    assert h["aktif"] == 2 and h["dakika"] == 45 and h["seans"] == 2
    assert [t["ad"] for t in h["turler"]] == ["Futbol", "Güç"]
    assert h["an"]["tur"] == "Futbol" and h["an"]["gun"] == "Cum"            # en yüksek yük (zorluk × dakika)
    assert h["gunler"][-1].get("gelecek") and len(h["gunler"]) == 7
    assert h["adim"] is None and h["kilo"] is None                            # veri yoksa uydurulmaz
    assert "Şimdiye kadar 2 gün" in h["kapanis"]


def test_hikaye_bos_hafta_ve_bugun_karti(ptv, monkeypatch):
    import pt_hikaye
    assert pt_hikaye.hikaye()["bos"]
    monkeypatch.setattr(ptv, "bugun", lambda: dt.date(2026, 11, 1))          # pazar: kart yalnız veri varsa
    assert pt_hikaye.bugun_karti() is None
    ptv.seans_kaydet("2026-10-29", {"tur": "mobilite", "baslik": "Hareketlilik", "sure_dk": 15, "zorluk": 3})
    k = pt_hikaye.bugun_karti()
    assert k and k["hafta"] == "2026-W44" and k["dakika"] == 15
    assert pt_hikaye.varsayilan_hafta(dt.date(2026, 11, 2)) == "2026-W44"     # pazartesi: geçen hafta

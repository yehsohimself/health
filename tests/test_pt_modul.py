"""Health modülleri (2026-10-31): yöntemi kişi seçmez; işaretlerden kod seçer, gidişata göre ekler/çıkarır, güvenlik kuralı kodda."""
import datetime as dt
import json

import pytest

BUGUN = dt.date(2026, 10, 30)


@pytest.fixture
def ptv(kok, tmp_path, monkeypatch):
    import pt
    import pt_modul
    import pt_oyun
    import pt_uzun
    v = tmp_path / "pt"
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program"), ("MESAJLAR", v / "mesajlar"), ("HAREKETLER", v / "hareketler")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pt, "bugun", lambda: BUGUN)
    monkeypatch.setattr(pt_oyun, "OYUN", v / "oyun.json")
    monkeypatch.setattr(pt_uzun, "RECETE", v / "recete.json")
    monkeypatch.setattr(pt_modul, "OLAYLAR", v / "modul_olaylar.json")
    monkeypatch.setenv("VH_CLAUDE_YOK", "1")
    pt.profil_kaydet({"ad": "Test", "kilo_kg": 84, "boy_cm": 178, "dogum_tarihi": "1986-05-02", "hedef_turleri": ["uzun_omur"],
                      "sevdikleri": ["yuruyus"], "gunler": [0, 2, 4], "gunluk_dk": 30, "kuruldu": True})
    return pt


def kodlar(L):
    return [m["kod"] for m in L]


def test_isaret_yoksa_az_modul(ptv):
    import pt_modul
    assert kodlar(pt_modul.sec()) == ["taichi"]          # uzun ömür hedefi: dengeyi erken korumak


def test_stres_ve_uyku_modul_getirir(ptv):
    import pt_modul
    ptv.profil_kaydet({"stres": "yogun", "uyku_kalite": "kotu", "is_duzeni": "oturarak"})
    K = kodlar(pt_modul.sec())
    assert "nefes" in K and "uyku" in K and "mola" in K and len(K) <= 4
    m = {x["kod"]: x for x in pt_modul.sec()}
    assert m["nefes"]["neden"] and m["nefes"]["kanit"] in ("güçlü", "orta", "sınırlı")


def test_kalp_varsa_soguk_su_yok(ptv):
    import pt_modul
    ptv.profil_kaydet({"tarama": {"kalp": True}})
    for t in ("2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"):
        (ptv.GUNLUK / f"{t}.json").write_text(json.dumps({"tarih": t, "sabah": {"enerji": 2}}), encoding="utf-8")
    assert "soguk" not in kodlar(pt_modul.sec(en_cok=10))


def test_gidisata_gore_ekler_ve_geri_alinir(ptv):
    import pt_modul
    import pt_uzun
    pt_uzun.recete_kaydet()
    assert pt_modul.guncelle() == []
    ptv.profil_kaydet({"stres": "yogun"})
    d = pt_modul.guncelle()
    assert any(x["kod"] == "nefes" and x["ne"] == "eklendi" for x in d)
    o = pt_modul.son_olay()
    pt_modul.olay_isaretle(o["t"], geri=True)
    rc = pt_uzun.recete_oku()
    assert "nefes" not in kodlar(rc["moduller"]) and "nefes" in rc["modul_cikan"]
    assert "nefes" not in kodlar(pt_modul.sec(cikan=rc["modul_cikan"]))


def test_isaretleme_ve_gunluk(ptv):
    import pt_modul
    import pt_uzun
    ptv.profil_kaydet({"stres": "yogun"})
    pt_uzun.recete_kaydet()
    L = pt_modul.isaretle("nefes", BUGUN.isoformat())
    assert next(m for m in L if m["kod"] == "nefes")["bitti"]

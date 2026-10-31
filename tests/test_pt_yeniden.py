"""Health: programı bugünden baştan başlatmak (2026-10-31). Kayıt silinmez; hedefler, ara kontrol, ilk hafta ve plan bugünden."""
import datetime as dt
import json

import pytest

BUGUN = dt.date(2026, 10, 31)


@pytest.fixture
def ptv(kok, tmp_path, monkeypatch):
    import pt
    import pt_hedef
    import pt_kontrol
    import pt_oyun
    import pt_yeniden
    v = tmp_path / "pt"
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program"), ("MESAJLAR", v / "mesajlar"), ("HAREKETLER", v / "hareketler")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pt, "bugun", lambda: BUGUN)
    monkeypatch.setattr(pt_oyun, "OYUN", v / "oyun.json")
    monkeypatch.setattr(pt_hedef, "HEDEFLER", v / "hedefler.json")
    monkeypatch.setattr(pt_kontrol, "DEGERLENDIRME", v / "degerlendirme.json")
    monkeypatch.setattr(pt_kontrol, "KONTROLLER", v / "kontroller")
    monkeypatch.setattr(pt_yeniden, "KAYIT", v / "yeniden.json")
    monkeypatch.setenv("VH_CLAUDE_YOK", "1")
    pt.profil_kaydet({"ad": "Test", "kilo_kg": 90, "boy_cm": 180, "dogum_tarihi": "1990-01-01", "hedef_turleri": ["kilo"], "gunler": [0, 2, 4],
                      "gunluk_dk": 30, "kuruldu": True})
    (pt.GUNLUK / "2026-10-25.json").write_text(json.dumps({"tarih": "2026-10-25", "sabah": {"enerji": 3}}), encoding="utf-8")
    kod = pt.hafta_kodu(BUGUN)
    pt._yaz(pt.program_yolu(kod), {"hafta": kod, "gunler": [{"tarih": t, "tur": "kalistenik", "id": t, "baslik": "x", "sure_dk": 20}
                                                           for t in ("2026-10-26", "2026-10-28", "2026-10-30")]})
    pt_hedef.kaydet([{"vade": "kisa", "metin": "4 haftada 8 antrenman", "olcu": {"tur": "seans", "hedef": 8}}])
    return pt


def test_durgun_programi_fark_eder(ptv):
    import pt_yeniden
    d = pt_yeniden.durgun()
    assert d and d["hic"] and d["kacan"] >= 2


def test_bugunden_baslar_kayit_silmez(ptv):
    import pt_hedef
    import pt_kontrol
    import pt_yeniden
    r = pt_yeniden.yeniden_basla("vaktim az")
    p = ptv.profil()
    assert p["program_baslangic"] == BUGUN.isoformat() and r["ilk_hafta"]
    h = pt_hedef.aktif()[0]
    assert h["bas"] == BUGUN.isoformat() and h["son"] == (BUGUN + dt.timedelta(days=28)).isoformat()
    assert pt_kontrol.zamani()["sonraki"] == (BUGUN + dt.timedelta(days=14)).isoformat()
    assert not ptv.program_yolu(ptv.hafta_kodu(BUGUN)).exists()                      # plan geçmişe kaldırıldı, bugünden yeniden yazılacak
    assert list((ptv.PROGRAM / "gecmis").glob("*_bastan.json"))
    assert (ptv.GUNLUK / "2026-10-25.json").exists()                                  # kayıt silinmez
    assert (ptv.VERI / ".yedek").exists()
    assert pt_yeniden.durgun() is None


def test_kaldigim_yerden_bir_hafta_sormaz(ptv):
    import pt_yeniden
    pt_yeniden.ertele(7)
    assert pt_yeniden.durgun() is None

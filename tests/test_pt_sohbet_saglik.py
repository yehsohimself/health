"""Health: sohbetten kayıt (maç, kilo, su) ve Apple Sağlık dışa aktarımı (2026-10-31)."""
import datetime as dt
import time
import zipfile

import pytest

BUGUN = dt.date(2026, 10, 31)


@pytest.fixture
def ptv(kok, tmp_path, monkeypatch):
    import pt
    import pt_oyun
    import pt_saglik
    v = tmp_path / "pt"
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program"), ("MESAJLAR", v / "mesajlar"), ("HAREKETLER", v / "hareketler")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pt, "bugun", lambda: BUGUN)
    monkeypatch.setattr(pt_oyun, "OYUN", v / "oyun.json")
    monkeypatch.setattr(pt_saglik, "KLASOR", v / "saglik")
    monkeypatch.setattr(pt_saglik, "AYAR", v / "ayar.json")
    (v / "saglik").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VH_CLAUDE_YOK", "1")
    pt.profil_kaydet({"ad": "Test", "kilo_kg": 90, "kuruldu": True})
    return pt


def test_mac_kaydi_doza_sayilir_ve_geri_alinir(ptv):
    import pt_sohbet
    import pt_uzun
    r = pt_sohbet.kayit_isle({"tur": "aktivite", "tarih": "2026-10-30", "spor": "futbol", "ad": "Futbol (büyük saha)", "sure_dk": 25, "zorluk": 8})
    assert r["ozet"].startswith("Dün") and "25 dk" in r["ozet"]
    s = ptv.gun("2026-10-30")["seanslar"][0]
    assert s["bitti"] and s["kardiyo"]["yogunluk"] == "aralik"
    assert pt_uzun.hafta_olcumu()["yogun"] == 1
    pt_sohbet.kayit_geri(r)
    assert not ptv.gun("2026-10-30")["seanslar"]


def test_kilo_su_ve_gelecek_tarih(ptv):
    import pt_sohbet
    r = pt_sohbet.kayit_isle({"tur": "kilo", "tarih": "2027-01-01", "kilo_kg": 93.4})
    assert r["tarih"] == BUGUN.isoformat() and "93,4" in r["ozet"]
    assert ptv.gun(BUGUN.isoformat())["kilo"] == 93.4
    pt_sohbet.kayit_geri(r)
    assert "kilo" not in ptv.gun(BUGUN.isoformat())
    pt_sohbet.kayit_isle({"tur": "su", "tarih": BUGUN.isoformat(), "ml": 500})
    assert ptv.gun(BUGUN.isoformat())["su_ml"] == 500


def test_apple_saglik_disa_aktarimi(ptv, tmp_path):
    import pt_saglik
    xml = """<?xml version="1.0" encoding="UTF-8"?><HealthData>
<Record type="HKQuantityTypeIdentifierStepCount" unit="count" startDate="2026-10-29 09:00:00 +0100" endDate="2026-10-29 10:00:00 +0100" value="4000"/>
<Record type="HKQuantityTypeIdentifierStepCount" unit="count" startDate="2026-10-29 15:00:00 +0100" endDate="2026-10-29 16:00:00 +0100" value="3000"/>
<Record type="HKQuantityTypeIdentifierRestingHeartRate" unit="count/min" startDate="2026-10-29 07:00:00 +0100" endDate="2026-10-29 07:00:00 +0100" value="58"/>
<Record type="HKQuantityTypeIdentifierBodyMass" unit="lb" startDate="2026-10-29 08:00:00 +0100" endDate="2026-10-29 08:00:00 +0100" value="200"/>
<Record type="HKCategoryTypeIdentifierSleepAnalysis" startDate="2026-10-28 23:00:00 +0100" endDate="2026-10-29 03:00:00 +0100" value="HKCategoryValueSleepAnalysisAsleepCore"/>
<Record type="HKCategoryTypeIdentifierSleepAnalysis" startDate="2026-10-29 02:30:00 +0100" endDate="2026-10-29 06:30:00 +0100" value="HKCategoryValueSleepAnalysisAsleepDeep"/>
<Record type="HKCategoryTypeIdentifierSleepAnalysis" startDate="2026-10-28 22:30:00 +0100" endDate="2026-10-29 07:00:00 +0100" value="HKCategoryValueSleepAnalysisInBed"/>
<Record type="HKQuantityTypeIdentifierStepCount" unit="count" startDate="2025-01-01 09:00:00 +0100" endDate="2025-01-01 10:00:00 +0100" value="9"/>
<Workout workoutActivityType="HKWorkoutActivityTypeSoccer" duration="60" durationUnit="min" startDate="2026-10-29 19:00:00 +0100" endDate="2026-10-29 20:00:00 +0100"/>
</HealthData>"""
    z = tmp_path / "export.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("apple_health_export/export.xml", xml)
    s = pt_saglik.ice_aktar(z)
    assert s["gun"] == 1 and s["antrenman"] == 1 and not z.exists()
    g = pt_saglik.gun("2026-10-29")
    assert g["adim"] == 7000 and g["nabiz"] == 58 and g["uyku_saat"] == 7.5 and abs(g["kilo"] - 90.7) < 0.1
    s0 = ptv.gun("2026-10-29")["seanslar"][0]
    assert s0["tur"] == "spor" and s0["kardiyo"]["yogunluk"] == "aralik"
    pt_saglik.ice_aktar(_kopya(z, xml))                      # ikinci kez aynı dosya: antrenman iki kez yazılmaz
    assert len(ptv.gun("2026-10-29")["seanslar"]) == 1


def _kopya(z, xml):
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("apple_health_export/export.xml", xml)
    return z


def test_icloud_drive_kendiliginden(ptv, tmp_path, monkeypatch):
    """Health Auto Export'un iCloud Drive'a yazdığı JSON: yeni dosya okunur, aynı dosya ikinci kez okunmaz."""
    import json
    import pt_saglik
    kok = tmp_path / "Mobile Documents"
    k = kok / "iCloud~com~ifunography~HealthExport" / "Documents" / "AutoSync"
    k.mkdir(parents=True)
    (kok / "com~apple~CloudDocs").mkdir()
    monkeypatch.setattr(pt_saglik, "ICLOUD", kok)
    veri = {"data": {"metrics": [
        {"name": "step_count", "units": "count", "data": [{"date": "2026-10-30 00:00:00 +0100", "qty": 8123}]},
        {"name": "sleep_analysis", "units": "hr", "data": [{"date": "2026-10-30 00:00:00 +0100", "totalSleep": 6.8}]},
        {"name": "resting_heart_rate", "units": "count/min", "data": [{"date": "2026-10-30 00:00:00 +0100", "qty": 57}]},
        {"name": "weight_body_mass", "units": "lb", "data": [{"date": "2026-10-30 08:00:00 +0100", "qty": 205}]}],
        "workouts": [{"name": "Outdoor Walk", "start": "2026-10-30 12:00:00 +0100", "duration": {"qty": 40, "units": "min"}},
                     {"name": "Soccer", "start": "2026-10-30 19:00:00 +0100", "duration": 3600}]}}
    (k / "HealthAutoExport-2026-10-30.json").write_text(json.dumps(veri), encoding="utf-8")
    r = pt_saglik.icloud_tara()
    assert r == {"dosya": 1, "gun": 1}
    g = pt_saglik.gun("2026-10-30")
    assert g["adim"] == 8123 and g["uyku_saat"] == 6.8 and g["nabiz"] == 57 and abs(g["kilo"] - 93.0) < 0.1
    S = {s["baslik"]: s for s in ptv.gun("2026-10-30")["seanslar"]}
    assert S["Futbol"]["kardiyo"]["yogunluk"] == "aralik" and S["Yürüyüş"]["sure_dk"] == 40
    assert pt_saglik.icloud_tara() == {"dosya": 0, "gun": 0}
    assert pt_saglik.durum()["icloud"]["gun"] == 1


def _spor(pt_sohbet, **k):
    return pt_sohbet.kayit_isle({"tur": "aktivite", "tarih": BUGUN.isoformat(), "spor": "fitness", **k})


def test_ayni_is_ikinci_kez_kayit_acmaz_ve_geri_alinir(ptv):
    import pt_sohbet
    _spor(pt_sohbet, ad="Squat (vücut ağırlığı)", sure_dk=5, zorluk=5, **{"not": "set belirtilmedi"})
    r = _spor(pt_sohbet, ad="Squat (50 tekrar, tek set)", **{"not": "tek seferde"})
    L = ptv.gun(BUGUN.isoformat())["seanslar"]
    assert len(L) == 1 and L[0]["baslik"] == "Squat (50 tekrar, tek set)" and L[0]["not"] == "tek seferde"
    assert L[0]["sure_dk"] == 5 and L[0]["zorluk"] == 5           # söylenmeyen süre ve zorluk varsayılana dönmez
    assert "güncellendi" in r["ozet"]
    pt_sohbet.kayit_geri(r)
    L = ptv.gun(BUGUN.isoformat())["seanslar"]
    assert len(L) == 1 and L[0]["baslik"] == "Squat (vücut ağırlığı)"


def test_farkli_is_ve_acik_tekrar_ayri_kalir(ptv):
    import pt_sohbet
    _spor(pt_sohbet, ad="Squat", sure_dk=5)
    time.sleep(0.002)
    _spor(pt_sohbet, ad="Baldır kaldırma", sure_dk=3)
    time.sleep(0.002)
    _spor(pt_sohbet, ad="Squat", sure_dk=5, ayri=True)
    assert [s["baslik"] for s in ptv.gun(BUGUN.isoformat())["seanslar"]] == ["Squat", "Baldır kaldırma", "Squat"]


def test_on_dakikadan_eski_ayni_is_yeni_kayittir(ptv):
    import pt_sohbet
    eski = f"k{int((time.time() - 3 * 3600) * 1000)}"
    ptv.seans_kaydet(BUGUN.isoformat(), {"id": eski, "tur": "kardiyo", "baslik": "Yürüyüş", "sure_dk": 45, "kaynak": "sohbet"})
    _spor(pt_sohbet, ad="Yürüyüş", sure_dk=45)
    assert len(ptv.gun(BUGUN.isoformat())["seanslar"]) == 2


def test_kimlikle_eski_kayit_duzeltilir(ptv):
    import pt_sohbet
    eski = f"k{int((time.time() - 3 * 3600) * 1000)}"
    ptv.seans_kaydet(BUGUN.isoformat(), {"id": eski, "tur": "kardiyo", "baslik": "Yürüyüş", "sure_dk": 35, "kaynak": "sohbet"})
    _spor(pt_sohbet, guncelle=eski, sure_dk=60)
    L = ptv.gun(BUGUN.isoformat())["seanslar"]
    assert len(L) == 1 and L[0]["sure_dk"] == 60 and L[0]["baslik"] == "Yürüyüş"


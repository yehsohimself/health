"""pt_rota.py - Health bisiklet döngüsü (2026-10-25): konumdan çıkıp aynı yere dönen rota.

BRouter (brouter.de herkese açık sunucu, anahtar yok; ileride Mac'e kurulabilir) `engineMode=4` döngü modu: `roundTripDistance` YARIÇAP gibi
davranır (Berlin denemesi: 8000 → 38 km), bu yüzden hedef uzunluğa bir düzeltme turuyla yaklaşılır. 3 aday yön; rüzgâr (Open-Meteo, anahtarsız)
güçlüyse ilk yarı rüzgâra karşı. Adaylar uzunluk sapması, ana yol payı ve Arnavut kaldırımı payıyla puanlanır. Sürüşteki yol tarifi Komoot/Garmin'e
GPX olarak bırakılır (web uygulaması arka planda konum izleyemez).
"""
import json
import math
import time
import urllib.parse

import requests

import pt

BROUTER = "https://brouter.de/brouter"
UA = {"User-Agent": "VideoHub-PT/1.0 (kisisel kullanim)"}
HIZ = {"kolay": 19, "orta": 23, "aralik": 22, "tempo": 24}
ANA_YOL = {"primary", "primary_link", "trunk", "trunk_link", "secondary", "secondary_link"}
KALDIRIM = {"sett", "cobblestone", "unhewn_cobblestone", "paving_stones:30"}
ROTALAR = pt.VERI / "rotalar"


def konum_bul(ad):
    r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": ad, "format": "json", "limit": 1}, headers=UA, timeout=20)
    L = r.json()
    if not L:
        return None
    return {"ad": L[0].get("display_name", ad)[:120], "lat": float(L[0]["lat"]), "lon": float(L[0]["lon"])}


def ruzgar(lat, lon):
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "hourly": "wind_speed_10m,wind_direction_10m,precipitation_probability,temperature_2m",
            "forecast_hours": 6, "timezone": "Europe/Berlin", "wind_speed_unit": "kmh"}, timeout=20)
        h = r.json()["hourly"]
        return {"hiz": h["wind_speed_10m"][0], "yon": h["wind_direction_10m"][0], "yagis": max(h["precipitation_probability"][:3]),
                "sicaklik": h["temperature_2m"][0], "saatlik": [{"saat": t[-5:], "yagis": p, "sicaklik": s}
                                                                for t, p, s in zip(h["time"], h["precipitation_probability"], h["temperature_2m"])]}
    except Exception:  # noqa: BLE001
        return None


def _iste(lat, lon, yaricap, yon, profil="trekking"):
    r = requests.get(BROUTER, params={"lonlats": f"{lon:.5f},{lat:.5f}", "profile": profil, "alternativeidx": 0, "format": "geojson",
                                      "engineMode": 4, "roundTripDistance": int(yaricap), "direction": int(yon) % 360}, headers=UA, timeout=60)
    r.raise_for_status()
    f = r.json()["features"][0]
    return f


def _cozumle(f):
    pr = f["properties"]
    mesaj = pr.get("messages") or []
    bas = mesaj[0] if mesaj else []
    i_mes, i_tag = (bas.index("Distance"), bas.index("WayTags")) if "Distance" in bas and "WayTags" in bas else (None, None)
    toplam, ana, tas = 0.0, 0.0, 0.0
    for m in mesaj[1:]:
        if i_mes is None:
            break
        try:
            d = float(m[i_mes])
        except (ValueError, IndexError):
            continue
        tag = dict(x.split("=", 1) for x in str(m[i_tag]).split() if "=" in x)
        toplam += d
        if tag.get("highway") in ANA_YOL:
            ana += d
        if tag.get("surface") in KALDIRIM:
            tas += d
    return {"uzunluk_km": round(float(pr.get("track-length") or 0) / 1000, 1), "yukselis_m": int(float(pr.get("filtered ascend") or 0)),
            "ana_yol": round(ana / toplam, 2) if toplam else 0, "kaldirim": round(tas / toplam, 2) if toplam else 0,
            "koordinat": [[round(c[1], 5), round(c[0], 5), round(c[2]) if len(c) > 2 else None] for c in f["geometry"]["coordinates"]]}


def oner(lat, lon, sure_dk=60, yogunluk="kolay"):
    """3 aday döngü; puanı düşük olan iyi. Hedef uzunluk = süre × tempo hızı."""
    hedef = sure_dk / 60 * HIZ.get(yogunluk, 20)
    hava = ruzgar(lat, lon)
    if hava and hava["hiz"] >= 12:
        yonler = [hava["yon"], hava["yon"] - 50, hava["yon"] + 50]
    else:
        yonler = [20, 140, 260]
    adaylar = []
    for y in yonler:
        r = hedef * 1000 / 4.8
        try:
            c = _cozumle(_iste(lat, lon, r, y))
            if c["uzunluk_km"] and abs(c["uzunluk_km"] - hedef) / hedef > 0.18:
                time.sleep(0.4)
                c = _cozumle(_iste(lat, lon, r * hedef / c["uzunluk_km"], y))
        except Exception as e:  # noqa: BLE001
            adaylar.append({"yon": round(y) % 360, "hata": str(e)[:120]})
            continue
        sapma = abs(c["uzunluk_km"] - hedef) / hedef
        puan = sapma * 3 + c["ana_yol"] * 2 + c["kaldirim"] * 1.5
        ruzgara = bool(hava and hava["hiz"] >= 12 and abs(((y - hava["yon"]) + 180) % 360 - 180) < 30)
        if ruzgara:
            puan -= 0.15
        adaylar.append({**c, "yon": round(y) % 360, "puan": round(puan, 3), "ruzgara_karsi": ruzgara,
                        "sure_dk": round(c["uzunluk_km"] / HIZ.get(yogunluk, 20) * 60)})
        time.sleep(0.4)
    iyi = sorted([a for a in adaylar if "puan" in a], key=lambda a: a["puan"])
    for n, a in enumerate(iyi):
        a["no"] = n + 1
        a["aciklama"] = _aciklama(a, hava)
    sonuc = {"zaman": int(time.time()), "lat": lat, "lon": lon, "hedef_km": round(hedef, 1), "sure_dk": sure_dk, "yogunluk": yogunluk,
             "hava": hava, "adaylar": iyi, "hatalar": [a for a in adaylar if "hata" in a]}
    ROTALAR.mkdir(parents=True, exist_ok=True)
    rid = f"r{sonuc['zaman']}"
    sonuc["id"] = rid
    pt._yaz(ROTALAR / f"{rid}.json", sonuc)
    return sonuc


YON_AD = ["kuzey", "kuzeydoğu", "doğu", "güneydoğu", "güney", "güneybatı", "batı", "kuzeybatı"]


def _aciklama(a, hava):
    p = [f"{a['uzunluk_km']} km, yaklaşık {a['sure_dk']} dk, {a['yukselis_m']} m tırmanış"]
    p.append(f"önce {YON_AD[int(((a['yon'] % 360) + 22.5) // 45) % 8]} yönüne")
    if a.get("ruzgara_karsi"):
        p.append("ilk yarı rüzgâra karşı, dönüşte rüzgâr arkadan")
    p.append(f"ana yolda %{round(a['ana_yol'] * 100)}")
    if a["kaldirim"] >= 0.05:
        p.append(f"Arnavut kaldırımı %{round(a['kaldirim'] * 100)}")
    return " · ".join(p)


def gpx(rid, no):
    r = pt._json(ROTALAR / f"{rid}.json", {})
    a = next((x for x in r.get("adaylar") or [] if x.get("no") == int(no)), None)
    if not a:
        return None
    nok = "\n".join(f'<trkpt lat="{la}" lon="{lo}">' + (f"<ele>{e}</ele>" if e is not None else "") + "</trkpt>" for la, lo, e in a["koordinat"])
    ad = f"Health {r.get('sure_dk')} dk {r.get('yogunluk')} döngü {no}"
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Video Hub Health" xmlns="http://www.topografix.com/GPX/1/1">'
            f"<metadata><name>{ad}</name></metadata><trk><name>{ad}</name><trkseg>\n{nok}\n</trkseg></trk></gpx>\n"), ad


def harita_linki(lat, lon):
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=13/{lat}/{lon}"


if __name__ == "__main__":
    import sys
    print(json.dumps({k: v for k, v in oner(52.4986, 13.4030, int(sys.argv[1]) if len(sys.argv) > 1 else 45).items() if k != "adaylar"}, ensure_ascii=False))

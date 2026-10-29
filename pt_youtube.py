"""pt_youtube.py - Her hareket için doğru bir YouTube anlatım videosu (2026-10-25; kullanıcı: "doğru bir YouTube linki").

Claude (sonnet) hareket başına İngilizce + Türkçe arama sorgusu yazar (pt_medya/youtube_sorgu.json) → yt-dlp düz arama (anahtar yok, 25-900 sn)
→ Claude en doğru, kısa form anlatımını seçer → YouTube oEmbed ile gömülebilirlik doğrulanır → pt_medya/youtube.json {kod: {id, baslik, kanal, sure, neden}}.
Sayfa: hareket kartında "Videolu anlatım" (küçük resim; dokununca youtube-nocookie oynatıcı). Elle: `python pt_youtube.py [kod...]`.
"""
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pt
import pt_kart

MEDYA = pt_kart.MEDYA
YOUTUBE = MEDYA / "youtube.json"
SORGU = MEDYA / "youtube_sorgu.json"
YTDLP = str(pt.KLASOR / ".venv" / "bin" / "yt-dlp")
_kilit = threading.Lock()

SORGU_ISTEM = """Her egzersiz için YouTube'da bu hareketin İYİ bir form anlatımını bulacak arama sorguları yaz: "arama_en" (İngilizce, yerleşik adıyla;
ör. "how to <exercise> tutorial proper form"; BJJ ve animal flow'da o alandaki adıyla) ve "arama_tr" (Türkçe).
{liste}
JSON: {{"sorgular": {{"kod": {{"arama_en": "...", "arama_tr": "..."}}}}}}"""

SECIM_ISTEM = """Bir egzersiz uygulamasında her hareketin yanında kullanıcıya bir YouTube anlatım videosu göstereceğiz. Kullanıcı Türk; Türkçe ya da
İngilizce olabilir, önemli olan videonun TAM BU HAREKETİ doğru biçimde, açıkça göstermesi. Tercih: kısa (1-8 dk) form/teknik anlatımı, tanınmış
antrenör/fizyoterapist/kulüp kanalı, görüntüsü net. Kaçın: başka hareket, uzun antrenman videosu, derleme, şaka/tepki, Shorts olmayan ama alakasız,
başlığı tık tuzağı. Uygun aday yoksa null.

{liste}

JSON: {{"secim": {{"kod": {{"id": "...", "neden": "kısa"}} | null}}}}"""


def sorgular(kodlar=None):
    """Eksik sorguları Claude ile yazar; hepsini döner."""
    import claude_yaz
    S = pt._json(SORGU, {})
    eksik = [k for k in (kodlar or list(pt.KATALOG)) if k in pt.KATALOG and k not in S]
    for i in range(0, len(eksik), 20):
        grup = eksik[i:i + 20]
        liste = "\n".join(f"{k}: {pt.KATALOG[k]['ad']} · {pt.KATALOG[k]['tur']} · {pt.KATALOG[k]['aciklama']}" for k in grup)
        c = claude_yaz.sor_json(SORGU_ISTEM.format(liste=liste), model_adi="sonnet", zaman_asimi=300)
        for k, v in (c.get("sorgular") or {}).items():
            if k in grup and isinstance(v, dict):
                S[k] = {"arama_en": str(v.get("arama_en") or "")[:120], "arama_tr": str(v.get("arama_tr") or "")[:120]}
        pt._yaz(SORGU, S)
    return S


def _ara(sorgu, n=6):
    if not sorgu:
        return []
    try:
        r = subprocess.run([YTDLP, "--flat-playlist", "--dump-json", f"ytsearch{n}:{sorgu}"], capture_output=True, text=True, timeout=60)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for s in r.stdout.splitlines():
        try:
            d = json.loads(s)
        except ValueError:
            continue
        if d.get("id") and d.get("duration"):
            out.append({"id": d["id"], "baslik": d.get("title") or "", "kanal": d.get("channel") or d.get("uploader") or "",
                        "sure": int(d.get("duration") or 0), "izlenme": int(d.get("view_count") or 0)})
    return out


def _gomulur(vid):
    import requests
    try:
        return requests.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"},
                            timeout=15).status_code == 200
    except Exception:  # noqa: BLE001
        return False


def youtube_bul(kodlar=None, yenile=False, log=print):
    import claude_yaz
    C, Y = sorgular(), pt._json(YOUTUBE, {})
    kodlar = [k for k in (kodlar or list(pt.KATALOG)) if k in C and (yenile or k not in Y)]
    adaylar = {}
    with ThreadPoolExecutor(4) as ex:
        isler = {ex.submit(_ara, C[k].get(s), 6 if s == "arama_en" else 4): k for k in kodlar for s in ("arama_en", "arama_tr")}
        for f, k in isler.items():
            for a in f.result():
                if 25 <= a["sure"] <= 900 and a["id"] not in {x["id"] for x in adaylar.get(k, [])}:
                    adaylar.setdefault(k, []).append(a)

    def sec(grup):
        liste = "\n\n".join(f"{k}: {pt.KATALOG[k]['ad']} ({pt.KATALOG[k]['aciklama']})\n" + "\n".join(
            f"  - {a['id']} · {a['sure'] // 60}:{a['sure'] % 60:02d} · {a['izlenme']:,} izlenme · {a['kanal']} · {a['baslik']}" for a in adaylar.get(k, []))
            for k in grup)
        return (claude_yaz.sor_json(SECIM_ISTEM.format(liste=liste), model_adi="sonnet", zaman_asimi=300).get("secim") or {})
    with ThreadPoolExecutor(3) as ex:
        for sonuc in ex.map(sec, [kodlar[i:i + 12] for i in range(0, len(kodlar), 12)]):
            for k, v in sonuc.items():
                a = next((x for x in adaylar.get(k, []) if v and x["id"] == v.get("id")), None)
                if a and _gomulur(a["id"]):
                    Y[k] = {**a, "neden": str(v.get("neden") or "")[:160], "zaman": int(time.time())}
                else:
                    log(f"youtube bulunamadı: {k}")
            with _kilit:
                pt._yaz(YOUTUBE, Y)
    return len(Y)



if __name__ == "__main__":
    import sys
    print("youtube:", youtube_bul(sys.argv[1:] or None, yenile=bool(sys.argv[1:])))

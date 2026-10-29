"""pt_anatomi.py - hareket başına anatomi görseli ve kas şeridi için gövde simgeleri (2026-10-27; kullanıcı: Lyfta'daki gibi).

Görseller pt_storyboard'un yolu ile, kullanıcının ChatGPT üyeliğindeki görsel üretimiyle (Codex) çizilir; ücretli servis yok.
- Hareket: storyboard'un orta karesi (k2, yoksa k1) poz/kamera/ekipman referansı olarak verilir; aynı poz, deri yerine kas anatomisi
  (gri-gümüş kas modeli), kartta yazan birincil kaslar limon yeşili parlar, ikincil kaslar soluk yeşil. pt_medya/<kod>/anatomi.jpg (+ _k).
- Gövde simgesi: kas başına tek, ayakta anatomi figürü (önden ya da arkadan), yalnız o kas yeşil. pt_medya/_kas/<kas>_govde.jpg (+ _k).
Elle: `python pt_anatomi.py ikon [kas...]`, `python pt_anatomi.py [kod...]`, `python pt_anatomi.py resim kod...`.
"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pt
import pt_kart
import pt_storyboard as sb

MEDYA = pt_kart.MEDYA
DURUM = MEDYA / "anatomi.json"
_kilit = threading.Lock()

STIL = ("Use your image generation tool to create ONE image: a premium 3D anatomical render in the style of a high-end fitness app exercise "
        "illustration. The figure is an anatomical muscle model (écorché, no skin): realistic muscle fibres in neutral matte silver-grey, clean and "
        "sharp, male athletic proportions. Background: deep near-black studio with a very subtle lime-green (#C4F23A) glow behind the figure. ")
HAREKET = (STIL + "Match EXACTLY the pose, camera angle, framing and equipment of the attached photo (same exercise moment), but render the person as "
           "this anatomical muscle model; equipment rendered in clean dark grey. ONLY these muscles glow vivid lime-green (#C4F23A): {b1}.{b2} All other "
           "muscles stay silver-grey. 16:9 landscape, whole body visible, no text, no labels, no arrows, no logos. Save the image file into the current "
           "directory as anatomi.png and reply only with the file name.")
GOVDE = (STIL + "A single standing figure, relaxed neutral stance, {yon} view, whole body from head to feet, centered, small margin. ONLY the {kas} glow "
         "vivid lime-green (#C4F23A); everything else silver-grey. Square 1:1, no text, no labels, no logos. Save the image file into the current "
         "directory as govde.png and reply only with the file name.")
KAS_EN = {k: v[0] for k, v in sb.KAS_EN.items()}


def _durum_yaz(**ek):
    with _kilit:
        d = pt._json(DURUM, {})
        d.update(ek)
        pt._yaz(DURUM, d)


def anatomi(kod):
    return MEDYA / kod / "anatomi.jpg"


def govde(kas):
    return sb.KAS_KLASOR / f"{kas}_govde.jpg"


def durum():
    d = pt._json(DURUM, {})
    return {"hareket": sum(1 for k in pt.KATALOG if anatomi(k).exists()), "toplam": len(pt.KATALOG),
            "govde": sum(1 for k in sb.KAS_EN if govde(k).exists()), "govde_toplam": len(sb.KAS_EN), **{a: d.get(a) for a in ("calisiyor", "son", "durdu")}}


def _kaydet(png, jpg, gen, kucuk):
    sb._jpg(png, jpg, gen)
    sb._jpg(png, jpg.with_name(jpg.stem + "_k.jpg"), kucuk)
    png.unlink(missing_ok=True)


def govde_uret(kas, log=print):
    if govde(kas).exists():
        return True
    sb.KAS_KLASOR.mkdir(parents=True, exist_ok=True)
    yon = "back" if sb.KAS_EN[kas][1] == "back" else "front"
    png = sb.KAS_KLASOR / f"{kas}_govde.png"
    istem = GOVDE.format(kas=KAS_EN[kas], yon=yon)
    if sb._uret_tek(istem, [], png, log) or sb._uret_tek(istem, [], png, log):
        _kaydet(png, govde(kas), 640, 200)
        log(f"gövde simgesi hazır: {kas}")
        return True
    return False


def hareket_uret(kod, log=print):
    if anatomi(kod).exists():
        return True
    ref = next((MEDYA / kod / f"k{n}.jpg" for n in (2, 1) if (MEDYA / kod / f"k{n}.jpg").exists()), None)
    kas = (pt_kart.kartlar().get(kod) or {}).get("kaslar") or {}
    b1 = [KAS_EN.get(k, k) for k in kas.get("birincil") or []]
    if not ref or not b1:
        log(f"atlandı (referans kare ya da kas yok): {kod}")
        return False
    b2 = [KAS_EN.get(k, k) for k in kas.get("ikincil") or []]
    istem = HAREKET.format(b1=", ".join(b1), b2=f" These muscles glow a softer, dimmer lime-green (about 40%): {', '.join(b2)}." if b2 else "")
    png = MEDYA / kod / "anatomi.png"
    if sb._uret_tek(istem, [ref], png, log) or sb._uret_tek(istem, [ref], png, log):
        _kaydet(png, anatomi(kod), 1280, 480)
        log(f"anatomi hazır: {kod}")
        return True
    return False


def hepsini(kodlar=None, ikon=True, log=print, paralel=2):
    """Önce gövde simgeleri, sonra hareketler. Art arda 3 başarısızlıkta durur (ChatGPT görsel sınırı)."""
    _durum_yaz(calisiyor=True, bas=int(time.time()), durdu=None)
    isler = ([("govde", k) for k in sb.KAS_EN if not govde(k).exists()] if ikon else []) + \
            [("hareket", k) for k in (kodlar or list(pt.KATALOG)) if not anatomi(k).exists()]
    ard = [0]

    def tek(i):
        if ard[0] >= 3:
            return
        tur, k = i
        ok = (govde_uret if tur == "govde" else hareket_uret)(k, log)
        with _kilit:
            ard[0] = 0 if ok else ard[0] + 1
        _durum_yaz(son=k)
    with ThreadPoolExecutor(paralel) as h:
        list(h.map(tek, isler))
    _durum_yaz(calisiyor=False, bitis=int(time.time()), durdu="art arda 3 görsel çıkmadı" if ard[0] >= 3 else None)
    return durum()


if __name__ == "__main__":
    import sys
    a = sys.argv[1:]
    if a[:1] == ["ikon"]:
        for k in a[1:] or list(sb.KAS_EN):
            govde_uret(k)
    elif a[:1] == ["resim"]:
        from PIL import Image
        L = [anatomi(k) for k in a[1:] if anatomi(k).exists()]
        W = Image.new("RGB", (640 * 2, 360 * ((len(L) + 1) // 2)))
        for i, f in enumerate(L):
            W.paste(Image.open(f).resize((640, 360)), ((i % 2) * 640, (i // 2) * 360))
        W.save(MEDYA / "_anatomi.jpg")
        print(MEDYA / "_anatomi.jpg")
    else:
        print(json.dumps(hepsini(a or None), ensure_ascii=False))

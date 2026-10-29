"""pt_storyboard.py - Hareketlerin gerçekçi storyboard kareleri (2026-10-25; kullanıcı: "çöp adam kötü; aşırı gerçekçi görüntülerle storyboard; ChatGPT
üyeliğimle üretelim").

ChatGPT uygulamasıyla gelen Codex programı (`codex exec`, kullanıcının ChatGPT oturumu; görsel üretme aracı açık) kullanılır: ek ücret yok, ChatGPT
planının görsel hakkından düşer. Her hareket için kart tarifinden (pt_kart `gorsel`) 3 kare: başlangıç → hareket → bitiş (statik tutuşta 1 kare);
hep aynı model kişi (pt_medya/_kisi.png referans), ikinci ve üçüncü kare başlangıç karesi de referans verilerek (aynı yön, kamera, mat).
Kareler pt_medya/<kod>/k1.jpg… (1600 px) ve k1_k.jpg… (480 px). Durum pt_medya/storyboard.json. Codex her kareyi geçici klasörde üretir; dosya
çıkmazsa bir kez daha dener, art arda 3 kare çıkmazsa (büyük olasılıkla ChatGPT görsel sınırı) durur, kalan sonraki çalıştırmaya kalır.
"""
import json
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pt
import pt_kart

MEDYA = pt_kart.MEDYA
DURUM = MEDYA / "storyboard.json"
KISI = MEDYA / "_kisi.png"
CODEX_ADAY = [Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex")]
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
_kilit = threading.Lock()

ORTAK = ("Use your image generation tool to create ONE image: a photorealistic, high-end sports brand campaign photo (like a Nike or Apple Fitness+ ad). "
         "The SAME man as in the first attached reference photo (same face, hair, build), wearing a fitted charcoal t-shirt and black training shorts, "
         "barefoot. Dark moody studio, near-black seamless background, dramatic cinematic rim lighting, a subtle lime-green (#C4F23A) accent glow behind "
         "him, light haze, sharp detail, visible muscle definition, matte black exercise mat on a dark glossy floor. {kamera} view, whole body and all "
         "equipment visible, centered, 16:9 landscape, anatomically correct, realistic proportions, no text, no logos, no watermark.")
ADIM = {
    1: "Pose (START position of the exercise '{ad}'): {poz}.",
    2: "Keep exactly the same camera, framing, zoom, lighting, background, facing direction and mat position as in the second attached photo (the start position). "
       "Pose (MIDDLE of the movement of the exercise '{ad}', halfway from start to end): {hareket}. Start was: {bas}. End is: {bit}.",
    3: "Keep exactly the same camera, framing, zoom, lighting, background, facing direction and mat position as in the second attached photo (the start position). "
       "Pose (END position of the exercise '{ad}'): {poz}.",
}
SON = " Save the image file into the current directory as {ad}.png and reply only with the file name."


def codex():
    for p in CODEX_ADAY:
        if p.exists():
            return str(p)
    return shutil.which("codex")


def durum():
    d = pt._json(DURUM, {})
    hazir = [k for k in pt.KATALOG if (MEDYA / k / "k1.jpg").exists()]
    return {"hazir": len(hazir), "toplam": len(pt.KATALOG), **{a: d.get(a) for a in ("calisiyor", "hata", "son", "durdu")}}


def kareler(kod):
    """Hazır karelerin adları (k1, k2, k3)."""
    return [f"k{i}" for i in (1, 2, 3) if (MEDYA / kod / f"k{i}.jpg").exists()]


def _uret_tek(istem, refler, hedef_png, log):
    """Codex ile tek görsel; başarılıysa True."""
    is_ = MEDYA / ".codex_is" / f"{hedef_png.parent.name}_{hedef_png.stem}"
    shutil.rmtree(is_, ignore_errors=True)
    is_.mkdir(parents=True, exist_ok=True)
    komut = [codex(), "exec", "--skip-git-repo-check", "-s", "workspace-write", "-c", 'model_reasoning_effort="low"']
    for r in refler:
        komut += ["-i", str(r)]
    komut.append("-")
    try:
        r = subprocess.run(komut, input=istem, capture_output=True, text=True, timeout=420, cwd=is_)
    except subprocess.TimeoutExpired:
        log(f"zaman aşımı: {hedef_png}")
        return False
    png = sorted(is_.glob("*.png"), key=lambda p: p.stat().st_mtime)
    if not png:
        son = (r.stdout + r.stderr).strip().splitlines()[-3:]
        log(f"görsel çıkmadı ({hedef_png.parent.name}/{hedef_png.stem}): {' | '.join(son)[:300]}")
        return False
    shutil.move(str(png[-1]), hedef_png)
    shutil.rmtree(is_, ignore_errors=True)
    return True


def _jpg(png, jpg, genislik):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(png), "-vf", f"scale={genislik}:-2", "-q:v", "4", str(jpg)], capture_output=True, timeout=60)


def uret(kod, log=print, yenile=False):
    """Bir hareketin storyboard kareleri. Döner: üretilen kare sayısı (0 = hiçbiri)."""
    kart = pt_kart.kartlar().get(kod) or {}
    g = kart.get("gorsel") or {}
    if not g.get("bas"):
        log(f"{kod}: kart tarifi yok")
        return 0
    k = MEDYA / kod
    k.mkdir(parents=True, exist_ok=True)
    ad = pt.KATALOG[kod]["ad"]
    ekip = g.get("ekipman_en") or ""
    ekip = f" Equipment visible: {ekip}." if ekip and ekip.lower() != "none" else ""
    ortak = ORTAK.format(kamera={"front": "Front", "three-quarter": "Three-quarter"}.get(g.get("kamera"), "Side")) + ekip
    adimlar = [1] if g.get("tutus") else [1, 2, 3]
    yapilan = 0
    for n in adimlar:
        png, jpg = k / f"k{n}.png", k / f"k{n}.jpg"
        if jpg.exists() and not yenile:
            continue
        if n > 1 and not (k / "k1.png").exists():
            break
        istem = ortak + " " + ADIM[n].format(ad=ad, poz=g["bas"] if n == 1 else g.get("bit") or g["bas"], hareket=g.get("hareket") or "",
                                              bas=g["bas"], bit=g.get("bit") or "") + SON.format(ad=f"k{n}")
        refler = [KISI] + ([k / "k1.png"] if n > 1 else [])
        if not (_uret_tek(istem, refler, png, log) or _uret_tek(istem, refler, png, log)):
            return -1 if yapilan == 0 else yapilan
        _jpg(png, jpg, 1600)
        _jpg(png, k / f"k{n}_k.jpg", 480)
        if n > 1:
            png.unlink(missing_ok=True)
        yapilan += 1
    if (k / "k1.jpg").exists() and all((k / f"k{n}.jpg").exists() for n in adimlar):
        (k / "k1.png").unlink(missing_ok=True)
    return yapilan


def hepsini_uret(kodlar=None, log=print, paralel=2):
    """Eksik hareketleri sırayla üretir; art arda 3 başarısız harekette durur (ChatGPT görsel sınırı olabilir)."""
    if not codex():
        raise RuntimeError("ChatGPT uygulamasındaki Codex bulunamadı.")
    eksik = [k for k in (kodlar or list(pt.KATALOG)) if k in pt.KATALOG and not all(
        (MEDYA / k / f"k{n}.jpg").exists() for n in ([1] if (pt_kart.kartlar().get(k) or {}).get("gorsel", {}).get("tutus") else [1, 2, 3]))]
    pt._yaz(DURUM, {"calisiyor": True, "bas": int(time.time()), "kalan": len(eksik), "hata": None, "durdu": None})
    ardisik = [0]
    dur = threading.Event()

    def tek(kod):
        if dur.is_set():
            return
        n = uret(kod, log)
        with _kilit:
            ardisik[0] = ardisik[0] + 1 if n < 0 else 0
            d = pt._json(DURUM, {})
            d["kalan"] = max(0, (d.get("kalan") or 1) - 1)
            d["son"] = kod
            if ardisik[0] >= 3:
                dur.set()
                d["durdu"] = "Art arda 3 hareket üretilemedi; ChatGPT görsel sınırı dolmuş olabilir. Birkaç saat sonra kaldığı yerden sürer."
                log(d["durdu"])
            pt._yaz(DURUM, d)
        if n > 0:
            log(f"hazır: {kod} ({n} kare)")
    with ThreadPoolExecutor(paralel) as ex:
        list(ex.map(tek, eksik))
    d = pt._json(DURUM, {})
    d.update(calisiyor=False, bitis=int(time.time()))
    pt._yaz(DURUM, d)
    return durum()


def resim(kodlar, yol):
    """Kontrol için yan yana kareler (her satır bir hareket)."""
    from PIL import Image, ImageDraw
    satirlar = [[MEDYA / k / f"{n}_k.jpg" for n in kareler(k)] for k in kodlar]
    W, H = 480, 270
    im = Image.new("RGB", (W * 3, H * len(kodlar) + 20 * len(kodlar)), "white")
    d = ImageDraw.Draw(im)
    for i, (k, s) in enumerate(zip(kodlar, satirlar)):
        y = i * (H + 20)
        d.text((6, y + 4), f"{k}: {pt.KATALOG[k]['ad']}", fill=(0, 0, 0))
        for j, f in enumerate(s):
            im.paste(Image.open(f).resize((W, H)), (j * W, y + 20))
    im.save(yol, quality=80)
    return yol


# ----------------------------------------------------------------------------- çalışan kaslar: kas grubu başına bir gerçekçi görsel (eski çizim yerine)
KAS_KLASOR = MEDYA / "_kas"
KAS_EN = {"gogus": ("chest (pectoral) muscles", "front"), "on_omuz": ("front deltoid muscles", "front"), "yan_omuz": ("side deltoid muscles", "front"),
          "arka_omuz": ("rear deltoid muscles", "back"), "triceps": ("triceps muscles", "back"), "biceps": ("biceps muscles", "front"),
          "on_kol": ("forearm muscles", "front"), "karin": ("abdominal (rectus abdominis) muscles", "front"), "yan_karin": ("oblique muscles", "front"),
          "ust_sirt": ("upper back trapezius and rhomboid muscles", "back"), "kanat": ("latissimus dorsi (lats) muscles", "back"),
          "bel": ("lower back (erector spinae) muscles", "back"), "kalca": ("gluteal muscles", "back"), "on_bacak": ("quadriceps muscles", "front"),
          "arka_bacak": ("hamstring muscles", "back"), "ic_bacak": ("inner thigh (adductor) muscles", "front"), "baldir": ("calf muscles", "back"),
          "boyun": ("neck muscles", "front")}
KAS_ISTEM = ("Use your image generation tool to create ONE image: a photorealistic, high-end fitness campaign photo. The SAME man as in the attached "
             "reference photo (same face, hair, build), shirtless, athletic, wearing black training shorts, standing relaxed, {yon} view{yuz}, whole upper "
             "body and legs visible. Dark moody studio, near-black background, dramatic cinematic rim lighting. ONLY his {kas} are highlighted: they glow "
             "with a vivid lime-green (#C4F23A) translucent light on the skin, like an anatomy visualization, everything else natural skin tone. "
             "4:5 portrait, sharp detail, anatomically correct, no text, no labels, no logos. Save the image file into the current directory as kas.png "
             "and reply only with the file name.")


def kas_gorsel(kod):
    return KAS_KLASOR / f"{kod}.jpg"


def kas_uret(kodlar=None, log=print):
    KAS_KLASOR.mkdir(parents=True, exist_ok=True)
    for kod in kodlar or list(KAS_EN):
        if kas_gorsel(kod).exists():
            continue
        kas, yon = KAS_EN[kod]
        png = KAS_KLASOR / f"{kod}.png"
        istem = KAS_ISTEM.format(kas=kas, yon="back" if yon == "back" else "front", yuz=" (seen from behind, head turned slightly)" if yon == "back" else "")
        if _uret_tek(istem, [KISI], png, log) or _uret_tek(istem, [KISI], png, log):
            _jpg(png, kas_gorsel(kod), 720)
            png.unlink(missing_ok=True)
            log(f"kas hazır: {kod}")


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["kas"]:
        kas_uret(sys.argv[2:] or None)
    elif sys.argv[1:2] == ["resim"]:
        print(resim(sys.argv[2:], MEDYA / "_storyboard.jpg"))
    else:
        print(json.dumps(hepsini_uret(sys.argv[1:] or None), ensure_ascii=False))

/* pt_ana.js — Health'in Bugün ekranı (2026-10-31; kullanıcı: "Hiçbir şey anlamıyorum. Sitenin kullanım amacı nedir, ne işe yarıyor anlaşılmıyor.
   Siteye girince neye bakmam gerektiğini bilmiyorum. Bir amaç bulmalıyız; ona göre ux, ui kararları. Görselleştirme artmalı, full yazı gibi.").

   AMAÇ: Health uzun ve sağlıklı yaşamanız için her gün üç işi takip eder: HAREKET, BESLENME, TOPARLANMA.
   Ekran bu cümleye göre kurulur ve üç soruyu sırayla cevaplar:
     1. Bugün üç işin neresindeyim?  → üç halka (dokununca o işin ayrıntısı açılır)
     2. Şimdi ne yapmalıyım?          → tek "Şimdi" kartı, tek birincil düğme
     3. Haftam nasıl gidiyor?         → haftalık doz halkaları, seri, hikâye, hedefler
   Hiçbir kart kaldırılmadı (kullanıcı kuralı: sadeleştirmek özellik kısmak değil); hepsi üç işten birinin altına ya da "Health'ten" bölümüne taşındı.
   pt.html'deki bugunCiz'in yerini alır; kartlar ve bağlayıcılar (seansKart, pencereKart, …Bagla) pt.html'de aynen kalır. */
(() => {
'use strict';
if (typeof bugunCiz !== 'function') return;
const AYAK = {
  hareket: {ad: 'Hareket', renk: 'var(--vurgu)', neden: 'Güç, kardiyo ve denge: yaşla en çok kaybedilen ve uzun yaşamı en çok belirleyen üç şey.',
    ikon: '<svg viewBox="0 0 24 24"><path d="M2.5 12h19M6 7.5v9M3.5 9.5v5M18 7.5v9M20.5 9.5v5"/></svg>'},
  beslenme: {ad: 'Beslenme', renk: 'var(--mavi)', neden: 'Yeme saatleri, yeterli protein ve lif. Kas korunur, kilo ve kan değerleri dengelenir.',
    ikon: '<svg viewBox="0 0 24 24"><path d="M7 3v8a2 2 0 0 0 2 2v8M5 3v5M9 3v5M16 21V3c2.5 1.5 3.5 4 3.5 7s-1 4-3.5 4"/></svg>'},
  toparlanma: {ad: 'Toparlanma', renk: 'var(--sari)', neden: 'Uyku, nefes, gün içi hareket ve ağrı takibi. Vücudunuz antrenmanı burada kazanır.',
    ikon: '<svg viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>'}
};
const TIK = '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.2 4.2L19 7"/></svg>';
const ss = {get: k => { try{ return sessionStorage.getItem(k); }catch(e){ return null; } }, set: (k, v) => { try{ sessionStorage.setItem(k, v); }catch(e){} }};
const ls = {get: k => { try{ return localStorage.getItem(k); }catch(e){ return null; } }, set: (k, v) => { try{ localStorage.setItem(k, v); }catch(e){} }};
const saatYaz = t => new Date(t * 1000).toLocaleTimeString('tr-TR', {hour: '2-digit', minute: '2-digit'});

/* ---------- üç işin bugünkü durumu (yalnız istemcideki veriden) ---------- */
function hareketDurum(){
  const o = S.o, b = o.bugun || {}, il = o.ilk || {};
  const L = (b.seanslar || []).filter(s => s.tur !== 'dinlenme' && !s.kaynak);   // elle ve sohbetle girilenler planı "yapıldı" saydırmaz
  if (il.aktif && il.simdi){
    if (il.bugun_tamam) return {oran: 1, tamam: true, satir: 'Bugünkü adım tamam'};
    return {oran: 0, satir: `${il.simdi.ad} · ${il.simdi.dk} dk`, seans: {ilk: true, ad: il.simdi.ad, dk: il.simdi.dk}};
  }
  if (!L.length) return {oran: 1, tamam: true, dinlenme: true, satir: o.hafta && o.hafta.var ? 'Bugün dinlenme günü' : 'Bu hafta için plan yok'};
  const top = L.reduce((a, s) => a + (+s.sure_dk || 20), 0), yap = L.filter(s => s.bitti).reduce((a, s) => a + (+s.sure_dk || 20), 0);
  const sira = L.find(s => !s.bitti);
  return {oran: top ? yap / top : 0, tamam: !sira, seans: sira, satir: sira ? `${sira.baslik || 'Antrenman'}${sira.sure_dk ? ' · ' + sira.sure_dk + ' dk' : ''}` : `${yap} dk tamam`};
}
function beslenmeDurum(){
  const bs = S.o.beslenme || {}, h = bs.hedef || {}, t = bs.toplam || {}, pen = h.pencere || {};
  const oran = h.protein ? Math.min(1, (t.protein || 0) / h.protein) : (t.kcal ? Math.min(1, t.kcal / (h.kcal || 2000)) : 0);
  let satir = '';
  if (pen.oruc && pen.durum !== 'acik'){
    const sa = (Date.now() / 1000 - pen.oruc.bas_t) / 3600 + (pen.oruc.kayma_sa || 0);
    const fz = (pen.oruc.fazlar || []).reduce((a, x) => sa >= x.bas ? x : a, (pen.oruc.fazlar || [])[0]);
    const k = pen.oruc.sonraki_t ? pen.oruc.sonraki_t - Date.now() / 1000 : 0;
    satir = `${fz ? fz.ad : 'Oruç'}${k > 0 ? ' · yemeğe ' + Math.round(k / 3600) + ' sa' : ''}`;
  } else if (pen.durum === 'acik') satir = `Yeme saatindesiniz · ${sure(pen.kapanis_t - Date.now() / 1000)} kaldı`;
  else if (pen.durum === 'once') satir = `Yeme saati ${pen.acilis}'de açılır`;
  if (h.protein && !(pen.oruc && pen.durum !== 'acik')) satir += `${satir ? ' · ' : ''}${Math.round(t.protein || 0)}/${h.protein} g protein`;
  return {oran, tamam: oran >= 0.95, satir: satir || 'Öğünlerinizi kaydedin'};
}
function toparlanmaDurum(){
  const o = S.o, b = o.bugun || {};
  const M = (o.moduller || []).filter(m => m.bugun && m.uygulama !== 'not');
  const sabahVar = !!(b.sabah || {}).isik, isler = (sabahVar || new Date().getHours() < 15 ? [{ad: 'Sabah kontrolü', bitti: sabahVar}] : []).concat(M.map(m => ({ad: m.ad, bitti: !!m.bitti, m})));
  if (new Date().getHours() >= 17) isler.push({ad: 'Akşam görüşmesi', bitti: !!(b.aksam && b.aksam.koc), aksam: true});
  const bit = isler.filter(x => x.bitti).length, sira = isler.find(x => !x.bitti);
  return {oran: isler.length ? bit / isler.length : 1, tamam: !sira, sira, satir: sira ? `Sırada: ${sira.ad}` : `${bit}/${isler.length} tamam`};
}

/* ---------- şimdi ne yapmalı: tek iş, tek düğme ---------- */
function simdi(D){
  const o = S.o, b = o.bugun || {}, s = new Date().getHours(), pen = ((o.beslenme || {}).hedef || {}).pencere || {};
  if ((o.tarama || {}).bekliyor) return {ayak: 'hareket', baslik: 'Önce doktorunuzla konuşun', ozel: true, neden: 'Sağlık sorularından birine "evet" dediniz. Onay alınca plan başlar.', dugme: '<button class="btn ana genis" data-doktor>Doktorumla konuştum, onay aldım</button>'};
  if ((o.calisan || {}).plan) return {ayak: 'hareket', baslik: 'Haftanızı yazıyorum', ozel: true, neden: 'Bir iki dakika sürer. Bu sırada sabah sorularını cevaplayabilirsiniz.', dugme: (b.sabah || {}).isik ? '' : '<button class="btn ana genis" data-sabah>Sabah kontrolü · 30 sn</button>'};
  if (!(b.sabah || {}).isik && s < 15) return {ayak: 'toparlanma', baslik: 'Bugün nasılsınız?', neden: 'Uyku, enerji ve ağrı. Yarım dakika; cevaba göre bugünkü antrenmanı hafifletir ya da olduğu gibi bırakırım.', dugme: '<button class="btn ana genis" data-sabah>Sabah kontrolüne başla</button>'};
  const h = D.hareket;
  if (h.seans && h.seans.ilk) return {ayak: 'hareket', baslik: h.seans.ad, neden: 'İlk haftanızın bugünkü adımı. Ölçtükçe program size göre şekillenir.', dugme: `<button class="btn ana genis" data-tikla="[data-ilkbasla]">Başla · ${h.seans.dk} dk</button>`};
  if (h.seans && s < 22){
    const x = h.seans, sec = x.tur === 'test' ? '[data-test]' : x.tur === 'bjj_ders' ? `[data-bjj="${x.id}"]` : (x.bolumler || []).length ? `[data-basla="${x.id}"]` : `[data-yaptim="${x.id}"]`;
    const ad = x.tur === 'bjj_ders' ? 'Dersi kaydet' : (x.bolumler || []).length || x.tur === 'test' ? `Başla${x.sure_dk ? ' · ' + x.sure_dk + ' dk' : ''}` : 'Yaptım';
    return {ayak: 'hareket', baslik: x.baslik || 'Bugünkü antrenman', neden: x.neden || x.aciklama || 'Bugünün hareket işi bu. Bitirince haftalık güç ve kardiyo halkalarınız dolar.', dugme: `<button class="btn ana genis" data-tikla='${sec}'>${ad}</button>`};
  }
  if (pen.durum === 'acik' && !(b.yemekler || []).length) return {ayak: 'beslenme', baslik: 'Yeme saatindesiniz', neden: `Pencere ${pen.kapanis}'de kapanıyor. Ne yediğinizi listeden seçin; protein ve kaloriyi ben hesaplarım.`, dugme: `<button class="btn ana genis" data-yemek>Yemek ekle</button>`};
  const t = D.toparlanma.sira;
  if (t && t.m) return {ayak: 'toparlanma', baslik: t.m.ad, neden: t.m.neden || t.m.ne || '', dugme: t.m.uygulama === 'nefes' ? `<button class="btn ana genis" data-nefes="${t.m.kod}">Başla${t.m.dk ? ' · ' + t.m.dk + ' dk' : ''}</button>` : t.m.uygulama === 'video' ? `<button class="btn ana genis" data-mvideo="${t.m.kod}">İzle ve yap</button>` : `<button class="btn ana genis" data-myap="${t.m.kod}">Yaptım</button>`};
  if (t && t.aksam) return {ayak: 'toparlanma', baslik: 'Bugün nasıl geçti?', neden: 'Beş kısa soru; yarını birlikte hazırlayalım.', dugme: '<button class="btn ana genis" data-aksamg>Akşam görüşmesi · 1 dk</button>'};
  if (pen.oruc && pen.durum !== 'acik' && pen.oruc.sonraki_t) return {ayak: 'beslenme', baslik: 'Bugünün işleri tamam', neden: `Sıradaki yemeğiniz ${saatYaz(pen.oruc.sonraki_t)}'de. Bu arada vücudunuzda neler olduğunu Beslenme'de görebilirsiniz.`, dugme: '', tamam: true};
  return {ayak: 'hareket', baslik: 'Bugünün işleri tamam', neden: 'Yarın sizi yine burada bekleyen üç iş olacak. Haftanızın nasıl dolduğunu aşağıda görebilirsiniz.', dugme: '', tamam: true};
}

/* ---------- çizim ---------- */
function halka(oran, renk, ikon, tamam){
  const r = 30, c = 2 * Math.PI * r, d = c * (1 - Math.max(0, Math.min(1, oran)));
  return `<span class="an-halka"><svg viewBox="0 0 72 72"><circle cx="36" cy="36" r="${r}" class="an-iz"/><circle cx="36" cy="36" r="${r}" class="an-dol" style="stroke:${renk};--c:${c};--d:${d}" stroke-dasharray="${c}" stroke-dashoffset="${d}"/></svg>
    <span class="an-ik" style="color:${renk}">${tamam ? TIK : ikon}</span></span>`;
}
function ayakDetay(k){
  const o = S.o, b = o.bugun || {};
  if (k === 'hareket'){
    let h = '';
    if ((o.ilk || {}).aktif){ h += ilkKart(); (b.seanslar || []).filter(x => x.tur === 'bjj_ders').forEach(x => h += seansKart(x, false)); h += bjjSoruKart(); return h + gunPlaniKart(); }
    const L = b.seanslar || [];
    if (!L.length && o.hafta.var) h += `<div class="kart"><b>Bugün planda bir şey yok.</b><p class="gri2" style="margin:4px 0 10px;font-size:14px">İsterseniz 10 dakikalık kısa bir antrenman yapın.</p><button class="btn genis" data-asgari10>10 dakikalık kısa antrenman</button></div>`;
    else if (!o.hafta.var && !(o.calisan || {}).plan) h += `<div class="kart"><b>Bu hafta için plan yok.</b><p class="gri2" style="margin:4px 0 10px;font-size:14px">Haftanızı şimdi yazayım.</p><button class="btn genis" data-planyaz>Haftamı yaz</button></div>`;
    L.forEach((s, i) => h += seansKart(s, false));
    if (L.some(s => !s.bitti && (s.bolumler || []).length) && (b.sabah || {}).isik !== 'kirmizi') h += `<div class="satir" style="justify-content:center;margin:-2px 0 12px"><button class="metin sessiz" data-asgari10>Vaktiniz ya da enerjiniz az mı? 10 dakikalık kısa antrenman</button></div>`;
    if (o.oyun) h += telafiKart() + programBugunKart();
    return h + bjjSoruKart() + gunPlaniKart();
  }
  if (k === 'beslenme') return pencereKart() + suKart();
  return sabahKart() + modulOlayKart() + modulKart() + aksamKart();
}
function anaHtml(){
  const o = S.o, p = o.profil || {};
  const D = {hareket: hareketDurum(), beslenme: beslenmeDurum(), toparlanma: toparlanmaDurum()};
  const N = simdi(D), sec = ss.get('pt_ayak') && AYAK[ss.get('pt_ayak')] ? ss.get('pt_ayak') : N.ayak;
  const saat = new Date().getHours(), selam = saat < 12 ? 'Günaydın' : saat < 18 ? 'İyi günler' : 'İyi akşamlar';
  const tar = new Date().toLocaleDateString('tr-TR', {weekday: 'long', day: 'numeric', month: 'long'});
  const biten = Object.values(D).filter(x => x.tamam).length;
  const y = o.oyun, seriVar = y && (y.seri || y.en_uzun || (y.bugun || {}).durum === 'tamam' || ((y.puan || {}).toplam || 0) > 0);
  const gs = gidisatHtml();
  const notlar = [degerlendirmeKart(), receteKart(), araKontrolKart(), kontrolKart(), haftalikKart(),
    o.mesaj && o.mesaj.hafta && Date.now() / 1000 - o.mesaj.zaman < 4 * 86400 ? `<div class="kart"><div class="kbas"><h3>Haftalık mesajınız</h3><span class="mono">${esc(haftaYazi(o.mesaj.hafta))}</span></div><p class="gri2" style="margin:0 0 6px;font-size:14px">${esc(o.mesaj.degisecek || '')}</p><button class="metin" data-mesaj>Oku</button></div>` : '',
    o.oyun ? oneriKart() : '', araSoruKart(), aliskanlikKart(), tanismaKart()].filter(Boolean);
  const selamH = typeof selamKart === 'function' ? selamKart() : '';
  /* 2026-11-03 (kullanıcı: "Çok fazla şey alt alta. Daha odaklı olmalı."): ilk ekranda yalnız oruç, hareket, yedikleriniz ve son 7 gün; gerisi sekmede, hiçbiri silinmedi. */
  const SEK = [['bugun', 'Bugün'], ['ayrinti', 'Ayrıntı'], ['hafta', 'Haftam'], ['notlar', 'Notlar' + (notlar.length ? ` · ${notlar.length}` : '')]];
  const ak = SEK.some(x => x[0] === ss.get('pt_ansek')) ? ss.get('pt_ansek') : 'bugun';
  const panel = (k, ic) => `<div data-anp="${k}" ${k === ak ? '' : 'hidden'}>${ic}</div>`;
  const ayriSimdi = N.ozel || (N.ayak === 'toparlanma' && !N.tamam);
  let h = `<section class="an-ust an-kisa"><p class="mono">${esc(tar)}</p><h1 class="bas">${selam}${p.ad ? ', ' + esc(p.ad.split(' ')[0]) : ''}.</h1></section>
    <div class="an-sek" role="tablist">${SEK.map(([k, a]) => `<button role="tab" aria-selected="${k === ak}" class="${k === ak ? 'on' : ''}" data-ansek="${k}">${esc(a)}</button>`).join('')}</div>`;
  h += panel('bugun', kutlamaKart() + durgunKart() + agriTakipKart()
    + (ayriSimdi ? (N.ozel ? `<section class="kart an-simdi" style="--ar:${AYAK[N.ayak].renk}"><h2>${esc(N.baslik)}</h2>${N.neden ? `<p>${esc(N.neden)}</p>` : ''}${N.dugme || ''}</section>`
      : `<section class="kart an-ince"><b>${esc(N.baslik)}</b>${(N.dugme || '').replace('btn ana genis', 'btn kucuk')}</section>`) : '')
    + `<div class="an-ikili">${orucOzet()}${hareketOzet(D.hareket)}</div>` + yemekOzet(D.hareket) + yediGun());
  h += panel('ayrinti', `<section class="an-ust"><p class="an-amac">Health, uzun ve sağlıklı yaşamanız için her gün <b>üç işi</b> takip eder. Bugün <b>${biten}/3</b> tamam. <button class="metin" data-nasil>Nasıl çalışır?</button></p>
    <div class="an-uc" role="tablist">${Object.entries(AYAK).map(([k, a]) => `<button class="an-ayak ${k === sec ? 'on' : ''} ${D[k].tamam ? 'tamam' : ''}" role="tab" aria-selected="${k === sec}" data-ayak="${k}">
      ${halka(D[k].oran, a.renk, a.ikon, D[k].tamam)}<b>${a.ad}</b><small>${esc(D[k].satir)}</small></button>`).join('')}</div></section>
    <section class="an-detay"><div class="an-dbas"><span class="an-dik" style="color:${AYAK[sec].renk}">${AYAK[sec].ikon}</span><div><h2>${AYAK[sec].ad}</h2><p>${esc(AYAK[sec].neden)}</p></div></div>
    ${Object.keys(AYAK).map(k => `<div data-ayakic="${k}" ${k === sec ? '' : 'hidden'}>${ayakDetay(k)}</div>`).join('')}</section>`);
  h += panel('hafta', (seriVar ? puanSerit() : '') + gs + haftaHalka(true) + hikayeKart() + hedefKart(true) + (o.oyun ? gorevKart() : ''));
  h += panel('notlar', selamH + (notlar.join('') || (selamH ? '' : '<p class="gri2" style="font-size:14px;margin:12px 0">Şimdilik yeni not yok.</p>')));
  h += '<div id="telKart"></div>';
  return {h, N};
}
/* ---------- odaklı ilk ekran ---------- */
function hareketDugme(h){
  if (h.seans && h.seans.ilk) return `<button class="btn ana genis" data-tikla="[data-ilkbasla]">Başla · ${h.seans.dk} dk</button>`;
  if (!h.seans) return '';
  const x = h.seans, sec = x.tur === 'test' ? '[data-test]' : x.tur === 'bjj_ders' ? `[data-bjj="${x.id}"]` : (x.bolumler || []).length ? `[data-basla="${x.id}"]` : `[data-yaptim="${x.id}"]`;
  return `<button class="btn ana genis" data-tikla='${sec}'>${x.tur === 'bjj_ders' ? 'Dersi kaydet' : (x.bolumler || []).length || x.tur === 'test' ? `Başla${x.sure_dk ? ' · ' + x.sure_dk + ' dk' : ''}` : 'Yaptım'}</button>`;
}
function orucMetin(){
  const g = S.o.gidisat || {}, O = g.oruc || {}, sn = O.suren, pen = ((S.o.beslenme || {}).hedef || {}).pencere || {}, simdi = Date.now() / 1000;
  const hedef = O.hedef || pen.hedef_oruc || 18;
  if (sn && sn.durum === 'oruc'){
    const sa = (simdi - sn.bas_t) / 3600, kalan = hedef - sa;
    return {oruc: true, ust: 'Oruçtasınız', sure: sure(simdi - sn.bas_t) + (sn.tahmini ? ' ~' : ''), oran: Math.min(1, sa / hedef), alt: kalan > 0 ? `Hedef ${gsVir(hedef)} sa · ${sure(kalan * 3600)} kaldı` : `Hedef ${gsVir(hedef)} sa tuttu`, ok: kalan <= 0};
  }
  if (sn && sn.durum === 'yeme'){
    const k = (pen.kapanis_t || 0) - simdi;
    return {oruc: false, ust: 'Oruç bitti', sure: saatYaz(sn.bas_t) + "'den beri", oran: 0, alt: k > 0 ? `Yeme saati ${sure(k)} daha sürer` : 'Yeme saati doldu'};
  }
  return {oruc: false, ust: 'Oruç', sure: 'Kayıt yok', oran: 0, alt: `Hedef ${gsVir(hedef)} sa`, bos: true};
}
function orucOzet(){
  const m = orucMetin(), O = (S.o.gidisat || {}).oruc || {}, pen = ((S.o.beslenme || {}).hedef || {}).pencere || {};
  return `<section class="kart an-oz oruc"><div class="an-ozb"><span class="an-ozi" style="color:var(--mavi)">${GS_IK.oruc}</span><span>${esc(m.ust)}</span>${O.seri ? `<em>${O.seri} gün seri</em>` : ''}</div>
    <p class="an-ozs" data-orucsure>${esc(m.sure)}</p><div class="an-ozc"><i style="width:${Math.round(m.oran * 100)}%" class="${m.ok ? 'ok' : ''}"></i></div><p class="an-oza" data-orucalt>${esc(m.alt)}</p>
    ${m.oruc ? '<button class="btn genis" data-oruc="ac">Orucumu bitirdim</button>' : `<button class="btn genis" data-oruc="kapat">Oruca başladım</button>`}
    ${pen.oruc && m.oruc ? '<button class="metin an-ozl" data-ansekgit="ayrinti" data-ayakgit="beslenme">Vücudunuzda şu an ne oluyor?</button>' : ''}</section>`;
}
function hareketOzet(h){
  const H = (S.o.gidisat || {}).hareket || {}, btn = hareketDugme(h);
  return `<section class="kart an-oz hareket ${h.tamam ? 'tamam' : ''}"><div class="an-ozb"><span class="an-ozi" style="color:var(--vurgu)">${AYAK.hareket.ikon}</span><span>Hareket</span>${H.seri ? `<em>${H.seri} gün seri</em>` : ''}</div>
    <p class="an-ozs">${h.tamam ? (h.dinlenme ? 'Dinlenme' : 'Tamam') : `${Math.round(h.oran * 100)}%`}</p><div class="an-ozc"><i style="width:${Math.round(h.oran * 100)}%" class="${h.tamam ? 'ok' : ''}"></i></div><p class="an-oza">${esc(h.satir)}</p>
    ${btn || (h.tamam && !h.dinlenme ? '' : '<button class="btn genis" data-ansekgit="ayrinti" data-ayakgit="hareket">Bugünü gör</button>')}
    <button class="metin an-ozl" data-hareket>Yaptığımı ekle</button>${btn ? '<button class="metin an-ozl" data-ansekgit="ayrinti" data-ayakgit="hareket">Listeye bak</button>' : ''}</section>`;
}
function yemekOzet(h){
  const bs = S.o.beslenme || {}, T = bs.toplam || {}, H = bs.hedef || {}, b = S.o.bugun || {};
  const L = (S.o.gunluk && S.o.gunluk.yemekler) || b.yemekler || [];
  const kc = y => Math.round((y.kalemler || []).reduce((a, x) => a + (+x.kcal || 0), 0));
  const bozar = y => typeof y.oruc_bozar === 'boolean' ? y.oruc_bozar : kc(y) >= 15 || !(y.kalemler || []).length;
  return `<section class="kart an-yem"><div class="an-yb"><div><b>Yedikleriniz</b>${L.length ? `<span class="gri">${Math.round(T.kcal || 0)}${H.kcal ? ' / ' + H.kcal : ''} kcal · ${Math.round(T.protein || 0)}${H.protein ? ' / ' + H.protein : ''} g protein</span>` : ''}</div>
      <button class="btn ${h.seans ? '' : 'ana'}" data-yemek>Ne yedim, ne içtim?</button></div>
    ${L.length ? `<ul class="an-yl">${L.map(y => `<li><span class="an-yt">${saatYaz(y.t)}</span><span class="an-ya">${esc(y.ad || 'Öğün')}<small>${kc(y)} kcal</small></span>
      <button class="an-yo ${bozar(y) ? 'boz' : ''}" data-yo="${esc(y.id)}" data-boz="${bozar(y) ? 1 : 0}" title="Dokununca değişir">${bozar(y) ? 'Orucu bozdu' : 'Oruç sürdü'}</button><button class="an-ys" data-ysil="${esc(y.id)}" aria-label="Kaldır">×</button></li>`).join('')}</ul>` : ''}</section>`;
}
function yediGun(){
  const g = S.o.gidisat; if (!g || !g.var) return '';
  return `<section class="kart an-yedi"><div class="an-yedib"><b>Son 7 gün</b><button class="metin" data-ansekgit="hafta">Takvim</button></div><div class="an-yg">${(g.yedi || []).map(x => `<button data-gsgun="${x.tarih}" class="${x.tarih === bugunT() ? 'bugun' : ''}" aria-label="${esc(gsTarih(x.tarih))}">
    <small>${esc(gsTarih(x.tarih, {weekday: 'short'}))}</small><span class="an-gh ${x.hareket ? 'ok' : ''}">${x.hareket ? (x.hareket_dk ? x.hareket_dk + ' dk' : '✓') : '–'}</span><span class="an-go ${x.oruc_tamam ? 'ok' : ''}">${x.oruc_sa != null ? gsVir(x.oruc_sa) + ' sa' : '–'}</span></button>`).join('')}</div>
    <p class="an-yga"><span class="h"></span>Hareket <span class="o"></span>Oruç · Bir güne dokunun, ne yaptığınızı görün.</p></section>`;
}
/* ---------- gidişat: seriler, takvim, bir günün dökümü (2026-11-02; kullanıcı: "kaç günlük streak'teyim, şu gün şu kadar saat oruç yapmışım; güne tıklayınca o gün ne yapmışım çıkacak") ---------- */
let gsTak = null, gsCizildi = false;
const gsSa = x => { const dk = Math.round((+x || 0) * 60), s = Math.floor(dk / 60), d = dk % 60; return s ? `${s} sa${d ? ' ' + d + ' dk' : ''}` : `${d} dk`; };
const gsVir = x => String(Math.round((+x || 0) * 10) / 10).replace('.', ',');
const gsTarih = (t, o = {weekday: 'long', day: 'numeric', month: 'long'}) => new Date(t + 'T12:00').toLocaleDateString('tr-TR', o);
const GS_IK = {hareket: AYAK.hareket.ikon, oruc: '<svg viewBox="0 0 24 24"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9.5 2.5h5"/></svg>'};
function gsCubuk(L, tur, hedef){
  const en = tur === 'oruc' ? Math.max(24, ...L.map(g => g.oruc_sa || 0)) : Math.max(60, ...L.map(g => g.hareket_dk || 0));
  return `<div class="gs-yedi ${tur}">${tur === 'oruc' && hedef ? `<i class="gs-hedef" style="bottom:calc(16px + (100% - 16px) * ${hedef / en})"></i>` : ''}${L.map(g => {
    const d = tur === 'oruc' ? g.oruc_sa : g.hareket_dk, ok = tur === 'oruc' ? g.oruc_tamam : g.hareket;
    const yaz = tur === 'oruc' ? (d != null ? gsSa(d) + ' oruç' : 'oruç kaydı yok') : (g.hareket ? g.hareket_dk + ' dk hareket' : 'hareket yok');
    return `<button data-gsgun="${g.tarih}" title="${esc(gsTarih(g.tarih, {day: 'numeric', month: 'long'}))}: ${yaz}" aria-label="${esc(gsTarih(g.tarih))}: ${yaz}" class="${ok ? 'ok' : ''} ${g.tarih === bugunT() ? 'bugun' : ''}"><span><u style="height:${d ? Math.max(6, Math.round(d / en * 100)) : 0}%"></u></span><small>${esc(gsTarih(g.tarih, {weekday: 'narrow'}))}</small></button>`; }).join('')}</div>`;
}
function gsTakvimHtml(T){
  const G = T.gunler || [], ilk = G[0], son = G[G.length - 1];
  const aralik = ilk && son ? `${gsTarih(ilk.tarih, {day: 'numeric', month: 'short'})} – ${gsTarih(son.tarih, {day: 'numeric', month: 'short'})}` : '';
  const gunler = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'].map(x => `<span>${x}</span>`).join('');
  const hucre = G.map((g, i) => {
    const n = +g.tarih.slice(8);
    if (g.gelecek) return `<span class="gs-gun gel"><b>${n}</b></span>`;
    const sol = i % 7 && G[i - 1].hareket, sag = i % 7 < 6 && G[i + 1] && G[i + 1].hareket;
    const yaz = [g.hareket ? g.hareket_dk + ' dk hareket' : '', g.oruc_sa != null ? gsSa(g.oruc_sa) + ' oruç' : ''].filter(Boolean).join(', ') || 'kayıt yok';
    return `<button class="gs-gun ${g.hareket ? 'h' : ''} ${g.hareket && sol ? 'sol' : ''} ${g.hareket && sag ? 'sag' : ''} ${g.tarih === bugunT() ? 'bugun' : ''}" data-gsgun="${g.tarih}" aria-label="${esc(gsTarih(g.tarih))}: ${yaz}" style="--g:${g.hareket ? Math.min(1, .45 + (g.hareket_dk || 0) / 120) : 0}">
      <b>${n}</b>${g.hareket ? `<small>${g.hareket_dk ? g.hareket_dk + ' dk' : '✓'}</small>` : ''}${g.oruc_sa != null ? `<small class="o ${g.oruc_tamam ? 'ok' : ''}">${g.oruc_tahmini ? '~' : ''}${gsVir(g.oruc_sa)} sa</small>` : ''}</button>`; }).join('');
  return `<div class="gs-tbas"><h3>Takvim</h3><span class="gri">${esc(aralik)}</span><span class="gs-ok"><button data-gsok="-" aria-label="Önceki haftalar" ${T.onceki ? '' : 'disabled'}>‹</button><button data-gsok="+" aria-label="Sonraki haftalar" ${T.sonraki ? '' : 'disabled'}>›</button></span></div>
    <div class="gs-gunler">${gunler}</div><div class="gs-izgara">${hucre}</div>
    <p class="gs-acik"><span><i class="h"></i>Hareket</span><span><i class="o"></i>Oruç hedefi tuttu</span><span><i class="z"></i>Tutmadı</span><em>Bir güne dokunun, o gün ne yaptığınızı görün.</em></p>`;
}
function gidisatHtml(){
  const g = S.o.gidisat; if (!g || !g.var) return '';
  const H = g.hareket, O = g.oruc, sn = O.suren;
  const altH = `${H.en_uzun > H.seri ? `En uzunu ${H.en_uzun} gün · ` : ''}Bu hafta ${H.hafta_gun} gün, ${H.hafta_dk} dk`;
  const simdiO = !sn ? '' : sn.durum === 'yeme' ? 'Şu an yeme saatindesiniz' : `Şu an ${sure(Date.now() / 1000 - sn.bas_t)}${sn.tahmini ? ' (tahmini)' : ''} oruçtasınız`;
  const sonO = O.son ? `Son oruç ${gsSa(O.son.oruc_sa)} · hedef ${gsVir(O.hedef)} sa` : `Hedef ${gsVir(O.hedef)} sa. Yemeye başlayınca işaretleyin, burada birikir.`;
  const kart = (tur, ad, seri, alt, cub) => `<div class="kart gs-kart ${tur} ${seri ? '' : 'sifir'}"><div class="gs-kb"><span class="gs-ik">${GS_IK[tur]}</span><span>${ad}</span></div>
    <p class="gs-sayi"><b data-yuvarla="health-gs-${tur}">${seri}</b> gün seri</p><p class="gs-alt">${alt}</p>${cub}</div>`;
  const ilk = !gsCizildi; gsCizildi = true;                     // çubuklar yalnız ilk açılışta büyür; veri yenilenince oynamaz
  return `<section class="gs ${ilk ? 'ilk' : ''}"><div class="gs-kartlar">
    ${kart('hareket', 'Hareket', H.seri, esc(altH), gsCubuk(g.yedi, 'hareket'))}
    ${kart('oruc', 'Oruç', O.seri, esc(sonO) + (simdiO ? `<br>${esc(simdiO)}` : ''), gsCubuk(g.yedi, 'oruc', O.hedef))}</div>
    <div class="kart gs-takvim" id="gsTakvim">${gsTakvimHtml(gsTak || g.takvim)}</div></section>`;
}
function gsSeritHtml(r){
  const y = r.yeme, bas0 = new Date(r.tarih + 'T00:00').getTime() / 1000, oran = t => Math.max(0, Math.min(100, (t - bas0) / 864));
  if (!y || !y.bas_t) return '';
  const bugunMu = r.tarih === bugunT(), simdi = Date.now() / 1000;
  const bitis = y.bit_t || (bugunMu ? simdi : y.bas_t);
  const nokta = (r.seanslar || []).filter(s => s.bitis_t && s.bitis_t >= bas0 && s.bitis_t < bas0 + 86400).map(s => `<i class="n" style="left:${oran(s.bitis_t)}%" title="${esc(s.baslik)}"></i>`).join('');
  return `<div class="gs-serit"><span class="z" style="width:${bugunMu ? oran(simdi) : 100}%"></span><span class="y" style="left:${oran(y.bas_t)}%;width:${Math.max(.8, oran(bitis) - oran(y.bas_t))}%"></span>${nokta}</div>
    <div class="gs-saat"><span>00</span><span>06</span><span>12</span><span>18</span><span>24</span></div>`;
}
async function gunDokum(tarih){
  const p = sayfa(`<h3>${esc(gsTarih(tarih))}</h3><div class="satir gri"><span class="donen"></span> Alınıyor</div>`, {sabit: true});
  let r; try{ r = await api('/api/pt/gun-dokum?tarih=' + tarih); }catch(e){ p.kapat(); return toast(e.message); }
  const s = r.satir, S_ = r.sabah, sa = t => t ? saatYaz(t) : '';
  const modAd = k => ((S.o.moduller || []).find(m => m.kod === k) || {}).ad || k;
  const kutu = (ad, deger, alt, cl) => `<div class="gs-m ${cl || ''}"><small>${ad}</small><b>${deger}</b>${alt ? `<small>${alt}</small>` : ''}</div>`;
  let h = `<div class="gs-mler">${kutu('Hareket', s.hareket ? (s.hareket_dk ? s.hareket_dk + ' dk' : 'Yapıldı') : '—', r.seanslar.length ? r.seanslar.length + ' kayıt' : '', s.hareket ? 'h' : '')}
    ${kutu('Oruç', r.oruc ? (r.oruc.tahmini ? '~' : '') + gsSa(r.oruc.saat) : '—', r.oruc ? `hedef ${gsVir(r.hedef_oruc)} sa` : '', s.oruc_tamam ? 'o' : '')}
    ${kutu('Uyku', S_ && S_.uyku_saat ? gsVir(S_.uyku_saat) + ' sa' : '—', S_ && S_.enerji ? `enerji ${Math.round(S_.enerji)}/5` : '')}</div>`;
  let ic = '';
  if (r.seanslar.length || r.bjj.length){
    ic += `<h4>Hareket</h4>` + r.seanslar.map(x => `<div class="gs-is"><div class="gs-isb"><b>${esc(x.baslik)}</b><span>${x.dk ? x.dk + ' dk' : ''}</span></div>${x.not ? `<p>${esc(x.not)}</p>` : ''}${x.hareketler.length ? `<ul>${x.hareketler.map(k => `<li><span>${esc(k.ad)}</span><span>${esc(k.setler)}</span></li>`).join('')}</ul>` : ''}</div>`).join('')
      + r.bjj.map(b => `<div class="gs-is"><div class="gs-isb"><b>Jiu-jitsu dersi</b><span>${b.sure_dk ? b.sure_dk + ' dk' : ''}</span></div>${b.not ? `<p>${esc(b.not)}</p>` : ''}</div>`).join('');
  }
  if (r.oruc || r.yeme){
    const o = r.oruc, y = r.yeme;
    const gun0 = new Date(tarih + 'T00:00').getTime() / 1000;
    const c = o ? `Oruç: ${o.bas_t < gun0 ? 'önceki gün ' : ''}${sa(o.bas_t)}${o.tahmini ? ' (tahmini)' : ''} – ${sa(o.bit_t)}. ` : '';
    const d = y ? (y.bit_t ? `Yeme saati: ${sa(y.bas_t)} – ${sa(y.bit_t)}${y.tahmini ? ' (tahmini)' : ''}.` : `Yemeye başlama: ${sa(y.bas_t)}.`) : '';
    ic += `<h4>Oruç</h4><p class="gs-c">${esc(c + d)}</p>${gsSeritHtml(r)}`;
  }
  if (r.yemekler.length) ic += `<h4>Yemek <span class="gri">${r.toplam.kcal} kcal · ${r.toplam.protein} g protein</span></h4>` + r.yemekler.map(y => `<div class="gs-is"><div class="gs-isb"><b>${esc(y.ad || 'Öğün')}</b><span>${y.kcal} kcal</span></div></div>`).join('');
  const dig = [r.adim ? (r.adim.duzeltildi ? `~${r.adim.tahmin.toLocaleString('tr-TR')} adım (telefon ${r.adim.sayilan.toLocaleString('tr-TR')} saydı)` : `${r.adim.sayilan.toLocaleString('tr-TR')} adım`) : '', r.kilo ? `Kilo ${gsVir(r.kilo)} kg` : '', r.bel_cm ? `Bel ${gsVir(r.bel_cm)} cm` : '', r.su_ml ? `Su ${gsVir(r.su_ml / 1000)} L` : ''].filter(Boolean);
  const mod = (r.moduller || []).map(modAd);
  if (dig.length || mod.length || r.agri.length) ic += `<h4>Diğer</h4><div class="gs-cip">${dig.concat(mod).map(x => `<span>${esc(x)}</span>`).join('')}${r.agri.map(a => `<span class="ag">${esc(a.bolge || 'Ağrı')}${a.puan ? ' ' + a.puan + '/10' : ''}</span>`).join('')}</div>`;
  if (r.aksam) ic += `<h4>Akşam notu</h4><p class="gs-c">${esc(r.aksam)}</p>`;
  if (!ic) ic = `<p class="gri2" style="margin:14px 0 0;font-size:14px">Bu gün için kayıt yok.</p>`;
  $('.sayfa', p).innerHTML = `<div class="tutac"></div><button class="kapatx" data-kapat aria-label="Kapat">×</button><h3>${esc(gsTarih(tarih))}</h3>${h}<div class="gs-dok">${ic}</div>`;
}
function gsBagla(k){
  $$('[data-gsgun]', k).forEach(b => b.onclick = () => gunDokum(b.dataset.gsgun));
  $$('[data-gsok]', k).forEach(b => b.onclick = async () => {
    const T = gsTak || S.o.gidisat.takvim, d = new Date(T.son + 'T12:00'); d.setDate(d.getDate() + (b.dataset.gsok === '-' ? -35 : 35));
    const t = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    try{ gsTak = (await api('/api/pt/gidisat?son=' + t)).takvim; const kutu = $('#gsTakvim', k.closest ? k.closest('#main') || k : k); if (kutu){ kutu.innerHTML = gsTakvimHtml(gsTak); gsBagla(kutu); } }catch(e){ toast(e.message); }
  });
}
function nasilSayfa(){
  const A = [['Siz anlatırsınız', 'Hedefiniz, gününüz, ağrılarınız. Sabah 30 saniyelik kontrol, yediğinizin fotoğrafı, "dün maç yaptım" gibi bir cümle.'],
    ['Health\'in ekibi düşünür', 'Antrenör, diyetisyen ve toparlanma uzmanının kurallarıyla çalışır. Sayılar tahmin edilmez, hesaplanır.'],
    ['Size her gün üç iş verir', 'Hareket, beslenme, toparlanma. Ekranın başındaki üç halka bunlar; "Şimdi" kartı sıradakini söyler.'],
    ['Haftanız dolar, program güncellenir', 'Haftalık sağlık dozu halkaları dolar. 14 günde bir ara kontrolde program size göre değişir.']];
  const p = sayfa(`<h3>Health nasıl çalışır?</h3><p class="gri2" style="margin:0 0 4px;font-size:14px">Tek bir amaç için: uzun ve sağlıklı yaşamak.</p>
    <svg class="an-dongu" viewBox="0 0 320 120" aria-hidden="true">
      <path class="an-yol" d="M40 60 H280" /><path class="an-don" d="M280 70 C280 112 40 112 40 70" />
      ${[40, 120, 200, 280].map((x, i) => `<g class="an-dg" style="--i:${i}"><circle cx="${x}" cy="60" r="16"/><text x="${x}" y="65" text-anchor="middle">${i + 1}</text></g>`).join('')}
      <circle class="an-isik" r="4"><animateMotion dur="5s" repeatCount="indefinite" path="M40 60 H280 C280 112 40 112 40 70"/></circle></svg>
    ${A.map((a, i) => `<div class="an-adim"><span>${i + 1}</span><div><b>${a[0]}</b><p>${a[1]}</p></div></div>`).join('')}
    <div class="salt"><button class="btn ana genis" data-kapat>Anladım</button></div>`);
  ls.set('pt_nasil', '1');
  return p;
}

/* ---------- diğer sekmeler: amaç başlığı + "Bu sayfada" + bölüm açıklamaları (2026-10-31, aynı istek, ikinci tur) ----------
   Sekmeler kendi içeriklerini (bazıları geç gelen veriyle) çizer; burada #main değiştikçe üstüne sayfa başlığı eklenir. İçerik silinmez. */
const SAYFA = {
  plan: {ayak: 'hareket', ad: 'Antrenman', amac: 'Hareket işinin planı. Health haftanızı güç, kardiyo ve denge dozuna göre kurar; burada görür, değiştirir ve başlatırsınız.'},
  beslenme: {ayak: 'beslenme', ad: 'Beslenme', amac: 'Beslenme işinin yeri. Ne yediğinizi kaydedin; kalori ve proteini Health hesaplar, yeme saatlerinizi ve oruçta vücudunuzda olanları gösterir.'},
  ilerleme: {ayak: null, ad: 'İlerleme', amac: 'Uzun ve sağlıklı yaşamın göstergeleri: kondisyon, güç, denge, kilo. Yaptıklarınız burada birikir; neyin değiştiğini görürsünüz.',
    ikon: '<svg viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8M15 7h6v6"/></svg>'}
};
const ALT_ACIK = {
  program: 'Bu haftanın günleri. Bir güne dokunun: neden o gün, hangi hareketler; oradan başlatın ya da başka güne taşıyın.',
  hizli: 'Vaktiniz az ya da plan dışı bir gün mü? Süreyi ve yeri seçin, seviyenize göre kısa bir antrenman kurulur.',
  programlar: 'Bir hedefe giden birkaç haftalık hazır yollar: ilk barfiks, amut, hareketlilik… Katılırsanız haftalık planınıza girer.',
  hareketler: 'Bütün hareketler: nasıl yapılır, hangi kası çalıştırır, sizin seviyeniz neresi.'
};
const BOLUM_ACIK = {
  'Öğünler': 'Listeden seçin, fotoğraf çekin ya da yazın; besin değerini Health hesaplar.',
  'Kilo': 'Haftada birkaç kez, sabah aç karna tartılın. Tek gün değil, çizgi önemli.',
  'Yeme saatleri': 'Ne zaman yiyip ne zaman ara verdiğiniz. Oruçtayken hangi fazda olduğunuzu ve sıradaki yemeğe kalan süreyi gösterir.',
  'Haftalık menü': 'Hedefinize ve yeme saatlerinize göre yazılmış bir hafta; alışveriş listesiyle.',
  'Takviyeler': 'Bilgi için; reçete değil. Kullanmadan önce doktorunuza danışın.',
  'Uzun ömür': 'Yaşla en çok kaybedilen yetenekler. Hangisini ölçtüğünüzü ve yaşıtlarınıza göre nerede olduğunuzu gösterir.',
  'Rozetler': 'Düzenli kaldıkça kazanılır: seri, görevler, rekorlar.',
  'Kas toparlanması': 'Hangi kas grubu dinlendi, hangisi yorgun. Kısa antrenman bu bilgiyle kurulur.',
  'Hedef becerileriniz': 'Hedef hareketlere giden basamaklar ve sıradakinin şartı.',
  'Son değişiklikler': 'Antrenmanlarınıza bakıp Health\'in programda değiştirdikleri.',
  'Testler': 'Ara ara yapılan ölçümler; program başlangıç noktasını bunlardan alır.',
  'Dinlenmiş mi, yorgun mu?': 'Son haftaların yükü. Fazla yüklendiğinizde hafif hafta gelir.',
  'Bir şey değişirse': 'Plan beklenmedik durumlara kendiliğinden şöyle uyar.',
  'Jiu-jitsu': 'Derslerde zorlandığınız pozisyonlar ve onlar için evde çalışmalar.',
  'Form kontrolü': 'Bir setinizi kaydedin; açıları ölçüp tek bir düzeltme önereyim.',
  'Fotoğraflar': 'Yalnız bu cihazda saklanır.',
  'Koçunuzun haftalık mesajı': 'Her pazar: geçen hafta ne oldu, gelecek hafta ne değişecek.'
};
const bolumAdi = h => (h.childNodes[0] && h.childNodes[0].nodeType === 3 ? h.childNodes[0].textContent : h.textContent).trim();
function sayfaSusle(){
  const sk = S.sek, C = SAYFA[sk], m = $('#main');
  if (!C || !m || !m.firstElementChild) return;
  if (m.children.length < 2 && m.querySelector('.donen')) return;                              // içerik henüz gelmedi
  const A = C.ayak ? AYAK[C.ayak] : {renk: 'var(--ink)', ikon: C.ikon};
  let head = m.querySelector(':scope > .an-sayfa');
  if (!head){
    let ek = '';
    const ilk = [...m.children].slice(0, 4), mono = ilk.find(e => e.matches('p.mono')), h1 = ilk.find(e => e.matches('h1.bas')), alt = ilk.find(e => e.matches('p.alti'));
    if (sk === 'ilerleme' || sk === 'beslenme'){                                                // sekmenin eski başlığı yerine bu başlık
      ek = sk === 'ilerleme' ? (mono || {}).textContent || '' : (alt || {}).textContent || '';
      [mono, h1, alt].forEach(e => e && e.remove());
    }
    head = document.createElement('section'); head.className = 'an-sayfa';
    head.innerHTML = `<div class="an-sbas"><span class="an-dik buyuk" style="color:${A.renk}">${A.ikon}</span><div>
        ${C.ayak ? `<span class="mono">Üç işten biri · ${esc(A.ad)}</span>` : '<span class="mono">Üç işin toplamı</span>'}<h1 class="bas">${esc(C.ad)}</h1></div></div>
      <p class="an-amac">${esc(C.amac)}${ek ? ` <span class="gri">${esc(ek)}</span>` : ''}</p><div class="an-git"></div>`;
    m.insertBefore(head, m.firstElementChild);
  }
  if (sk === 'beslenme'){                                                                       // başlıksız iki büyük kart için bölüm adı
    const pk = [...m.querySelectorAll(':scope > .kart')].find(k => /Yeme saatleri/.test((k.querySelector('.mono') || {}).textContent || ''));
    if (pk && !m.querySelector('#b-yeme-saatleri')) pk.insertAdjacentHTML('beforebegin', '<h2 class="bolum" id="b-yeme-saatleri">Yeme saatleri</h2>');
    const mk = m.querySelector(':scope > #menuKart');
    if (mk && !m.querySelector('#b-haftalik-menu')) mk.insertAdjacentHTML('beforebegin', '<h2 class="bolum" id="b-haftalik-menu">Haftalık menü</h2>');
  }
  const altsek = m.querySelector(':scope > .altsek');
  if (altsek && ALT_ACIK[S.alt]){
    const sonra = [];
    for (let e = altsek.nextElementSibling; e && sonra.length < 4; e = e.nextElementSibling) sonra.push(e);
    const kendi = sonra.find(e => e.matches('h1.bas')), mevcut = m.querySelector('.an-altacik');
    if (kendi && S.alt === 'program'){ kendi.classList.add('an-altbas'); const a2 = kendi.nextElementSibling;
      if (mevcut && mevcut.previousElementSibling !== (a2 && a2.matches('p.alti') ? a2 : kendi)) mevcut.remove();
      if (!m.querySelector('.an-altacik')) (a2 && a2.matches('p.alti') ? a2 : kendi).insertAdjacentHTML('afterend', `<p class="alti an-altacik">${esc(ALT_ACIK.program)}</p>`); }
    else if (kendi){ if (mevcut) mevcut.remove(); kendi.classList.add('an-altbas');
      const a2 = kendi.nextElementSibling; if (S.alt !== 'program' && a2 && a2.matches('p.alti') && !a2.dataset.an){ a2.textContent = ALT_ACIK[S.alt]; a2.dataset.an = 1; } }
    else if (!mevcut) altsek.insertAdjacentHTML('afterend', `<p class="alti an-altacik">${esc(ALT_ACIK[S.alt])}</p>`);
  }
  $$('h2.bolum', m).forEach(h => { const ad = bolumAdi(h), a = BOLUM_ACIK[ad];
    if (a && !(h.nextElementSibling && h.nextElementSibling.classList.contains('an-bacik'))) h.insertAdjacentHTML('afterend', `<p class="an-bacik">${esc(a)}</p>`);
    if (!h.id) h.id = 'b-' + ad.toLocaleLowerCase('tr').replace(/[^a-zçğıöşü0-9]+/g, '-'); });
  const B = $$('h2.bolum', m).map(h => [h.id, bolumAdi(h)]), git = head.querySelector('.an-git'), imza = B.map(x => x[0]).join('|');
  if (git.dataset.imza !== imza){
    git.dataset.imza = imza;
    git.innerHTML = B.length > 1 ? `<span class="mono">Bu sayfada</span>${B.map(([id, ad]) => `<button data-git="${id}">${esc(ad)}</button>`).join('')}` : '';
    $$('[data-git]', git).forEach(b => b.onclick = () => { const h = document.getElementById(b.dataset.git); if (h) h.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'}); });
  }
}
const mainEl = document.getElementById('main');
if (mainEl){                                                  // kendi eklediklerimiz gözlemciyi yeniden tetiklemesin (2026-11-01: başlıklar durmadan çoğalıyordu)
  let bekle = 0; const AYAR = {childList: true, subtree: true};
  const gozcu = new MutationObserver(() => { clearTimeout(bekle); bekle = setTimeout(() => { gozcu.disconnect(); try{ sayfaSusle(); }finally{ gozcu.takeRecords(); gozcu.observe(mainEl, AYAR); } }, 30); });
  gozcu.observe(mainEl, AYAR);
}

setInterval(() => { if (document.hidden || !S.o) return; const a = document.querySelector('[data-orucsure]'); if (!a) return; const m = orucMetin(); a.textContent = m.sure; const b = document.querySelector('[data-orucalt]'); if (b) b.textContent = m.alt; }, 60000);
window.bugunCiz = function(){
  const o = S.o, m = $('#main');
  const {h, N} = anaHtml();
  m.innerHTML = h;
  $$('.btn.ana', m).forEach(x => { if (!x.closest('.an-simdi, .an-oz, .an-yem')) x.classList.remove('ana'); });   // birincil düğme yalnız ilk ekranda
  durgunBagla(m); haftaHalkaBagla(m); modulBagla(m); telKartYukle(); ilkBagla(m); agriTakipBagla(m); orucBagla(m); bjjSoruBagla(m); bugunBagla(m); selamBagla(m);
  hikayeBagla(m); if (typeof oneriBagla === 'function') oneriBagla(m); hizliFotoBagla(m); kontrolBagla(m); if (typeof sohbetBagla === 'function') sohbetBagla(m);
  gsBagla(m); suBagla(m); if (typeof kocBagla === 'function') kocBagla(m); seriBagla(m); yeniBagla(m);
  $$('[data-sekme]', m).forEach(x => x.onclick = () => { S.sek = 'plan'; S.alt = 'program'; store.set('pt_sek', 'plan'); store.set('pt_alt', 'program'); window.scrollTo(0, 0); ciz(); });
  $$('[data-tikla]', m).forEach(x => x.onclick = () => { const h = $(`[data-ayakic] ${x.dataset.tikla}`, m); if (h) h.click(); });
  $$('[data-nasil]', m).forEach(x => x.onclick = nasilSayfa);
  document.body.classList.toggle('an-haftada', (ss.get('pt_ansek') || 'bugun') === 'hafta');
  const sekAc = k => { ss.set('pt_ansek', k); document.body.classList.toggle('an-haftada', k === 'hafta'); $$('[data-ansek]', m).forEach(y => { y.classList.toggle('on', y.dataset.ansek === k); y.setAttribute('aria-selected', y.dataset.ansek === k); }); $$('[data-anp]', m).forEach(d => d.hidden = d.dataset.anp !== k); window.scrollTo(0, 0); };
  $$('[data-ansek]', m).forEach(x => x.onclick = () => sekAc(x.dataset.ansek));
  $$('[data-ansekgit]', m).forEach(x => x.onclick = () => { sekAc(x.dataset.ansekgit); if (x.dataset.ayakgit){ const a = $(`[data-ayak="${x.dataset.ayakgit}"]`, m); if (a) a.click(); } });
  $$('[data-hareket]', m).forEach(x => x.onclick = () => window.hareketSayfa());
  $$('[data-yo]', m).forEach(x => x.onclick = async () => { const bozar = x.dataset.boz !== '1';
    try{ await api('/api/pt/yemek/oruc', json({tarih: bugunT(), id: x.dataset.yo, bozar})); toast(bozar ? 'Bu kayıt orucu bitirdi.' : 'Orucunuz sürüyor.'); yukle(); }catch(e){ toast(e.message); } });
  $$('[data-ysil]', m).forEach(x => x.onclick = async () => { try{ await fetch(`/api/pt/yemek/${bugunT()}/${x.dataset.ysil}`, {method: 'DELETE'}); toast('Kaldırıldı.'); yukle(); }catch(e){ toast(e.message); } });
  $$('[data-ayak]', m).forEach(x => x.onclick = () => {
    const k = x.dataset.ayak; ss.set('pt_ayak', k);
    $$('[data-ayak]', m).forEach(y => { y.classList.toggle('on', y === x); y.setAttribute('aria-selected', y === x); });
    $$('[data-ayakic]', m).forEach(d => d.hidden = d.dataset.ayakic !== k);
    const db = $('.an-dbas', m); db.querySelector('.an-dik').innerHTML = AYAK[k].ikon; db.querySelector('.an-dik').style.color = AYAK[k].renk;
    db.querySelector('h2').textContent = AYAK[k].ad; db.querySelector('p').textContent = AYAK[k].neden;
    $('.an-detay', m).scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
  });
  (o.bugun.seanslar || []).forEach(s => (s.bolumler || []).length && !s.bitti && sesHazirla(s));
  const ss2 = ((o.ilk || {}).simdi || {}).seans; if ((o.ilk || {}).aktif && ss2) sesHazirla(ss2);
  if (!ls.get('pt_nasil') && o.kurulu) setTimeout(() => { if (!$('.perde')) nasilSayfa(); }, 900);
};
})();

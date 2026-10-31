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
  const L = (b.seanslar || []).filter(s => s.tur !== 'dinlenme');
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
  if ((o.tarama || {}).bekliyor) return {ayak: 'hareket', baslik: 'Önce doktorunuzla konuşun', neden: 'Sağlık sorularından birine "evet" dediniz. Onay alınca plan başlar.', dugme: '<button class="btn ana genis" data-doktor>Doktorumla konuştum, onay aldım</button>'};
  if ((o.calisan || {}).plan) return {ayak: 'hareket', baslik: 'Haftanızı yazıyorum', neden: 'Bir iki dakika sürer. Bu sırada sabah sorularını cevaplayabilirsiniz.', dugme: (b.sabah || {}).isik ? '' : '<button class="btn ana genis" data-sabah>Sabah kontrolü · 30 sn</button>'};
  if (!(b.sabah || {}).isik && s < 15) return {ayak: 'toparlanma', baslik: 'Bugün nasılsınız?', neden: 'Uyku, enerji ve ağrı. Yarım dakika; cevaba göre bugünkü antrenmanı hafifletir ya da olduğu gibi bırakırım.', dugme: '<button class="btn ana genis" data-sabah>Sabah kontrolüne başla</button>'};
  const h = D.hareket;
  if (h.seans && h.seans.ilk) return {ayak: 'hareket', baslik: h.seans.ad, neden: 'İlk haftanızın bugünkü adımı. Ölçtükçe program size göre şekillenir.', dugme: `<button class="btn ana genis" data-tikla="[data-ilkbasla]">Başla · ${h.seans.dk} dk</button>`};
  if (h.seans && s < 22){
    const x = h.seans, sec = x.tur === 'test' ? '[data-test]' : x.tur === 'bjj_ders' ? `[data-bjj="${x.id}"]` : (x.bolumler || []).length ? `[data-basla="${x.id}"]` : `[data-yaptim="${x.id}"]`;
    const ad = x.tur === 'bjj_ders' ? 'Dersi kaydet' : (x.bolumler || []).length || x.tur === 'test' ? `Başla${x.sure_dk ? ' · ' + x.sure_dk + ' dk' : ''}` : 'Yaptım';
    return {ayak: 'hareket', baslik: x.baslik || 'Bugünkü antrenman', neden: x.neden || x.aciklama || 'Bugünün hareket işi bu. Bitirince haftalık güç ve kardiyo halkalarınız dolar.', dugme: `<button class="btn ana genis" data-tikla='${sec}'>${ad}</button>`};
  }
  if (pen.durum === 'acik' && !(b.yemekler || []).length) return {ayak: 'beslenme', baslik: 'Yeme saatindesiniz', neden: `Pencere ${pen.kapanis}'de kapanıyor. Ne yediğinizi fotoğrafla ya da yazarak ekleyin; protein ve kaloriyi ben hesaplarım.`, dugme: `<div class="satir" style="gap:8px;flex-wrap:nowrap">${typeof hizliFotoHtml === 'function' ? hizliFotoHtml('btn ana').replace('class="', 'style="flex:1" class="') : ''}<button class="btn" data-yemek>Yazarak</button></div>`};
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
  let h = `<section class="an-ust"><p class="mono">${esc(tar)}</p><h1 class="bas">${selam}${p.ad ? ', ' + esc(p.ad.split(' ')[0]) : ''}.</h1>
    <p class="an-amac">Health, uzun ve sağlıklı yaşamanız için her gün <b>üç işi</b> takip eder. Bugün <b>${biten}/3</b> tamam. <button class="metin" data-nasil>Nasıl çalışır?</button></p>
    <div class="an-uc" role="tablist">${Object.entries(AYAK).map(([k, a]) => `<button class="an-ayak ${k === sec ? 'on' : ''} ${D[k].tamam ? 'tamam' : ''}" role="tab" aria-selected="${k === sec}" data-ayak="${k}">
      ${halka(D[k].oran, a.renk, a.ikon, D[k].tamam)}<b>${a.ad}</b><small>${esc(D[k].satir)}</small></button>`).join('')}</div></section>`;
  h += `<section class="kart an-simdi ${N.tamam ? 'tamam' : ''}" style="--ar:${AYAK[N.ayak].renk}"><div class="an-sb"><span class="an-nok"></span><span class="mono">${N.tamam ? 'Durum' : 'Şimdi'} · ${AYAK[N.ayak].ad}</span></div>
    <h2>${esc(N.baslik)}</h2>${N.neden ? `<p>${esc(N.neden)}</p>` : ''}${N.dugme || ''}</section>`;
  h += (typeof selamKart === 'function' ? selamKart() : '');
  h += kutlamaKart() + durgunKart() + agriTakipKart();          // acil olanlar (kutlama, uzun ara, dünkü ağrı) Şimdi'nin hemen altında
  h += `<section class="an-detay"><div class="an-dbas"><span class="an-dik" style="color:${AYAK[sec].renk}">${AYAK[sec].ikon}</span><div><h2>${AYAK[sec].ad}</h2><p>${esc(AYAK[sec].neden)}</p></div></div>
    ${Object.keys(AYAK).map(k => `<div data-ayakic="${k}" ${k === sec ? '' : 'hidden'}>${ayakDetay(k)}</div>`).join('')}</section>`;
  const y = o.oyun, seriVar = y && (y.seri || y.en_uzun || (y.bugun || {}).durum === 'tamam' || ((y.puan || {}).toplam || 0) > 0);
  h += `<h2 class="an-bolum">Haftanız <span>Uzun ömrün asıl ölçüsü günler değil, haftalar.</span></h2>`;
  h += haftaHalka(true) + (seriVar ? puanSerit() : '') + hikayeKart() + hedefKart(true) + (o.oyun ? gorevKart() : '');
  const notlar = [degerlendirmeKart(), receteKart(), araKontrolKart(), kontrolKart(), haftalikKart(),
    o.mesaj && o.mesaj.hafta && Date.now() / 1000 - o.mesaj.zaman < 4 * 86400 ? `<div class="kart"><div class="kbas"><h3>Haftalık mesajınız</h3><span class="mono">${esc(haftaYazi(o.mesaj.hafta))}</span></div><p class="gri2" style="margin:0 0 6px;font-size:14px">${esc(o.mesaj.degisecek || '')}</p><button class="metin" data-mesaj>Oku</button></div>` : '',
    o.oyun ? oneriKart() : '', araSoruKart(), aliskanlikKart(), tanismaKart()].filter(Boolean);
  if (notlar.length) h += `<h2 class="an-bolum">Health'ten <span>Sizi tanıdıkça programı nasıl değiştirdiğim.</span></h2>` + notlar.slice(0, 2).join('')
    + (notlar.length > 2 ? `<details class="an-daha"><summary>${notlar.length - 2} not daha</summary>${notlar.slice(2).join('')}</details>` : '');
  h += '<div id="telKart"></div>';
  return {h, N};
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

window.bugunCiz = function(){
  const o = S.o, m = $('#main');
  const {h, N} = anaHtml();
  m.innerHTML = h;
  $$('.btn.ana', m).forEach((x, i) => { if (i && !x.closest('.an-simdi')) x.classList.remove('ana'); });   // tek birincil: Şimdi kartınınki
  durgunBagla(m); haftaHalkaBagla(m); modulBagla(m); telKartYukle(); ilkBagla(m); agriTakipBagla(m); orucBagla(m); bjjSoruBagla(m); bugunBagla(m); selamBagla(m);
  hikayeBagla(m); if (typeof oneriBagla === 'function') oneriBagla(m); hizliFotoBagla(m); kontrolBagla(m); if (typeof sohbetBagla === 'function') sohbetBagla(m);
  suBagla(m); if (typeof kocBagla === 'function') kocBagla(m); seriBagla(m); yeniBagla(m);
  $$('[data-sekme]', m).forEach(x => x.onclick = () => { S.sek = 'plan'; S.alt = 'program'; store.set('pt_sek', 'plan'); store.set('pt_alt', 'program'); window.scrollTo(0, 0); ciz(); });
  $$('[data-tikla]', m).forEach(x => x.onclick = () => { const h = $(`[data-ayakic] ${x.dataset.tikla}`, m); if (h) h.click(); });
  $$('[data-nasil]', m).forEach(x => x.onclick = nasilSayfa);
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

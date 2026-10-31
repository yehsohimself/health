/* pt_gorsel.js — Health'in görsel katmanı (2026-10-31; kullanıcı: "doğru, anlatımı netleştiren, güzel görselleştirme; bizim görsel dünyamıza
   uygun hareketli görüntüler; beni programımı yaptırmaya itmeli").
   İlke: her görsel bir bilgiyi yazıdan daha net söyler, süs değildir. Dil tanıtım filmlerininki: koyu zemin, ince çizgi, limon yeşili tek vurgu,
   küçük mono etiket, akan noktalı çizgi. Çöp adam yok; hareketler storyboard fotoğraflarıyla (pt_medya/<kod>/k1-3) canlanır.
   pt.html'e dokunmadan çalışır: oradaki işlevleri sarar (window.ad = …) ve çizilen sayfayı zenginleştirir. Bir işlev adı değişirse o parça sessizce atlanır.
   - Bugün: seans haritası (hareketlerin canlı kareleri + bölüm şeridi + "bitirince" halkası), ilk hafta yolu
   - Antrenman: haftanın şeridi, açılan günde hareket kareleri; hareket kartında basamak merdiveni
   - Oynatıcı: parçalı ilerleme, geri sayım halkası, dinlenmede nefes halkası, tekrar halkası
   - Seans sonu: halka + sayılar + haftanın noktaları
   - Beslenme: iç içe halkalar (kalori, protein, lif) ve kalorinin dağılımı
   - İlerleme: son sekiz haftanın antrenman dakikası
   Hareket azaltma tercihinde animasyon yok, sayılar doğrudan son değerde. */
(() => {
'use strict';
const AZ = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const q = (s, k = document) => k.querySelector(s), qa = (s, k = document) => [...k.querySelectorAll(s)];
const kacis = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const KAT = k => (typeof kat === 'function' ? kat(k) : {ad: k, kod: k});
const VERI = () => (typeof S !== 'undefined' && S) || {};
const TIK_SVG = '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.2 4.2L19 7"/></svg>';
const GUNK = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'];

/* sar: pt.html'deki genel işlevi sarar; sonra(dönüş, argümanlar) çizimden sonra çalışır. dönüş metinse dönüştürebilir. */
function sar(ad, sonra, {metin} = {}){
  const f = window[ad]; if (typeof f !== 'function' || f.__pg) return;
  const y = function(...a){
    const r = f.apply(this, a);
    if (r && typeof r.then === 'function') return r.then(v => { try{ sonra(v, a); }catch(e){ console.warn('pt_gorsel', ad, e); } return v; });
    if (metin){ try{ const d = sonra(r, a); return d == null ? r : d; }catch(e){ console.warn('pt_gorsel', ad, e); return r; } }
    try{ sonra(r, a); }catch(e){ console.warn('pt_gorsel', ad, e); }
    return r;
  };
  y.__pg = true; window[ad] = y;
}
/* sayı sayarak yükselir (hareket azaltmada doğrudan) */
function say(el, hedef, ms = 900, bicim = v => String(Math.round(v))){
  if (!el) return; if (AZ() || !hedef){ el.textContent = bicim(hedef); return; }
  const bas = performance.now(); const adim = t => { const x = Math.min(1, (t - bas) / ms), e = 1 - Math.pow(1 - x, 3); el.textContent = bicim(hedef * e); if (x < 1 && el.isConnected) requestAnimationFrame(adim); };
  requestAnimationFrame(adim);
}
/* halka: SVG daire; oran 0-1, CSS --c ile dolma animasyonu */
function halka({r, sw, oran, sinif = '', iz = true, cx = r + sw, renk}){
  const c = 2 * Math.PI * r, o = Math.max(0, Math.min(1, oran || 0));
  return `${iz ? `<circle class="pg-iz0" cx="${cx}" cy="${cx}" r="${r}" stroke-width="${sw}"/>` : ''}<circle class="pg-dol ${sinif}" cx="${cx}" cy="${cx}" r="${r}" stroke-width="${sw}" ${renk ? `style="stroke:${renk}"` : ''}
    stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c * (1 - o)).toFixed(1)}" transform="rotate(-90 ${cx} ${cx})" data-c="${c.toFixed(1)}" data-o="${o}"/>`;
}
/* yeni çizilen halkalar boştan dolar */
function halkalariDoldur(k){
  qa('circle.pg-dol:not(.pg-hazir)', k).forEach(c => { c.classList.add('pg-hazir'); if (AZ()) return;
    const hedef = c.getAttribute('stroke-dashoffset'); c.style.transition = 'none'; c.setAttribute('stroke-dashoffset', c.dataset.c);
    requestAnimationFrame(() => requestAnimationFrame(() => { c.style.transition = ''; c.setAttribute('stroke-dashoffset', hedef); })); });
}

/* ---------------------------------------------------------------- canlı kare: storyboard kareleri yavaşça birbirine geçer */
function kareHtml(kod, sinif = ''){
  const k = KAT(kod), K = (k.kareler || []).map(x => x.k).filter(Boolean);
  const L = K.length ? K : k.kapak ? [k.kapak] : [];
  if (!L.length) return `<span class="pg-kare bos ${sinif}"><svg viewBox="0 0 24 24"><path d="M4 16l4-4 3 3 5-6 4 5"/></svg></span>`;
  return `<span class="pg-kare ${sinif}" data-pgk="0">${L.map((u, i) => `<img src="${kacis(u)}" alt="" loading="lazy" class="${i ? '' : 'on'}">`).join('')}</span>`;
}
let kareSira = 0;
setInterval(() => {
  if (AZ() || document.hidden) return; kareSira++;
  qa('.pg-kare[data-pgk]').forEach((e, j) => { const I = e.querySelectorAll('img'); if (I.length < 2) return;
    if ((kareSira + j) % 2) return;                                             // komşular aynı anda değişmesin
    const n = (+e.dataset.pgk + 1) % I.length; e.dataset.pgk = n; I.forEach((im, i) => im.classList.toggle('on', i === n)); });
}, 1100);

/* ---------------------------------------------------------------- seans haritası (Bugün'deki seans kartı) */
function bolumSureleri(s){
  if (typeof adimlar !== 'function') return [];
  const m = new Map();
  adimlar(s).forEach(a => { const sn = a.sn || (a.olcu === 'tekrar' ? Math.min(60, (+String(a.hedef || '').split('-').pop() || 8) * 3.2) : 15);
    m.set(a.bolum || 'Bölüm', (m.get(a.bolum || 'Bölüm') || 0) + sn); });
  return [...m].map(([ad, sn]) => ({ad, sn}));
}
function hedefYazi(b, h){
  if (['tur', 'tabata', 'emom'].includes(b.bicim)) return `${h.sure_sn || b.calisma_sn || (b.bicim === 'tabata' ? 20 : 40)} sn`;
  if (typeof hedefMetni === 'function'){ const m = hedefMetni(h); if (m) return m; }
  return h.sure_sn ? `${h.sure_sn} sn` : h.tekrar ? `${h.tekrar} tekrar` : '';
}
function seansHaritasi(s, {bitirince = true} = {}){
  if (!s || !(s.bolumler || []).length) return '';
  const hs = []; s.bolumler.forEach(b => (b.hareketler || []).forEach(h => { if (!hs.find(x => x.h.kod === h.kod)) hs.push({b, h}); }));
  const film = `<div class="pg-film" role="list">${hs.map(({b, h}) => `<button class="pg-fk" data-hk="${kacis(h.kod)}" role="listitem">${kareHtml(h.kod)}<b>${kacis(KAT(h.kod).ad)}</b><small>${kacis(hedefYazi(b, h))}</small></button>`).join('')}</div>`;
  const P = bolumSureleri(s), top = P.reduce((a, x) => a + x.sn, 0) || 1;
  const serit = P.length ? `<div class="pg-serit" aria-hidden="true"><div class="pg-serit-bar">${P.map((p, i) => `<i class="${/ana|kuvvet|bölüm|devre|akış|tur/i.test(p.ad) || (P.length > 2 && i > 0 && i < P.length - 1) ? 'ana' : ''}" style="flex:${Math.max(p.sn, top * .16).toFixed(0)}"></i>`).join('')}<b class="pg-isik"></b></div>
    <div class="pg-serit-et">${P.map(p => `<span style="flex:${Math.max(p.sn, top * .16).toFixed(0)}">${kacis(p.ad)} · ${Math.max(1, Math.round(p.sn / 60))} dk</span>`).join('')}</div></div>` : '';
  return `<div class="pg-harita">${film}${serit}${bitirince && !s.bitti ? bitirinceHtml(s) : ''}</div>`;
}
/* "Bitirince": haftalık halkanın bugünkü hali ve seans bitince geleceği yer; seri başlar ya da uzar. Baskı değil, ne kazanılacağının resmi. */
function bitirinceHtml(s){
  const y = VERI().o && VERI().o.oyun; if (!y) return '';
  const H = y.halka || {}, hedef = H.hedef_dk || 0, dk = H.dk || 0, ek = s.sure_dk || 0;
  if (!hedef || !ek) return '';
  const once = Math.min(1, dk / hedef), sonra = Math.min(1, (dk + ek) / hedef), r = 15, sw = 4, c = 2 * Math.PI * r;
  const bugunTamam = (y.bugun || {}).durum === 'tamam';
  const seri = bugunTamam ? '' : !y.seri ? 'seriniz başlar' : `seriniz ${y.seri + 1} gün olur`;
  return `<div class="pg-sonra"><svg viewBox="0 0 38 38" aria-hidden="true"><circle class="pg-iz0" cx="19" cy="19" r="${r}" stroke-width="${sw}"/>
      <circle class="pg-sonra-yeni" cx="19" cy="19" r="${r}" stroke-width="${sw}" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c * (1 - sonra)).toFixed(1)}" transform="rotate(-90 19 19)"/>
      <circle class="pg-sonra-eski" cx="19" cy="19" r="${r}" stroke-width="${sw}" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${(c * (1 - once)).toFixed(1)}" transform="rotate(-90 19 19)"/></svg>
    <span>Bitirince haftalık halkanız <b>%${Math.round(once * 100)} → %${Math.round(sonra * 100)}</b>${seri ? `, ${seri}` : ''}.</span></div>`;
}
sar('hareketSiri', (eski, [s]) => seansHaritasi(s) || eski, {metin: true});

/* ---------------------------------------------------------------- ilk hafta yolu: yedi düğüm, akan çizgi, bugünün adımı nabız atar */
function ilkYolHtml(il){
  const A = il.adimlar || []; if (!A.length) return '';
  const kalanDk = A.filter(a => a.durum !== 'tamam').reduce((t, a) => t + (a.dk || 0), 0);
  return `<div class="pg-yol" style="--n:${A.length}">${A.map((a, i) => `${i ? `<i class="pg-yc ${A[i - 1].durum === 'tamam' ? 'dolu' : ''} ${a.durum === 'simdi' && A[i - 1].durum === 'tamam' ? 'akan' : ''}"></i>` : ''}<span class="pg-yd ${kacis(a.durum)}" title="${kacis(a.ad)} · ${a.dk} dk"><em>${a.durum === 'tamam' ? TIK_SVG : i + 1}</em></span>`).join('')}</div>
    <div class="pg-yol-et"><span>${A.filter(a => a.durum === 'tamam').length} / ${A.length} adım</span><span>${kalanDk} dk kaldı</span></div>`;
}
function testFilm(il){
  const t = (il.simdi || {}).testler || ((il.adimlar || []).find(a => a.durum === 'simdi') || {}).testler || [];
  const T = ((VERI().kat || {}).testler || []);
  const L = t.map(k => T.find(x => x[0] === k)).filter(x => x && x[3]);
  if (!L.length) return '';
  return `<div class="pg-harita"><div class="pg-film">${L.map(x => `<button class="pg-fk" data-hk="${kacis(x[3])}">${kareHtml(x[3])}<b>${kacis(x[1])}</b><small>${x[2] === 'sure' ? 'süre' : x[2] === 'tekrar' ? 'tekrar' : 'seçim'}</small></button>`).join('')}</div></div>`;
}
sar('ilkKart', h => {
  const il = (VERI().o || {}).ilk || {}; if (!il.aktif || !h) return h;
  h = h.replace(/<div class="ilknok">[\s\S]*?<\/div>/, ilkYolHtml(il));
  if (!il.bugun_tamam){ const on = il.simdi && il.simdi.seans ? seansHaritasi(il.simdi.seans, {bitirince: true}) : testFilm(il) + bitirinceHtml({sure_dk: (il.simdi || {}).dk});
    if (on) h = h.replace('<button class="btn ana genis" data-ilkbasla', on + '<button class="btn ana genis" data-ilkbasla'); }
  return h;
}, {metin: true});

/* ---------------------------------------------------------------- Antrenman: haftanın şeridi */
const TUR_RENK = {kalistenik: 'var(--vurgu)', guc: 'var(--vurgu)', asgari: 'var(--vurgu)', hizli: 'var(--vurgu)', kardiyo: 'var(--mavi)', bisiklet: 'var(--mavi)',
  mobilite: 'var(--sari)', flow: 'var(--sari)', esneme: 'var(--sari)', bjj: 'var(--turuncu)', bjj_ders: 'var(--turuncu)', bjj_solo: 'var(--turuncu)', test: 'var(--ink2)'};
function haftaSeridi(r){
  const gunler = ((r || {}).program || {}).gunler || []; if (!gunler.length) return '';
  const bug = typeof bugunT === 'function' ? bugunT() : '', H = Object.fromEntries((((VERI().o || {}).oyun || {}).hafta || []).map(x => [x.tarih, x.durum]));
  const mx = Math.max(30, ...gunler.map(g => g.sure_dk || 0));
  const toplam = gunler.filter(g => g.tur !== 'dinlenme'), dk = toplam.reduce((a, g) => a + (g.sure_dk || 0), 0);
  const bitti = toplam.filter(g => g.bitti || H[g.tarih] === 'tamam').length;
  return `<div class="kart pg-hs-kart"><div class="pg-hs">${gunler.map((g, i) => { const d = new Date(g.tarih + 'T12:00'), dinlen = g.tur === 'dinlenme';
      const tamam = g.bitti || (!dinlen && H[g.tarih] === 'tamam'), gecti = g.tarih < bug && !tamam, bugun = g.tarih === bug;
      const yuk = dinlen ? 10 : Math.max(24, Math.round((g.sure_dk || 10) / mx * 100));
      return `<button class="pg-hs-g ${dinlen ? 'dinlen' : ''} ${tamam ? 'tamam' : ''} ${gecti && !dinlen ? 'kacti' : ''} ${bugun ? 'bugun' : ''}" data-pghs="${kacis(g.id || '')}" style="--i:${i};--h:${yuk}%;--r:${TUR_RENK[g.tur] || 'var(--vurgu)'}" title="${kacis(g.baslik || '')}">
        <small>${GUNK[(d.getDay() + 6) % 7]}</small><span class="pg-hs-bar"><i>${tamam ? TIK_SVG : ''}</i></span><b>${d.getDate()}</b><em>${dinlen ? 'dinlen' : (g.sure_dk || '') + (g.sure_dk ? ' dk' : '')}</em></button>`; }).join('')}</div>
    <div class="pg-hs-alt"><span>${toplam.length} antrenman · ${dk} dk</span><span>${bitti ? `<b>${bitti}</b> bitti` : 'Henüz biten yok'}</span></div></div>`;
}
sar('planCiz', async (_, [hafta]) => {
  const m = q('#main'), kart = m && q('.hafta', m) && q('.hafta', m).closest('.kart'); if (!kart || q('.pg-hs-kart', m)) return;
  let r = null;
  if (!hafta){ try{ r = JSON.parse(localStorage.getItem('pt_plan') || 'null'); }catch(e){ r = null; } }
  if (!r){ try{ r = await api('/api/pt/program' + (hafta ? '?hafta=' + hafta : '')); }catch(e){ return; } }
  if (!kart.isConnected) return;
  kart.insertAdjacentHTML('beforebegin', haftaSeridi(r));
  qa('[data-pghs]', m).forEach(b => b.onclick = () => { const g = q(`.hgun[data-id="${CSS.escape(b.dataset.pghs)}"]`, m); if (!g) return;
    if (q('.hacik', g) && q('.hacik', g).classList.contains('hidden')) g.click(); g.scrollIntoView({behavior: AZ() ? 'auto' : 'smooth', block: 'center'}); });
});
/* açılan günde hareketlerin kareleri: satır adından katalog koduna */
function adKod(){ const K = (VERI().kat || {}).katalog || {}; const m = {}; Object.values(K).forEach(k => { if (k.ad) m[k.ad] = k.kod; }); return m; }
document.addEventListener('click', e => {
  const g = e.target.closest && e.target.closest('.hgun'); if (!g) return;
  setTimeout(() => { const M = adKod(); qa('.hacik .hsatir:not([data-pg])', g).forEach(r => { r.dataset.pg = 1; const ad = (r.firstElementChild || {}).textContent, kod = M[ad];
    if (!kod) return; r.dataset.hk = kod; r.classList.add('pg-hsatir'); r.insertAdjacentHTML('afterbegin', kareHtml(kod, 'mini')); }); }, 0);
});

/* ---------------------------------------------------------------- hareket kartı: basamak merdiveni */
sar('hareketKart', (_, [kod, ops]) => {
  const k = KAT(kod), K = (VERI().kat || {}).katalog || {}; if (!k.zincir) return;
  const L = Object.values(K).filter(x => x.zincir === k.zincir && x.basamak != null).sort((a, b) => a.basamak - b.basamak);
  if (L.length < 3) return;
  const sayfalar = qa('.perde'), p = sayfalar[sayfalar.length - 1]; if (!p) return;
  const yer = q('.komsu', p); if (!yer || q('.pg-mer', p)) return;
  const ak = L.findIndex(x => x.aktif), bu = L.findIndex(x => x.kod === kod);
  const html = `<div class="pg-mer" style="--n:${L.length}">${L.map((x, i) => `<button class="pg-mb ${i === bu ? 'bu' : ''} ${ak >= 0 && i < ak ? 'gecti' : ''} ${i === ak ? 'siz' : ''}" data-pgmer="${kacis(x.kod)}" style="--i:${i};--h:${Math.round(48 + i / (L.length - 1) * 66)}px">
      ${i === ak ? '<em>Siz</em>' : ''}<span class="pg-mb-s">${((x.kareler || [])[0] || {}).k ? `<img src="${kacis(x.kareler[0].k)}" alt="" loading="lazy">` : ''}</span><small>${kacis(x.ad)}</small></button>`).join('')}</div>
    <div class="pg-mer-et"><span>← Daha kolay</span><span>${ak >= 0 ? `Şu anki basamağınız: ${kacis(L[ak].ad)}` : `${L.length} basamak`}</span><span>Daha zor →</span></div>`;
  yer.insertAdjacentHTML('beforebegin', html); yer.classList.add('hidden');
  qa('[data-pgmer]', p).forEach(b => b.onclick = () => { if (b.dataset.pgmer === kod) return; p.remove(); hareketKart(b.dataset.pgmer, ops || {}); });
  const m = q('.pg-mer', p), b0 = q('.pg-mb.bu', m); if (m && b0) m.scrollLeft = Math.max(0, b0.offsetLeft - m.clientWidth / 2 + b0.offsetWidth / 2);
});

/* ---------------------------------------------------------------- oynatıcı */
let oynGozcu = null, oynDongu = 0;
function oynZenginlestir(el){
  if (typeof O === 'undefined' || !O.A) return;
  const a = O.A[O.i]; if (!a) return;
  /* parçalı ilerleme: her çalışma adımı bir parça */
  const cb = q('.cubuk', el);
  if (cb && !cb.classList.contains('pg-cubuk')){
    const C = O.A.map((x, i) => [x, i]).filter(([x]) => x.tip === 'calis');
    cb.classList.add('pg-cubuk');
    cb.innerHTML = C.map(([x, i]) => `<i class="${i < O.i ? 'd' : i === O.i ? 's' : ''}" data-i="${i}"><u></u></i>`).join('') || '<i><u></u></i>';
    const sonraki = O.A.findIndex((x, i) => i > O.i && x.tip === 'calis'), hedef = a.tip === 'calis' ? O.i : sonraki;
    qa('i', cb).forEach(s => { if (+s.dataset.i === hedef && a.tip !== 'calis') s.classList.add('bekle'); });
  }
  /* geri sayım halkası */
  const z = q('.zaman', el);
  if (z && a.sn && !z.closest('.pg-zh')){
    const R = 118, sw = 6, c = 2 * Math.PI * R, kap = document.createElement('div');
    kap.className = 'pg-zh' + (a.tip === 'dinlen' ? ' dinlen' : '');
    kap.innerHTML = `<svg viewBox="0 0 ${2 * (R + sw)} ${2 * (R + sw)}" aria-hidden="true">${a.tip === 'dinlen' ? `<circle class="pg-nefes" cx="${R + sw}" cy="${R + sw}" r="${R - 20}"/>` : ''}<circle class="pg-zh-iz" cx="${R + sw}" cy="${R + sw}" r="${R}" stroke-width="${sw}"/>
      <circle class="pg-zh-dol" cx="${R + sw}" cy="${R + sw}" r="${R}" stroke-width="${sw}" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="0" transform="rotate(-90 ${R + sw} ${R + sw})" data-c="${c}"/></svg>`;
    z.parentNode.insertBefore(kap, z); kap.appendChild(z);
    if (a.tip === 'dinlen') kap.insertAdjacentHTML('beforeend', '<span class="pg-zh-not">nefes alın · verin</span>');
  }
  /* dinlenmede sıradaki hareketin canlı karesi */
  const sr = q('.sonraki', el);
  if (sr && a.sonraki && !q('img, .pg-kare', sr)) sr.insertAdjacentHTML('afterbegin', kareHtml(a.sonraki.h.kod, 'mini'));
  /* tekrar halkası: hedef aralığa göre dolar, her dokunuşta sayı zıplar */
  const ts = q('#tsay', el);
  if (ts && a.olcu === 'tekrar' && !ts.closest('.pg-th')){
    const ust = +String(a.hedef || '').split('-').pop() || 10, alt = +String(a.hedef || '').split('-')[0] || ust;
    const R = 52, sw = 5, c = 2 * Math.PI * R, kap = document.createElement('span'); kap.className = 'pg-th';
    const ac = i => -90 + i / ust * 360;
    kap.innerHTML = `<svg viewBox="0 0 ${2 * (R + sw)} ${2 * (R + sw)}" aria-hidden="true"><circle class="pg-zh-iz" cx="${R + sw}" cy="${R + sw}" r="${R}" stroke-width="${sw}"/>
      <circle class="pg-th-hedef" cx="${R + sw}" cy="${R + sw}" r="${R}" stroke-width="${sw}" stroke-dasharray="${(c * (ust - alt + 1) / ust).toFixed(1)} ${c.toFixed(1)}" transform="rotate(${ac(alt - 1)} ${R + sw} ${R + sw})"/>
      <circle class="pg-th-dol" cx="${R + sw}" cy="${R + sw}" r="${R}" stroke-width="${sw}" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${c.toFixed(1)}" transform="rotate(-90 ${R + sw} ${R + sw})" data-c="${c}" data-ust="${ust}"/></svg>`;
    ts.parentNode.insertBefore(kap, ts); kap.appendChild(ts);
    const guncelle = (zipla) => { const d = q('.pg-th-dol', kap), v = +ts.textContent || 0; d.setAttribute('stroke-dashoffset', (c * (1 - Math.min(1, v / ust))).toFixed(1));
      kap.classList.toggle('hedefte', v >= alt); if (zipla && !AZ()){ ts.classList.remove('pg-zip'); void ts.offsetWidth; ts.classList.add('pg-zip'); } };
    guncelle(false);
    new MutationObserver(() => guncelle(true)).observe(ts, {childList: true, characterData: true, subtree: true});
  }
}
function oynDonguCalis(){
  cancelAnimationFrame(oynDongu);
  const adim = () => {
    const el = q('#oyn'); if (!el || typeof O === 'undefined' || !O.A) return;
    const a = O.A[O.i];
    if (a && a.sn && typeof kalan === 'function'){
      const k = Math.max(0, kalan() || 0), oran = Math.min(1, Math.max(0, k / a.sn));
      const d = q('.pg-zh-dol', el); if (d) d.setAttribute('stroke-dashoffset', (+d.dataset.c * (1 - oran)).toFixed(1));
      const s = q('.pg-cubuk i.s u', el); if (s) s.style.width = ((1 - oran) * 100).toFixed(1) + '%';
      const zh = q('.pg-zh', el); if (zh) zh.classList.toggle('son', k <= 3.2 && k > 0);
    }
    oynDongu = requestAnimationFrame(adim);
  };
  oynDongu = requestAnimationFrame(adim);
}
new MutationObserver(() => {
  const el = q('#oyn');
  if (el && !el.__pg){ el.__pg = true; oynGozcu = new MutationObserver(() => oynZenginlestir(el)); oynGozcu.observe(el, {childList: true}); oynZenginlestir(el); oynDonguCalis(); }
  if (!el && oynGozcu){ oynGozcu.disconnect(); oynGozcu = null; cancelAnimationFrame(oynDongu); }
}).observe(document.body, {childList: true});

/* ---------------------------------------------------------------- seans sonu */
sar('bitir', (_, [yarim]) => {
  if (typeof O === 'undefined' || !O.kayit) return;
  const P = qa('.perde'), p = P[P.length - 1]; if (!p || q('.pg-son', p)) return;
  const h3 = q('.sayfa h3', p); if (!h3) return;
  const R = Object.values(O.kayit), set = R.reduce((t, x) => t + (x.setler || []).length, 0);
  const tekrarli = new Set(O.A.filter(x => x.tip === 'calis' && x.olcu === 'tekrar').map(x => x.h.kod));
  const tekrar = R.filter(x => tekrarli.has(x.kod)).reduce((t, x) => t + (x.setler || []).reduce((a, s) => a + (+s.deger || 0), 0), 0);
  const dk = Math.max(1, Math.round((Date.now() - O.bas) / 60000));
  const calis = O.A.filter(x => x.tip === 'calis').length, yapilan = O.A.slice(0, O.i + 1).filter(x => x.tip === 'calis').length;
  const oran = yarim ? Math.min(1, yapilan / Math.max(1, calis)) : 1;
  const y = ((VERI().o || {}).oyun) || {}, bug = typeof bugunT === 'function' ? bugunT() : '';
  const hafta = (y.hafta || []).map((g, i) => `<span class="${g.durum === 'tamam' ? 'tamam' : ''} ${g.tarih === bug ? 'bugun' : ''}" style="--i:${i}"><i>${g.durum === 'tamam' ? TIK_SVG : ''}</i><small>${GUNK[i]}</small></span>`).join('');
  const r = 46, sw = 7;
  h3.insertAdjacentHTML('afterend', `<div class="pg-son ${yarim ? 'yarim' : ''}">
    <div class="pg-son-h"><svg viewBox="0 0 ${2 * (r + sw)} ${2 * (r + sw)}">${halka({r, sw, oran, sinif: 'pg-son-dol'})}${yarim ? '' : `<path class="pg-son-tik" d="M${r + sw - 17} ${r + sw + 1}l11 11 22-24"/>`}</svg>${yarim ? `<b class="pg-son-yuzde">%${Math.round(oran * 100)}</b>` : ''}</div>
    <div class="pg-son-say"><div><b data-pgsay="${dk}">0</b><small>dakika</small></div><div><b data-pgsay="${R.length}">0</b><small>hareket</small></div><div><b data-pgsay="${set}">0</b><small>set</small></div>${tekrar ? `<div><b data-pgsay="${tekrar}">0</b><small>tekrar</small></div>` : ''}</div>
    ${hafta ? `<div class="pg-son-hafta">${hafta}</div>` : ''}</div>`);
  const ilkP = h3.parentNode.querySelector('.pg-son + p.gri2'); if (ilkP) ilkP.classList.add('hidden');
  halkalariDoldur(p);
  qa('[data-pgsay]', p).forEach((e, i) => setTimeout(() => say(e, +e.dataset.pgsay, 800), AZ() ? 0 : 450 + i * 120));
  if (!yarim) setTimeout(() => { const n = q('.pg-son-hafta span.bugun', p); if (n){ n.classList.add('tamam', 'yeni'); q('i', n).innerHTML = TIK_SVG; } }, AZ() ? 0 : 1100);
});

/* ---------------------------------------------------------------- Beslenme: iç içe halkalar */
sar('beslenmeCiz', () => {
  const o = VERI().o || {}, b = o.beslenme; if (!b) return;
  const h = b.hedef || {}, t = b.toplam || {}, m = q('#main'), iz = m && q('.izgara2', m);
  if (!iz || !h.kcal) return;
  const S3 = [['kcal', 'Kalori', t.kcal || 0, h.kcal, 'kcal', 'var(--vurgu)'], ['protein', 'Protein', t.protein || 0, h.protein, 'g', 'var(--mavi)'], h.lif ? ['lif', 'Lif', t.lif || 0, h.lif, 'g', 'var(--sari)'] : null].filter(Boolean);
  const kalan = Math.max(0, Math.round(h.kcal - (t.kcal || 0))), fazla = (t.kcal || 0) > h.kcal * 1.08;
  const W = 140, sw = 11, gap = 4;
  const svg = `<svg viewBox="0 0 ${W} ${W}" aria-hidden="true">${S3.map((x, i) => { const r = W / 2 - sw / 2 - i * (sw + gap); return halka({r, sw, oran: x[3] ? x[2] / x[3] : 0, cx: W / 2, renk: i === 0 && fazla ? 'var(--turuncu)' : x[5]}); }).join('')}</svg>`;
  const kart = document.createElement('div'); kart.className = 'pg-bes';
  kart.innerHTML = `<div class="pg-bes-h">${svg}<div class="pg-bes-m"><b data-pgsay="${fazla ? Math.round(t.kcal - h.kcal) : kalan}">0</b><small>${fazla ? 'kcal fazla' : 'kcal kaldı'}</small></div></div>
    <div class="pg-bes-l">${S3.map(x => `<div><i style="background:${x[5]}"></i><span>${x[1]}</span><b>${Math.round(x[2])}<small> / ${x[3] || '–'} ${x[4]}</small></b></div>`).join('')}
    ${t.kcal ? (() => { const P = (t.protein || 0) * 4, Y = (t.yag || 0) * 9, K = (t.karb || 0) * 4, T = P + Y + K || 1; return `<div class="pg-mak" title="Kalorinin nereden geldiği"><i style="flex:${P};background:var(--mavi)"></i><i style="flex:${Y};background:var(--turuncu)"></i><i style="flex:${K};background:var(--ink3)"></i></div><div class="pg-mak-et"><span>Protein %${Math.round(P / T * 100)}</span><span>Yağ %${Math.round(Y / T * 100)}</span><span>Karbonhidrat %${Math.round(K / T * 100)}</span></div>`; })() : '<p class="pg-bes-bos">İlk öğünü kaydedince halkalar dolmaya başlar.</p>'}</div>`;
  iz.replaceWith(kart);
  halkalariDoldur(kart); qa('[data-pgsay]', kart).forEach(e => say(e, +e.dataset.pgsay, 900, v => Math.round(v).toLocaleString('tr-TR')));
});

/* ---------------------------------------------------------------- İlerleme: son sekiz hafta */
function haftaBasi(t){ const d = new Date(t + 'T12:00'); d.setDate(d.getDate() - (d.getDay() + 6) % 7); return d.toISOString().slice(0, 10); }
sar('ilerlemeCiz', async () => {
  const m = q('#main'); if (!m || q('.pg-8h', m) || VERI().sek !== 'ilerleme') return;
  const alti = q('p.alti', m); if (!alti) return;
  let r; try{ r = await api('/api/pt/ilerleme'); }catch(e){ return; }
  if (!alti.isConnected) return;
  const T = r.takvim || [], hb = {}; T.forEach(([t, dk]) => { const k = haftaBasi(t); hb[k] = (hb[k] || 0) + (dk || 0); });
  const bu = haftaBasi(typeof bugunT === 'function' ? bugunT() : new Date().toISOString().slice(0, 10)), L = [];
  for (let i = 7; i >= 0; i--){ const d = new Date(bu + 'T12:00'); d.setDate(d.getDate() - i * 7); const k = d.toISOString().slice(0, 10); L.push([k, hb[k] || 0]); }
  const hedef = (((VERI().o || {}).oyun || {}).halka || {}).hedef_dk || 0, mx = Math.max(hedef, 30, ...L.map(x => x[1])) * 1.12;
  const bos = !L.some(x => x[1]), toplam = L.reduce((a, x) => a + x[1], 0);
  const html = `<div class="kart pg-8h"><div class="kbas"><h3>Haftalık antrenman</h3><span class="mono">${bos ? 'son 8 hafta' : `son 8 hafta · ${toplam} dk`}</span></div>
    ${hedef ? `<div class="pg-8h-lej"><i></i>Haftalık hedefiniz ${hedef} dk</div>` : ''}
    <div class="pg-8h-g ${hedef ? 'hedefli' : ''}" style="--hd:${(hedef / mx * 100).toFixed(1)}%">
      ${L.map(([k, dk], i) => { const d = new Date(k + 'T12:00'); return `<div class="pg-8h-s ${k === bu ? 'bu' : ''} ${hedef && dk >= hedef ? 'tam' : ''}" style="--i:${i}"><em>${dk || ''}</em><span class="pg-8h-k"><i style="height:${bos ? 6 + (i % 3) * 3 : Math.max(dk ? 3 : 1.5, dk / mx * 100).toFixed(1)}%"></i></span><small>${k === bu ? 'bu hafta' : d.toLocaleDateString('tr-TR', {day: 'numeric', month: 'short'})}</small></div>`; }).join('')}</div>
    ${bos ? '<p class="pg-bes-bos">İlk antrenmanınızla ilk çubuk yükselir; çizgiye her hafta biraz daha yaklaşırsınız.</p>' : ''}</div>`;
  alti.insertAdjacentHTML('afterend', html);
});

/* ---------------------------------------------------------------- her çizimden sonra yeni halkalar dolsun */
['bugunCiz', 'kocCiz'].forEach(ad => sar(ad, () => halkalariDoldur(q('#main'))));
})();

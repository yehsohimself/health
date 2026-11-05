/* pt_hazir.js — "Ne yedim, ne içtim?" (2026-11-03; kullanıcı: "Ben yediklerimi seçsem. Bir tabak makarna, bir bardak kahve, bir buçuk kahve. Hazır seçenekler bol bol olsa.
   Orucun devam edip etmemesi de benim kontrolümde olsa."). Değerler BLS 4.0'dan (/api/pt/hazir); yapay zekâ çağrılmaz. Listede olmayan için eski yazma/fotoğraf sayfası. */
(() => {
'use strict';
let veri = null;
const kucuk = s => String(s).toLocaleLowerCase('tr');
const adetYaz = a => { const t = Math.floor(a), y = a - t > .01; return t ? `${t}${y ? '½' : ''}` : '½'; };
const kc = (x, a) => Math.round(x.g * a * (x.yuz.kcal || 0) / 100);
const pr = (x, a) => Math.round(x.g * a * (x.yuz.protein || 0) / 10) / 10;

window.hazirSayfa = async function(){
  const p = sayfa(`<h3>Ne yediniz, ne içtiniz?</h3><div class="satir gri"><span class="donen"></span> Liste geliyor</div>`, {sabit: true});
  try{ veri = veri && Date.now() - veri._t < 60000 ? veri : {...await api('/api/pt/hazir'), _t: Date.now()}; }catch(e){ p.kapat(); toast(e.message); return; }
  if (!(veri.yemekler || []).length){ p.kapat(); yemekSayfa(); return; }
  const Y = {}; veri.yemekler.forEach(x => Y[x.kod] = x);
  const sik = (veri.sik || []).filter(k => Y[k]);
  const GR = (sik.length ? [{kod: 'sik', ad: 'Sık seçtikleriniz'}] : []).concat(veri.gruplar);
  const secim = new Map();
  let grup = GR[0].kod, ara = '', zaman = 0, saat = '', orucElle = null;
  const ku = $('.sayfa', p);
  ku.classList.add('hz');
  ku.innerHTML = `<div class="tutac"></div><button class="kapatx" data-kapat aria-label="Kapat">×</button><h3>Ne yediniz, ne içtiniz?</h3>
    <input class="alan hz-ara" id="hzAra" placeholder="Ara: makarna, kahve, döner…" autocomplete="off">
    <div class="hz-gr" id="hzGr">${GR.map(g => `<button data-g="${g.kod}">${esc(g.ad)}</button>`).join('')}</div>
    <div class="hz-l" id="hzL"></div>
    <button class="metin hz-yok" id="hzYok">Listede yok: yazarak ya da fotoğrafla ekleyin</button>
    <div class="hz-tepsi" id="hzT"></div>`;
  $$('[data-kapat]', ku).forEach(b => b.onclick = () => p.kapat());
  const liste = () => {
    const q = kucuk(ara.trim());
    const L = q ? veri.yemekler.filter(x => kucuk(x.ad).includes(q)) : grup === 'sik' ? sik.map(k => Y[k]) : veri.yemekler.filter(x => x.grup === grup);
    $$('#hzGr button', ku).forEach(b => b.classList.toggle('on', !q && b.dataset.g === grup));
    $('#hzL', ku).innerHTML = L.map(x => { const a = secim.get(x.kod);
      return `<div class="hz-s ${a ? 'on' : ''}" data-k="${x.kod}"><button class="hz-e" data-ekle="${x.kod}"><b>${esc(x.ad)}</b><small>1 ${esc(x.birim)} · ${kc(x, 1)} kcal</small></button>
        ${a ? `<span class="hz-ad"><button data-az="${x.kod}" aria-label="Azalt">−</button><b>${adetYaz(a)} ${esc(x.birim)}</b><button data-cok="${x.kod}" aria-label="Artır">+</button></span>` : '<span class="hz-art">+</span>'}</div>`; }).join('') || `<p class="gri2" style="font-size:14px;margin:14px 0">"${esc(ara)}" listede yok. Aşağıdan yazarak ekleyebilirsiniz.</p>`;
    $$('[data-ekle]', ku).forEach(b => b.onclick = () => { const k = b.dataset.ekle; if (secim.has(k)) secim.delete(k); else secim.set(k, 1); ciz(); });
    $$('[data-cok]', ku).forEach(b => b.onclick = () => { secim.set(b.dataset.cok, secim.get(b.dataset.cok) + .5); ciz(); });
    $$('[data-az]', ku).forEach(b => b.onclick = () => { const k = b.dataset.az, a = secim.get(k) - .5; if (a <= 0) secim.delete(k); else secim.set(k, a); ciz(); });
  };
  const kcalTop = () => [...secim].reduce((t, [k, a]) => t + kc(Y[k], a), 0);
  const bozarMi = () => orucElle !== null ? orucElle : kcalTop() >= (veri.oruc_kcal || 15);
  const tepsi = () => { const T = $('#hzT', ku);
    if (!secim.size){ T.innerHTML = ''; T.hidden = true; return; }
    T.hidden = false;
    const prot = [...secim].reduce((t, [k, a]) => t + pr(Y[k], a), 0);
    T.innerHTML = `<p class="hz-oz">${[...secim].map(([k, a]) => `${adetYaz(a)} ${esc(Y[k].birim)} ${esc(kucuk(Y[k].ad))}`).join(', ')}</p>
      <div class="hz-t"><b>${kcalTop()} kcal</b><span>${Math.round(prot)} g protein</span></div>
      <div class="hz-sat"><span>Ne zaman</span><div class="hz-c">${[[0, 'Şimdi'], [30, '30 dk önce'], [60, '1 sa önce'], [120, '2 sa önce']].map(([d, a]) => `<button data-z="${d}" class="${!saat && zaman === d ? 'on' : ''}">${a}</button>`).join('')}<input type="time" id="hzS" value="${saat}" aria-label="Saat seçin"></div></div>
      <div class="hz-sat"><span>Oruç</span><div class="hz-c"><button data-o="0" class="${bozarMi() ? '' : 'on'}">Sürüyor</button><button data-o="1" class="${bozarMi() ? 'on' : ''}">Bitti</button></div></div>
      <button class="btn ana genis" id="hzEkle">Ekle</button>`;
    $$('[data-z]', T).forEach(b => b.onclick = () => { zaman = +b.dataset.z; saat = ''; tepsi(); });
    $('#hzS', T).onchange = e => { saat = e.target.value; tepsi(); };
    $$('[data-o]', T).forEach(b => b.onclick = () => { orucElle = b.dataset.o === '1'; tepsi(); });
    $('#hzEkle', T).onclick = kaydet;
  };
  const ciz = () => { liste(); tepsi(); };
  const kaydet = async () => {
    let t = Math.floor(Date.now() / 1000) - zaman * 60;
    if (saat){ const [a, b] = saat.split(':').map(Number), d = new Date(); d.setHours(a, b, 0, 0); if (d.getTime() > Date.now() + 60000) d.setDate(d.getDate() - 1); t = Math.floor(d.getTime() / 1000); }
    const kalemler = [...secim].map(([k, a]) => { const x = Y[k]; return {ad: `${adetYaz(a)} ${x.birim} ${kucuk(x.ad)}`, hazir: k, adet: a, birim: x.birim, miktar_g: Math.round(x.g * a), yuz: x.yuz, kaynak: x.kaynak, bls: x.bls}; });
    const bozar = bozarMi(), ad = kalemler.slice(0, 3).map(k => k.ad).join(', ') + (kalemler.length > 3 ? ` +${kalemler.length - 3}` : '');
    const yem = {ad, kalemler, t, secim: true, favori: false, kontrol: false};
    if (orucElle !== null) yem.oruc_bozar = orucElle;
    try{ await gonder('/api/pt/yemek', {tarih: bugunT(), yemek: yem}); veri = null; p.kapat(); toast(bozar ? 'Eklendi. Orucunuz bitti.' : 'Eklendi. Orucunuz sürüyor.'); yukle(); }catch(e){ toast(e.message); }
  };
  $$('#hzGr button', ku).forEach(b => b.onclick = () => { grup = b.dataset.g; ara = ''; $('#hzAra', ku).value = ''; liste(); $('#hzL', ku).scrollTop = 0; });
  $('#hzAra', ku).oninput = e => { ara = e.target.value; liste(); };
  $('#hzYok', ku).onclick = () => { p.kapat(); yemekSayfa(); };
  ciz();
};

/* "Yaptığımı ekle" (2026-11-03; kullanıcı: "Harekette de 'yürüyüş yaptım' gibi seçenekler. Köpek gezdirme, 45 dk gibi seçebilmeliyim. Apple Health'ten de onları matchleyebilirsin.")
   Yapay zekâ çağrılmaz. Telefonun ölçtüğü yürüyüş üstte: dokununca doldurulmuş gelir; seçilen kayıt zamanla eşleşir, aynı yürüyüş iki kez sayılmaz. */
const EFOR = [[3, 'Rahat'], [5, 'Orta'], [7, 'Zor']];
const efor = z => z >= 7 ? 7 : z >= 5 ? 5 : 3;
const saatYaz = t => new Date(t * 1000).toLocaleTimeString('tr-TR', {hour: '2-digit', minute: '2-digit'});
window.hareketSayfa = async function(hazir){
  const p = sayfa(`<h3>Ne yaptınız?</h3><div class="satir gri"><span class="donen"></span> Liste geliyor</div>`, {sabit: true});
  let v; try{ v = await api('/api/pt/aktivite'); }catch(e){ p.kapat(); toast(e.message); return; }
  const ku = $('.sayfa', p); ku.classList.add('hz');
  let sec = null, dk = 30, zor = 3, zaman = 0, ozel = '', tarih = null;
  const adSec = (a, dk_, z, t) => { sec = a; dk = dk_; zor = efor(z); ozel = t ? new Date(t * 1000 - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16) : ''; zaman = 0; ciz(); requestAnimationFrame(() => { const d = $('#hzHEkle', ku); if (d) d.scrollIntoView({block: 'nearest', behavior: 'smooth'}); }); };
  const ciz = () => {
    const TEL = v.telefon || [];
    ku.innerHTML = `<div class="tutac"></div><button class="kapatx" data-kapat aria-label="Kapat">×</button><h3>Ne yaptınız?</h3>
      ${TEL.length ? `<div class="hz-tel"><b>Telefonun gördükleri</b>${TEL.map((w, i) => `<div class="hz-ts"><span><b>${esc(w.ad)}</b><small>${w.tarih === bugunT() ? 'Bugün' : 'Dün'} ${saatYaz(w.bas)} · ${w.dk} dk · ${w.adim.toLocaleString('tr-TR')} adım</small></span>
        <button class="btn kucuk" data-tok="${i}">Onayla</button><button class="metin sessiz" data-tyok="${i}">Değildi</button></div>`).join('')}</div>` : ''}
      <div class="hz-gr hz-akt">${v.liste.map(a => `<button data-a="${esc(a.ad)}" class="${sec && sec.ad === a.ad ? 'on' : ''}">${esc(a.ad)}</button>`).join('')}</div>
      <input class="alan hz-ara" id="hzOzelAd" placeholder="Listede yoksa yazın: bahçe işi, taşınma…" value="${sec && sec.ozel ? esc(sec.ad) : ''}">
      <div class="hz-tepsi hz-duz" ${sec ? '' : 'hidden'}>
        <div class="hz-sat"><span>Süre</span><div class="hz-c">${[10, 15, 20, 30, 45, 60, 90].map(x => `<button data-d="${x}" class="${dk === x ? 'on' : ''}">${x} dk</button>`).join('')}<input type="number" min="1" max="600" id="hzDk" value="${[10, 15, 20, 30, 45, 60, 90].includes(dk) ? '' : dk}" placeholder="dk" aria-label="Dakika"></div></div>
        <div class="hz-sat"><span>Efor</span><div class="hz-c">${EFOR.map(([z, a]) => `<button data-e="${z}" class="${zor === z ? 'on' : ''}">${a}</button>`).join('')}</div></div>
        <div class="hz-sat"><span>Ne zaman</span><div class="hz-c">${[[0, 'Şimdi bitti'], [60, '1 sa önce'], [180, '3 sa önce']].map(([d, a]) => `<button data-z="${d}" class="${!ozel && zaman === d ? 'on' : ''}">${a}</button>`).join('')}<input type="datetime-local" id="hzZ" value="${ozel}" aria-label="Tarih ve saat"></div></div>
        <button class="btn ana genis" id="hzHEkle">${sec ? esc(sec.ad) + ' · ' + dk + ' dk ekle' : 'Ekle'}</button></div>
      ${(v.elle || []).length ? `<div class="hz-tel"><b>Bugün eklediğiniz</b>${v.elle.map(x => `<div class="hz-ts"><span><b>${esc(x.ad)}</b><small>${x.t ? saatYaz(x.t) + ' · ' : ''}${x.dk} dk</small></span>${x.kaynak === 'elle' ? `<button class="an-ys" data-sil="${esc(x.id)}" aria-label="Kaldır">×</button>` : ''}</div>`).join('')}</div>` : ''}`;
    $$('[data-kapat]', ku).forEach(b => b.onclick = () => p.kapat());
    $$('[data-a]', ku).forEach(b => b.onclick = () => { const a = v.liste.find(x => x.ad === b.dataset.a); adSec(a, a.dk, a.zorluk); });
    const oz = $('#hzOzelAd', ku); oz.onchange = () => { const t = oz.value.trim(); if (t) adSec({ad: t, spor: 'diger', ozel: true}, dk, 5); };
    $$('[data-tok]', ku).forEach(b => b.onclick = () => { const w = TEL[+b.dataset.tok], a = v.liste.find(x => x.ad === w.ad) || {ad: w.ad, spor: 'yuruyus'}; adSec(a, w.dk, 3, w.bit); });
    $$('[data-tyok]', ku).forEach(b => b.onclick = async () => { const w = TEL[+b.dataset.tyok]; await api('/api/pt/yuruyus-gizle', json({tarih: w.tarih, bas: w.bas})); TEL.splice(+b.dataset.tyok, 1); toast('Bu yürüyüş sayılmayacak.'); ciz(); yukle(); });
    $$('[data-d]', ku).forEach(b => b.onclick = () => { dk = +b.dataset.d; ciz(); });
    const dki = $('#hzDk', ku); if (dki) dki.onchange = () => { const x = +dki.value; if (x > 0){ dk = Math.min(600, Math.round(x)); ciz(); } };
    $$('[data-e]', ku).forEach(b => b.onclick = () => { zor = +b.dataset.e; ciz(); });
    $$('[data-z]', ku).forEach(b => b.onclick = () => { zaman = +b.dataset.z; ozel = ''; ciz(); });
    const zi = $('#hzZ', ku); if (zi) zi.onchange = () => { ozel = zi.value; ciz(); };
    const ek = $('#hzHEkle', ku); if (ek) ek.onclick = async () => {
      const t = ozel ? Math.floor(new Date(ozel).getTime() / 1000) : Math.floor(Date.now() / 1000) - zaman * 60;
      try{ await api('/api/pt/aktivite', json({ad: sec.ad, spor: sec.spor, sure_dk: dk, zorluk: zor, t})); p.kapat(); toast(`${sec.ad} eklendi.`); yukle(); }catch(e){ toast(e.message); } };
    $$('[data-sil]', ku).forEach(b => b.onclick = async () => { await fetch(`/api/pt/aktivite/${bugunT()}/${b.dataset.sil}`, {method: 'DELETE'}); v.elle = v.elle.filter(x => x.id !== b.dataset.sil); toast('Kaldırıldı.'); ciz(); yukle(); });
  };
  ciz();
};
})();

/* Yemeğin günü ve saati (2026-11-05; kullanıcı: "bu yemeği bugün değil dün yedim, sonrasında hiç yemedim; bunları sitede de kolayca yapabilmeliyim").
   zamanKutu: Bugün · Dün · Önceki gün + saat + "Bundan sonra bir şey yemedim". oku(): {t: yalnız değiştiyse, son}. */
const gunMetni = o => { const d = new Date(); d.setDate(d.getDate() - o); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
window.zamanKutu = function(el, t0, z = {}){
  const ilk = t0 ? new Date(t0 * 1000) : new Date();
  const yerel = d => new Date(d - d.getTimezoneOffset() * 60000).toISOString();
  z.gun = z.gun || yerel(ilk).slice(0, 10);
  z.saat = z.saat || yerel(ilk).slice(11, 16);
  const ciz = () => {
    el.innerHTML = `<div class="hz-sat hz-zk"><span>Ne zaman</span><div class="hz-c">${[[0, 'Bugün'], [1, 'Dün'], [2, 'Önceki gün']].map(([o, a]) => `<button type="button" data-zg="${gunMetni(o)}" class="${z.gun === gunMetni(o) ? 'on' : ''}">${a}</button>`).join('')}
      <input type="date" data-zt value="${z.gun}" max="${gunMetni(0)}" min="${gunMetni(14)}" aria-label="Tarih"><input type="time" data-zs value="${z.saat}" aria-label="Saat"></div></div>
      <label class="satir hz-son"><input type="checkbox" data-zson ${z.son ? 'checked' : ''}> Bundan sonra bir şey yemedim</label>`;
    $$('[data-zg]', el).forEach(b => b.onclick = () => { z.gun = b.dataset.zg; z.dokundu = true; ciz(); });
    $('[data-zt]', el).onchange = e => { if (e.target.value){ z.gun = e.target.value; z.dokundu = true; ciz(); } };
    $('[data-zs]', el).onchange = e => { if (e.target.value){ z.saat = e.target.value; z.dokundu = true; } };
    $('[data-zson]', el).onchange = e => { z.son = e.target.checked; };
  };
  ciz();
  return {oku: () => ({t: z.dokundu ? Math.floor(new Date(`${z.gun}T${z.saat}`).getTime() / 1000) : null, son: !!z.son})};
};

/* Bir yemeğin ayrıntısı: hedefe göre nasıl, ne zaman yendi, Health'e sor, düzenle, kaldır. */
window.yemekDetay = async function(tarih, id){
  let v; try{ v = await api(`/api/pt/yemek-detay/${tarih}/${id}`); }catch(e){ toast(e.message); return; }
  const y = v.yemek, n = v.nasil; let kod = n.secili;
  const p = sayfa(`<h3>${esc(y.ad || 'Öğün')}</h3>${y.foto ? `<img class="hz-yfoto" src="/pt-yemek-foto/${esc(y.id)}.jpg" alt="">` : ''}
    <p class="gri2 hz-kal">${esc((y.kalemler || []).map(k => k.ad).join(', '))}</p>
    <div class="hz-seg" id="ydSeg"><button data-k="tek">Tek öğünümse</button><button data-k="iki">İki öğünden biriyse</button></div><div id="ydN"></div>
    <h4 class="hz-b">Ne zaman yediniz?</h4><div id="ydZ"></div><div class="satir" style="margin-top:6px"><button class="btn kucuk" id="ydTasi">Saati kaydet</button></div>
    <div class="salt"><button class="btn" id="ydDuz">Gramları düzenle</button><button class="btn" id="ydSor">Health'e sor</button><button class="metin sessiz" id="ydSil">Kaldır</button></div>`);
  const nc = () => { const d = n[kod];
    $$('#ydSeg button', p).forEach(b => b.classList.toggle('on', b.dataset.k === kod));
    $('#ydN', p).innerHTML = `<p class="hz-karar">${esc(d.baslik)}</p><div class="hz-olc">${d.satirlar.map(s => { const a = s.hedef ? Math.min(100, Math.round(s.deger / s.hedef * 100)) : 0, asti = s.ust && s.deger > s.hedef;
      return `<div><span>${esc(s.ad)}</span><div class="an-ozc"><i style="width:${a}%${asti ? ';background:var(--turuncu)' : ''}"></i></div><b>${s.deger} / ${s.hedef} ${s.birim}</b></div>`; }).join('')}</div>${d.notlar.map(x => `<p class="hz-not">${esc(x)}</p>`).join('')}<p class="gri hz-kay">Sayılar tahmin; hedef ${kod === 'tek' ? 'günün tamamı' : 'günün yarısı'}.</p>`; };
  $$('#ydSeg button', p).forEach(b => b.onclick = () => { kod = b.dataset.k; nc(); }); nc();
  const zk = window.zamanKutu($('#ydZ', p), y.t);
  $('#ydTasi', p).onclick = async () => { const z = zk.oku();
    if (!z.t && !z.son) return toast('Değişiklik yok.');
    try{ const r = await api('/api/pt/yemek/tasi', json({tarih, id, t: z.t || y.t, son_yemek: z.son})); p.kapat(); yukle();
      toast(z.son ? 'Kaydedildi. Oruç o andan sürüyor.' : 'Kaydedildi.', 'Geri al', async () => { await api('/api/pt/yemek/tasi-geri', json({geri: r.geri})); yukle(); }); }catch(e){ toast(e.message); } };
  $('#ydDuz', p).onclick = () => { p.kapat(); yemekSayfa(y, {duzenle: {tarih}}); };
  $('#ydSor', p).onclick = () => { p.kapat(); sohbetSayfa(`${gunMetni(0) === tarih ? 'Bugünkü' : tarih + ' tarihli'} "${y.ad}" öğünüm ${kod === 'tek' ? 'tek öğünüm olarak' : 'iki öğünümden biri olarak'} nasıl? Neyi ekleyeyim?`); };
  $('#ydSil', p).onclick = async () => { await fetch(`/api/pt/yemek/${tarih}/${id}`, {method: 'DELETE'}); p.kapat(); toast('Kaldırıldı.'); yukle(); };
};

/* Tek ve iki öğün düzeni (2026-11-05): ne yiyeceği, porsiyonlarıyla; "Yedim" tek dokunuş. Beslenme'de kart, başka yerde sayfa. */
const duzenHtml = v => { const d = v.duzenler[v.secili], h = v.hedef;
  return `<div class="kbas"><h3>Yemek düzeni</h3></div><div class="hz-seg" data-dseg>${Object.values(v.duzenler).map(x => `<button data-dk="${x.kod}" class="${x.kod === v.secili ? 'on' : ''}">${esc(x.ad)}</button>`).join('')}</div>
    <p class="gri2 hz-kal">${esc(d.neden)}</p>
    ${d.ogunler.map((o, i) => `<div class="hz-ogun" data-oi="${i}"><div class="hz-ob"><b>${esc(o.ad)}</b><span class="gri">${esc(o.saat)}</span>${o.secenekler.length > 1 ? `<span class="hz-c hz-osec">${o.secenekler.map((s, j) => `<button data-os="${j}" class="${j ? '' : 'on'}">${esc(s.ad)}</button>`).join('')}</span>` : ''}</div>
      ${o.secenekler.map((s, j) => `<div class="hz-os" data-osg="${j}" ${j ? 'hidden' : ''}><ul>${s.kalemler.map(k => `<li>${esc(k)}</li>`).join('')}</ul><div class="hz-oa"><span class="gri">${Math.round(s.kcal)} kcal · ${Math.round(s.protein)} g protein</span><button class="btn kucuk" data-oy="${i}:${j}">Yedim</button></div></div>`).join('')}</div>`).join('')}
    <p class="hz-top">Günün toplamı <b>${d.toplam.kcal}</b>${h.kcal ? ' / ' + h.kcal : ''} kcal · <b>${d.toplam.protein}</b>${h.protein ? ' / ' + h.protein : ''} g protein · <b>${d.toplam.doymus}</b>${h.doymus_ust ? ' / en çok ' + h.doymus_ust : ''} g doymuş yağ</p>
    ${h.kolesterol ? '<p class="gri hz-kay">Kolesterol için: krema ve tereyağı yerine zeytinyağı. Yumurtayı doktorunuza sorun; gerekirse yerine yoğurt ya da lor.</p>' : ''}
    <p class="gri hz-kay">Değerler Alman besin tablosundan (BLS 4.0); porsiyonlar protein hedefinize göre. Haftalık menünün öğün sayısı da bu seçime uyar.</p>`; };
const duzenBagla = (k, v, yenile) => {
  $$('[data-dk]', k).forEach(b => b.onclick = async () => { if (b.dataset.dk === v.secili) return; try{ const r = await api('/api/pt/ogun-duzeni', json({duzen: b.dataset.dk})); yenile(r); toast(`${r.duzenler[r.secili].ad} seçildi.`); }catch(e){ toast(e.message); } });
  $$('.hz-ogun', k).forEach(o => $$('[data-os]', o).forEach(b => b.onclick = () => { $$('[data-os]', o).forEach(x => x.classList.toggle('on', x === b)); $$('[data-osg]', o).forEach(x => x.hidden = x.dataset.osg !== b.dataset.os); }));
  $$('[data-oy]', k).forEach(b => b.onclick = async () => { const [i, s] = b.dataset.oy.split(':').map(Number);
    try{ const r = await api('/api/pt/ogun-duzeni/yedim', json({duzen: v.secili, i, s})); yukle();
      toast('Eklendi.', 'Geri al', async () => { await fetch(`/api/pt/yemek/${r.tarih}/${r.yemek.id}`, {method: 'DELETE'}); yukle(); }); }catch(e){ toast(e.message); } });
};
window.duzenKartYukle = async function(){
  const k = $('#duzenKart'); if (!k) return;
  const ciz = v => { k.innerHTML = duzenHtml(v); duzenBagla(k, v, ciz); };
  try{ ciz(await api('/api/pt/ogun-duzeni')); }catch(e){ k.remove(); }
};
window.duzenSayfa = async function(){
  let v; try{ v = await api('/api/pt/ogun-duzeni'); }catch(e){ toast(e.message); return; }
  const p = sayfa('<div id="dzS"></div>'), k = $('#dzS', p);
  const ciz = x => { k.innerHTML = duzenHtml(x); duzenBagla(k, x, ciz); };
  ciz(v);
};
document.addEventListener('click', e => {
  const d = e.target.closest('[data-duzen]'); if (d){ window.duzenSayfa(); return; }
  const y = e.target.closest('[data-ydetay]'); if (y && y.dataset.ydetay) window.yemekDetay(y.dataset.ytarih, y.dataset.ydetay);
});
document.addEventListener('keydown', e => { if (e.key !== 'Enter') return; const y = e.target.closest && e.target.closest('[data-ydetay]'); if (y && y.dataset.ydetay) window.yemekDetay(y.dataset.ytarih, y.dataset.ydetay); });

/* Recent discoveries and monthly archive. A mention does not verify validity. */
(function () {
  'use strict';
  const pl = document.documentElement.lang === 'pl';
  const say = (uk, polish) => pl ? polish : uk;
  const $ = id => document.getElementById(id);
  const tabs = [$('recentTab'), $('archiveTab')];
  const search = $('codesSearch');
  const locale = pl ? 'pl-PL' : 'uk-UA';
  const day = 86400000;
  let records = [], loaded = false, active = 0, limit = 18;
  function date(value) {
    if (!value) return null;
    const time = Date.parse(/^\d{4}-\d{2}-\d{2}$/.test(value) ? value + 'T00:00:00Z' : value);
    return Number.isFinite(time) ? time : null;
  }
  function classify(promo, now) {
    const seen = date(promo.last_seen);
    const expiryValue = promo.expires_at || promo.expires_on;
    let expiry = date(expiryValue);
    if (expiry !== null && /^\d{4}-\d{2}-\d{2}$/.test(expiryValue)) expiry += day - 1;
    const expired = expiry !== null && expiry < now;
    return { ...promo, seen, expired, archived: expired || seen === null || seen > now || now - seen > 30 * day };
  }
  function card(p) {
    const el = document.createElement('article'); el.className = 'promo-card';
    const top = document.createElement('div'); top.className = 'promo-card__top';
    const stamp = document.createElement('span'); stamp.className = 'promo-card__date';
    stamp.textContent = say('Остання згадка: ', 'Ostatnia wzmianka: ') + (p.seen === null ? '—' : new Date(p.seen).toLocaleDateString(locale,{timeZone:'UTC'})); top.append(stamp);
    const button = document.createElement('button'); button.type = 'button'; button.className = 'promo-card__code-wrap'; button.dataset.copyCode = p.code;
    button.setAttribute('aria-label',say('Скопіювати промокод ', 'Kopiuj kod ') + p.code);
    const code = document.createElement('span'); code.className = 'promo-card__code'; code.textContent = p.code;
    const copy = document.createElement('span'); copy.className = 'promo-card__copy'; copy.textContent = say('Копіювати','Kopiuj'); button.append(code,copy);
    const status = document.createElement('p'); status.className = 'promo-code-status';
    status.textContent = p.expired ? say('Термін дії минув','Termin ważności minął') : p.archived ? say('Архівний · дію не підтверджено','Archiwalny · ważność niepotwierdzona') : say('Дію перевіряй у кошику AliExpress','Sprawdź ważność w koszyku AliExpress');
    el.append(top,button);
    if (Number.isFinite(p.discount) && Number.isFinite(p.min_order)) {
      const benefit = document.createElement('p'); benefit.className = 'promo-code-status';
      benefit.textContent = '−' + p.discount + ' ' + p.currency + say(' від ', ' od ') + p.min_order + ' ' + p.currency;
      el.append(benefit);
    }
    const note = pl ? p.notes_pl : p.notes_uk;
    if (note) { const conditions = document.createElement('p'); conditions.className = 'promo-code-status'; conditions.textContent = note; el.append(conditions); }
    if (p.expires_on) {
      const expiry = document.createElement('p'); expiry.className = 'promo-code-status';
      expiry.textContent = say('Діє до: ', 'Ważny do: ') + new Date(p.expires_on + 'T00:00:00Z').toLocaleDateString(locale,{timeZone:'UTC'});
      el.append(expiry);
    }
    el.append(status); return el;
  }
  function select(index, focus = false) {
    active = index;
    tabs.forEach((tab,i) => {tab.setAttribute('aria-selected',String(i === index));tab.tabIndex = i === index ? 0 : -1;});
    $('recentPanel').hidden = index !== 0; $('archivePanel').hidden = index !== 1;
    if (focus) tabs[index].focus();
    render();
  }
  function render() {
    if (!loaded) return;
    const now = Date.now(), query = search.value.trim().toLocaleLowerCase();
    const all = records.map(p => classify(p,now));
    const recent = all.filter(p => !p.archived), archive = all.filter(p => p.archived);
    $('recentCount').textContent = recent.length; $('archiveCount').textContent = archive.length;
    const matches = list => list.filter(p => p.code.toLocaleLowerCase().includes(query));
    const fresh = matches(recent), old = matches(archive);
    $('recentCodes').replaceChildren(...fresh.slice(0,limit).map(card));
    $('recentMore').hidden = fresh.length <= limit;
    $('recentEmpty').hidden = fresh.length > 0;
    $('recentEmpty').replaceChildren(document.createTextNode(recent.length ? say('Такого коду серед нових знахідок немає.','Nie znaleziono tego kodu w nowych znaleziskach.') : say('За останні 30 днів нових згадок промокодів немає. Попередні знахідки збережені в архіві.','Brak nowych wzmianek o kodach w ostatnich 30 dniach. Wcześniejsze znaleziska są w archiwum.')));
    const link = document.createElement('button');link.type='button';link.className='load-more__btn';link.textContent=say('Переглянути архів','Zobacz archiwum');link.onclick=()=>select(1);$('recentEmpty').append(link);
    const groups = new Map();
    old.forEach(p=>{const month=p.seen === null ? 'unknown' : new Date(p.seen).toISOString().slice(0,7);if(!groups.has(month)) groups.set(month,[]);groups.get(month).push(p);});
    const opened = new Set(Array.from($('archiveMonths').querySelectorAll('details[open]')).map(el=>el.dataset.month));
    $('archiveMonths').replaceChildren();
    Array.from(groups.keys()).sort((a,b)=>a==='unknown'?1:b==='unknown'?-1:b.localeCompare(a)).forEach(month=>{
      const items=groups.get(month),details=document.createElement('details');details.className='promo-month';details.dataset.month=month;details.open=!!query || opened.has(month);
      const summary=document.createElement('summary');summary.textContent=month==='unknown'?say('Дата невідома','Data nieznana'):new Date(month+'-01T00:00:00Z').toLocaleDateString(locale,{month:'long',year:'numeric',timeZone:'UTC'});
      const count=document.createElement('span');count.textContent=items.length;summary.append(count);
      const grid=document.createElement('div');grid.className='promo-grid';grid.append(...items.map(card));details.append(summary,grid);$('archiveMonths').append(details);
    });
    const history=$('historicPromos'), historicCards=Array.from(history.querySelectorAll('.promo-card'));
    let historicMatches=0;
    historicCards.forEach(el=>{el.hidden=!!query&&!el.textContent.toLocaleLowerCase().includes(query);if(!el.hidden)historicMatches++;});
    history.hidden=!!query&&!historicMatches;
    history.querySelector('details').open=!!query&&historicMatches>0;
    $('archiveEmpty').hidden=old.length>0 || (!!query&&historicMatches>0);
    $('archiveEmpty').textContent=query?say('Такого коду в архіві немає.','Nie znaleziono kodu w archiwum.'):say('Архів поки порожній.','Archiwum jest puste.');
    $('codesStatus').textContent=active===0 ? say('Нові знахідки: ','Nowe znaleziska: ')+fresh.length : say('Знайдено в архіві: ','Znaleziono w archiwum: ')+old.length+(query&&historicMatches?say(' · також є збіги в попередніх акціях',' · są też wyniki we wcześniejszych promocjach'):'');
  }
  tabs.forEach((tab,index)=>{tab.addEventListener('click',()=>select(index));tab.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();select(e.key==='Home'?0:e.key==='End'?1:1-index,true);}});});
  search.addEventListener('input',()=>{limit=18;if(!search.value.trim())$('archiveMonths').querySelectorAll('details').forEach(el=>el.open=false);render();});
  $('recentMore').addEventListener('click',()=>{limit+=18;render();});
  async function init() {
    try {
      const response=await fetch((pl?'../':'')+'data/promos.json?v='+Math.floor(Date.now()/300000));
      if(!response.ok)throw new Error('HTTP '+response.status);
      const data=await response.json();if(!Array.isArray(data.promos))throw new Error('Invalid promo data');
      records=data.promos.filter(p=>p&&typeof p.code==='string'&&p.code.trim()).sort((a,b)=>String(b.last_seen||'').localeCompare(String(a.last_seen||'')));
      loaded=true;render();
    } catch (_) { $('codesStatus').textContent=say('Не вдалося завантажити коди. Онови сторінку, щоб повторити.','Nie udało się wczytać kodów. Odśwież stronę, aby spróbować ponownie.'); }
  }
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)render();});
  document.addEventListener('DOMContentLoaded',init);
})();

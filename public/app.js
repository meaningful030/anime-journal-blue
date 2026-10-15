/* Plain HTML + a small renderer. All imported text is rendered as text. */
"use strict";
function taipeiDay(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', {timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
  const get = name => parts.find(p => p.type === name).value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}
function sixMonthsBefore(iso) {
  const [year, month, day] = iso.split('-').map(Number);
  const target = new Date(Date.UTC(year, month - 7, 1));
  const last = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(day, last));
  return target.toISOString().slice(0, 10);
}
function entryCategory(premiere, today) {
  if (!premiere) return 'pending';
  let first = premiere, last = premiere;
  if (premiere.length === 7) {
    const [year, month] = premiere.split('-').map(Number);
    first = `${premiere}-01`;
    last = `${premiere}-${new Date(Date.UTC(year, month, 0)).getUTCDate()}`;
  }
  const cutoff = sixMonthsBefore(today);
  if (last > today) return 'pending';
  if (last < cutoff) return 'archive';
  return first >= cutoff ? 'recent' : 'pending';
}
function premiereMonth(iso) {
  const [year, month] = iso.split('-');
  return `${year}／${Number(month)}`;
}
function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}
let renderedDay;
function renderJournal() {
  const today = taipeiDay();
  if (today === renderedDay) return;
  renderedDay = today;
  const data = Array.isArray(window.JOURNAL_ENTRIES) ? window.JOURNAL_ENTRIES : [];
  const recent = data.filter(e => entryCategory(e.premiere, today) === 'recent').sort((a,b) => b.premiere.localeCompare(a.premiere) || b.id-a.id);
  const archive = data.filter(e => entryCategory(e.premiere, today) === 'archive').sort((a,b) => b.premiere.localeCompare(a.premiere) || b.id-a.id);
  const recentList = document.getElementById('recent-list');
  const archiveList = document.getElementById('archive-list');
  recentList.replaceChildren();
  archiveList.replaceChildren();
  for (const entry of recent) {
    const card = element('article', 'recent-card');
    if (typeof entry.image === 'string' && /^images\/[a-f0-9]{32}\.jpg$/.test(entry.image)) {
      const image = element('img');
      image.src = './' + entry.image;
      image.alt = entry.alt || entry.title;
      image.loading = 'lazy';
      image.decoding = 'async';
      card.append(image);
    } else card.classList.add('no-image');
    const copy = element('div', 'entry-copy');
    const date = element('p', 'entry-date', `原始首播 ${premiereMonth(entry.premiere)}`);
    copy.append(date, element('h3', '', entry.title));
    if (entry.note) copy.append(element('p', 'entry-note', entry.note));
    card.append(copy);
    recentList.append(card);
  }
  for (const entry of archive) {
    const row = element('li');
    const date = element('time', '', premiereMonth(entry.premiere));
    date.dateTime = entry.premiere.slice(0, 7);
    row.append(element('span', 'archive-title', entry.title), date);
    archiveList.append(row);
  }
  document.getElementById('recent-empty').hidden = recent.length > 0;
  document.getElementById('archive-empty').hidden = archive.length > 0;
  document.getElementById('recent-count').textContent = String(recent.length).padStart(2,'0');
  document.getElementById('archive-count').textContent = String(archive.length).padStart(2,'0');
  document.getElementById('total-count').textContent = recent.length + archive.length;
  document.getElementById('date-range').textContent = `${sixMonthsBefore(today).replaceAll('-','.')} — ${today.replaceAll('-','.')}`;
}
if (typeof document !== 'undefined') {
  renderJournal();
  setInterval(renderJournal, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) renderJournal(); });
}
if (typeof module !== 'undefined') module.exports = {taipeiDay, sixMonthsBefore, entryCategory, premiereMonth};

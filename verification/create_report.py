#!/usr/bin/env python3
""" report V4: takes a pre-filtered csv-file and create an html report
    the report is a single self-contained (X)HTML file, no external scripts or stylesheets are needed
"""

import base64
import gzip
import html
import json
import os
import sys
import traceback
import util
from util import Column
from util import eprint

# see https://validator.w3.org/nu/#textarea
# the output must stay well-formed XML, test_opencanary.py checks this


# priority bands, following the guideline in rules/priorities.txt (lowest number = most important)
TIERS = [
    ("t1", 10, "Fix now", "priority &#8804; 10"),
    ("t2", 50, "Likely bug", "priority 11&#8211;50"),
    ("t3", 75, "Wrong approach", "priority 51&#8211;75"),
    ("t4", None, "Style", "priority 76+"),
]

COLUMNS = [
    ("prio", "Prio", "Team assigned priority, lower is more important"),
    ("team", "Team", "Team responsible for the file"),
    ("component", "Component", "Component the file belongs to"),
    ("file", "File", "Location of the issue"),
    ("source", "Source", "Tool that raised the issue"),
    ("rule", "Rule", "Rule that raised the issue"),
    ("category", "Category", "Category of the issue"),
    ("description", "Description", "Description of the issue"),
]


FUNNEL_ICON = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true">' \
              '<path d="M2 3h12l-4.5 5.5V13l-3 1.5v-6z"/></svg>'

BLOCK_SIZE = 4000  # issues per compressed block

# the [[keywords]] apply_environment.py fills in, the page script fills them into the issues as well
ENVIRONMENT_KEYS = ["permalink-prefix", "wiki-issue-prefix", "wiki-url", "job-url", "branch-id", "user-name", "commit-message"]


def get_tier(priority):
    try:
        value = int(priority)
    except ValueError:
        return TIERS[-1][0]
    for tier, limit, _label, _hint in TIERS:
        if limit is None or value <= limit:
            return tier
    return TIERS[-1][0]


# the dark colors, used both for the system setting and for the theme button
DARK_VARIABLES = """
  --bg: #0f1115;
  --surface: #171a21;
  --surface-2: #1e222b;
  --text: #e6e8ec;
  --muted: #98a2b3;
  --border: #2a2f3a;
  --accent: #6c9dff;
  --accent-soft: #1d2a45;
  --row-hover: #1c2230;
  --t1: #ff6b5e; --t1-soft: #3a1d1b;
  --t2: #ffa04d; --t2-soft: #3a2a17;
  --t3: #e8c547; --t3-soft: #352f15;
  --t4: #98a2b3; --t4-soft: #262b35;
  --shadow: none;
"""


def get_html_head():
    return r'''<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>OpenCanary issue report</title>
<script>/*<![CDATA[*/
try {
  const theme = localStorage.getItem('opencanary-theme');
  if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
} catch (error) { /* no storage, follow the system setting */ }
/*]]>*/</script>
<style>
:root {
  color-scheme: light dark;
  --bg: #f6f7f9;
  --surface: #ffffff;
  --surface-2: #f1f3f6;
  --text: #1d2330;
  --muted: #667085;
  --border: #e3e6eb;
  --accent: #2f6fed;
  --accent-soft: #e8efff;
  --row-hover: #f5f8ff;
  --t1: #d92d20; --t1-soft: #fdecea;
  --t2: #dc6803; --t2-soft: #fef3e6;
  --t3: #b08800; --t3-soft: #fdf8e1;
  --t4: #667085; --t4-soft: #eef0f3;
  --radius: 10px;
  --shadow: 0 1px 2px rgba(16, 24, 40, .06), 0 1px 3px rgba(16, 24, 40, .08);
  --mono: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
}
/* the theme button sets data-theme on the html element, without it the page follows the system setting */
:root[data-theme="light"] { color-scheme: light; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {/*DARK*/}
}
:root[data-theme="dark"] {
  color-scheme: dark;/*DARK*/}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.page { max-width: 1600px; margin: 0 auto; padding: 24px; }

.masthead { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; justify-content: space-between; margin-bottom: 20px; }
.brand { font-size: 12px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.brand .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #f5c400; margin-right: 6px; }
h1 { margin: 4px 0 8px; font-size: 26px; font-weight: 650; letter-spacing: -.01em; }
.meta { display: flex; flex-wrap: wrap; gap: 6px 20px; margin: 0; color: var(--muted); }
.meta div { display: flex; gap: 6px; }
.meta dt { font-weight: 600; }
.meta dd { margin: 0; color: var(--text); }
.links { display: flex; gap: 8px; }
.button {
  display: inline-block; padding: 6px 12px; border: 1px solid var(--border); border-radius: 8px;
  background: var(--surface); color: var(--text); font-weight: 500; box-shadow: var(--shadow);
}
.button:hover { border-color: var(--accent); color: var(--accent); text-decoration: none; }
button.button { font: inherit; cursor: pointer; }
.button.theme { display: inline-flex; align-items: center; padding: 6px 8px; }
.button.theme svg { width: 18px; height: 18px; }
.button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
.card {
  position: relative; display: block; width: 100%; padding: 14px 16px; text-align: left;
  border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface);
  color: var(--text); font: inherit; box-shadow: var(--shadow); cursor: pointer;
  transition: border-color .15s, background-color .15s, transform .15s;
}
.card:hover { border-color: var(--accent); transform: translateY(-1px); }
.card:focus-visible, .sort:focus-visible, .filter input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.card .count { display: block; font-size: 28px; font-weight: 700; line-height: 1.1; }
.card .label { display: block; font-weight: 600; }
.card .hint { display: block; font-size: 12px; color: var(--muted); }
.card.tier::before { content: ""; position: absolute; left: 0; top: 12px; bottom: 12px; width: 4px; border-radius: 0 4px 4px 0; background: var(--tier); }
.card[aria-pressed="true"] { border-color: var(--tier, var(--accent)); background: var(--tier-soft, var(--accent-soft)); }
.card.empty { opacity: .5; }
.t1 { --tier: var(--t1); --tier-soft: var(--t1-soft); }
.t2 { --tier: var(--t2); --tier-soft: var(--t2-soft); }
.t3 { --tier: var(--t3); --tier-soft: var(--t3-soft); }
.t4 { --tier: var(--t4); --tier-soft: var(--t4-soft); }

.toolbar {
  position: sticky; top: 0; z-index: 2; display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
  justify-content: space-between; padding: 10px 0; background: var(--bg);
}
.search { display: flex; flex: 1 1 400px; gap: 8px; max-width: 620px; }
.filter { position: relative; flex: 1 1 auto; }
.reset { flex: none; font: inherit; cursor: pointer; }
.reset:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.filter input {
  width: 100%; padding: 8px 12px 8px 34px; border: 1px solid var(--border); border-radius: 8px;
  background: var(--surface); color: var(--text); font: inherit; box-shadow: var(--shadow);
}
.filter svg { position: absolute; left: 11px; top: 50%; width: 15px; height: 15px; transform: translateY(-50%); color: var(--muted); }
.status { color: var(--muted); }
.status strong { color: var(--text); }
kbd { padding: 1px 5px; border: 1px solid var(--border); border-radius: 4px; background: var(--surface-2); font-family: var(--mono); font-size: 12px; }

.table-wrap { overflow: auto; max-height: calc(100vh - 70px); border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); }
/* fixed layout and one line per row, so every row has the same height and only the visible rows need to exist */
table { width: 100%; min-width: 1100px; border-collapse: separate; border-spacing: 0; table-layout: fixed; }
col.prio { width: 96px; }
col.team { width: 120px; }
col.component { width: 140px; }
col.file { width: 30%; }
col.source { width: 120px; }
col.rule { width: 112px; }
col.category { width: 124px; }
thead th {
  position: sticky; top: 0; z-index: 1; padding: 0; text-align: left; white-space: nowrap;
  background: var(--surface-2); border-bottom: 1px solid var(--border);
}
.head { display: flex; align-items: stretch; }
.sort {
  display: flex; flex: 1 1 auto; gap: 6px; align-items: center; min-width: 0; padding: 10px 12px 10px 2px; border: 0; background: none;
  color: var(--muted); font: inherit; font-size: 12px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; cursor: pointer;
}
.sort .name { overflow: hidden; text-overflow: ellipsis; }
.sort:hover { color: var(--text); }
.column-filter {
  display: flex; flex: none; align-items: center; justify-content: center; width: 26px; margin: 6px 0 6px 5px; padding: 0;
  border: 0; border-radius: 6px; background: none; color: var(--muted); opacity: .45; cursor: pointer;
}
.column-filter svg { width: 13px; height: 13px; }
th:hover .column-filter, .column-filter:focus-visible, .column-filter[aria-expanded="true"], .column-filter.active { opacity: 1; }
.column-filter:hover, .column-filter[aria-expanded="true"] { color: var(--text); background: var(--surface); }
.column-filter.active { color: var(--accent); }
.column-filter.active svg { fill: currentColor; }
.column-filter:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.value-filter {
  position: fixed; z-index: 10; width: min(340px, calc(100vw - 32px)); padding: 10px;
  border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); box-shadow: 0 8px 24px rgba(16, 24, 40, .18);
}
.value-search { width: 100%; padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); font: inherit; }
.value-search:focus-visible, .value-actions button:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.value-actions { display: flex; gap: 6px; margin: 8px 0; }
.value-actions button {
  padding: 3px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface-2);
  color: var(--text); font: inherit; font-size: 12.5px; cursor: pointer;
}
.value-actions button:hover { border-color: var(--accent); color: var(--accent); }
.value-list { max-height: 300px; margin: 0; padding: 0; overflow: auto; list-style: none; }
.value-list label { display: flex; gap: 8px; align-items: center; padding: 3px 4px; border-radius: 4px; cursor: pointer; }
.value-list label:hover { background: var(--row-hover); }
.value-list input { margin: 0; accent-color: var(--accent); }
.value-list .value { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.value-list .blank { font-style: italic; color: var(--muted); }
.value-list .count { color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.value-more { margin: 6px 4px 0; color: var(--muted); font-size: 12px; }
.sort::after { content: "\2195"; opacity: .35; }
th[aria-sort="ascending"] .sort, th[aria-sort="descending"] .sort { color: var(--accent); }
th[aria-sort="ascending"] .sort::after { content: "\2191"; opacity: 1; }
th[aria-sort="descending"] .sort::after { content: "\2193"; opacity: 1; }
tbody td {
  padding: 8px 12px; vertical-align: top; border-bottom: 1px solid var(--border);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
tbody tr.expanded td { white-space: normal; overflow-wrap: anywhere; }
tbody tr[data-index] { cursor: pointer; }
tbody tr[data-index]:hover td, tbody tr[data-index]:focus td { background: var(--row-hover); }
tbody tr[data-index]:focus { outline: 2px solid var(--accent); outline-offset: -2px; }
tbody tr.spacer td, tbody tr.loading td { padding: 0; border: 0; }
tbody tr.loading td { padding: 40px; text-align: center; color: var(--muted); }
td.team, td.component, td.source, td.category { color: var(--muted); }
td.file { font-family: var(--mono); font-size: 12.5px; }
/* cut long paths at the start, the file name and line number at the end matter most */
tbody tr:not(.expanded) td.file { direction: rtl; text-align: left; }
td.file .path { direction: ltr; unicode-bidi: isolate; }
td.rule span { padding: 1px 6px; border-radius: 4px; background: var(--surface-2); font-family: var(--mono); font-size: 12.5px; }
/* the solution icon stays visible after a long rule name, the name is cut instead */
td.rule .rule-cell { display: flex; align-items: center; gap: 4px; min-width: 0; padding: 0; background: none; }
td.rule .rule-cell > span { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
td.rule a.solution { flex: none; display: inline-flex; color: var(--accent); }
td.rule a.solution svg { width: 15px; height: 15px; }
.badge {
  display: inline-block; min-width: 2.4em; padding: 1px 8px; border-radius: 999px; text-align: center;
  background: var(--tier-soft); color: var(--tier); font-weight: 700; font-size: 12.5px;
}
.badge a { color: inherit; }
.empty-message { margin: 0; padding: 40px; text-align: center; color: var(--muted); }
.notice { margin: 0 0 12px; padding: 8px 12px; border-radius: 8px; background: var(--t2-soft); color: var(--text); }
footer { padding: 16px 0 0; color: var(--muted); font-size: 12px; text-align: center; }
[hidden] { display: none !important; }
</style>
</head>
'''.replace("/*DARK*/", DARK_VARIABLES)


def get_script_section():
    return r'''<script>/*<![CDATA[*/
(() => {
  'use strict';

  // remove header items for which apply_environment.py had no value
  for (const item of document.querySelectorAll('[data-optional]')) {
    const value = (item.querySelector('dd') || item).textContent.trim();
    const href = item.getAttribute('href') || '';
    if (!value || value === '(commit_id)' || value.includes('[[') || href.includes('[[')) item.remove();
  }

  // the theme button cycles auto (follow the system setting), light and dark, and remembers the choice
  const themeButton = document.getElementById('theme');
  if (themeButton) {
    const THEMES = ['auto', 'light', 'dark'];
    const SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';
    const ICONS = {
      auto: SVG + '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/></svg>',
      light: SVG + '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
      dark: SVG + '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    };
    const showTheme = () => {
      const theme = document.documentElement.dataset.theme || 'auto';
      themeButton.innerHTML = ICONS[theme];
      themeButton.title = 'Theme: ' + theme + ', click to switch between auto (system setting), light and dark';
      themeButton.setAttribute('aria-label', 'Theme: ' + theme);
    };
    themeButton.addEventListener('click', () => {
      const current = document.documentElement.dataset.theme || 'auto';
      const next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
      if (next === 'auto') delete document.documentElement.dataset.theme;
      else document.documentElement.dataset.theme = next;
      try {
        if (next === 'auto') localStorage.removeItem('opencanary-theme');
        else localStorage.setItem('opencanary-theme', next);
      } catch (error) { /* no storage, the choice lasts until the page is closed */ }
      showTheme();
    });
    showTheme();
  }

  const table = document.getElementById('issues');
  const dataElement = document.getElementById('oc-data');
  if (!table || !dataElement) return;
  const wrap = table.closest('.table-wrap');
  const tbody = table.tBodies[0];
  const filterInput = document.getElementById('filter');
  const shownCount = document.getElementById('shown');
  const progress = document.getElementById('progress');
  const emptyMessage = document.getElementById('no-match');
  const tierButtons = [...document.querySelectorAll('.card[data-tier]')];
  const headers = [...table.tHead.rows[0].cells];
  const columns = headers.map(th => th.dataset.column);
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
  const OVERSCAN = 12;    // rows rendered above and below the visible area

  // the issues are embedded as gzip compressed, base64 encoded JSON blocks, each row is [tier, ...cells, {column: link}]
  // [[keywords]] in the rows are filled from #oc-env, which apply_environment.py filled in like the rest of the page
  const data = JSON.parse(dataElement.textContent);
  const environment = new Map([...document.querySelectorAll('#oc-env [data-key]')].map(e => [e.dataset.key, e.textContent]));
  const fillEnvironment = json => json.replace(/\[\[([\w-]+)\]\]/g, (match, key) =>
    environment.has(key) ? JSON.stringify(environment.get(key)).slice(1, -1) : match);

  async function inflate(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
  }

  const records = [];             // every issue in report order
  let ordered = records;          // records in the current sort order
  let view = [];                  // ordered records that pass the filter
  let offsets = new Float64Array(1);  // offsets[i] is the top of view[i] within the tbody
  let rowHeight = 0;              // measured from a rendered row, 0 means measure again
  const expanded = new Set();     // record indices of the expanded rows
  const expandedHeights = new Map();
  let sortColumn = -1;
  let sortDirection = 1;
  let loading = true;
  let focusIndex = -1;

  const activeTiers = () => new Set(tierButtons.filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.tier));
  const searchWords = () => filterInput.value.toLowerCase().split(/\s+/).filter(Boolean);

  // per column the values that are switched off, values not seen yet (still unpacking) stay visible
  const excluded = columns.map(() => new Set());

  // does the record pass the tier, text and column value filters, the value filter of column skip is ignored
  function matches(record, words, tiers, skip) {
    if (tiers.size !== 0 && !tiers.has(record.tier)) return false;
    for (let column = 0; column < excluded.length; column++) {
      if (column !== skip && excluded[column].has(record.cells[column])) return false;
    }
    return words.every(word => record.text.includes(word));
  }

  function reorder() {
    ordered = records.slice();
    // ties keep the original order (priority, then file), also when sorting descending
    if (sortColumn >= 0) ordered.sort((a, b) => sortDirection * collator.compare(a.cells[sortColumn], b.cells[sortColumn]) || a.index - b.index);
  }

  function updateView() {
    const words = searchWords();
    const tiers = activeTiers();
    view = ordered.filter(r => matches(r, words, tiers, -1));
    shownCount.textContent = view.length;
    emptyMessage.hidden = loading || view.length !== 0;
    layout();
  }

  function layout() {
    const height = rowHeight || 38;
    offsets = new Float64Array(view.length + 1);
    for (let i = 0; i < view.length; i++) {
      const index = view[i].index;
      offsets[i + 1] = offsets[i] + (expanded.has(index) ? expandedHeights.get(index) || height : height);
    }
  }

  // the position in view of the row at height y in the tbody
  function rowAt(y) {
    let low = 0;
    let high = view.length;
    while (low < high) {
      const mid = (low + high + 1) >> 1;
      if (offsets[mid] <= y) low = mid;
      else high = mid - 1;
    }
    return low;
  }

  // a light bulb, after the rule of an issue with a solution suggestion ([solution]{url} link)
  const SOLUTION_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round" aria-hidden="true"><path d="M9 18h6M10 22h4"/>' +
    '<path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.3h6c0-1 .4-1.8 1-2.3A7 7 0 0 0 12 2z"/></svg>';

  function element(name, className, text) {
    const result = document.createElement(name);
    if (className) result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  }

  function spacer(height) {
    const row = element('tr', 'spacer');
    row.setAttribute('aria-hidden', 'true');
    const cell = element('td');
    cell.colSpan = columns.length;
    cell.style.height = height + 'px';
    row.append(cell);
    return row;
  }

  function createRow(record) {
    const isExpanded = expanded.has(record.index);
    const row = element('tr', record.tier + (isExpanded ? ' expanded' : ''));
    row.dataset.index = record.index;
    row.tabIndex = 0;
    row.setAttribute('aria-expanded', String(isExpanded));
    record.cells.forEach((value, column) => {
      const name = columns[column];
      const cell = element('td', name);
      let content = document.createTextNode(value);
      const link = record.links[column];
      if (link && !/^\s*javascript:/i.test(link)) {
        content = element('a', '', value);
        content.href = link;
      }
      if (name === 'prio' || name === 'file' || (name === 'rule' && value)) {
        const wrapper = element('span', { prio: 'badge', file: 'path' }[name] || '');
        wrapper.append(content);
        content = wrapper;
      }
      const solution = record.links.solution;
      if (name === 'rule' && value && solution && !/^\s*javascript:/i.test(solution)) {
        const icon = element('a', 'solution');
        icon.href = solution;
        icon.title = 'How to solve ' + value;
        icon.setAttribute('aria-label', icon.title);
        icon.innerHTML = SOLUTION_ICON;
        const cellContent = element('span', 'rule-cell');
        cellContent.append(content, icon);
        content = cellContent;
      }
      cell.append(content);
      if (value && name !== 'prio') cell.title = value;
      row.append(cell);
    });
    return row;
  }

  let measuring = false;
  function render() {
    const top = Math.max(0, wrap.scrollTop - table.tHead.offsetHeight);
    const first = Math.max(0, rowAt(top) - OVERSCAN);
    const last = Math.min(view.length, rowAt(top + wrap.clientHeight) + 1 + OVERSCAN);
    const fragment = document.createDocumentFragment();
    if (offsets[first] > 0) fragment.append(spacer(offsets[first]));
    for (let i = first; i < last; i++) fragment.append(createRow(view[i]));
    const rest = offsets[view.length] - offsets[last];
    if (rest > 0) fragment.append(spacer(rest));
    const hadFocus = tbody.contains(document.activeElement);
    tbody.replaceChildren(fragment);
    if (focusIndex >= 0 && (hadFocus || document.activeElement === document.body)) {
      const row = tbody.querySelector('tr[data-index="' + focusIndex + '"]');
      if (row) row.focus({ preventScroll: true });
    }
    if (!measuring) measure();
  }

  // the row heights depend on fonts and zoom, measure them and lay out again when they differ from the estimate
  function measure() {
    let changed = false;
    for (const row of tbody.rows) {
      if (!row.dataset.index) continue;
      const index = Number(row.dataset.index);
      const height = row.getBoundingClientRect().height;
      if (expanded.has(index)) {
        if (Math.abs((expandedHeights.get(index) || 0) - height) > 0.5) {
          expandedHeights.set(index, height);
          changed = true;
        }
      } else if (rowHeight === 0) {
        rowHeight = height;
        changed = true;
      }
    }
    if (changed) {
      measuring = true;
      layout();
      render();
      measuring = false;
    }
  }

  let frame = 0;
  function scheduleRender() {
    if (!frame) frame = requestAnimationFrame(() => { frame = 0; render(); });
  }

  function refresh() {
    updateView();
    wrap.scrollTop = 0;
    render();
  }

  function toggle(row) {
    const index = Number(row.dataset.index);
    if (!expanded.delete(index)) expanded.add(index);
    focusIndex = index;
    layout();
    render();
  }

  function sortBy(column) {
    sortDirection = column === sortColumn ? -sortDirection : 1;
    sortColumn = column;
    reorder();
    refresh();
    headers.forEach((th, i) => {
      if (i === column) th.setAttribute('aria-sort', sortDirection === 1 ? 'ascending' : 'descending');
      else th.removeAttribute('aria-sort');
    });
  }

  headers.forEach((th, column) => th.querySelector('.sort').addEventListener('click', () => sortBy(column)));

  // the value filter panel: a checkbox per distinct value of one column, unchecked values are hidden
  const MAX_VALUES = 500;   // checkboxes rendered at once, the search narrows longer lists
  const filterButtons = headers.map(th => th.querySelector('.column-filter'));
  const valuePanel = document.getElementById('value-filter');
  const valueSearch = valuePanel.querySelector('.value-search');
  const valueList = valuePanel.querySelector('.value-list');
  const valueMore = valuePanel.querySelector('.value-more');
  let panelColumn = -1;
  let panelValues = [];     // [value, count] of the open column, sorted by value
  let shownValues = [];     // the panelValues that match the search

  function openPanel(column) {
    closePanel(false);
    panelColumn = column;
    // count the rows each value would show, given all other filters, like a spreadsheet does
    const words = searchWords();
    const tiers = activeTiers();
    const counts = new Map();
    for (const record of records) {
      if (!matches(record, words, tiers, column)) continue;
      const value = record.cells[column];
      counts.set(value, (counts.get(value) || 0) + 1);
    }
    for (const value of excluded[column]) if (!counts.has(value)) counts.set(value, 0);
    panelValues = [...counts].sort((a, b) => collator.compare(a[0], b[0]));
    valueSearch.value = '';
    valuePanel.setAttribute('aria-label', filterButtons[column].getAttribute('aria-label'));
    filterButtons[column].setAttribute('aria-expanded', 'true');
    valuePanel.hidden = false;
    fillPanel();
    placePanel();
    valueSearch.focus();
  }

  function closePanel(returnFocus) {
    if (panelColumn < 0) return;
    filterButtons[panelColumn].setAttribute('aria-expanded', 'false');
    if (returnFocus) filterButtons[panelColumn].focus();
    valuePanel.hidden = true;
    valueList.replaceChildren();
    panelColumn = -1;
    panelValues = shownValues = [];
  }

  function fillPanel() {
    const term = valueSearch.value.toLowerCase();
    shownValues = term ? panelValues.filter(([value]) => value.toLowerCase().includes(term)) : panelValues;
    const fragment = document.createDocumentFragment();
    shownValues.slice(0, MAX_VALUES).forEach(([value, count], i) => {
      const label = element('label');
      const box = element('input');
      box.type = 'checkbox';
      box.checked = !excluded[panelColumn].has(value);
      box.dataset.i = i;
      label.append(box, element('span', value ? 'value' : 'value blank', value || '(empty)'), element('span', 'count', count));
      if (value) label.title = value;
      const item = element('li');
      item.append(label);
      fragment.append(item);
    });
    valueList.replaceChildren(fragment);
    const rest = shownValues.length - MAX_VALUES;
    valueMore.hidden = shownValues.length > 0 && rest <= 0;
    valueMore.textContent = shownValues.length === 0 ? 'No values match.'
      : rest + ' more values, search to narrow the list. Select all/none applies to all ' + shownValues.length + '.';
  }

  function placePanel() {
    if (panelColumn < 0) return;
    const rect = headers[panelColumn].getBoundingClientRect();
    valuePanel.style.left = Math.max(16, Math.min(rect.left, window.innerWidth - valuePanel.offsetWidth - 16)) + 'px';
    valuePanel.style.top = Math.max(8, rect.bottom + 4) + 'px';
  }

  function updateFilterButtons() {
    excluded.forEach((values, column) => {
      filterButtons[column].classList.toggle('active', values.size > 0);
      filterButtons[column].title = values.size ? 'Filtered by value, ' + values.size + ' hidden' : 'Filter by value';
    });
  }

  function valuesChanged() {
    updateFilterButtons();
    refresh();
  }

  filterButtons.forEach((button, column) => button.addEventListener('click', () => {
    if (panelColumn === column) closePanel(false);
    else openPanel(column);
  }));
  valueList.addEventListener('change', event => {
    const value = shownValues[Number(event.target.dataset.i)][0];
    if (event.target.checked) excluded[panelColumn].delete(value);
    else excluded[panelColumn].add(value);
    valuesChanged();
  });
  valuePanel.querySelector('.value-actions').addEventListener('click', event => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const show = button.dataset.action === 'all';
    for (const [value] of shownValues) {
      if (show) excluded[panelColumn].delete(value);
      else excluded[panelColumn].add(value);
    }
    for (const box of valueList.querySelectorAll('input')) box.checked = show;
    valuesChanged();
  });
  valueSearch.addEventListener('input', fillPanel);
  valuePanel.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closePanel(true);
    }
  });
  document.addEventListener('pointerdown', event => {
    if (panelColumn >= 0 && !valuePanel.contains(event.target) && !filterButtons[panelColumn].contains(event.target)) closePanel(false);
  });
  window.addEventListener('scroll', placePanel, { passive: true });
  wrap.addEventListener('scroll', placePanel, { passive: true });

  for (const button of tierButtons) {
    button.addEventListener('click', () => {
      button.setAttribute('aria-pressed', button.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
      refresh();
    });
  }
  function clearFilters() {
    tierButtons.forEach(b => b.setAttribute('aria-pressed', 'false'));
    filterInput.value = '';
    closePanel(false);
    excluded.forEach(values => values.clear());
    updateFilterButtons();
    refresh();
  }
  document.getElementById('show-all').addEventListener('click', clearFilters);
  document.getElementById('reset').addEventListener('click', clearFilters);

  // click or Enter/Space on a row shows its full text, links and text selection keep working
  tbody.addEventListener('click', event => {
    const row = event.target.closest('tr[data-index]');
    if (!row || event.target.closest('a') || String(window.getSelection()).length > 0) return;
    toggle(row);
  });
  tbody.addEventListener('keydown', event => {
    const row = event.target.closest('tr[data-index]');
    if (row && event.target === row && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      toggle(row);
    }
  });
  document.addEventListener('focusin', event => {
    const row = event.target.closest && event.target.closest('tr[data-index]');
    focusIndex = row ? Number(row.dataset.index) : -1;
  });

  wrap.addEventListener('scroll', scheduleRender, { passive: true });
  window.addEventListener('resize', () => {
    rowHeight = 0;
    scheduleRender();
    placePanel();
  });

  let debounce;
  filterInput.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(refresh, 120);
  });
  filterInput.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      filterInput.value = '';
      refresh();
      filterInput.blur();
    }
  });
  document.addEventListener('keydown', event => {
    if (event.key === '/' && document.activeElement.tagName !== 'INPUT') {
      event.preventDefault();
      filterInput.focus();
    }
  });

  // unpack block by block, the first rows are shown while the rest is still being unpacked
  async function load() {
    try {
      if (typeof DecompressionStream === 'undefined') throw new Error('this browser has no DecompressionStream');
      for (const block of data.blocks) {
        for (const [tier, ...rest] of JSON.parse(fillEnvironment(await inflate(block)))) {
          const links = rest.pop();
          records.push({ index: records.length, tier, cells: rest, links, text: rest.join(' ').toLowerCase() });
        }
        progress.textContent = ' (unpacking ' + records.length + ' of ' + data.count + ')';
        reorder();
        updateView();
        render();
      }
      progress.textContent = '';
    } catch (error) {
      progress.textContent = '';
      emptyMessage.textContent = 'The issues could not be unpacked (' + error.message + '), use a current version of Chrome, Edge, Firefox or Safari.';
      emptyMessage.hidden = false;
      tbody.replaceChildren();
      return;
    }
    loading = false;
    updateView();
    render();
  }

  load();
})();
/*]]>*/</script>
'''


def has_index(list_value, column):
    return len(list_value) > column


def get_part(list_value, column):
    if not has_index(list_value, column):
        return "<missing " + str(column) + ">"
    return list_value[column]

# transform the Column.Link field "[1]{URL_1}[2]{URL_2}"
# [index]{URL}  # the index is a 0-indexed reference to the fields the URL if for.
#


def get_link_map(parts):
    # initialize a list of empty strings ["", "", ...]
    links = [""] * (len(parts) - 1)

    linktexts = parts[Column.LINK]
    if (linktexts == ""):
        return zip(parts, links)    # no links, just return

    link_string = parts[Column.LINK].rstrip("}").split("}")
    for index_with_link in link_string:
        kv = index_with_link[1:].split("]{")
        if len(kv) == 2:
            if kv[0].isdigit():   # named links, such as [solution]{url}, are not a column, see create_record()
                links[int(kv[0])] = kv[1]
        else:
            eprint("REPORT ERROR: assumed we would get a key/value pair, got ", kv)
            sys.exit(1)
    return zip(parts, links)


def create_header():
    return '''<header class="masthead">
<div>
<div class="brand"><span class="dot"></span>OpenCanary</div>
<h1>Software Quality Report</h1>
<dl class="meta">
<div data-optional=""><dt>Branch</dt><dd>[[branch-id]]</dd></div>
<div data-optional=""><dt>By</dt><dd>[[user-name]]</dd></div>
<div data-optional=""><dt>Last commit</dt><dd>[[commit-message]]</dd></div>
</dl>
</div>
<nav class="links">
<a class="button" data-optional="" href="[[job-url]]">CI job</a>
<a class="button" data-optional="" href="[[wiki-url]]">Wiki</a>
<button type="button" class="button theme" id="theme" title="Theme: auto" aria-label="Theme: auto"></button>
</nav>
</header>
'''


def create_summary(tiers, total):
    result = '<section class="summary" aria-label="Issues per priority">\n'
    result += f'<button type="button" class="card" id="show-all" title="Clear all filters"><span class="count">{total}</span>' \
              '<span class="label">Issues</span><span class="hint">show all</span></button>\n'
    for tier, _limit, label, hint in TIERS:
        count = tiers.count(tier)
        empty = " empty" if count == 0 else ""
        result += f'<button type="button" class="card tier {tier}{empty}" data-tier="{tier}" aria-pressed="false" ' \
                  f'title="Show only these issues, click more to combine"><span class="count">{count}</span>' \
                  f'<span class="label">{label}</span><span class="hint">{hint}</span></button>\n'
    return result + '</section>\n'


def create_toolbar(display_count, total_count):
    result = '''<div class="toolbar">
<div class="search">
<label class="filter">
<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="9" cy="9" r="6"/><path d="m14 14 4 4"/></svg>
<input type="search" id="filter" placeholder="Filter on text in any column, for example: hides local" aria-label="Filter issues on text in any column" autocomplete="off"/>
</label>
<button type="button" class="button reset" id="reset" title="Clear all filters">Reset</button>
</div>
'''
    result += f'<span class="status">Showing <strong id="shown">0</strong> of {display_count} issues<span id="progress"></span> &#183; ' \
              'click a row for the full text &#183; press <kbd>/</kbd> to filter</span>\n'
    result += '</div>\n'
    if display_count < total_count:
        result += f'<p class="notice">This report is limited to the first {display_count} of {total_count} issues.</p>\n'
    return result


def create_record(parts):
    """one issue as [tier, ...cells, {column: link}], the cells as plain text, the page script escapes them"""
    cells = []
    links = {}
    for column, (value, link) in enumerate(get_link_map(parts)):
        if column >= len(COLUMNS):
            break
        cells.append(html.unescape(value))
        if link:
            links[column] = link
    solution = util.links_to_dict(parts[Column.LINK]).get(util.SOLUTION_LINK)
    if solution:
        links[util.SOLUTION_LINK] = solution
    return [get_tier(parts[Column.PRIO])] + cells + [links]


def encode_block(records):
    """gzip compressed (deterministic, no timestamp) and base64 encoded JSON, the page unpacks it with DecompressionStream"""
    data = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii")


def create_table():
    # only the table shell, the page script renders the rows that are visible from the embedded data
    result = '<div class="table-wrap">\n<table id="issues">\n<colgroup>'
    result += ''.join(f'<col class="{column}"/>' for column, _name, _title in COLUMNS)
    result += '</colgroup>\n<thead><tr>\n'
    for column, name, title in COLUMNS:
        result += f'<th scope="col" data-column="{column}" title="{title}"><div class="head">' \
                  f'<button type="button" class="column-filter" aria-haspopup="dialog" aria-expanded="false" ' \
                  f'aria-label="Filter {name} values" title="Filter by value">{FUNNEL_ICON}</button>' \
                  f'<button type="button" class="sort"><span class="name">{name}</span></button></div></th>\n'
    result += '</tr></thead>\n<tbody>\n'
    result += f'<tr class="loading"><td colspan="{len(COLUMNS)}">Unpacking the issues&#8230;' \
              '<noscript> this report needs JavaScript to show them.</noscript></td></tr>\n'
    result += '</tbody>\n</table>\n<p class="empty-message" id="no-match" hidden="hidden">No issues match the filter.</p>\n</div>\n'
    return result + create_value_filter()


def create_value_filter():
    # one shared panel, the page script opens it below the header of the column being filtered
    return '''<div class="value-filter" id="value-filter" role="dialog" aria-label="Filter values" hidden="hidden">
<input type="search" class="value-search" placeholder="Search values" aria-label="Search values" autocomplete="off"/>
<div class="value-actions"><button type="button" data-action="all">Select all</button><button type="button" data-action="none">Select none</button></div>
<ul class="value-list"></ul>
<p class="value-more" hidden="hidden"></p>
</div>
'''


def create_environment():
    # apply_environment.py cannot reach [[keywords]] inside the compressed data, it fills them here and the page script copies them
    spans = ''.join(f'<span data-key="{key}">[[{key}]]</span>' for key in ENVIRONMENT_KEYS)
    return f'<div id="oc-env" hidden="hidden">{spans}</div>\n'


def create_data(records):
    blocks = [encode_block(records[i:i + BLOCK_SIZE]) for i in range(0, len(records), BLOCK_SIZE)]
    payload = json.dumps({"count": len(records), "blocks": blocks}, separators=(",", ":"))
    return f'<script type="application/json" id="oc-data">{payload}</script>\n'


def create_html_report(lines, count):
    records = [create_record(util.read_structured_line(line)) for line in lines[:count]]
    tiers = [record[0] for record in records]

    sys.stdout.write('<!DOCTYPE html>\n<html lang="en">\n' + get_html_head() + '<body>\n<div class="page">\n')
    sys.stdout.write(create_header())
    sys.stdout.write(create_summary(tiers, len(records)))
    sys.stdout.write(create_toolbar(len(records), len(lines)))
    sys.stdout.write(create_table())
    sys.stdout.write('<footer>Generated by <a href="https://github.com/janwilmans/OpenCanary">OpenCanary</a></footer>\n')
    sys.stdout.write('</div>\n' + create_environment() + create_data(records))
    sys.stdout.write(get_script_section() + '</body>\n</html>\n')


def show_usage():
    eprint("Usage: " + os.path.basename(__file__) + " [/limit=N] < issues.txt > report.html")
    eprint("   create a self-contained html report from opencanary-formatted issues on stdin, written to stdout")
    eprint("")
    eprint("   /limit=N     include only the first N issues, the report notes that it is limited")
    eprint("                (the input is normally sorted by priority, so these are the most important ones)")
    eprint("   -h, --help   show this help")
    eprint("")
    eprint("   input, one issue per line: priority|team|component|file|source|rule|category|description|link-info")
    eprint("   [[keywords]] in the report, such as [[branch-id]], are filled in by apply_environment.py")
    eprint("   see also: https://github.com/janwilmans/OpenCanary")
    eprint("")


def main():
    if sys.argv[1:] in (["-h"], ["--help"]):
        show_usage()
        sys.exit(0)

    limit = 0

    if len(sys.argv) == 2 and "/limit=" in sys.argv[1].lower():
        limit = int(sys.argv[1].split("=")[1])

    if len(sys.argv) != 1 and limit == 0:
        eprint(os.path.basename(__file__) +
               " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    issues = []
    for raw in sys.stdin:
        issues += [raw]

    if limit == 0:
        create_html_report(issues, len(issues))
    else:
        create_html_report(issues, limit)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        sys.exit(1)

#!/usr/bin/env python3
""" report V4: takes a pre-filtered csv-file and create an html report
    the report is a single self-contained (X)HTML file, no external scripts or stylesheets are needed
"""

import html
import os
import re
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


def get_tier(priority):
    try:
        value = int(priority)
    except ValueError:
        return TIERS[-1][0]
    for tier, limit, _label, _hint in TIERS:
        if limit is None or value <= limit:
            return tier
    return TIERS[-1][0]


def get_html_head():
    return r'''<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>OpenCanary issue report</title>
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
@media (prefers-color-scheme: dark) {
  :root {
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
  }
}
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
.filter { position: relative; flex: 1 1 320px; max-width: 520px; }
.filter input {
  width: 100%; padding: 8px 12px 8px 34px; border: 1px solid var(--border); border-radius: 8px;
  background: var(--surface); color: var(--text); font: inherit; box-shadow: var(--shadow);
}
.filter svg { position: absolute; left: 11px; top: 50%; width: 15px; height: 15px; transform: translateY(-50%); color: var(--muted); }
.status { color: var(--muted); }
.status strong { color: var(--text); }
kbd { padding: 1px 5px; border: 1px solid var(--border); border-radius: 4px; background: var(--surface-2); font-family: var(--mono); font-size: 12px; }

.table-wrap { overflow: auto; max-height: calc(100vh - 70px); border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); }
table { width: 100%; border-collapse: separate; border-spacing: 0; }
thead th {
  position: sticky; top: 0; z-index: 1; padding: 0; text-align: left; white-space: nowrap;
  background: var(--surface-2); border-bottom: 1px solid var(--border);
}
.sort {
  display: flex; gap: 6px; align-items: center; width: 100%; padding: 10px 12px; border: 0; background: none;
  color: var(--muted); font: inherit; font-size: 12px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; cursor: pointer;
}
.sort:hover { color: var(--text); }
.sort::after { content: "\2195"; opacity: .35; }
th[aria-sort="ascending"] .sort, th[aria-sort="descending"] .sort { color: var(--accent); }
th[aria-sort="ascending"] .sort::after { content: "\2191"; opacity: 1; }
th[aria-sort="descending"] .sort::after { content: "\2193"; opacity: 1; }
tbody td { padding: 8px 12px; vertical-align: top; border-bottom: 1px solid var(--border); }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover td { background: var(--row-hover); }
td.prio { width: 1%; }
td.team, td.component, td.source, td.category { white-space: nowrap; color: var(--muted); }
td.file { font-family: var(--mono); font-size: 12.5px; overflow-wrap: anywhere; min-width: 220px; }
td.rule { white-space: nowrap; }
td.rule span { padding: 1px 6px; border-radius: 4px; background: var(--surface-2); font-family: var(--mono); font-size: 12.5px; }
td.description { min-width: 320px; }
.clamp { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }
.clamp.expanded { display: block; }
td.description .more { display: inline-block; margin-top: 2px; padding: 0; border: 0; background: none; color: var(--accent); font: inherit; font-size: 12px; cursor: pointer; }
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
'''


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

  const table = document.getElementById('issues');
  if (!table) return;
  const tbody = table.tBodies[0];
  const filterInput = document.getElementById('filter');
  const shownCount = document.getElementById('shown');
  const emptyMessage = document.getElementById('no-match');
  const tierButtons = [...document.querySelectorAll('.card[data-tier]')];
  const headers = [...table.tHead.rows[0].cells];
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

  // read every row once, sorting and filtering then work on plain strings
  const records = [...tbody.rows].map((row, index) => {
    const cells = [...row.cells].map(cell => cell.textContent.trim());
    return { row, index, cells, tier: row.dataset.tier, text: cells.join(' ').toLowerCase() };
  });
  let sortColumn = -1;
  let sortDirection = 1;

  const activeTiers = () => new Set(tierButtons.filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.tier));

  function applyFilter() {
    const words = filterInput.value.toLowerCase().split(/\s+/).filter(Boolean);
    const tiers = activeTiers();
    let shown = 0;
    for (const record of records) {
      const visible = (tiers.size === 0 || tiers.has(record.tier)) && words.every(word => record.text.includes(word));
      record.row.hidden = !visible;
      if (visible) shown++;
    }
    shownCount.textContent = shown;
    emptyMessage.hidden = shown !== 0;
  }

  function sortBy(column) {
    sortDirection = column === sortColumn ? -sortDirection : 1;
    sortColumn = column;
    // ties keep the original order (priority, then file), also when sorting descending
    records.sort((a, b) => sortDirection * collator.compare(a.cells[column], b.cells[column]) || a.index - b.index);
    const fragment = document.createDocumentFragment();
    for (const record of records) fragment.append(record.row);
    tbody.append(fragment);
    headers.forEach((th, i) => {
      if (i === column) th.setAttribute('aria-sort', sortDirection === 1 ? 'ascending' : 'descending');
      else th.removeAttribute('aria-sort');
    });
  }

  headers.forEach((th, column) => th.querySelector('button').addEventListener('click', () => sortBy(column)));

  for (const button of tierButtons) {
    button.addEventListener('click', () => {
      button.setAttribute('aria-pressed', button.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
      applyFilter();
    });
  }
  document.getElementById('show-all').addEventListener('click', () => {
    tierButtons.forEach(b => b.setAttribute('aria-pressed', 'false'));
    filterInput.value = '';
    applyFilter();
  });

  // long descriptions are clamped to a few lines, add a toggle to the ones that are cut off
  // (measure all first, then change the DOM, so the layout is only calculated once)
  const clamped = [...tbody.querySelectorAll('.clamp')].filter(clamp => clamp.scrollHeight > clamp.clientHeight + 1);
  for (const clamp of clamped) {
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'more';
    toggle.textContent = 'Show more';
    toggle.setAttribute('aria-expanded', 'false');
    toggle.addEventListener('click', () => {
      const expanded = clamp.classList.toggle('expanded');
      toggle.textContent = expanded ? 'Show less' : 'Show more';
      toggle.setAttribute('aria-expanded', String(expanded));
    });
    clamp.after(toggle);
  }

  let debounce;
  filterInput.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(applyFilter, 120);
  });
  filterInput.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      filterInput.value = '';
      applyFilter();
      filterInput.blur();
    }
  });
  document.addEventListener('keydown', event => {
    if (event.key === '/' && document.activeElement !== filterInput) {
      event.preventDefault();
      filterInput.focus();
    }
  });

  applyFilter();
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
<label class="filter">
<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="9" cy="9" r="6"/><path d="m14 14 4 4"/></svg>
<input type="search" id="filter" placeholder="Filter, for example: C4701 core" aria-label="Filter issues" autocomplete="off"/>
</label>
'''
    result += f'<span class="status">Showing <strong id="shown">{display_count}</strong> of {display_count} issues &#183; press <kbd>/</kbd> to filter</span>\n'
    result += '</div>\n'
    if display_count < total_count:
        result += f'<p class="notice">This report is limited to the first {display_count} of {total_count} issues.</p>\n'
    return result


def create_cell(column, value, link):
    text = value
    if column == "file":
        # allow long paths to wrap at the separators instead of anywhere
        text = re.sub(r"([\\/])", r"\1<wbr/>", value)
    content = f'<a href="{html.escape(link)}">{text}</a>' if link else text
    if column == "prio":
        return f'<td class="prio"><span class="badge">{content}</span></td>'
    if column == "rule" and value:
        return f'<td class="rule"><span>{content}</span></td>'
    if column == "description":
        return f'<td class="description"><div class="clamp">{content}</div></td>'
    return f'<td class="{column}">{content}</td>'


def create_table(lines):
    result = '<div class="table-wrap">\n<table id="issues">\n<thead><tr>\n'
    for _column, name, title in COLUMNS:
        result += f'<th scope="col" title="{title}"><button type="button" class="sort">{name}</button></th>\n'
    result += '</tr></thead>\n<tbody>\n'
    tiers = []
    for line in lines:
        parts = util.read_structured_line(line)
        tier = get_tier(parts[Column.PRIO])
        tiers.append(tier)
        cells = (create_cell(column[0], value, link) for column, (value, link) in zip(COLUMNS, get_link_map(parts)))
        result += f'<tr class="{tier}" data-tier="{tier}">' + ''.join(cells) + '</tr>\n'
    result += '</tbody>\n</table>\n<p class="empty-message" id="no-match" hidden="hidden">No issues match the filter.</p>\n</div>\n'
    return result, tiers


def create_html_report(lines, count):
    display_lines = lines[:count]
    table, tiers = create_table(display_lines)

    sys.stdout.write('<!DOCTYPE html>\n<html lang="en">\n' + get_html_head() + '<body>\n<div class="page">\n')
    sys.stdout.write(create_header())
    sys.stdout.write(create_summary(tiers, len(display_lines)))
    sys.stdout.write(create_toolbar(len(display_lines), len(lines)))
    sys.stdout.write(table)
    sys.stdout.write('<footer>Generated by <a href="https://github.com/janwilmans/OpenCanary">OpenCanary</a></footer>\n')
    sys.stdout.write('</div>\n' + get_script_section() + '</body>\n</html>\n')


def show_usage():
    if len(sys.argv) > 1:
        eprint("  I got:", sys.argv)
        eprint("")
    eprint("Usage: type <foo> | " + os.path.basename(__file__) + " [/limit=N]")
    eprint("   create an html report from a opencanary-formatted CSV input, optionally limiting the output")
    eprint("   opencanary-format: ")
    eprint("        priority|team|component|file|source|rule|category|description|link-info")
    eprint("   see also: https://github.com/janwilmans/OpenCanary")
    eprint("")


def main():

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

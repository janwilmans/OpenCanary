#!/usr/bin/env python3
""" report V3: takes a pre-filtered csv-file and create an html report
"""

import os
import sys
import traceback
import util
from util import Column
from util import eprint

# see https://divtable.com/table-styler/
# see https://validator.w3.org/nu/#textarea
# see https://validator.github.io/validator/ (integrate into build as a test)
# use https://jinja.palletsprojects.com/en/2.10.x/ for html generation?


def get_html_styles():
    return r'''<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
<title>Issue report</title>
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<style>
body { font-family: Calibri, Arial;}

th {
  text-align: left;
}

td { font-size: 85%; }
.hideextra { white-space: nowrap; overflow: hidden; text-overflow:ellipsis; }

table.blueTable {
  border: 1px solid #1C6EA4;
  background-color: #EEEEEE;
  width: 100%;
  text-align: left;
  border-collapse: collapse;
}
table.blueTable td, table.blueTable th {
  border: 1px solid #AAAAAA;
  padding: 3px 2px;
}
table.blueTable tbody td {
  font-size: 13px;
}
table.blueTable tr:nth-child(even) {
  background: #D0E4F5;
}
table.blueTable thead {
  background: #1C6EA4;
  background: -moz-linear-gradient(top, #5592bb 0%, #327cad 66%, #1C6EA4 100%);
  background: -webkit-linear-gradient(top, #5592bb 0%, #327cad 66%, #1C6EA4 100%);
  background: linear-gradient(to bottom, #5592bb 0%, #327cad 66%, #1C6EA4 100%);
  border-bottom: 2px solid #444444;
}
table.blueTable thead th {
  font-size: 15px;
  font-weight: bold;
  color: #FFFFFF;
  border-left: 2px solid #D0E4F5;
}
table.blueTable thead th:first-child {
  border-left: none;
}

table.blueTable tfoot {
  font-size: 14px;
  font-weight: bold;
  color: #FFFFFF;
  background: #D0E4F5;
  background: -moz-linear-gradient(top, #dcebf7 0%, #d4e6f6 66%, #D0E4F5 100%);
  background: -webkit-linear-gradient(top, #dcebf7 0%, #d4e6f6 66%, #D0E4F5 100%);
  background: linear-gradient(to bottom, #dcebf7 0%, #d4e6f6 66%, #D0E4F5 100%);
  border-top: 2px solid #444444;
}
table.blueTable tfoot td {
  font-size: 14px;
}
table.blueTable tfoot .links {
  text-align: right;
}
table.blueTable tfoot .links a{
  display: inline-block;
  background: #1C6EA4;
  color: #FFFFFF;
  padding: 2px 8px;
  border-radius: 5px;
}

.sortable {
    cursor: pointer; /* Change cursor only for sortable headers */
}
.sortable:hover {
    background-color: lightblue; /* Change background color when hovering over sortable headers */
}

</style>
</head>
'''


def get_script_section():
    return r'''
<script>
$(document).ready(function() {
    $('th').click(function() {
        var table = $(this).parents('table').eq(0)
        var column = $(this).index()
        var rows = table.find('tr:gt(0)').toArray().sort((a, b) => {
            var valA = $(a).children('td').eq(column).text()
            var valB = $(b).children('td').eq(column).text()
            return $.isNumeric(valA) && $.isNumeric(valB) ? valA - valB : valA.localeCompare(valB)
        })
        this.asc = !this.asc
        if (!this.asc) { rows = rows.reverse() }
        for (var i = 0; i < rows.length; i++) { table.append(rows[i]) }
    })
})
</script>
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


def create_html_report(lines, count):
    display_lines = lines[:count]

    html_content = r'''<!DOCTYPE html><html lang="en">
{styles}
<body>
{issue_count}
<br/><a href="[[wiki-url]]">Open-canary Wiki page</a>
<br/><a href="[[job-url]]">The CI job that generated this report</a>
<h2>SQR for branch: "[[branch-id]]" on behalf of [[user-name]]</h2>
Last commit message: [[commit-message]]<br/>
Listing {display_count} out of {total_count} issues.
<table class="blueTable">
<thead><tr>
<th class="sortable" title="Team assigned priority">Prio</th>
<th class="sortable" title="Team responsible for file">Team</th>
<th class="sortable" title="Component the file belongs to">Component</th>
<th class="sortable" title="Location of the file">File</th>
<th class="sortable" title="Tool that raised/generated the issue">Source</th>
<th class="sortable" title="Rule that raised/genereated the issue">Rule</th>
<th class="sortable" title="Category or the issue">Category</th>
<th class="sortable" title="Description">Description</th>
</tr></thead>
'''

    td = '<td><div>'
    tdend = '</div></td>\n'

    for line in display_lines:
        html_content += '<tr>'
        parts = util.read_structured_line(line)
        link_map = get_link_map(parts)

        for value, link in link_map:
            if link == "":
                html_content += td + value + tdend
            else:
                html_content += td + f'<a href="{link}">{value}</a>' + tdend
        html_content += '</tr>\n'

    html_content += '</table>\n{script_section}\n</body></html>\n'

    sys.stdout.write(html_content.format(
        styles=get_html_styles(),
        issue_count=str(len(lines)) + ' issues were found relevant for this Software Quality Report (SQR)',
        display_count=len(display_lines),
        total_count=len(lines),
        script_section=get_script_section()
    ))


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

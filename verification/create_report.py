#!/usr/bin/env python3
""" report V3: takes a pre-filtered csv-file and create an html report
"""

import os, sys
import traceback
from util import *

# see https://divtable.com/table-styler/
# see https://validator.w3.org/nu/#textarea
# see https://validator.github.io/validator/ (integrate into build as a test)
# use https://jinja.palletsprojects.com/en/2.10.x/ for html generation?

def getHtmlStyles():
    return """
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
<title>Issue report</title>
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

</style>
</head>"""


def hasIndex(list, column):
    return len(list) > column


def getPart(list, column):
    if not hasIndex(list, column):
        return "<missing " + str(column) + ">" 
    return list[column]

# transform the Column.Link field "[1]{URL_1}[2]{URL_2}"
# [index]{URL}  # the index is a 0-indexed reference to the fields the URL if for.
#
def getLinkMap(parts):
    links = [""] * (len(parts)-1)   # initialize a list of empty strings ["", "", ...]

    linktexts = parts[Column.LINK]
    if (linktexts == ""):
        return zip(parts, links)    # no links, just return

    linkString = parts[Column.LINK].rstrip("}").split("}")
    for indexWithLink in linkString:
        kv = indexWithLink[1:].split("]{")
        if len(kv) == 2:
            links[int(kv[0])] = kv[1]
        else:
            eprint("REPORT ERROR: assumed we would get a key/value pair, got ", kv)
            sys.exit(1)
    return zip(parts, links)


def createHtmlReport(lines, count):
    displayLines = lines[:count]

    f = sys.stdout
    f.write(r'<!DOCTYPE html><html lang="en">')
    f.write(getHtmlStyles())
    f.write(r'<body>')
    f.write(str(len(lines)) + r' issues were found relevant for this Software Quality Report (SQR)')
    f.write(r'<br/><a href="[[wiki-url]]">Open-canary Wiki page</a>')
    f.write(r'<br/><a href="[[job-url]]">The CI job that generated this report</a>')
    f.write(r'<h2>SQR for branch: "[[branch-id]]" on behalf of [[user-name]]</h2>')
    f.write(r'Last commit message: [[commit-message]]<br/>')
    f.write(r'Listing ' + str(len(displayLines)) + ' out of ' + str(len(lines)) + ' issues.')
    f.write(r'<table class="blueTable">')
    f.write(r'<thead><tr>')
    f.write('<th title="Team assigned priority">Prio</th>\n')
    f.write('<th title="Team responsible for file">Team</th>\n')
    f.write('<th title="Component the file belongs to">Component</th>\n')
    f.write('<th title="Location of the file">File</th>\n')
    f.write('<th title="Tool that raised/generated the issue">Source</th>\n')
    f.write('<th title="Rule that raised/genereated the issue">Rule</th>\n')
    f.write('<th title="Category or the issue">Category</th>\n')
    f.write('<th title="Description">Description</th>\n')
    f.write('</tr></thead>\n')
    f.write(os.linesep)

    td = '<td><div>'   # class="hideextra"
    tdend = '</div></td>\n'

    for line in displayLines:
        f.write('<tr>')
        parts = read_issues_parts(line)
        linkMap = getLinkMap(parts)
        
        index = 0
        for value, link in linkMap:
            if not link == "":
                f.write(td + r'<a href="' + link + '">' + value + '</a>' + tdend)
            else:
                f.write(td + value + tdend)
            index = index + 1
        f.write('</tr>\n')

    f.write('</table>\n')
    f.write('</body></html>\n')
    f.close()


def show_usage():
    if len(sys.argv) > 1:
        eprint("  I got:", sys.argv)
        eprint("")
    eprint("Usage: type <foo> | " + os.path.basename(__file__) + " [/limit=N]")
    eprint("   create an html report from a opencanary-formatted CSV input, optionally limiting the output")
    eprint("   opencanary-format: " )
    eprint("        priority|team|component|file|source|rule|category|description|link-info")
    eprint("   see also: https://github.com/janwilmans/OpenCanary")
    eprint("")


def main():

    limit = 0

    if len(sys.argv) == 2 and "/limit=" in sys.argv[1].lower():
        limit = int(sys.argv[1].split("=")[1])

    if len(sys.argv) != 1 and limit == 0:
        eprint(os.path.basename(__file__) + " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    issues = []
    for raw in sys.stdin:
        issues += [raw]
        
    if limit == 0:
        createHtmlReport(issues, len(issues))
    else:
        createHtmlReport(issues, limit)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        sys.exit(1)


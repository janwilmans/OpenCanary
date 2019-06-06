""" report V3: takes a pre-filtered csv-file and create an html report
"""

from __future__ import print_function
import os, sys, re, urllib
import getopt
import tempfile
import traceback
import subprocess
from enum import IntEnum
from util import *

# see https://divtable.com/table-styler/
# see https://validator.w3.org/nu/#textarea
# see https://validator.github.io/validator/ (integrate into build as a test)
def getHtmlStyles():
    return """
    <head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
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

# _Issue_XXX_NN will be contatenated for issues specific pages
# _Issues will be contatenated for the overview page 
wiki_url_prefix = "https://wiki.kindtechnologies.nl/wiki/index.php?title=OpenCanary"

class Column(IntEnum):
    Prio = 0
    Team = 1
    Component = 2
    File = 3
    Source = 4
    Rule = 5
    Category = 6            # category and rule should be reversed (coarse -> fine)
    Description = 7
    Link = 8

def getWikiUrl(issueId):
    return wiki_url_prefix + "_Issue_" + issueId
    
def getWikiMainUrl():
    return wiki_url_prefix + "_Issues"

def stripSqlEscapingWord(word):
    result = word
    if word.startswith('b"'):
        result = word[1:]
    if word.startswith("b'"):
        result = word[1:]
    return result.strip('"').strip("'")

def stripSqlEscaping(line):
    result = []
    for word in line:
        result += [stripSqlEscapingWord(word)]
    return result
    
def hasIndex(list, column):
    return len(list) > column
    
def getPart(list, column):
    if not hasIndex(list, column):
        return "<missing " + str(column) + ">" 
    return list[column]

# transform the Column.Link field "[1](URL_1)[2](URL_2)"
# [index](URL)  # the index is a 0-indexed reference to the fields the URL if for.
# to a sequence of parts where the first is the value/text and the second is an optional URL
# 
def getLinkMap(parts):
    links = [""] * (len(parts)-1)   # initialize a list of empty strings ["", "", ...]
    
    linkString = parts[Column.Link].split(")")
    for indexWithLink in linkString:
        kv = indexWithLink[1:].split("](")
        if len(kv) == 2:
            links[int(kv[0])] = kv[1]

    return zip(parts, links)

def createHtmlReport(lines):

    f = sys.stdout
    f.write(r'<!DOCTYPE html><html lang="en">')
    f.write(getHtmlStyles())
    f.write(r'<body>')
    f.write(str(len(lines)) + r' issues were found relevant for this report')
    f.write(r'<a href="' + getWikiMainUrl() + '"><h2> Issues overview page </h2></a>')
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
    
    # urls for the wiki should be created in the Column.Link field in a separate tool
    # todo: move wiki-links out of here and create two scripts to add the links to rule reference-pages and wiki-pages

    for line in lines:
        f.write('<tr>')
        parts = stripSqlEscaping(line.strip().split("|"))
        linkMap = getLinkMap(parts)
        
        index = 0
        for value, link in linkMap:
            if not link == "":
                f.write(td + r'<a href="' + link + '">' + value + '</a>' + tdend)
            else:
                if index == Column.Rule:
                    rule = value.replace("#", "_")
                    f.write(td + r'<a href="' + getWikiUrl(rule) + '">' + value + '</a>' + tdend)
                else:
                    f.write(td + value + tdend)
            index = index + 1
        f.write('</tr>\n')

    f.write('</table>\n')
    f.write('</body></html>\n')
    f.close()

def showUsage():
    eprint("Usage: type <foo> | " + os.path.basename(__file__))
    eprint("   will create an html report from a opencanary-formatted CSV input")
    eprint("   opencanary-format: " )
    eprint("        priority|team |component|file|source|rule|category|description|link")
    eprint("   see also: https://github.com/janwilmans/OpenCanary")

def main():
    if len(sys.argv) > 1:
        eprint("error: invalid argument(s)\n")
        showUsage()
        sys.exit(1)

    issues = []
    for raw in sys.stdin:
        issues += [raw]
    createHtmlReport(issues)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        info = traceback.format_exc()
        eprint(info)
        showUsage()
        sys.exit(1)


"""Parse warnings and error messages from MSVC 
"""

from __future__ import print_function
import traceback, sys, os, time
from enum import IntEnum
from util import *

def stripPreFix(v):
    return v
    
class Column(IntEnum):
    Prio = 0
    Team = 1
    Component = 2
    File = 3
    Source = 4
    Rule = 5
    Category = 6
    Description = 7
    Link = 8

def find_nth(s, substr, n):
    i = 0
    while n >= 0:
        n -= 1
        i = s.find(substr, i + 1)
    return i

def makeRelative(v):
    i = find_nth(v, "/", 5)
    if i == -1:
        return v
    return v[i:]

def reportIssue(filename, line, rule, description, component, category):
    links = "[3](https://gitlab.kindtechnologies.nl/OOAKT/tin/blob/master/" + stripPreFix(filename) + "#L" + str(line) + ")"
    if not rule == "":
        links += "[5](https://duckduckgo.com/?q=!ducky+msdn+" + rule + ")"
        
    report(10, "tin", component, makeRelative(filename), line, "msvc", rule, category, description, links)

def report(priority, team, component, filename, line, source, rule, category, description, link):
    s = "|" # csv separator
    #sprint(s.join([str(priority), team, component, filename + ":" + str(line), source, rule, category, description, link))
    print (str(priority) + s + team + s + component + s + filename + ":" + str(line) + s + source + s + rule + s + category + s + description + s + link)

def splitWarningLine(line):
    parts = line.split(": warning ")
    filepart = parts[0]
    remaining = parts[1]
    idx = remaining.find(":")
    rule = remaining[:idx]
    description = remaining[idx+2:]
    component = ""
    
    lastbrace = filepart.rfind("(")
    filename = filepart[:lastbrace]
    remaining = filepart[lastbrace:]
    parts = remaining.rstrip().rstrip(")")
    line = int(parts[1].split(",")[0])
    
    return filename, line, rule, description, component
    
def splitMessageLine(line):
    i = find_nth(line, ":", 1)
    parts = line.split(": message :")
    line = 88
    filepart = parts[0]
    description = parts[1]
    component = ""
    return filepart, line, "", description, component

def ParseMsvc(line):
    if ": message" in line:
        # message lines sometimes seem to contain ": warning", this seem to be caused by compilers writing interleaved to stdout ??
        return
    if ": warning" in line:
        filename, line, rule, description, component = splitWarningLine(line)
        reportIssue(filename, line, rule, description, component, "warning")
        return
    #if ": message" in line:
    #    filename, line, rule, description, component = splitMessageLine(line)
    #    reportIssue(filename, line, rule, description, component, "message")
    #    return
    if "Command line warning" in line:      # broken!! todo: create a test-case
        s = line.split(":") 
        reportIssue(s[0], 0, s[1], s[2])
        return

def showUsage():
    sprint("Usage: type <filename> | " + os.path.basename(__file__))
    sprint("   will be parse all msvc warnings from stdin")

def main():
    for raw in sys.stdin:
        line = raw.strip()
        ParseMsvc(line)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        info = traceback.format_exc()
        print(info)
        showUsage()
        sys.exit(0)

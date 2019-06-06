"""Parse warnings and error messages from MSVC 
"""

from __future__ import print_function
import traceback, sys, os, time
from enum import IntEnum
from subprocess import Popen, PIPE
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
    i = find_nth(v, "/", 6)
    if i == -1:
        return v
    return v[i:]

def reportIssue(filename, line, rule, description, component, category):
    links = "[3](https://gitlab.kindtechnologies.nl/OOAKT/tin/blob/master/" + stripPreFix(filename) + "#L" + str(line) + ")"
    if not rule == "":
        links += "[5](https://duckduckgo.com/?q=!ducky+msdn+" + rule + ")"
        
    source = "cppcheck" # os.path.splitext(os.path.basename(__file__))[0]
    
    priority = 10
    if int(line) == 0:
        priority = 1
    report(priority, "tin", component, makeRelative(filename), line, source, rule, category, description, links)

def report(priority, team, component, filename, line, source, rule, category, description, link):
    s = "|" # csv separator
    #sprint(s.join([str(priority), team, component, filename + ":" + str(line), source, rule, category, description, link))
    sprint(str(priority) + s + team + s + component + s + filename + ":" + str(line) + s + source + s + rule + s + category + s + description + s + link)

def parse(msg):
    s = msg[2:].split(":") 
    if len(s) < 4:          # corresponds with the fields in the --template argument
        if len(msg.strip()) > 0:
            eprint("err:", msg)
        return
    reportIssue(s[0], s[1], "rule", s[3], "tincomp", s[2])

def runcppcheck(path):
    cmd = r'c:\Program Files\Cppcheck\cppcheck.exe'
    list = [cmd, os.path.realpath(path), '-q', '--template={file}:{line}:{severity}:{message}', '--enable=all']        # notice 4 fields in the --template argument
    process = Popen(list, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    (std_out, std_err) = process.communicate()
    exit_code = process.wait()
    return std_out, std_err

def showUsage():
    sprint("Usage: " + os.path.basename(__file__) + " <path>")
    sprint(r"   will run c:\Program Files\Cppcheck\cppcheck.exe on <path> and output report in open-canary format")

def main():
    if not len(sys.argv) == 2:
        eprint("error: invalid argument(s)\n")
        showUsage()
        sys.exit(1)
    
    std_out, std_err = runcppcheck(sys.argv[1])
    # cppcheck report its own errors on stdout
    eprint(std_out)

    for line in std_err.split("\n"):
        parse(line)

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

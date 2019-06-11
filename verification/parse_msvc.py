#!/usr/bin/env python3
"""Parse warnings and error messages from MSVC
"""


from __future__ import print_function
import traceback, sys, os
from enum import IntEnum
from util import *

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


def normpath(pathstr):
    # os.path.normpath cant be used here, as it would also convert the / to \ on windows.
    return pathstr.rstrip("/")

# returns project directory _without_ trailing /
def getProjectDir():
    directory = r"C:/gitlab-runner11/builds/CKAzv-Sw/0/OOAKT/tin/"
    project_dir = os.getenv('CI_PROJECT_DIR')
    if not project_dir is None:
        directory = project_dir
    return normpath(directory)


def removeProjectPath(str):
    return str.replace(getProjectDir(), "")

def removeBuildPath(str):
    oneDirectoryUp = os.path.dirname(getProjectDir())
    return str.replace(oneDirectoryUp, "")


def reportIssue(filename, line, rule, description, component, category):
    url = r"https://gitlab.kindtechnologies.nl/OOAKT/tin/blob/master/"
    project_url = os.getenv('CI_PROJECT_URL')
    if not project_url is None:
        url = project_url
    url = normpath(url)

    links = "[3](" + url + removeProjectPath(filename) + "#L" + str(line) + ")"
    if not rule == "":
        links += "[5](https://duckduckgo.com/?q=!ducky+msdn+" + rule + ")"

    s = "|"  # csv separator
    line = s.join(["10", "tin", component, filename + ":" + str(line), "msvc", rule, category, description, links])
    sprint(removeBuildPath(line))

def splitWarningLine(line):
    parts = line.split(": warning ")
    filepart = parts[0]
    remaining = parts[1]
    idx = remaining.find(":")
    rule = remaining[:idx]
    description = remaining[idx + 2:]
    component = ""

    lastbrace = filepart.rfind("(")
    filename = filepart[:lastbrace]
    remaining = filepart[lastbrace:]
    parts = remaining.rstrip().rstrip(")")
    line = int(parts.split(",")[0][1:])
    return filename, line, rule, description, component


def splitMessageLine(line):
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
    # if ": message" in line:
    #    filename, line, rule, description, component = splitMessageLine(line)
    #    reportIssue(filename, line, rule, description, component, "message")
    #    return
    if "Command line warning" in line:  # broken!! todo: create a test-case
        s = line.split(":")
        reportIssue(s[0], 0, s[1], s[2])
        return


def showUsage():
    eprint("Usage: type <filename> | " + os.path.basename(__file__))
    eprint("   will be parse all msvc warnings from stdin")


def main():
    # only used for debugging
    if len(sys.argv) == 2:
        sys.stdin = open(sys.argv[1], 'r')

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
        eprint(info)
        showUsage()
        sys.exit(0)

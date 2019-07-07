#!/usr/bin/env python3
""" filter out what are not errors, but the team should ignore (unmaintained code for example)
assign priorities according to the teams judgement
the result of this yields a prioritized work-list for the team
"""

import traceback, sys, os
from util import *

reported_issues = 0

def write_issue(line):
    global reported_issues
    reported_issues = reported_issues + 1
    sys.stdout.write(line)


def filter(line):
    if "external/" in line:
        return
    write_issue(line)


def filterAndNormalizeMsvc(line):
    result = line.replace('\\', '/')
    if "external/" in result:
        return
    if "/MSVC/" in result:
        return
    if "D9025" in result:
        return
    write_issue(result)


def showUsage():
    eprint("Usage: <input> | " + os.path.basename(__file__))
    eprint("   The 'valuable' transformation will yields only issues considered valuable to solve by the team")


def main():
    global reported_issues

    if len(sys.argv) != 1:
        eprint("error: invalid argument(s)\n")
        showUsage()
        sys.exit(1)

    for line in sys.stdin:
         filter(line)

    if reported_issues > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        showUsage()
        sys.exit(1)

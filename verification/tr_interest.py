#!/usr/bin/env python3
"""Filter third party warnings
"""

import traceback, sys, os
from util import *


def filter(line):
    if "external/" in line:
        return
    sys.stdout.write(line)


def filterAndNormalizeMsvc(line):
    result = line.replace('\\', '/')
    if "external/" in result:
        return
    if "/MSVC/" in result:
        return
    if "D9025" in result:
        return
    sys.stdout.write(result)


def showUsage():
    eprint("Usage: " + os.path.basename(__file__) + " [/msvc]")
    eprint("   will filter all lines from 3rd party as hardcoded by you in this script")
    eprint(r"   /msvc  - also ignore messages from MSVC system headers and normalize paths, replacing \ with /")


def main():
    if len(sys.argv) < 2:
        for line in sys.stdin:
            filter(line)
        sys.exit(0)

    if len(sys.argv) == 2 and sys.argv[1] == "/msvc":
        for line in sys.stdin:
            filterAndNormalizeMsvc(line)
        sys.exit(0)

    eprint("error: invalid argument(s)\n")
    showUsage()
    sys.exit(1)


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

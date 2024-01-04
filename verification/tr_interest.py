#!/usr/bin/env python3
"""Filter third party warnings
"""

import traceback, sys, os
from util import *


# note: return True if the line should be kept
def is_interesting(line):
    if "C4242" in line:     # in WebCore, CsCore, CsGui and 3rdparty
        return False
    if "|3rdparty|" in line:
        if "C4291" in line:
            return False
    if "C4244" in line:
        return False
    if "C4291" in line:
        return False
    if "C4267" in line:
        return False
    if "needs to have dll-interface" in line:
        return False
    if "via dominance" in line:
        return False
    return True

def filter(line):
    if is_interesting(line):
        sys.stdout.write(line)

def filterAndNormalizeMsvc(line):
    if is_interesting(line):
        sys.stdout.write(line.replace('\\', '/'))


def show_usage():
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
    show_usage()
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        show_usage()
        sys.exit(1)

#!/usr/bin/env python3
"""Filter third party warnings
"""

import traceback, sys, os
from util import *

def filter(line):
    if "external/" in line:
        return
    sys.stdout.write(line)


def filter_and_normalize_msvc(line):
    result = line.replace('\\', '/')
    result_lower = result.lower()
    if "external/" in result_lower:
        return
    if "/msvc/" in result_lower:
        return
    if "/sdk/" in result_lower[:20]:
        return
    sys.stdout.write(result)


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
            filter_and_normalize_msvc(line)
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

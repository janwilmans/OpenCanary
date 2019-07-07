#!/usr/bin/env python3
"""Filter messages to limit the logs in gitlabs output view (since it has a 4MB limit)
"""

import traceback, sys, os
from util import *


def filter(line):
    if ": message :" in line:
        return
    if ": warning C" in line:
        return
    sys.stdout.write(line)


def showUsage():
    eprint("Usage: " + os.path.basename(__file__))
    eprint("   will filter lines as hardcoded by you in this script")


def main():
    if len(sys.argv) == 1:
        for line in sys.stdin:
            filter(line)
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

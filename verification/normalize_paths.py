#!/usr/bin/env python3
""" replace all '\\' (single backslash) with a forward slash '/'
    notice: filter_thirdparty.py /msvc already does this, so don't use both
"""

import traceback, sys, os
from util import *

def showUsage():
    eprint("Usage: type <foo> | " + os.path.basename(__file__))
    eprint("   all \\ will be replaced with /")

def main():
    if len(sys.argv) > 1:
        eprint("error: invalid argument(s)\n")
        showUsage()
        sys.exit(1)

    for raw in sys.stdin:
        sys.stdout.write(raw.replace('\\', '/'))


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

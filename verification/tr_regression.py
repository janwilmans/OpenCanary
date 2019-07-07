#!/usr/bin/env python3
"""include all categories that should currently have zero issues
exclude all projects that do not comply yet
any issues that pass this filter fail the build
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
    eprint("Usage: <input> | " + os.path.basename(__file__))
    eprint("   When the 'regression' transformation yields any results new issues have be introduced and the build should fail!")


def main():
    if len(sys.argv) != 1:
        eprint("error: invalid argument(s)\n")
        showUsage()
        sys.exit(1)

    for line in sys.stdin:
        filter(line)
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

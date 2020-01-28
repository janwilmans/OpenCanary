#!/usr/bin/env python3
""" set errorlevel (can be useful to suppress returncodes from, for example, clang-tidy, that would otherwise fail the build) sort like || echo exit-code $? would
"""

import traceback, sys, os, time
from util import *

if __name__ == "__main__":
    rc = 0
    if len(sys.argv) > 1:
        rc = int(sys.argv[1])
    eprint("## returncode.py returning " + str(rc) + "\n")
    sys.exit(rc)
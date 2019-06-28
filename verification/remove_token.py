#!/usr/bin/env python3
""" Removes a specific (set of) tokens
"""

from __future__ import print_function
import traceback, sys, os, time, re
from util import *

def removetoken(line, tokens):
    result = line
    for token in tokens:
        pattern = re.compile(token)
        result = pattern.sub('', result)
    return result

def showUsage():
    eprint("Usage: " + os.path.basename(__file__) + " <token> <token...>")
    eprint("   <token> will be stripped from the data send to stdin")

def main():

    if len(sys.argv) < 2:
        eprint("error: missing argument(s)\n")
        showUsage()
        sys.exit(1)

    for raw in sys.stdin:
        sys.stdout.write(removetoken(raw, sys.argv[1:]))

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        info = traceback.format_exc()
        eprint(info)
        sys.exit(1)

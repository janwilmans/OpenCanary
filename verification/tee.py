#!/usr/bin/env python3
""" tee - split stdin into stdout and a file
"""

import traceback, sys, os, time
from util import *

def show_usage():
    eprint ("tee - split stdin into stdout and a file")
    eprint ("usage: tee <filename>")

def main():
    if len(sys.argv) < 2:
        show_usage()
        sys.exit(1)

    eprint("tee default encoding: ", sys.getdefaultencoding())

    lastline = ""

    with open(sys.argv[1], 'w', encoding="utf-8") as outputfile:
        for line in sys.stdin:
            try:
                outputfile.write(line)
                sys.stdout.write(get_timestamp() + " " + line)
                lastline = line
            except Exception as ex:
                eprint("TEE ERROR: ", ex)
                eprint("## last: ", lastline)
                eprint("## now : ", line)

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
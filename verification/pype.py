#!/usr/bin/env python3
""" pype - redirect output to a file and to std.err (making it unbuffered / live-streaming)
"""

import traceback, sys, os, time
from util import *
from subprocess import Popen, PIPE, STDOUT

def showUsage():
    eprint ("pype - redirect output to a file and to std.err")
    eprint ("usage: pipe <filename> -- <cmd>")

def main():
    if len(sys.argv) < 4:
        showUsage()
        sys.exit(1)

    if sys.argv[2] != "--":
        showUsage()
        sys.exit(1)

    cmd = " ".join(sys.argv[3:])
    lastline = ""

    with open(sys.argv[1], 'wb') as outputfile:
        sub_process = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True)
        for line in sub_process.stdout:
            try:
                outputfile.write(line)
                sys.stderr.buffer.write(line)
                lastline = line
            except Exception as ex:
                eprint("PYPE", type(ex).__name__ + ":", ex)
                eprint("## last: ", lastline)
                eprint("## now : ", line)
                sys.exit(1)
    sub_process.wait()
    rc = sub_process.returncode
    sys.stderr.write("PYPE subprocess exited with code " + str(rc) + "\n")
    sys.exit(rc)    # forward return code

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
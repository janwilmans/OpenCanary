#!/usr/bin/env python3
""" pype - redirect output to a file and to std.err (making it unbuffered / live-streaming)
"""

import traceback, sys, os, time
import datetime as dt
from util import *
from subprocess import Popen, PIPE, STDOUT

def showUsage():
    eprint ("pype - redirect stdout+stderrr of <cmd> to a file and to stderr")
    eprint ("usage: pipe <filename> -- <cmd>")

def format_delta(delta):
    sec = delta.total_seconds()
    hours = int(sec /60 /60)
    sec = sec - (60*60*hours)
    minutes = int(sec /60)
    seconds = sec - (60*minutes)
    return str.format("{0:d}h {1:d}m {2:.3f}s", hours, minutes, seconds)

def main():
    if len(sys.argv) < 4:
        showUsage()
        sys.exit(1)

    if sys.argv[2] != "--":
        showUsage()
        sys.exit(1)

    cmd = " ".join(sys.argv[3:])
    lastline = ""

    starttime = datetime.now()

    # combine sub-process' stdout+stderr into one stream using `stdout=PIPE, stderr=STDOUT`
    # see https://docs.python.org/3/library/subprocess.html
    with open(sys.argv[1], 'wb') as outputfile:
        sub_process = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True)
        for line in sub_process.stdout:
            try:
                outputfile.write(line)
                # write to unbuffered stderr output to get a responsive line-by-line build log
                sys.stderr.buffer.write(line)
                lastline = line
            except Exception as ex:
                eprint("PYPE", type(ex).__name__ + ":", ex)
                eprint("## last: ", lastline)
                eprint("## now : ", line)
                sys.exit(1)
    sub_process.wait()
    rc = sub_process.returncode
    elapsedTime = datetime.now() - starttime

    sys.stderr.write("PYPE subprocess exited with code " + str(rc) + " after " + format_delta(elapsedTime) + ".\n")
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
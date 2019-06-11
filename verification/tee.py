""" tee - split stdin into stdout and a file
"""

import traceback, sys, os, time
from util import *

def showUsage():
    eprint ("tee - split stdin into stdout and a file")
    eprint ("usage: tee <filename>")

def main():
    if len(sys.argv) < 2:
        showUsage()

    global warnings
    warnings = open(sys.argv[1], 'w')

    for line in sys.stdin:
        warnings.write(line)
        print(line.strip())

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        info = traceback.format_exc()
        eprint(info)
        showUsage()
        sys.exit(1)
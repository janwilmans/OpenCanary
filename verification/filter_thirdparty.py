"""Filter thrid party warnings
"""

import traceback, sys, os
from util import *

def filter(line):
    if "external/" in line:
        return
    sys.stdout.write(line)

def filterMsvc(line):
    if "external\\" in line:
        return
    if "\\MSVC\\" in line:
        return
    if "D9025" in line:
        return
    sys.stdout.write(line)

def showUsage():
    sprint("Usage: " + os.path.basename(__file__) + " [/msvc]")
    sprint("   will filter all lines from 3rd party as hardcoded by you in this script")
    sprint(r"   /msvc  - search for \ instead of / and also ignore messages from MSVC system headers")

def main():
    if len(sys.argv) < 2:
        for line in sys.stdin:
            filter(line)
        sys.exit(0)

    if len(sys.argv) == 2 and sys.argv[1] == "/msvc":
        for line in sys.stdin:
            filterMsvc(line)
        sys.exit(0)

    eprint("error: invalid argument(s)\n")
    showUsage()
    sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        info = traceback.format_exc()
        print(info)
        showUsage()
        sys.exit(1)

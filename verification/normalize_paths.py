""" replace all '\\' (single backslash) with a forward slash '/'
"""

from __future__ import print_function
import traceback, sys, os, time, re

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    
def sprint(*args, **kwargs):
    print(*args, file=sys.stdout, **kwargs)

def scriptName():
    return __file__.split(os.sep)[-1:][0]

def showUsage():
    eprint("Usage: type <foo> | " + scriptName())
    eprint("   all \\ will be replaced with /")

def main():
    if len(sys.argv) > 1:
        eprint("error: invalid argument(s)\n")
        showUsage()
        sys.exit(1)

    for raw in sys.stdin:
        sys.stdout.write(raw.replace('\\', '/'));

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

"""Parse warnings and error messages from MSVC 
"""

from __future__ import print_function
import traceback, sys, os, time

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    
def sprint(*args, **kwargs):
    print(*args, file=sys.stdout, **kwargs)

def ParseMsvc(line):
    if ": warning" in line:
        sprint(line)
        return
    if "Command line warning" in line:
        sprint(line)
        return

def scriptName():
    return __file__.split('/')[-1:][0]

def showUsage():
    sprint("Usage: type <filename> | " + scriptName() )
    sprint("   will be parse all msvc warnings from stdin")

def main():

    
    for raw in sys.stdin:
        line = raw.strip()
        ParseMsvc(line)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        info = traceback.format_exc()
        print(info)
        showUsage()
        sys.exit(0)

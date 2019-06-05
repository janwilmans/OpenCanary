""" tee - split stdin into stdout and a file
"""

import traceback, sys, os, time

def main():

    if len(sys.argv) < 2:
        print ("tee - split stdin into stdout and a file")
        print ("usage: tee <filename>")
        return

    global warnings
    warnings = open(sys.argv[1], 'w')

    for line in sys.stdin:
        warnings.write(line)
        print(line.strip())

if __name__ == "__main__":
    try:
        main()
    except:
        info = traceback.format_exc()
        print(info)
    sys.exit(0)

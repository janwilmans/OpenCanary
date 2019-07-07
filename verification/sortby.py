#!/usr/bin/env python3
# sortby.py will sort the input from stdin and filter out all duplicate entries
# for example compilation results from debug/debug64/release/release64 or central header files included in many translation units
# cause duplicate entries to be reported

import os, sys, traceback
from util import *


# the tuple is used for a lexicographically sort by its fields
def MakeTuple(line):
    data = line.split("|")
    
    # sort the first colomn by its integer-representation
    return int(data[0]), data[3]


# we should sort numerically by colomn 1 (prio) and then textually by colomn 4 (filename)
def SortBy(inputlines):
    return sorted(inputlines, key=MakeTuple)


def getStdinLines():
    lines = []
    for line in sys.stdin:
        lines += [line.strip()]
    return lines


def show_usage():
    eprint(r"Usage: type <file> | " + os.path.basename(__file__))
    eprint(r"  will sort the input from stdin and filter out all duplicate entries")


def main():
    if len(sys.argv) > 1:
        show_usage()
        sys.exit(1)

    for line in SortBy(set(getStdinLines())):
        sprint(line)

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


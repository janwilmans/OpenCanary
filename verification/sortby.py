#!/usr/bin/env python3
# makeUniq is a workaround for issues being gathered from multiple sources containing duplicate information 
# for example compilation results from debug/debug64/release/release64

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


# guaranteed to keep the first result
def makeUniq(lines):
    result = []
    lines_seen = set() # holds lines already seen
    for line in lines:
        if line not in lines_seen: # not a duplicate
            result += [line]
            lines_seen.add(line)
    return result

def show_usage():
    eprint(r"Usage: type <file> | " + os.path.basename(__file__))
    eprint(r"  will sort the input from stdin and filter out all duplicate entries")


def main():
    if len(sys.argv) > 1:
        show_usage()
        sys.exit(1)

    for line in SortBy(makeUniq(getStdinLines())):
        print(line)

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


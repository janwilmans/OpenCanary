#!/usr/bin/env python3
""" extract the command line to ignore all warnings
"""

import traceback, sys, os
from util import *

def read():
    results = []
    for line in sys.stdin:
        results += [readIssuesParts(line)]
    return results

def countRules(lines):
    results = {}
    for parts in lines:
        rule = parts[Column.Rule]
        if rule in results:
            results[rule] = results[rule] + 1
        else:
            results[rule] = 1
    return results


def show_usage():
    eprint("Usage: <input> | " + os.path.basename(__file__))


def main():
    if len(sys.argv) != 1:
        eprint("error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    print("The required command line arguments to ignore all warnings are:")
    lines = read()
    gcc_result = []
    msvc_result = []
    for rule in sorted(countRules(lines)):
        if rule == "rule-missing":
            continue
        if rule[0] == "C" and len(rule) == 5:    # msvc warnings look like "Cxxxx"
            msvc_result += ["/wd" + rule[1:]]
        else:
            gcc_result += ["-Wno-" + rule]
        
    print("for gcc/clang:")
    print(" ".join(gcc_result))
    if msvc_result != "":
        print("\nand for msvc:")
        print(" ".join(msvc_result))

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

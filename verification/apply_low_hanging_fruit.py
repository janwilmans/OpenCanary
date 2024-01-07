#!/usr/bin/env python3
""" re-prioritize rules that have less then 5 issues to top priority
"""

import traceback
import sys
import os
from util import *


def read():
    results = []
    for line in sys.stdin:
        results += [read_issues_parts(line)]
    return results


def count_rules(lines):
    results = {}
    for parts in lines:
        rule = parts[Column.RULE]
        if rule in results:
            results[rule] = results[rule] + 1
        else:
            results[rule] = 1
    return results


def show_usage():
    if len(sys.argv) > 1:
        eprint("  I got:", sys.argv)
        eprint("")
    eprint("Usage: <input> | " + os.path.basename(__file__))
    eprint("   re-prioritize rules that have less then 5 issues to top-priority")


def main():
    if len(sys.argv) != 1:
        eprint(os.path.basename(__file__) + " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    lines = read()
    rules = count_rules(lines)
    ruleSet = set()
    for rule in rules:
        count = rules[rule]
        if count <= 5:
            ruleSet.add(rule)

    for line in lines:
        rule = line[Column.RULE]
        if rule in ruleSet:
            # prime number 7 means: priority overridden automatically to solve 'low hanging fruit' first
            line[Column.PRIO] = "7"
        report_list(line)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise
    except SystemExit:
        raise
    except BrokenPipeError:   # still makes piping into 'head -n' work nicely
        sys.exit(0)
    except:
        info = traceback.format_exc()
        eprint(info)
        show_usage()
        sys.exit(1)

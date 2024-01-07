#!/usr/bin/env python3
""" assign team specific priorities and/or categories to the issues
"""

import traceback
import sys
import os
from util import *


def show_usage():
    if len(sys.argv) > 1:
        eprint("  I got:", sys.argv)
        eprint("")
    eprint("Usage: <input> | " + os.path.basename(__file__))
    eprint("   " + __doc__)


def read():
    results = []
    for line in sys.stdin:
        results += [read_issues_parts(line)]
    return results


def get_priority(rule):

    # gcc warnings, exact matches if possible, some contains trailing =
    # for example `implicit-fallthrough=`, `format-overflow=`, `stringop-overflow=` or `format-truncation=`
    if "aggressive-loop-optimizations" == rule:  # ub
        return 5
    if "array-bounds" == rule:
        return 5
    if "literal-conversion" == rule:
        return 5
    if "restrict" == rule:
        return 5
    if "stringop-overflow=" == rule:
        return 5
    if "varargs" == rule:  # ub
        return 5
    if "overloaded-virtual" == rule:
        return 5
    if "self-assign" == rule:
        return 5
    if "gnu-zero-variadic-macro-arguments" == rule:
        return 10
    if "ignored-qualifiers" == rule:
        return 10
    if "stringop-truncation" == rule:  # ub
        return 10
    if "unused-value" == rule:
        return 10
    if "main" == rule:
        return 10
    if "comment" in rule:
        return 10
    if "pointer-bool-conversion" in rule:
        return 10
    if "implicit-fallthrough" in rule:
        return 20
    if "uninitialized" == rule:
        return 25
    if "self-assign" in rule:
        return 30
    if "maybe-uninitialized" in rule:
        return 40
    if "unused-" in rule:
        return 40
    if "format-overflow" in rule:
        return 45
    if "missing-field-initializers" in rule:
        return 45
    if "sign-compare" in rule:
        return 45
    if "write-strings" in rule:
        return 50
    if "format-y2k" == rule:
        return 60
    if "vla" == rule:
        return 60
    if "ignored-qualifiers" in rule:
        return 60
    if "format-nonliteral" == rule:
        return 70
    if "format-truncation" == rule:
        return 80
    if "format-nonliteral" in rule:
        return 80
    if "overflow" in rule:
        return 80

    # open canary issues

    if "MO#1" == rule:  # /make_unique
        return 70
    if "MO#2" == rule:  # make_unique
        return 70
    if "AP#3" == rule:  # reinterpret_cast
        return 35
    if "AP#4" == rule:  # volatile
        return 15
    if "MO#5" == rule:  # nullptr
        return 85
    if "AP#6" == rule:  # non-english words
        return 65
    if "AP#7" == rule:  # ifdef
        return 80
    if "AP#8" == rule:  # c-style-cast
        return 40
    if "AP#9" == rule:  # c-style-cast
        return 75
    if "AP#10" == rule:
        return 70
    if "AP#11" == rule:
        return 60
    if "AP#12" == rule:  # ??
        return 99
    if "AP#13" == rule:  # delete
        return 45
    if "AP#14" == rule:  # c-style-cast
        return 15
    if "AP#15" == rule:  # casting literals
        return 30
    if "AP#16" == rule:  # const_cast
        return 30

    return Priority.UNASSIGNED.value


def get_category(line):
    rule = line[Column.RULE]
    if "aggressive-loop-optimizations" == rule:
        return "ub"
    if "stringop-truncation" in rule:
        return "ub"
    if "varargs" in rule:
        return "ub"
    if "array-bounds" in rule:
        return "ub"
    return line[Column.CATEGORY]


# move into team-specific script that also fills in the category field
# guideline for priotity:
# - likeliness to be an actual bug means higher priority
# - below 10: solve immediately, likely currently causing problems
# - 11-50: likely a bug
# - 51-75: probably not causing active problems, but just the wrong way to do it
# - 75-99: hard to read / old style / bad style
def transform(line):
    try:
        rule = line[Column.RULE]
        line[Column.PRIO] = str(get_priority(rule))
        line[Column.CATEGORY] = get_category(line)
    except Exception:
        eprint("Exception in transform of:", line)
        raise
    return line


def main():
    if len(sys.argv) != 1:
        eprint(os.path.basename(__file__) + " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    for line in read():
        report_list(transform(line))


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
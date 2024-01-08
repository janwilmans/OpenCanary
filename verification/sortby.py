#!/usr/bin/env python3
# sortby.py will sort the input from stdin and filter out all duplicate entries
# for example compilation results from debug/debug64/release/release64 or central header files included in many translation units
# cause duplicate entries to be reported
# consider using 'sort -t \| -k 1n,4 | uniq' if this is available on your platform

import os
import sys
import traceback
from util import Column
from util import eprint
from util import sprint


# the tuple is used for a lexicographically sort by its fields
def make_tuple(line):
    data = line.split("|")

    # sort the first column by its integer-representation, column[0] (prio) and column[3] (filename)
    # bug: we should sort also by the line-number and column-number at the end of the "filename:line:column"

    file = data[Column.FILE]
    parts = file.split(":")
    filename = parts[0]
    line_number = 0
    column_number = 0
    if len(parts) > 1:
        line_number = parts[1]
        if len(parts) > 2:
            column_number = parts[2]
    return int(data[Column.PRIO]), filename, int(line_number), int(column_number)


def sort_by(inputlines):
    return sorted(inputlines, key=make_tuple)


def get_stdin_lines():
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

    for line in sort_by(set(get_stdin_lines())):
        sprint(line)


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

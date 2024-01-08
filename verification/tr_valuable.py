#!/usr/bin/env python3
""" filter out what are not errors, but the team should ignore (unmaintained code for example)
assign priorities according to the teams judgement
the result of this yields a prioritized work-list for the team
"""

import traceback
import sys
import os
import util
from util import Column
from util import eprint

categoryMap = {}    # rule -> category

categoryMap.update('C4838', 'conversions')
categoryMap.update('C4312', 'conversions')


def process(linetext):
    parts = util.read_issues_parts(linetext)

    # add filters here for what the team should ignore / currently has no focus

    # categorize issues here
    v = categoryMap.get(parts[Column.RULE], None)
    if v is not None:
        parts[Column.CATEGORY] = v

    # prioritize issues here
    util.write_structured_line(parts)


def show_usage():
    eprint("Usage: <input> | " + os.path.basename(__file__))
    eprint("   The 'valuable' transformation will yields only issues considered valuable to solve by the team")


def main():
    global reported_issues

    if len(sys.argv) != 1:
        eprint("error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    for line in sys.stdin:
        process(line)


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

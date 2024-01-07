#!/usr/bin/env python3
"""Filter third party warnings
"""

import traceback
import sys
import os
from util import *


# note: return True if the line should be kept
def is_interesting(line):
    if "_autogen" in line:
        return False
    if "|use of old-style|" in line:
        return False
    return True


def apply_filter(line):
    if is_interesting(line):
        sys.stdout.write(line)


def apply_filter_and_normalize_msvc(line):
    if is_interesting(line):
        sys.stdout.write(line.replace('\\', '/'))


def show_usage():
    eprint("Usage: " + os.path.basename(__file__) + " [/msvc]")
    eprint("   will filter all lines from 3rd party as hardcoded by you in this script")
    eprint(r"   /msvc  - also ignore messages from MSVC system headers and normalize paths, replacing \ with /")


def main():
    if len(sys.argv) < 2:
        for line in sys.stdin:
            apply_filter(line)
        sys.exit(0)

    if len(sys.argv) == 2 and sys.argv[1] == "/msvc":
        for line in sys.stdin:
            apply_filter_and_normalize_msvc(line)
        sys.exit(0)

    eprint("error: invalid argument(s)\n")
    show_usage()
    sys.exit(1)


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

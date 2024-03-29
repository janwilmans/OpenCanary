#!/usr/bin/env python3
"""Filter third party warnings
"""

import traceback
import sys
import os
from util import eprint


# note: return True if the line should be kept
def is_interesting(line):
    if "C4101" in line:  # unreferenced local variable
        return False
    if "|3rdparty|" in line:
        if "C4706" in line:  # assignment within conditional expression (checked)
            return False
        if "C4245" in line:  # 'return': conversion from 'int' to 'unsigned int', signed/unsigned mismatch
            return False
        if "4459" in line:  # [3rdparty]: declaration of 'table_tags' hides global declaration
            return False
    if "|webkit|" in line:
        if "C4706" in line:  # assignment within conditional expression (checked)
            return False
        if "C4389" in line:  # '==': signed/unsigned mismatch
            return False
    if "|WebCore|" in line:
        if "C4702" in line:  # unreachable code
            return False
        if "C4065" in line:  # switch statement contains 'default' but no 'case' labels
            return False
    if "harfbuzz" in line:
        if "C4702" in line:  # unreachable code
            return False
    if "C4242" in line:     # [WebCore]: '=': conversion from 'int' to 'yytype_int16', possible loss of data
        return False        # in WebCore, CsCore, CsGui and 3rdparty
    if "C4244" in line:     # 'argument': conversion from 'qint64' to 'double', possible loss of data
        return False
    if "C4291" in line:     # no matching operator delete
        return False
    if "C4267" in line:     # [CsCore]: 'initializing': conversion from 'size_t' to 'int', possible loss of data
        return False
    if "C4706" in line:     # assignment within conditional expression
        return False
    if "dll-interface" in line:
        return False
    if "via dominance" in line:
        return False
    if "marked as __forceinline not inlined" in line:
        return False
    if "The POSIX name for this item is deprecated" in line:
        return False
    if "_CRT_SECURE_NO_WARNINGS" in line:
        return False
    if "C4100" in line:  # 'size': unreferenced formal parameter
        return False
    if "C4456" in line:  # [CsCore]: declaration of 'oldNext' hides previous local declaration
        return False
    if "C4458" in line:  # [CsGui]: declaration of 'state' hides class member
        return False
    if "C4457" in line:  # declaration of 'value' hides function parameter
        return False
    if "C4996" in line:  # non-deprecation warning in iterator (was actually never standard)
        if "|MSVC|" in line:
            return False
    if "C4389" in line:    # [CsCore]: '!=': signed/unsigned mismatc
        return False
    if "C4389" in line:
        return False
    if "attribute [[gnu::used]] is not recognized" in line:
        return False
    if "|CsCore|" in line:  # signed/unsigned mismatch, \network\qt\QNetworkReplyHandler.cpp:122 used on positive sizes
        if "C4018" in line:
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
    eprint(r"   /msvc   - ignore messages from MSVC system headers and normalize paths, replacing \ with /")


def has_argument(value):
    for arg in sys.argv:
        if value in arg:
            return True
    return False


def main():
    if has_argument("msvc"):
        for line in sys.stdin:
            apply_filter_and_normalize_msvc(line)
    else:
        for line in sys.stdin:
            apply_filter(line)
    sys.exit(0)


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

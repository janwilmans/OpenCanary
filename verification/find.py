#!/usr/bin/env python3
"""Parse issues from cppcheck
"""

import traceback, sys, os
from subprocess import Popen, PIPE
from util import *


def main():
    s = "/one/two/three/four/five/"
    sprint("1", s[find_nth(s, "/", 1):])
    sprint("2", s[find_nth(s, "/", 2):])
    sprint("3", s[find_nth(s, "/", 3):])
    sprint("4", s[find_nth(s, "/", 4):])
    sprint("5", s[find_nth(s, "/", 5):])
    sprint("6", s[find_nth(s, "/", 6):])
    sprint("7", find_nth(s, "/", 7))
    sprint("bla", find_nth("bla", "/", 0))

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        sys.exit(1)

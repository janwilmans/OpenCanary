#!/usr/bin/env python3
"""Parse issues from cppcheck
"""

import traceback, sys, os
from subprocess import Popen, PIPE
from util import *

def shortenPathStem(v):
    i = find_nth(v, "/", 2)
    if i == -1:
        return v
    return v[i:]


def report_issue(filename, line, rule, description, component, category):
    links = "[3](" + get_git_url() + "/blob/master" + shortenPathStem(filename) + "#L" + str(line) + ")"
    if not rule == "":
        links += "[5](https://duckduckgo.com/?q=!ducky+msdn+" + rule + ")"

    priority = 10
    if int(line) == 0:
        priority = 1
    source = "cppcheck"
    report(priority, "tin", component, filename + ":" + str(line), source, rule, category, description, links)


def parse(msg):
    s = msg.split(":")
    if len(s) < 4:  # corresponds with the fields in the --template argument
        if len(msg.strip()) > 0:
            eprint("err:", msg)
        return
    report_issue(normpath(s[0]), s[1], "rule", s[3], "tincomp", s[2])


def run_cppcheck(path):
    cmd = r'c:\Program Files\Cppcheck\cppcheck.exe'
    list = [cmd, os.path.realpath(path), '-q', '--template={file}:{line}:{severity}:{message}',
            '--enable=all']  # notice 4 fields in the --template argument
    process = Popen(list, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    (std_out, std_err) = process.communicate()
    process.wait()
    return std_out, std_err


def show_usage():
    eprint("Usage: " + os.path.basename(__file__) + " <env.txt> <path> <basepath>")
    eprint(r"  <env.txt> file containing CI environment variables")
    eprint(r"  <path> is recursively processed by c:\Program Files\Cppcheck\cppcheck.exe and output reported in open-canary format")
    eprint(r"  <basepath> files are shown as relative to this path")


def main():
    if not len(sys.argv) == 4:
        eprint("error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    read_envfile(sys.argv[1])

    cpppath = os.path.abspath(sys.argv[2])
    std_out, std_err = run_cppcheck(cpppath)

    basepath = os.path.abspath(sys.argv[3])
    pathlen = len(basepath)

    # cppcheck report its own errors on stdout, we redirect them to stderr
    eprint(std_out)

    for line in std_err.splitlines():
        parse(line[pathlen:])


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        info = traceback.format_exc()
        eprint(info)
        show_usage()
        sys.exit(1)

#!/usr/bin/env python3
""" Run cppcheck and write its issues in the OpenCanary format.

    Usage: cppcheck.py <path> [--basepath DIR]
           cppcheck.py cdb [--basepath DIR]
      <path>          directory that cppcheck analyses recursively (on one core, so unusedFunction runs too)
      cdb             instead of a directory: the compile database build_cppcheck/compile_commands.json in the
                      current directory, and ./suppressions.xml when it exists
      --basepath DIR  remove DIR from the start of the file names; without it the file names are as cppcheck prints
                      them (absolute for <path>), like the compiler logs, so tr_customize.py --reference-depth
                      handles both the same way

    The older form cppcheck.py <env.txt> <path> <basepath> still works (the environment file is not used).
    The CPPCHECK environment variable selects the cppcheck binary, else cppcheck on the PATH, else
    C:\\Program Files\\Cppcheck\\cppcheck.exe.

    The rule is cppcheck's id (nullPointer, variableScope, ...) and the category its severity. Messages with severity
    'information' are about cppcheck itself (an include file it did not find, the check level), not about the code, and
    are skipped, as are constStatement and useStlAlgorithm. The priority is 99, apply_team_priorities.py assigns it.
"""

import argparse
import os
import shutil
import sys
import traceback
from subprocess import Popen, PIPE

from util import Priority, create_link, eprint, get_rule_url, normpath, report, urljoin

# override with the CPPCHECK environment variable
cppcheck_cmd = os.environ.get("CPPCHECK") or shutil.which("cppcheck") or r'c:\Program Files\Cppcheck\cppcheck.exe'

# tab separated: a file name can contain ':' (C:\...), and so can a message
TEMPLATE = "--template={file}\\t{line}\\t{severity}\\t{id}\\t{message}"
# one core: with -j cppcheck skips unusedFunction (unless it gets a --cppcheck-build-dir)
OPTIONS = ['-q', '-DTEST', '-DTEST_F', TEMPLATE, '--enable=all']

# ids that are not reported: constStatement was a false positive (maybe caused by -DTEST), useStlAlgorithm not useful
SKIPPED_IDS = {"constStatement", "useStlAlgorithm"}


def report_issue(filename, line, rule, description, component, category):
    links = create_link(3, urljoin("[[permalink-prefix]]", normpath(filename) + "#L" + str(line)))
    if not rule == "":
        links += create_link(5, get_rule_url("cppcheck", rule))

    # assignment of priority is done in apply_team_priorities.py, as for the other parsers
    source = "cppcheck"
    report(Priority.UNASSIGNED.value, "", component, filename + ":" + str(line), source, rule, category, description, links)


def parse(msg, basepath=""):
    """one line of cppcheck's stderr, in the TEMPLATE format"""
    fields = msg.split("\t", 4)
    if len(fields) < 5:  # not a template line
        if len(msg.strip()) > 0:
            eprint("err:", msg)
        return
    filename, line, severity, rule, message = fields
    if severity == "information" or rule in SKIPPED_IDS:
        return
    filename = normpath(filename)
    if basepath and filename.lower().startswith(basepath.lower() + "/"):
        filename = filename[len(basepath) + 1:]
    report_issue(filename, line, rule, message, "", severity)


def run_cppcheck(path):
    return execute_popen([cppcheck_cmd, os.path.realpath(path)] + OPTIONS)


def run_cppcheck_compile_db():
    list_value = [cppcheck_cmd] + OPTIONS + ['--project=build_cppcheck/compile_commands.json']
    if os.path.exists('./suppressions.xml'):
        list_value += ['--suppress-xml=./suppressions.xml']
    return execute_popen(list_value)


def execute_popen(list_value):
    try:
        sub_process = Popen(list_value, stdout=PIPE, stderr=PIPE, universal_newlines=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        eprint(f"cppcheck.py: cppcheck not found ({list_value[0]}), install it or set CPPCHECK to its path")
        sys.exit(1)
    (std_out, std_err) = sub_process.communicate()
    sub_process.wait()
    exitcode = sub_process.returncode
    return std_out, std_err, exitcode


def show_usage():
    eprint(__doc__)


def parse_args(argv):
    if len(argv) == 3 and not any(arg.startswith("-") for arg in argv):
        return argparse.Namespace(path=argv[1], basepath=argv[2])  # the older form: <env.txt> <path> <basepath>
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="directory to analyse, or cdb for the compile database")
    parser.add_argument("--basepath", help="remove this directory from the start of the file names")
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])
    if args.path == "cdb":
        std_out, std_err, exitcode = run_cppcheck_compile_db()
    else:
        std_out, std_err, exitcode = run_cppcheck(os.path.abspath(args.path))

    basepath = normpath(os.path.abspath(args.basepath)) if args.basepath else ""
    # cppcheck reports its own errors on stdout, we redirect them to stderr
    if std_out.strip():
        eprint(std_out)
    for line in std_err.splitlines():
        parse(line, basepath)

    if exitcode != 0:
        report_issue(cppcheck_cmd, 0, "exec", "cppcheck exited with exitcode " + str(exitcode), "ci", "ci")


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

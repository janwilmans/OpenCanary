#!/usr/bin/env python3
""" Run cppcheck and write its issues in the OpenCanary format.

    Usage: cppcheck.py <path> [--basepath DIR] [--option=OPTION ...]
           cppcheck.py cdb [--basepath DIR] [--option=OPTION ...]
      <path>          directory that cppcheck analyses recursively, or a compile_commands.json (or the build directory
                      that contains it) whose translation units cppcheck analyses with their flags; on Linux on every
                      core (-j, with a temporary --cppcheck-build-dir so the whole program checks such as
                      unusedFunction run too), on Windows and macOS on one core (file names that only differ in case
                      clash in a build directory there)
      cdb             the compile database build_cppcheck/compile_commands.json in the current directory, and
                      ./suppressions.xml when it exists
      --basepath DIR  remove DIR from the start of the file names; without it the file names are as cppcheck prints
                      them (absolute for <path>), like the compiler logs, so tr_customize.py --reference-depth
                      handles both the same way
      --option=OPTION an extra option for cppcheck, such as --option=--library=qt; repeat it for more options

    A directory is analysed with -DTEST -DTEST_F: without include paths cppcheck does not know googletest's macros. A
    compile database is not: it has the include paths, and those defines would break googletest's TEST(...) macros.

    cppcheck stops when a file in the compile database does not exist, such as the generated file of a target that
    was not built (mocs_compilation.cpp of Qt's AUTOMOC); those entries are left out, with a warning.

    The older form cppcheck.py <env.txt> <path> <basepath> still works (the environment file is not used).
    The CPPCHECK environment variable selects the cppcheck binary, else cppcheck on the PATH, else
    C:\\Program Files\\Cppcheck\\cppcheck.exe.

    The rule is cppcheck's id (nullPointer, variableScope, ...) and the category its severity. Messages with severity
    'information' are about cppcheck itself (an include file it did not find, the check level), not about the code, and
    are skipped, as are constStatement and useStlAlgorithm. The priority is 99, apply_team_priorities.py assigns it.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import traceback
from subprocess import Popen, PIPE

from util import Priority, create_link, eprint, get_rule_url, normpath, report, urljoin

# override with the CPPCHECK environment variable
cppcheck_cmd = os.environ.get("CPPCHECK") or shutil.which("cppcheck") or r'c:\Program Files\Cppcheck\cppcheck.exe'

# tab separated: a file name can contain ':' (C:\...), and so can a message
TEMPLATE = "--template={file}\\t{line}\\t{severity}\\t{id}\\t{message}"
OPTIONS = ['-q', TEMPLATE, '--enable=all']
DIRECTORY_OPTIONS = ['-DTEST', '-DTEST_F']

# With -j cppcheck skips the whole program checks (unusedFunction) unless it gets a --cppcheck-build-dir; it names the
# files in that directory after the source files, so on a file system that ignores case (Windows, macOS) cosmetic.cc
# and Cosmetic.cc share one and the parallel checks fail ("failed to load cosmetic.a1"). There cppcheck runs on one
# core, elsewhere on every core with a new, empty build directory per run (a cache kept between runs saved little).
PARALLEL = sys.platform not in ("win32", "darwin")


def parallel_options(build_dir):
    return [f'-j{os.cpu_count() or 1}', f'--cppcheck-build-dir={build_dir}'] if PARALLEL else []

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


def compile_db_path(path):
    """the compile database that path names, or None when path is a directory to analyse"""
    if os.path.isfile(path):
        return path
    candidate = os.path.join(path, "compile_commands.json")
    return candidate if os.path.isfile(candidate) else None


def entry_file(entry):
    return os.path.join(entry.get("directory", ""), entry["file"])


def existing_entries(database):
    """the entries of the compile database whose file exists, and the files that do not"""
    kept, missing = [], []
    for entry in database:
        (kept if os.path.isfile(entry_file(entry)) else missing).append(entry)
    return kept, [normpath(entry_file(entry)) for entry in missing]


def run_cppcheck(path, extra=()):
    db_path = compile_db_path(path)
    if db_path:
        return run_cppcheck_compile_db(db_path, list(extra))
    return execute_popen([cppcheck_cmd, os.path.realpath(path)] + OPTIONS + DIRECTORY_OPTIONS + list(extra))


def run_cppcheck_compile_db(db_path, extra):
    with open(db_path, encoding="utf-8") as f:
        kept, missing = existing_entries(json.load(f))
    if missing:
        eprint(f"cppcheck.py: {len(missing)} file(s) in {normpath(db_path)} do not exist and are not analysed (not built?), "
               f"such as {missing[0]}")
    with tempfile.TemporaryDirectory(prefix="cppcheck-db-") as db_dir:
        filtered = os.path.join(db_dir, "compile_commands.json")
        with open(filtered, "w", encoding="utf-8") as f:
            json.dump(kept, f)
        return execute_popen([cppcheck_cmd] + OPTIONS + extra + ['--project=' + filtered])


def execute_popen(list_value):
    with tempfile.TemporaryDirectory(prefix="cppcheck-build-") as build_dir:
        try:
            sub_process = Popen(list_value + parallel_options(build_dir), stdout=PIPE, stderr=PIPE,
                                universal_newlines=True, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            eprint(f"cppcheck.py: cppcheck not found ({list_value[0]}), install it or set CPPCHECK to its path")
            sys.exit(1)
        (std_out, std_err) = sub_process.communicate()
        exitcode = sub_process.returncode
    return std_out, std_err, exitcode


def show_usage():
    eprint(__doc__)


def parse_args(argv):
    if len(argv) == 3 and not any(arg.startswith("-") for arg in argv):
        return argparse.Namespace(path=argv[1], basepath=argv[2], option=[])  # the older form: <env.txt> <path> <basepath>
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="directory to analyse, compile_commands.json or its build directory, or cdb")
    parser.add_argument("--basepath", help="remove this directory from the start of the file names")
    parser.add_argument("--option", action="append", default=[], help="an extra option for cppcheck (repeatable)")
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])
    if args.path == "cdb":
        suppressions = ['--suppress-xml=./suppressions.xml'] if os.path.exists('./suppressions.xml') else []
        std_out, std_err, exitcode = run_cppcheck_compile_db('build_cppcheck/compile_commands.json', suppressions + args.option)
    else:
        std_out, std_err, exitcode = run_cppcheck(os.path.abspath(args.path), args.option)

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

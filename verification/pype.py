#!/usr/bin/env python3
""" pype - redirect output to a file and to std.err (making it unbuffered / live-streaming)
"""

import traceback, sys, os, time, re
import datetime as dt
from util import *
from subprocess import Popen, PIPE, STDOUT

filter_msvc = False
summary_msvc = False
filter_gcc = False
summary_gcc = False
summary = []

# build_summary / test_summary append the interesting lines to SUMMARY_LOG, so a CI job can show them at the end
SUMMARY_LOG = "summary.log"
BUILD_KEYWORDS = ["FAILED:", "Failed", "error:", "Killed"]
TEST_KEYWORDS = [": [  FAILED  ]", "***Failed", ": Failure"]
SANITIZERS = [("ASAN", "SUMMARY: AddressSanitizer:"), ("UBSAN", "ubsan:"), ("TSAN", "SUMMARY: ThreadSanitizer:")]
SOURCE_REFERENCE = re.compile(r"\.(c|cc|cpp|cxx|h|hh|hpp|hxx):\d")
build_summary = False
test_summary = False
summary_log = None
sanitizer_counts = {name: 0 for name, _ in SANITIZERS}
sanitizer_lines = {name: set() for name, _ in SANITIZERS}

def show_usage():
    eprint ("pype - redirect stdout+stderrr of <cmd> to a file and to stderr")
    eprint ("usage: pipe <filename> [build_summary] [test_summary] -- <cmd>")
    eprint ("   build_summary   append build failures (FAILED:, error:, Killed, ...) to " + SUMMARY_LOG)
    eprint ("   test_summary    append test failures (gtest/ctest) and a sanitizer summary to " + SUMMARY_LOG)

def format_delta(delta):
    sec = delta.total_seconds()
    hours = int(sec /60 /60)
    sec = sec - (60*60*hours)
    minutes = int(sec /60)
    seconds = sec - (60*minutes)
    return str.format("{0:d}h {1:d}m {2:.3f}s", hours, minutes, seconds)


def add_to_summary_log(line):
    text = line.decode(errors="replace")
    keywords = (BUILD_KEYWORDS if build_summary else []) + (TEST_KEYWORDS if test_summary else [])
    if any(keyword in text for keyword in keywords):
        summary_log.write(line)
        summary_log.flush()
    if test_summary:
        text = text.strip()
        for name, keyword in SANITIZERS:
            if keyword in text:
                sanitizer_counts[name] += 1
                sanitizer_lines[name].add(text)


def write_sanitizer_summary():
    """all unique sanitizer lines, the counts, and the lines that point at a source file once more"""
    result = ["Sanitizer issues:"]
    for name, _ in SANITIZERS:
        result += sorted(sanitizer_lines[name])
    result += ["Sanitizer summary:"]
    for name, _ in SANITIZERS:
        result += [f"{name}: {sanitizer_counts[name]} issues ({len(sanitizer_lines[name])} unique)"]
    references = [line for name, _ in SANITIZERS for line in sorted(sanitizer_lines[name]) if SOURCE_REFERENCE.search(line)]
    if references:
        result += ["----- Sanitizer issues with direct source references ----"] + references
    summary_log.write(("\n".join(result) + "\n").encode("utf-8"))


def process(line):
    global summary

    if summary_log:
        add_to_summary_log(line)

    is_error = False
    if summary_msvc or filter_msvc:
        is_error = b": error " in line

    if summary_gcc or filter_gcc:
        is_error = b": error " in line

    if summary_msvc or summary_gcc:
        if is_error:
            summary += [line]

    output_message = True
    if filter_msvc:
        if line.startswith(b" "):
            output_message = False
        if not is_error and b": warning" in line:
            output_message = False
        if b": note" in line:
            output_message = False

    if filter_gcc:
        if b"[-W" in line:
            output_message = False

    if output_message:
        # write to unbuffered stderr output to get a responsive line-by-line build log
        sys.stderr.buffer.write(line)

def main():
    global filter_msvc
    global summary_msvc
    global filter_gcc
    global summary_gcc
    global build_summary
    global test_summary
    global summary_log

    if len(sys.argv) < 4:
        show_usage()
        sys.exit(1)
    position = 0
    for arg in sys.argv:
        position = position + 1
        if arg == "--":
            break
        if "filter-msvc-warnings" in arg:
            filter_msvc = True
        if "add-msvc-summary" in arg:
            summary_msvc = True
        if "filter-gcc-warnings" in arg:
            filter_gcc = True
        if "add-gcc-summary" in arg:
            summary_gcc = True
        if arg in ("build_summary", "build-summary"):
            build_summary = True
        if arg in ("test_summary", "test-summary"):
            test_summary = True

    cmd = " ".join(sys.argv[position:])
    lastline = ""

    starttime = datetime.now()
    if build_summary or test_summary:
        summary_log = open(SUMMARY_LOG, 'ab')

    # combine sub-process' stdout+stderr into one stream using `stdout=PIPE, stderr=STDOUT`
    # see https://docs.python.org/3/library/subprocess.html
    with open(sys.argv[1], 'wb') as outputfile:
        sub_process = Popen(cmd, stdout=PIPE, stderr=STDOUT, shell=True)
        for line in sub_process.stdout:
            try:
                outputfile.write(line)
                process(line)
                lastline = line
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as ex:
                eprint("PYPE", type(ex).__name__ + ":", ex)
                eprint("## last: ", lastline)
                eprint("## now : ", line)
                sys.exit(1)
    sub_process.wait()
    rc = sub_process.returncode
    elapsedTime = datetime.now() - starttime

    if summary_log:
        if test_summary:
            write_sanitizer_summary()
        summary_log.close()

    if summary_gcc or summary_msvc:
        eprint("-- Build summary --")
        for line in summary:
            eprint(line.strip().decode("utf-8"))

    sys.stderr.write("PYPE subprocess exited with code " + str(rc) + " after " + format_delta(elapsedTime) + ".\n")
    sys.exit(rc)    # forward return code

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        show_usage()
        sys.exit(1)
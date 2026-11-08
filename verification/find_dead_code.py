#!/usr/bin/env python3
""" Find dead code candidates by looking for words that occur only once in the sources.
    Replaces find_unique_*.sh and find_sources_unreferenced_by_cmake.sh, works on Linux and Windows.

    Usage: find_dead_code.py <mode> [path]
      arrays      arrays that are declared but never used, e.g. 'int foo[...]'
      functions   functions that are declared but never used (can have false positives)
      defines     '#define NAME' that are never used
      variables   variables that are declared or assigned but never used
      sources     source files on disk that no CMakeLists.txt refers to
    path is the directory to search, default '.', files in .opencanaryignore are skipped
"""

import os
import re
import sys
from collections import Counter

import gitignore_parser
import util

SOURCE_EXTENSIONS = (".h", ".hpp", ".c", ".cc", ".cpp")
WORD = re.compile(r"[A-Za-z0-9_]{4,}")

# for every mode: how a use of a unique word looks like, {w} is replaced by the (escaped) word
CONTEXTS = {
    "arrays": r"\s{w}\s*\[",
    "functions": r"\s{w}\s*\(",
    "defines": r"#define\s{w}\s",
    "variables": r"(?<!=)\s+{w}(;|\s=)",
}
WHOLE_LINE_MODES = ("arrays", "functions")


def show_usage():
    print(__doc__, file=sys.stderr)


def find_files(path, filenames_to_match):
    result = []
    for root, _dirs, files in gitignore_parser.walk(os.path.abspath(path), filenames=['.opencanaryignore']):
        result += [os.path.join(root, f) for f in files if filenames_to_match(f)]
    return result


def read_text(filename):
    with open(filename, encoding="utf-8", errors="replace") as f:
        return f.read()


def find_unreferenced_sources(path):
    on_disk = find_files(path, lambda f: f.lower().endswith(SOURCE_EXTENSIONS))
    cmake_text = "\n".join(line for f in find_files(path, lambda f: f == "CMakeLists.txt")
                           for line in read_text(f).splitlines() if re.search(r"\.(cc|c|h)", line))
    referenced = set(re.findall(r"[A-Za-z0-9_.]+", cmake_text))
    return sorted({os.path.basename(f) for f in on_disk if ".c" in os.path.basename(f)} - referenced)


def find_unused(mode, path):
    # arrays and functions always used the narrower [A-Za-z_] pattern
    word = re.compile(r"[A-Za-z_]{4,}") if mode in WHOLE_LINE_MODES else WORD
    lines = []
    for filename in find_files(path, lambda f: f.lower().endswith((".h", ".c", ".cc"))):
        lines += read_text(filename).splitlines()

    counts = Counter(w for line in lines for w in word.findall(line))
    unique = {w for w, n in counts.items() if n == 1}
    util.eprint(f"Found {len(lines)} source lines, {len(unique)} words that occur only once.")

    context = re.compile(CONTEXTS[mode].replace("{w}", "(" + word.pattern + ")"))
    result = []
    for line in lines:
        for match in context.finditer(line):
            if match.group(1) in unique:
                result.append(line if mode in WHOLE_LINE_MODES else match.group(0).strip())
    return result


def main():
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in list(CONTEXTS) + ["sources"]:
        show_usage()
        sys.exit(1)
    mode, path = sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else "."
    for line in find_unreferenced_sources(path) if mode == "sources" else find_unused(mode, path):
        util.sprint(line)


if __name__ == "__main__":
    util.run_main(main, show_usage)

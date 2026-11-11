#!/usr/bin/env python3
""" Remove issues the team is not interested in (3rd party code, known noise).
    Lines matching a 'drop' rule in the rules file are removed, see rules/interest.txt for the format.

    The matcher !nolint matches an issue whose source line has a clang-tidy style NOLINT comment that covers its rule:
    '// NOLINT' covers every rule, '// NOLINT(a, b*)' only the rules a and b* (globs; a compiler warning <rule> is
    also covered by clang-tidy's name for it, clang-diagnostic-<rule>). The line is read from the file in the fileref,
    a relative path is relative to the current directory; an issue whose line cannot be read is not matched.

    Usage: <input> | tr_interest.py [--rules FILE] [--msvc]
      --rules FILE  rules file, default rules/interest.txt
      --msvc        normalize paths, replacing \\ with / before the rules are applied
"""

import argparse
import fnmatch
import re
import sys
import util
from util import Column

NOLINT = re.compile(r"\bNOLINT(?!\w)(?:\(([^)]*)\))?")   # not NOLINTNEXTLINE, NOLINTBEGIN or NOLINTEND
FILEREF = re.compile(r"^(.+?):(\d+)(?::\d+)?$")       # file:line[:column], file may be C:/...


def show_usage():
    print(__doc__, file=sys.stderr)


def nolint_covers(code, rule):
    """true when the source line 'code' has a NOLINT comment that covers 'rule'"""
    for match in NOLINT.finditer(code):
        if match[1] is None:
            return True
        checks = [check.strip() for check in match[1].split(",") if check.strip()]
        if any(fnmatch.fnmatchcase(rule, check) or fnmatch.fnmatchcase("clang-diagnostic-" + rule, check) for check in checks):
            return True
    return False


class SourceLines:
    """reads source files once, None for a file that cannot be read"""

    def __init__(self):
        self.files = {}

    def line(self, path, number):
        if path not in self.files:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    self.files[path] = f.read().splitlines()
            except OSError:
                self.files[path] = None
        lines = self.files[path]
        return lines[number - 1] if lines is not None and 1 <= number <= len(lines) else None


def has_nolint(sources, line):
    """true when 'line' is an issue whose source line has a NOLINT comment that covers its rule"""
    fields = line.rstrip("\r\n").split("|")
    if len(fields) <= Column.RULE:
        return False
    fileref = FILEREF.match(fields[Column.FILE].strip())
    if not fileref:
        return False
    code = sources.line(fileref[1], int(fileref[2]))
    return code is not None and nolint_covers(code, fields[Column.RULE].strip())


CONDITIONS = ["nolint"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rules", default=util.default_rules_file("interest.txt"), help="rules file, 'drop' rules remove the line")
    parser.add_argument("--msvc", action="store_true", help="replace \\ with / in the output")
    args = parser.parse_args(util.legacy_args(sys.argv[1:], ["msvc"]))

    rules = util.load_rules(args.rules)
    for rule in rules:
        for matcher in rule.matchers:
            if matcher[0] == "!" and matcher[1:] not in CONDITIONS:
                raise ValueError(f"unknown condition {matcher!r} in {args.rules}, known: " + ", ".join("!" + c for c in CONDITIONS))
    sources = SourceLines()
    for line in sys.stdin:
        if args.msvc:
            line = line.replace("\\", "/")
        if util.first_match(rules, line, conditions={"nolint": lambda: has_nolint(sources, line)}) != "drop":
            sys.stdout.write(line)


if __name__ == "__main__":
    util.run_main(main, show_usage)

#!/usr/bin/env python3
"""include all categories that should currently have zero issues
exclude all projects that do not comply yet
any issues that pass this filter fail the build
"""

import traceback, sys, os

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def sprint(*args, **kwargs):
    print(*args, file=sys.stdout, **kwargs)


def filter():
    results = []
    for line in sys.stdin:
        # filter out all issues that currently exist, so we know when to fail the build (when new issues are introduced)
        if "format-extra-args" in line:
            continue
        if "format=" in line:
            continue
        if "ignored-qualifiers" in line:
            continue
        if "missing-field-initializers" in line:
            continue
        if "overflow" in line:
            continue
        if "rule-missing" in line:
            continue
        if "sign-compare" in line:
            continue
        if "unused-but-set-variable" in line:
            continue
        if "unused-function" in line:
            continue
        if "unused-parameter" in line:
            continue
        if "vla" in line:
            continue
        if "write-strings" in line:
            continue
        results += [line]
    return results


def show_usage():
    eprint("Usage: <input> | " + os.path.basename(__file__))
    eprint("   When the 'regression' transformation yields any results new issues have be introduced and the build should fail!")


def main():
    if len(sys.argv) != 1:
        eprint("error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    regression_issues = filter()

    if len(regression_issues) > 0:
        eprint(len(regression_issues), "new issue(s) where introduced!\n")
        for line in regression_issues:
            sprint(line.strip())
        sys.exit(1)
    sys.exit(0)


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

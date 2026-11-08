#!/usr/bin/env python3
""" OpenCanary entry point.

    opencanary.py init                      write a starter opencanary.toml in the current directory
    opencanary.py run [-c opencanary.toml]  parse, filter, prioritize and report according to the configuration
    opencanary.py <command> [args...]       run one stage, input/output is stdin/stdout like the scripts themselves

    commands: parse-gcc, parse-msvc, cpp-issues, cppcheck, interest, customize, prioritize, low-hanging, sort,
              report, summary, environment, regression
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

COMMANDS = {
    "parse-gcc": "parse_gcc.py",
    "parse-msvc": "parse_msvc.py",
    "cpp-issues": "oc_cpp_issues.py",
    "cppcheck": "cppcheck.py",
    "interest": "tr_interest.py",
    "customize": "tr_customize.py",
    "prioritize": "apply_team_priorities.py",
    "low-hanging": "apply_low_hanging_fruit.py",
    "sort": "sortby.py",
    "report": "create_report.py",
    "summary": "create_summary.py",
    "environment": "apply_environment.py",
    "regression": "tr_regression.py",
}

# stages that produce their output without reading stdin
NO_STDIN_COMMANDS = {"cpp-issues", "cppcheck"}

STARTER_CONFIG = '''# OpenCanary configuration, all relative paths are relative to this file.
# run with: opencanary.py run

# one [[input]] table for every log or location to analyse
#   format  gcc | msvc          the log file is parsed (gcc also handles clang output)
#           cpp-issues          the directory is scanned for common C++ problems
#   source  name shown in the 'source' column (defaults to the format)
[[input]]
format = "gcc"
source = "gcc"
path = "build/gcc.log"

# [[input]]
# format = "cpp-issues"
# path = "."

[rules]
# all optional, shown with their defaults (the files in the verification/rules directory)
# priorities = "priorities.txt"
# interest = "interest.txt"
# customize = "customize.txt"
# low_hanging_threshold = 20

[customize]
# options for tr_customize.py, all optional
# msvc = false              show windows style paths in the report
# display_depth = 0         strip n leading path elements from the path in the report
# reference_depth = 0       strip n leading path elements when creating the link to the source

[output]
issues = "issues.txt"       # the prioritized work list
report = "report.html"      # the html report, [[keywords]] are filled using the environment file
# summary = "summary.html"  # issues per category and team, as e-mail body (Outlook friendly)
# environment = "env.txt"   # key=value file (CI_JOB_URL, CI_PROJECT_URL, CI_COMMIT_SHA, ...), see apply_environment.py
'''


def script(name):
    return [sys.executable, os.path.join(HERE, COMMANDS.get(name, name))]


def run_stage(command, data=None):
    """run one stage, returns its stdout as bytes; stderr is passed through"""
    result = subprocess.run(command, input=data, stdout=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise SystemExit(f"opencanary: stage '{os.path.basename(command[1])}' failed with exit code {result.returncode}")
    return result.stdout


def load_config(filename):
    try:
        import tomllib  # python 3.11+
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            raise SystemExit("opencanary: reading the configuration needs python 3.11 or newer, or 'pip install tomli'")
    with open(filename, "rb") as f:
        return tomllib.load(f)


def run_pipeline(config, base):
    def path(value):
        return value if os.path.isabs(value) else os.path.join(base, value)

    rules, customize, output = config.get("rules", {}), config.get("customize", {}), config.get("output", {})
    inputs = config.get("input", [])
    if not inputs:
        raise SystemExit("opencanary: no [[input]] defined in the configuration")

    data = b""
    for item in inputs:
        fmt, location = item.get("format"), path(item["path"])
        source = item.get("source", fmt)
        if fmt in ("gcc", "msvc"):
            with open(location, "rb") as f:
                data += run_stage(script("parse-" + fmt) + [source], f.read())
        elif fmt == "cpp-issues":
            data += run_stage(script("cpp-issues") + [location])
        else:
            raise SystemExit(f"opencanary: unknown input format {fmt!r}, expected gcc, msvc or cpp-issues")

    def rules_option(key):
        return ["--rules", path(rules[key])] if key in rules else []

    customize_args = [f"--{key.replace('_', '-')}={customize[key]}" for key in ("display_depth", "reference_depth") if key in customize]
    if customize.get("msvc"):
        customize_args.append("--msvc")
    threshold = ["--threshold", str(rules["low_hanging_threshold"])] if "low_hanging_threshold" in rules else []

    data = run_stage(script("interest") + rules_option("interest") + (["--msvc"] if customize.get("msvc") else []), data)
    data = run_stage(script("customize") + rules_option("customize") + customize_args, data)
    data = run_stage(script("prioritize") + rules_option("priorities"), data)
    data = run_stage(script("low-hanging") + threshold, data)
    data = run_stage(script("sort"), data)

    issues_file = path(output.get("issues", "issues.txt"))
    with open(issues_file, "wb") as f:
        f.write(data)
    print(f"opencanary: {len(data.splitlines())} issues written to {issues_file}", file=sys.stderr)

    html = run_stage(script("report"), data)
    if "environment" in output:
        html = run_stage(script("environment") + [path(output["environment"])], html)
    report_file = path(output.get("report", "report.html"))
    with open(report_file, "wb") as f:
        f.write(html)
    print(f"opencanary: report written to {report_file}", file=sys.stderr)

    if "summary" in output:
        summary_file = path(output["summary"])
        with open(summary_file, "wb") as f:
            f.write(run_stage(script("summary"), data))
        print(f"opencanary: summary written to {summary_file}", file=sys.stderr)


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 1

    command = argv[0]
    if command == "init":
        if os.path.exists("opencanary.toml"):
            raise SystemExit("opencanary: opencanary.toml already exists")
        with open("opencanary.toml", "w", encoding="utf-8") as f:
            f.write(STARTER_CONFIG)
        print("opencanary: created opencanary.toml, edit it and run: opencanary.py run", file=sys.stderr)
        return 0

    if command == "run":
        parser = argparse.ArgumentParser(prog="opencanary.py run")
        parser.add_argument("-c", "--config", default="opencanary.toml")
        args = parser.parse_args(argv[1:])
        config_file = os.path.abspath(args.config)
        run_pipeline(load_config(config_file), os.path.dirname(config_file))
        return 0

    if command in COMMANDS:
        if command not in NO_STDIN_COMMANDS and sys.stdin.isatty():
            example = f"{command} < issues.txt > {command}.html" if command in ("report", "summary") else f"{command} < input > output"
            print(f"opencanary: '{command}' reads its input from stdin, pipe or redirect data into it, e.g.\n"
                  f"    opencanary.py {example}\n"
                  f"or use 'opencanary.py run' to run the whole pipeline from opencanary.toml", file=sys.stderr)
            return 1
        return subprocess.run(script(command) + argv[1:], check=False).returncode

    print(f"opencanary: unknown command {command!r}\n\n{__doc__}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        sys.exit(0)

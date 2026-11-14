#!/usr/bin/env python3
""" Report the targets in a compile database that are compiled with other ABI relevant settings than the rest.

    Usage: compile_flags.py <compile_commands.json | build directory> [--macro NAME]... [--ignore-setting NAME]...
                            [--ignore-target NAME]...
      --macro NAME           also compare this macro, a project setting that changes types (a glob: MYLIB_CONFIG_*)
      --ignore-setting NAME  do not compare this setting (as named in the report: "runtime library", _FILE_OFFSET_BITS)
      --ignore-target NAME   leave out this target (a glob: *_test), one that is built differently on purpose; it does
                             not count for the norm either
      opencanary.toml sets these with macros, ignore_settings and ignore_targets on the [[input]] of compile-flags.

    When two parts of one program see a different definition of the same type, the program breaks the One Definition
    Rule (ODR). Neither the compiler nor the linker reports it: the linker only compares names. The program crashes at
    random, or the debugger steps through the code in strange ways. The usual cause is a target that is built with
    another language standard than the rest. For example, a library such as variant-lite is std::variant under C++17
    and its own implementation under C++14, so every type built on it gets two definitions. GCC's -Wodr finds this,
    but only in an LTO build.

    For each setting below, the value that most C++ translation units use is the norm. Every target with another
    value is reported once, on its first source file, as rule inconsistent-compile-flags. The target is CMake's
    CMakeFiles/<target>.dir in the output path of the translation unit; without one it is the directory of the source.
      language standard   -std=c++NN, -std=gnu++NN, /std:c++NN (gnu++17 and c++17 are the same standard)
      library ABI macros  _GLIBCXX_USE_CXX11_ABI, _GLIBCXX_DEBUG, _LIBCPP_ABI_VERSION, _ITERATOR_DEBUG_LEVEL,
                          _FILE_OFFSET_BITS, _TIME_BITS, ... and the *_CONFIG_SELECT_* macros of the nonstd -lite
                          libraries (variant-lite, optional-lite, ...)
      layout flags        -m32/-m64, -fpack-struct, /Zp, -fshort-enums, -fshort-wchar, -malign-double,
                          -fabi-version, /vd
      runtime library     /MD, /MDd, /MT, /MTd
    C sources (.c, -x c, /TC) are left out, the C standard differs from the C++ one on purpose. Arguments in a
    response file (@file) are not read.

    A compile database only has what the build compiles: a library that arrives prebuilt is not in it. CMake writes
    one with -DCMAKE_EXPORT_COMPILE_COMMANDS=ON (Makefile and Ninja generators).
"""

import argparse
import fnmatch
import json
import os
import re
import shlex
import sys
from collections import Counter

import util
from util import Priority

RULE = "inconsistent-compile-flags"
CATEGORY = "bug"
DEFAULT = "(default)"
NOT_DEFINED = "(not defined)"

C_EXTENSIONS = {".c"}
STANDARD = re.compile(r"^(?:-std=(?:c|gnu)\+\+|[-/]std:c\+\+)(\w+)$")
STANDARD_ALIASES = {"0x": "11", "1y": "14", "1z": "17", "2a": "20", "2b": "23", "2c": "26"}

# macros that change the layout or the identity of standard library types
ABI_MACROS = {"_GLIBCXX_USE_CXX11_ABI", "_GLIBCXX_DEBUG", "_GLIBCXX_DEBUG_PEDANTIC", "_LIBCPP_ABI_VERSION",
              "_LIBCPP_ABI_UNSTABLE", "_LIBCPP_DEBUG", "_ITERATOR_DEBUG_LEVEL", "_HAS_ITERATOR_DEBUGGING", "_SECURE_SCL",
              "_FILE_OFFSET_BITS", "_TIME_BITS", "_USE_32BIT_TIME_T"}
CONFIG_SELECT = re.compile(r"^\w+_CONFIG_SELECT_\w+$")  # variant_CONFIG_SELECT_VARIANT, optional_CONFIG_SELECT_OPTIONAL

# (setting, regex): the last matching argument is the value; -fno-... and -mno-... are the compiler default
FLAGS = [
    ("data model", re.compile(r"^-m(32|64|x32)$")),
    ("struct packing", re.compile(r"^(-f(no-)?pack-struct(=\d+)?|[-/]Zp\d*)$")),
    ("enum size", re.compile(r"^-f(no-)?short-enums$")),
    ("wchar_t size", re.compile(r"^-f(no-)?short-wchar$")),
    ("double alignment", re.compile(r"^-m(no-)?align-double$")),
    ("C++ ABI version", re.compile(r"^-fabi-version=\d+$")),
    ("vtordisp", re.compile(r"^[-/]vd\d$")),
    ("runtime library", re.compile(r"^[-/]M[DT]d?$")),
]

FLAG_SETTINGS = {setting for setting, _regex in FLAGS}


def show_usage():
    print(__doc__, file=sys.stderr)


def arguments(entry):
    """the arguments of a compile database entry, from 'arguments' or from 'command'"""
    if "arguments" in entry:
        return list(entry["arguments"])
    command = entry.get("command", "")
    try:
        # backslashes are path separators on Windows, not escapes; only the flags matter here, not the paths
        return shlex.split(command.replace("\\", "/"))
    except ValueError:
        return command.split()


def is_cpp(file, args):
    """false for a C source: by extension, or -x c / /TC"""
    for index, arg in enumerate(args):
        if arg in ("-x", "--language") and index + 1 < len(args):
            return args[index + 1].startswith("c++")
        if arg in ("/TP", "-TP"):
            return True
        if arg in ("/TC", "-TC"):
            return False
    return os.path.splitext(file)[1] not in C_EXTENSIONS


def macro(arg, next_arg):
    """(name, value) for -DNAME[=value] (also '-D NAME' and /D), (name, None) for -UNAME, else None"""
    match = re.match(r"^[-/]([DU])(.*)$", arg)
    if not match:
        return None
    definition = match[2] or (next_arg or "")
    name, _, value = definition.partition("=")
    if not re.match(r"^\w+$", name):
        return None
    if match[1] == "U":
        return name, None
    return name, value if "=" in definition else "1"


def is_compared_macro(name, extra_macros=()):
    return name in ABI_MACROS or bool(CONFIG_SELECT.match(name)) or any(fnmatch.fnmatchcase(name, glob) for glob in extra_macros)


def settings(args, extra_macros=()):
    """the ABI relevant settings of one translation unit as {setting: value shown in the report}; extra_macros are
    globs of macros that are compared as well"""
    result = {"language standard": DEFAULT}
    macros = {}
    for index, arg in enumerate(args):
        standard = STANDARD.match(arg)
        if standard:
            level = STANDARD_ALIASES.get(standard[1], standard[1])
            result["language standard"] = "C++" + level
            continue
        for setting, regex in FLAGS:
            if regex.match(arg):
                result[setting] = DEFAULT if re.match(r"^-[fm]no-", arg) else arg
        definition = macro(arg, args[index + 1] if index + 1 < len(args) else None)
        if definition and is_compared_macro(definition[0], extra_macros):
            macros[definition[0]] = definition[1]
    for name, value in macros.items():
        result[name] = NOT_DEFINED if value is None else value
    return result


def target(entry, args, file):
    """CMake's target (from CMakeFiles/<target>.dir/ in the output path), else the directory of the source"""
    output = entry.get("output", "")
    for index, arg in enumerate(args):
        if arg == "-o" and index + 1 < len(args):
            output = output or args[index + 1]
        elif arg.startswith("/Fo") or arg.startswith("-Fo"):
            output = output or arg[3:]
    match = re.search(r"CMakeFiles/([^/]+)\.dir/", util.normpath(output))
    return match[1] if match else os.path.dirname(file)


def translation_units(database, extra_macros=(), ignore_targets=()):
    """[(target, file, settings)] of the C++ translation units, the file as an absolute path with /, without the
    targets that match a glob in ignore_targets"""
    units = []
    for entry in database:
        args = arguments(entry)
        file = entry.get("file", "")
        if not file:
            continue
        file = util.normpath(os.path.normpath(os.path.join(entry.get("directory", ""), file)))
        unit_target = target(entry, args, file)
        if is_cpp(file, args) and not any(fnmatch.fnmatchcase(unit_target, glob) for glob in ignore_targets):
            units.append((unit_target, file, settings(args, extra_macros)))
    return units


def find_inconsistencies(units, ignore_settings=()):
    """[(file, setting, value, norm, target, files with value in target, units with norm)] for every target and
    setting where (some of) the target differs from the value that most translation units use"""
    names = sorted({name for _target, _file, values in units for name in values} - set(ignore_settings))
    found = []
    for name in names:
        # a translation unit without the macro or flag has the default value
        missing = DEFAULT if name == "language standard" or name in FLAG_SETTINGS else NOT_DEFINED
        counts = Counter(values.get(name, missing) for _target, _file, values in units)
        if len(counts) < 2:
            continue
        norm, norm_count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        groups = {}
        for unit_target, file, values in units:
            value = values.get(name, missing)
            if value != norm:
                groups.setdefault((unit_target, value), []).append(file)
        for (unit_target, value), files in sorted(groups.items()):
            found.append((sorted(files)[0], name, value, norm, unit_target, len(files), norm_count))
    return sorted(found)


def report_issue(file, line, description):
    links = util.create_link(3, util.urljoin("[[permalink-prefix]]", file) + ("#L" + str(line) if line else ""))
    links += util.create_link(5, util.RULES_DOCUMENTATION_URL + "#" + util.heading_anchor(RULE))
    util.report(Priority.UNASSIGNED.value, "", "", file + (":" + str(line) if line else ""), "opencanary", RULE, CATEGORY,
                description, links)


def describe(setting, value, norm, unit_target, count, norm_count):
    files = "1 file" if count == 1 else f"{count} files"
    return (f"{setting} is {value} for {files} of {unit_target}, but {norm} for {norm_count} other translation units: "
            "a type that depends on it gets two definitions in one program (ODR violation)")


def load(path):
    if os.path.isdir(path):
        path = os.path.join(path, "compile_commands.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="compile_commands.json, or the build directory that contains it")
    parser.add_argument("--macro", action="append", default=[], help="also compare this macro (a glob)")
    parser.add_argument("--ignore-setting", action="append", default=[], help="do not compare this setting")
    parser.add_argument("--ignore-target", action="append", default=[], help="leave out this target (a glob)")
    args = parser.parse_args()

    units = translation_units(load(args.path), args.macro, args.ignore_target)
    for file, setting, value, norm, unit_target, count, norm_count in find_inconsistencies(units, args.ignore_setting):
        report_issue(file, 0, describe(setting, value, norm, unit_target, count, norm_count))
    util.eprint(f"compile_flags.py: {len(units)} C++ translation units compared")


if __name__ == "__main__":
    util.run_main(main, show_usage)

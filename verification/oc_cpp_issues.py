#!/usr/bin/env python3
"""Checks c++ projects
- using namespace is not allowed in header files
- treatwarningaserror should be true in all configurations
- warninglevel should be 4 in all configurations
- use std::make_unique iso custom implementations
- with --mark-comments, an issue that is only found in a comment gets the category 'comments'
- see https://github.com/janwilmans/OpenCanary/issues/4

"""

import argparse
import os
import re
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

import gitignore_parser
import util
from util import Priority, eprint

ns = '{http://schemas.microsoft.com/developer/msbuild/2003}'

ignore_rule_list = []

wrong_word_list = [
    'accomodate', 'aquire', 'arguement', 'athiest', 'belive', 'bizzare', 'calender', 'carribean',
    'cemetary', 'cheif', 'collegue', 'columist', 'commitee', 'comitted', 'concensus',
    'definately', 'dilemna', 'dissapoint', 'embarras', 'embarassed', 'enviroment', 'exilerate',
    'facinate', 'florescent', 'foriegn', 'fourty', 'freind', 'goverment', 'greatful',
    'happend', 'harras', 'horderves', 'humourous', 'immediatly', 'independant',
    'knowlege', 'liesure', 'liason', 'maintanance', 'manuever',
    'medival', 'millenium', 'minature', 'mischevious', 'mispell', 'nausious',
    'neccessary', 'ocassion', 'occured', 'paralel', 'parralel', 'perseverence',
    'phillipines', 'playwrite', 'privelege', 'publically', 'questionaire', 'recieve', 'recomend',
    'resistence', 'responsability', 'rythm', 'sacreligious', 'seige', 'seperate', 'strenght',
    'succesful', 'successfull', 'sucessful', 'supercede', 'tatoo', 'tendancy', 'threshhold', 'tollerance',
    'truely', 'unecessary', 'unforseen', 'untill', 'vacum', 'viscious', 'visibile', 'wether',
    'wich', 'wierd', 'whereever', 'writting', 'yatch', 'zealos', 'unkown', 'nolonger'
]


def rip_grep(rootpath):
    """the output of one ripgrep run for all words of wrong_word_list in rootpath, empty when ripgrep is not installed"""
    command = ["rg", "-o", "-n", "-w", "--column", "--color=never", "--no-heading", "--with-filename"]
    for word in wrong_word_list:
        command += ["-e", word]
    # without a path (and with a stdin that is not a terminal, as in CI) ripgrep searches stdin instead of the directory
    command += ["--", "."]
    try:
        return subprocess.run(command, cwd=rootpath, check=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace").stdout
    except FileNotFoundError:
        eprint("ripgrep (rg) not found, spelling check (misspelled-word) skipped")
        return ""


def get_spelling_violations(rg_output, rootpath, files):
    """(filename, line_number, word) for every 'path:line:column:word' line of rg_output whose path, relative to
    rootpath, is one of files (absolute paths), so the spelling check covers the same files as the other checks"""
    checked = {os.path.normcase(file) for file in files}
    result = []
    for line in rg_output.splitlines():
        parts = line.rsplit(":", 3)
        if len(parts) != 4 or not parts[1].isdigit():
            continue
        filename = os.path.abspath(os.path.join(rootpath, parts[0]))
        if os.path.normcase(filename) in checked:
            result += [(filename, parts[1], parts[3])]
    return result


def get_project_xml_root(projectname):
    project_tree = ET.parse(projectname)
    return project_tree.getroot()


def get_include_files_from_project(project_root, project_directory):
    result = []
    for include_section in project_root.iter(ns + 'ClInclude'):
        relative_filename = include_section.get('Include')
        result += [os.path.join(project_directory, relative_filename)]
    return result


def get_cpp_files_from_project(project_root, project_directory):
    result = []
    for include_section in project_root.iter(ns + 'ClCompile'):
        relative_filename = include_section.get('Include')
        if relative_filename is not None:
            result += [os.path.join(project_directory, relative_filename)]
    return result


def check_source_line(filename, line_number, line, report):
    check_line(filename, line_number, line, report, SOURCE_LINE_RULES)


COMMENTS_CATEGORY = "comments"  # the category of an issue that is only found in a comment, see --mark-comments


def without_comments(lines):
    """the lines with every comment replaced by spaces (line endings are kept), so checking these lines finds only
    what is in the code; string and character literals are kept, a // or /* inside one does not start a comment"""
    result = []
    in_block = False
    for line in lines:
        # fast paths: most lines have no comment and no literal, or are completely inside a /* */ comment
        if not in_block and "/" not in line and '"' not in line and "'" not in line:
            result.append(line)
            continue
        if in_block and "*/" not in line:
            result.append(re.sub(r"[^\r\n]", " ", line))
            continue
        code = []
        quote = None  # unterminated literals end at the end of the line
        i = 0
        while i < len(line):
            char, pair = line[i], line[i:i + 2]
            if in_block:
                if pair == "*/":
                    in_block = False
                    code.append("  ")
                    i += 2
                    continue
                code.append(char if char in "\r\n" else " ")
            elif quote:
                code.append(char)
                if char == "\\":
                    code.append(line[i + 1:i + 2])
                    i += 1
                elif char == quote:
                    quote = None
            elif pair == "//":
                code.append(re.sub(r"[^\r\n]", " ", line[i:]))
                break
            elif pair == "/*":
                in_block = True
                code.append("  ")
                i += 2
                continue
            else:
                # a ' between two letters or digits is a digit separator (1'000), not the start of a character literal
                if char == '"' or (char == "'" and not (line[i - 1:i].isalnum() and line[i + 1:i + 2].isalnum())):
                    quote = char
                code.append(char)
            i += 1
        result.append("".join(code))
    return result


def check_cpp_file(filename, check_file_line, mark_comments):
    """check every line with check_file_line(filename, line_number, line, report), and the includes, and report the
    issues; with mark_comments, an issue that is not found again with the comments removed (it was only matched inside
    a comment) gets the category COMMENTS_CATEGORY"""
    lines = read_lines(filename)
    issues = []
    collect = lambda *issue: issues.append(issue)
    for line_number, line in enumerate(lines, 1):
        check_file_line(filename, line_number, line, collect)
    check_includes(filename, lines, collect)
    if mark_comments and issues:
        code = without_comments(lines)
        in_code = set()
        add = lambda _filename, line, rule, *_: in_code.add((line, rule))
        # only the lines with an issue are checked again, the includes need the lines before them
        for line_number in sorted({int(issue[1]) for issue in issues}):
            check_file_line(filename, line_number, code[line_number - 1], add)
        check_includes(filename, code, add)
        issues = [issue if (issue[1], issue[2]) in in_code else (*issue[:3], COMMENTS_CATEGORY, issue[4]) for issue in issues]
    for issue in issues:
        report_issue(*issue)


def read_lines(filename):
    with open(filename, encoding='utf-8') as f:  # , errors='ignore'
        return f.readlines()


def get_priority():
    # assignment of priority is done in apply_team_priorities.py
    return Priority.UNASSIGNED.value


def get_source():
    # fixed source string for OpenCanary
    return "opencanary"

# we do not have the information about the location of the repo here
# [[permalink-prefix]] is replaced in apply_environment.py


def create_default_link(filename, line):
    url = util.urljoin("[[permalink-prefix]]", util.normpath(filename))
    if line == 0:
        links = util.create_link(3, url)
    else:
        links = util.create_link(3, url + "#L" + line)
    return links


def report_issue_detail(fileref, filename, line, rule, description, component, category):
    # the rule links to its section in documentation/rules.md, why it is reported and how to solve it
    links = create_default_link(filename, line) + util.create_link(5, util.RULES_DOCUMENTATION_URL + "#" + util.heading_anchor(rule))
    team = ""
    component = ""
    util.report(get_priority(), team, component, fileref,
                get_source(), rule, category, description, links)


def report_issue(filename, line, rule, category, description):
    if len(str(line)) > 0:
        fileref = filename + ":" + line
    else:
        fileref = filename
    report_issue_detail(fileref, filename, line, rule, description, "", category)


def is_generated(filename):
    dirname = os.path.dirname(filename)
    basename = os.path.basename(os.path.normpath(dirname)).lower()
    if basename == "gen":
        return True
    return basename == "gen64"


def clean_group(match_group):
    return match_group.group(1).replace("\n", "")


def check_line(filename, line_number, line, report, rules=None):
    try:
        check_line_impl(filename, str(line_number), line, report, LINE_RULES if rules is None else rules)
    except:
        eprint("open canary parsing error: ", filename + ":" + str(line_number))
        eprint(line)
        raise


# rule names are lowercase words separated by "-" like the clang warnings, but must not be the name of a compiler warning:
# rules/priorities.txt matches on the rule name only, and its ~ matchers for compiler warnings (such as ~comment) must not
# match it either; test_every_rule_has_a_section_and_a_solution_link checks this, see documentation/rules.md
# every rule is (rule, category, regex, description); {match} in the description is replaced by the first group of the
# match; documentation/details.md lists the patterns and documentation/rules.md explains each rule
LINE_RULES = [
    ("make-unique-header", "modernize", r"#\s*include\s*[\"<][^\">]*\bmake_unique\b", "For C++14 and later use #include <memory>"),
    ("unqualified-make-unique", "modernize", r"(?<!std::)\bmake_unique\s*<", "For C++14 and later use std::make_unique"),
    ("reinterpret-cast", "casting", r"reinterpret_cast<", "Anti-pattern: do not reinterpret_cast"),
    ("volatile-variable", "redflag", r"^(?!.*\bextern\s+volatile\b).*\bvolatile\b.*;", "Anti-pattern: do not use volatile"),
    ("null-macro", "modernize", r"\bNULL\b", "Anti-pattern: do not use NULL, use 0 or nullptr instead"),
    ("non-english-word", "readability", r"(?i)(\sdeze\s|\sniet\s|\w+ectie|\snaam\s|\sals\s|voet)", "Anti-pattern: do not use non-english words ('{match}') in code or comments"),
    ("constant-if-directive", "readability", r"(#\s*if\s*\(?\s*\d)", "Anti-pattern: {match}, do not keep historical code in ifdefs"),
    ("c-style-pointer-cast", "modernize", r"\(\w+\s*\*\s*\)", "Anti-pattern: dont use c-style casts"),
    ("reserved-macro-name", "ub", r"#define\s+(_\w+|\w*__\w*)", "prevent UB: names starting with an underscore or containing a double underscore ({match}) are reserved"),
    ("min-max-macro", "modernize", r"(?i)#define.*((min|max).*\(.*?.*:.*$)", "Anti-pattern: do not define {match}, use std::min and std::max"),
    ("extern", "redflag", r"\bextern\s+(?!\"|template\b|volatile\b)", "Anti-pattern: do not use extern"),
    ("manual-delete", "redflag", r"^(?!.*(=\s*delete\b|\boperator\s+delete\b)).*\bdelete\b\s*(\[\s*\])?\s*[\w(*:][^;]*;", "Anti-pattern: do not use delete"),
    ("extern-volatile", "redflag", r"\bextern\s+volatile\b", "Anti-pattern: extern volatile ?!"),
    ("string-literal-cast", "ub", r"\(char\s*\*\)\s*\"", "prevent UB: do not cast away constness of string literals"),
    ("const-cast", "readability", r"const_cast<", "Anti-pattern: do not cast away constness"),
    ("assign-in-condition", "assign_in_condition", r"(while|if|switch)\s*\(.*\s=\s.*\)", "Anti-pattern: do not assign inside conditions"),
    ("throw-pointer", "redflag", r"\bthrow\s+new\b", "do not throw a pointer, throw by value and catch by reference"),
    ("throw-non-exception", "redflag", r"\bthrow\s+(\"|'|-?\d)", "throw an exception class, not a string or a number"),
    ("memset-zero-size", "bug", r"\bmemset\s*\(.*,\s*0\s*\)\s*;", "memset with size 0 does nothing, are the last two arguments swapped?"),
    ("void-pointer-pointer-cast", "ub", r"\(\s*void\s*\*\s*\*\s*\)|reinterpret_cast\s*<\s*void\s*\*\s*\*\s*>", "prevent UB: writing through a T** cast to void** breaks strict aliasing"),
    ("string-braced-size", "bug", r"\bstd::w?string\s+\w+\s*\{\s*\d+\s*\}", "std::string s{n} is a string of one character n, use std::string s(n, 0) for n characters"),
    ("undef-macro", "redflag", r"^\s*#\s*undef\b", "#undef changes a macro for everything that is included after it"),
    ("assign-to-self", "bug", r"(?<![\w.>:*&])(\w+)\s*=\s*\1\s*;", "assignment of a variable to itself"),
    ("include-source-file", "redflag", r"#\s*include\s*[\"<][^\">]*\.(cpp|cc|cxx)[\">]", "do not include a source file, it is compiled twice (odr violation)"),
    ("short-macro-name", "redflag", r"#\s*define\s+\w{1,3}\b", "a macro with a name of 3 characters or less clashes easily"),
    ("catch-by-value", "redflag", r"\bcatch\s*\(\s*[^&*.)\s][^&*.)]*\)", "catch exceptions by (const) reference, catching by value slices"),
    ("reset-with-new", "modernize", r"\.reset\s*\(\s*new\b", "use std::make_unique or std::make_shared instead of reset(new ...)"),
    ("deprecated-uncaught-exception", "modernize", r"\buncaught_exception\s*\(", "std::uncaught_exception is deprecated in C++17 and removed in C++20, use std::uncaught_exceptions"),
    ("triple-pointer", "readability", r"\w\s*\*\s*\*\s*\*(?=\s*[\w)>,])", "a pointer to a pointer to a pointer is hard to understand"),
    ("empty-special-member", "modernize", r"\b(\w+)::~?\1\s*\(\s*\)\s*\{\s*\}", "an empty constructor or destructor, remove it or use = default"),
    ("todo", "readability", r"(?i)\btodo\b", "a todo is left in the code"),
    ("address-null-check", "ub", r"(?<![&\w)\]])&\s*\w+\s*[!=]=\s*nullptr|\bnullptr\s*[!=]=\s*&\s*\w", "prevent UB: the address of a reference or object is never nullptr, the compiler may remove the check"),
    ("endless-for", "readability", r"\bfor\s*\(\s*;\s*;\s*\)", "use while (true) for an endless loop, it is clearer"),
    ("foreach-macro", "modernize", r"\b(foreach|Q_FOREACH|BOOST_FOREACH)\s*\(", "use a range-based for loop instead of a foreach macro"),
    ("dangling-range-for", "bug", r"\bfor\s*\(.*:\s*[\w:.>-]*\w\([^()]*\)\s*(\.|->)\s*\w+\([^()]*\)\s*\)", "a range-based for over a member of a temporary can dangle (before C++23)"),
    ("redundant-semicolon", "readability", r"^(?!.*\bfor\s*\().*;\s*;", "redundant semicolon"),
    ("short-include-guard", "readability", r"^\s*#\s*define\s+(?=\w{1,8}\s*$)(\w*_(H|HPP|HXX|INCLUDED)_?)\s*$", "include guard {match} is not unique enough"),
]

# only in sources: in headers these are mostly members, initialized by a constructor
SOURCE_LINE_RULES = LINE_RULES + [
    ("uninitialized-variable", "ub", r"^\s*(int|bool|double|float)\s+\w+\s*;", "initialize variables where they are declared"),
]

HEADER_LINE_RULES = LINE_RULES + [
    ("using-namespace-in-header", "redflag", r"^\s*using\s+namespace\b", "Using namespace found in header file"),
]


def check_line_impl(filename, line_number, line, report, rules):
    for rule, category, regex, description in rules:
        match = re.search(regex, line)
        if match:
            if "{match}" in description:
                description = description.replace("{match}", clean_group(match))
            report(filename, line_number, rule, category, description)


def check_includes(filename, lines, report):
    """self-include and duplicate-include: rules that need the other lines of the file"""
    seen = set()
    for line_number, line in enumerate(lines, 1):
        match = re.match(r"\s*#\s*include\s*[\"<]([^\">]+)[\">]", line)
        if not match:
            continue
        included = match[1].replace("\\", "/")
        if os.path.basename(included) == os.path.basename(filename) and os.path.splitext(filename)[1].lower() in (".h", ".hpp"):
            report(filename, str(line_number), "self-include", "bug", f"the header includes itself ({included})")
        if included in seen:
            report(filename, str(line_number), "duplicate-include", "readability", f"{included} is already included")
        seen.add(included)


def check_header_line(filename, line_number, line, report):
    check_line(filename, line_number, line, report, HEADER_LINE_RULES)


def check_spelling(rootpath, files, mark_comments):
    code = {}  # filename: its lines without comments, only read for files with a misspelled word
    for filename, line_number, word in get_spelling_violations(rip_grep(rootpath), rootpath, files):
        category = "spelling"
        if mark_comments:
            if filename not in code:
                code[filename] = without_comments(read_lines(filename))
            line = code[filename][int(line_number) - 1] if int(line_number) <= len(code[filename]) else ""
            if not re.search(r"\b" + re.escape(word) + r"\b", line):
                category = COMMENTS_CATEGORY
        report_issue(filename, line_number, "misspelled-word", category, f"Misspelled word '{word}' found")


def check_project(projectname):
    project_root = get_project_xml_root(projectname)

    # checks for cpp/header files are done recursively from a directory iso the project
    # checks for missing files moved to checkvsproject.py since they are not c++ project specific.

    for item_definition_group_node in project_root.iter(ns + 'ItemDefinitionGroup'):
        # print (itemDefinitionGroupNode.tag + " " + itemDefinitionGroupNode.get("Condition"))
        cl_compile_node = item_definition_group_node.find(ns + 'ClCompile')
        if not cl_compile_node is None:
            warning_as_error_node = cl_compile_node.find(ns + 'TreatWarningAsError')
            if not warning_as_error_node is None:  # noqa: SIM102
                # print (warningAsErrorNode.tag + " " + warningAsErrorNode.text)
                if warning_as_error_node.text.lower() == "true":
                    continue
        report_issue(projectname, "0", "warnings-not-errors", "redflag", "TreatWarningAsError is not set to true")

    for item_definition_group_node in project_root.iter(ns + 'ItemDefinitionGroup'):
        # print (itemDefinitionGroupNode.tag + " " + itemDefinitionGroupNode.get("Condition"))
        cl_compile_node = item_definition_group_node.find(ns + 'ClCompile')
        if not cl_compile_node is None:
            warning_level = cl_compile_node.find(ns + 'WarningLevel')
            if not warning_level is None:
                # print (warningAsErrorNode.tag + " " + warningAsErrorNode.text)
                if warning_level.text.endswith("4"):
                    continue
        report_issue(projectname, "0", "warning-level-not-4", "redflag", "Warning level is not set to 4")


def get_projects_recursively(path):
    result = []
    for root, _dirs, files in gitignore_parser.walk(path, filenames=['.opencanaryignore']):
        for file in files:
            if file.endswith("proj"):
                project = os.path.abspath(root + "\\" + file)
                # print ("Found " + project)
                result += [project]
    return result


def read_ignore_file(ignorefile, basepath):
    if not os.path.exists(ignorefile):
        return

    eprint("reading:", ignorefile)
    global ignore_rule_list
    ignore_rule_list += gitignore_parser.rules_from_file(ignorefile, basepath)


def main():
    parser = argparse.ArgumentParser(description="Checks C++ sources and Visual Studio projects for common problems.")
    parser.add_argument("path", help="location to search for c++ sources recursively")
    parser.add_argument("--mark-comments", action="store_true",
                        help=f"an issue that is only found in a comment gets the category '{COMMENTS_CATEGORY}'")
    args = parser.parse_args()

    rootpath = os.path.abspath(args.path)

    eprint("checking folder", rootpath, "(recursively)")
    projects = get_projects_recursively(rootpath)
    for project in projects:
        # eprint("checking " + project)
        try:
            check_project(project)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            # info = traceback.format_exc()
            # eprint(info)                   # uncomment to debug parsing issues
            # maybe related: https://stackoverflow.com/questions/31390213/how-to-parse-an-xml-file-with-encoding-declaration-in-python
            report_issue(project, "0", "parse-error", "parse", "Could not parse project file")

    headers, cpps = util.get_cpp_files_from_directory(rootpath)
    for filename in headers:
        try:
            check_cpp_file(filename, check_header_line, args.mark_comments)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            eprint("OC Error parsing header:", filename, "\n", e, "\n\n")
            report_issue(filename, "", "parse-error", "parse", "Could not parse header file")

    for filename in cpps:
        try:
            check_cpp_file(filename, check_source_line, args.mark_comments)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            eprint("OC Error parsing source:", filename, "\n", e, "\n\n")
            report_issue(filename, "", "parse-error", "parse", "Could not parse source file")

    check_spelling(rootpath, headers + cpps, args.mark_comments)

    sys.stdout.flush()
    eprint(str(len(projects)) + " msvc project(s) checked")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        sys.exit(1)

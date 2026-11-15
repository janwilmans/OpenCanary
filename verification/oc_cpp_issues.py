#!/usr/bin/env python3
""" Search C++ headers, sources and Visual Studio projects for common problems that compilers do not report.

    The checks are plain text searches, without a C++ parser:
    - line rules (LINE_RULES, SOURCE_LINE_RULES, HEADER_LINE_RULES): a regex per rule, matched against the code of
      every line only: comments and the contents of string literals are blanked, so commented out code and text such
      as 'returns NULL' are not reported; COMMENT_LINE_RULES (todo) only look at the comments, and
      CODE_AND_COMMENT_LINE_RULES (non-english-word) at both
    - whole-file rules (check_whole_file): self-include, duplicate-include, undef-macro, short-macro-name, empty-catch,
      also only in the code
    - misspelled-word: the words of wrong_word_list, anywhere in the file (code, comments and literals)
    - project rules: TreatWarningAsError and WarningLevel 4 in every configuration of a *proj file
    - cmake rule: hardcoded-cxx-standard, a C++ standard set in a CMakeLists.txt or *.cmake file other than the top level
      CMakeLists.txt of <path> and the files that it includes by path
    - file rule: file-name-case-clash, headers and sources whose directory and name only differ in case
      (util/header.h and Util/Header.h, also in different libraries)

    Files and directories listed in a .opencanaryignore file (.gitignore syntax) are skipped. Every issue is written
    to stdout as an OpenCanary issue line with source 'opencanary' and priority 99 (apply_team_priorities.py assigns
    the real one). Why each rule is reported and how to solve it: documentation/rules.md; the patterns:
    documentation/details.md.

    Usage: oc_cpp_issues.py <path>
      <path>  directory that is searched recursively
"""

import argparse
import os
import re
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


WRONG_WORDS = frozenset(wrong_word_list)
WORD = re.compile(r"\w+")  # a whole word: letters, digits and underscores, as grep -w and rg -w


def check_spelling(filename, lines, report):
    """misspelled-word for every word of wrong_word_list in the lines (code, literals and comments, case sensitive);
    the whole file is checked first, a misspelling is rare and splitting the lines is slower"""
    if WRONG_WORDS.isdisjoint(WORD.findall("".join(lines))):
        return
    for line_number, line in enumerate(lines, 1):
        for word in WORD.findall(line):
            if word in WRONG_WORDS:
                report(filename, str(line_number), "misspelled-word", "spelling", f"Misspelled word '{word}' found")


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


CODE, LITERAL, COMMENT = "c", "s", "m"  # what a character of a line is, see classify()


def classify(lines):
    """per line None when the whole line is code, or a string of the same length that says what each character is:
    CODE, LITERAL (the contents of a string or character literal, not its quotes) or COMMENT (including the // or /* */);
    a /* */ comment continues on the next lines, a // or /* inside a literal does not start a comment"""
    result = []
    in_block = False
    for line in lines:
        # fast paths: most lines have no comment and no literal, or are completely inside a /* */ comment
        if not in_block and "/" not in line and '"' not in line and "'" not in line:
            result.append(None)
            continue
        if in_block and "*/" not in line:
            result.append(COMMENT * len(line))
            continue
        mask = []
        quote = None  # unterminated literals end at the end of the line
        i = 0
        while i < len(line):
            char, pair = line[i], line[i:i + 2]
            if in_block:
                if pair == "*/":
                    in_block = False
                    mask.append(COMMENT * 2)
                    i += 2
                    continue
                mask.append(COMMENT)
            elif quote:
                if char == quote:
                    quote = None
                    mask.append(CODE)
                elif char == "\\":
                    mask.append(LITERAL * len(line[i:i + 2]))
                    i += 1
                else:
                    mask.append(LITERAL)
            elif pair == "//":
                mask.append(COMMENT * (len(line) - i))
                break
            elif pair == "/*":
                in_block = True
                mask.append(COMMENT * 2)
                i += 2
                continue
            else:
                # a ' between two letters or digits is a digit separator (1'000), not the start of a character literal
                if char == '"' or (char == "'" and not (line[i - 1:i].isalnum() and line[i + 1:i + 2].isalnum())):
                    quote = char
                mask.append(CODE)
            i += 1
        result.append("".join(mask))
    return result


def view(lines, masks, keep):
    """the lines with every character that is not of a kind in 'keep' replaced by a space (line endings are kept); the
    file name of an #include is kept as code, rules such as include-source-file look at it"""
    result = []
    for line, mask in zip(lines, masks):
        if mask is None:
            result.append(line if CODE in keep else re.sub(r"[^\r\n]", " ", line))
            continue
        if LITERAL not in keep and re.match(r"\s*#\s*include\b", line):
            mask = mask.replace(LITERAL, CODE)
        parts, start = [], 0
        for run in re.finditer(f"[^{keep}]+", mask):
            parts += [line[start:run.start()], re.sub(r"[^\r\n]", " ", line[run.start():run.end()])]
            start = run.end()
        result.append("".join(parts) + line[start:])
    return result


def check_cpp_file(filename, check_file_line):
    for issue in find_issues(filename, read_lines(filename), check_file_line):
        report_issue(*issue)


def find_issues(filename, lines, check_file_line):
    """the issues of the lines of a file. A C++ rule is about code, so check_file_line(filename, line_number, line,
    report) and the rules that need the whole file only look at the code: comments and the contents of string literals
    are blanked (a commented out line is not reported, and neither is text such as 'returns NULL'). COMMENT_LINE_RULES
    look only at the comments, CODE_AND_COMMENT_LINE_RULES at both, and the spelling check at everything"""
    masks = classify(lines)
    code = view(lines, masks, CODE)
    issues = []
    collect = lambda *issue: issues.append(issue)
    for line_number, (line, mask) in enumerate(zip(code, masks), 1):
        check_file_line(filename, line_number, line, collect)
        if mask is not None and COMMENT in mask:
            original = lines[line_number - 1]
            check_line(filename, line_number, view([original], [mask], COMMENT)[0], collect, COMMENT_LINE_RULES)
            check_line(filename, line_number, view([original], [mask], CODE + COMMENT)[0], collect, CODE_AND_COMMENT_LINE_RULES)
        else:
            check_line(filename, line_number, line, collect, CODE_AND_COMMENT_LINE_RULES)
    check_whole_file(filename, code, lambda: view(lines, masks, CODE + COMMENT), collect)
    check_spelling(filename, lines, collect)
    return issues


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
    ("constant-if-directive", "readability", r"(#\s*if\s*\(?\s*\d)", "Anti-pattern: {match}, do not keep historical code in ifdefs"),
    # (type *) followed by the expression that is cast: not a parameter list, a SLOT() signature or sizeof(T *);
    # (void **) is void-pointer-pointer-cast
    ("c-style-pointer-cast", "modernize",
     (r"(?<!sizeof)(?<!sizeof )(?<!alignof)(?<!alignof )\((?!\s*void\s*\*\s*\*\s*\))\s*((const|volatile|unsigned|signed|struct|class|enum)\s+)*"
      r"[A-Za-z_]\w*(::[A-Za-z_]\w*)*(\s*<[^()]*>)?\s*(const\s*)?(\*\s*(const\s*)?)+\)(?!\s*(const|override|final|noexcept|volatile|throw)\b)"
      r"\s*([\w&(*\"!~]|-(?!>))"),
     "Anti-pattern: dont use c-style casts"),
    ("reserved-macro-name", "ub", r"#define\s+(_\w+|\w*__\w*)", "prevent UB: names starting with an underscore or containing a double underscore ({match}) are reserved"),
    ("min-max-macro", "modernize", r"(?i)#\s*define\s+(min|max)\s*\(", "Anti-pattern: do not define a {match} macro, use std::min and std::max"),
    ("extern", "redflag", r"\bextern\s+(?!\"|template\b|volatile\b)", "Anti-pattern: do not use extern"),
    ("manual-delete", "redflag", r"^(?!.*(=\s*delete\b|\boperator\s+delete\b)).*\bdelete\b\s*(\[\s*\])?\s*[\w(*:][^;]*;", "Anti-pattern: do not use delete"),
    ("extern-volatile", "redflag", r"\bextern\s+volatile\b", "Anti-pattern: extern volatile ?!"),
    ("string-literal-cast", "ub", r"\(char\s*\*\)\s*\"", "prevent UB: do not cast away constness of string literals"),
    ("const-cast", "readability", r"const_cast<", "Anti-pattern: do not cast away constness"),
    # the condition is <lvalue> = ...: not a declaration (if (auto x = f())), an init-statement (if (auto x = f(); x))
    # or an assignment in extra parentheses (if ((x = f()))), the usual way to say that it is intended
    ("assign-in-condition", "bug", r"\b(while|if|switch)\s*\(\s*[\w.\->\[\]*]+\s=\s([^;()]|\([^;()]*\))*\)",
     "Anti-pattern: do not assign inside conditions"),
    ("throw-pointer", "redflag", r"\bthrow\s+new\b", "do not throw a pointer, throw by value and catch by reference"),
    ("throw-non-exception", "redflag", r"\bthrow\s+(\"|'|-?\d)", "throw an exception class, not a string or a number"),
    ("memset-zero-size", "bug", r"\bmemset\s*\(.*,\s*0\s*\)\s*;", "memset with size 0 does nothing, are the last two arguments swapped?"),
    ("void-pointer-pointer-cast", "ub", r"\(\s*void\s*\*\s*\*\s*\)|reinterpret_cast\s*<\s*void\s*\*\s*\*\s*>", "prevent UB: writing through a T** cast to void** breaks strict aliasing"),
    ("string-braced-size", "bug", r"\bstd::w?string\s+\w+\s*\{\s*\d+\s*\}", "std::string s{n} is a string of one character n, use std::string s(n, 0) for n characters"),
    ("assign-to-self", "bug", r"(?<![\w.>:*&])(\w+)\s*=\s*\1\s*;", "assignment of a variable to itself"),
    ("include-source-file", "redflag", r"#\s*include\s*[\"<][^\">]*\.(cpp|cc|cxx)[\">]", "do not include a source file, it is compiled twice (odr violation)"),
    ("catch-by-value", "redflag", r"\bcatch\s*\(\s*[^&*.)\s][^&*.)]*\)", "catch exceptions by (const) reference, catching by value slices"),
    ("reset-with-new", "modernize", r"\.reset\s*\(\s*new\b", "use std::make_unique or std::make_shared instead of reset(new ...)"),
    ("deprecated-uncaught-exception", "modernize", r"\buncaught_exception\s*\(", "std::uncaught_exception is deprecated in C++17 and removed in C++20, use std::uncaught_exceptions"),
    ("triple-pointer", "readability", r"\w\s*\*\s*\*\s*\*(?=\s*[\w)>,])", "a pointer to a pointer to a pointer is hard to understand"),
    ("empty-special-member", "modernize", r"\b(\w+)::~?\1\s*\(\s*\)\s*\{\s*\}", "an empty constructor or destructor, remove it or use = default"),
    ("address-null-check", "ub", r"(?<![&\w)\]])&\s*\w+\s*[!=]=\s*nullptr|\bnullptr\s*[!=]=\s*&\s*\w", "prevent UB: the address of a reference or object is never nullptr, the compiler may remove the check"),
    ("endless-for", "readability", r"\bfor\s*\(\s*;\s*;\s*\)", "use while (true) for an endless loop, it is clearer"),
    ("foreach-macro", "modernize", r"\b(foreach|Q_FOREACH|BOOST_FOREACH)\s*\(", "use a range-based for loop instead of a foreach macro"),
    ("dangling-range-for", "bug", r"\bfor\s*\(.*:\s*[\w:.>-]*\w\([^()]*\)\s*(\.|->)\s*\w+\([^()]*\)\s*\)", "a range-based for over a member of a temporary can dangle (before C++23)"),
    ("redundant-semicolon", "readability", r"^(?!.*\bfor\s*\().*;\s*;", "redundant semicolon"),
    ("short-include-guard", "readability", r"^\s*#\s*define\s+(?=\w{1,8}\s*$)(\w*_(H|HPP|HXX|INCLUDED)_?)\s*$", "include guard {match} is not unique enough"),
]

# only in sources: in headers these are mostly members, initialized by a constructor
LINE_RULES += [
    # a lock that is not a variable is a temporary, released at the end of the statement; not return std::unique_lock(m);
    ("unnamed-lock", "bug",
     r"^\s*(std::)?(lock_guard|unique_lock|scoped_lock|shared_lock|QMutexLocker|QReadLocker|QWriteLocker)\s*(<[^;]*>)?\s*[({][^;]*[)}]\s*;",
     "the lock is a temporary, it is released at the end of the statement: give it a name"),
    ("suppressed-warning", "redflag", r"#\s*pragma\s+(warning\s*\(\s*(disable|suppress|push\s*,\s*0)\b|(GCC|clang)\s+diagnostic\s+ignored\b)",
     "a compiler warning is suppressed, the build log does not show what it hides"),
]

# rules about comments, they only look at the comments of a line
COMMENT_LINE_RULES = [
    ("todo", "readability", r"(?i)\btodo\b", "a todo is left in the code"),
]

# rules about the words in names and comments, they look at the code and the comments of a line
CODE_AND_COMMENT_LINE_RULES = [
    ("non-english-word", "readability", r"(?i)(\sdeze\s|\sniet\s|\w+ectie|\snaam\s|\sals\s|voet)", "Anti-pattern: do not use non-english words ('{match}') in code or comments"),
]

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


def includes_itself(filename, included, quoted):
    """True when the #include of 'included' in 'filename' is the file itself: "x.h" is first searched next to the
    file, and a path with a directory (module/x.h) is the file when the path of the file ends with it; a bare <x.h>
    is searched in the include directories only, a wrapper header with the name of the real one does that"""
    path = util.normpath(os.path.normcase(os.path.abspath(filename)))
    included = util.normpath(os.path.normcase(included))  # normcase turns / into \ on Windows
    if quoted and util.normpath(os.path.normpath(os.path.join(os.path.dirname(path), included))) == path:
        return True
    return "/" in included and path.endswith("/" + included.lstrip("./"))


def check_whole_file(filename, code, code_and_comments, report):
    """the rules that need the other lines of the file; code are the lines without comments and literal contents,
    code_and_comments() returns them with the comments"""
    check_includes(filename, code, report)
    check_macros(filename, code, report)
    check_empty_catch(filename, code, code_and_comments, report)


def check_empty_catch(filename, code, code_and_comments, report):
    """a catch block with nothing in it, also when it spans lines; a comment in it says that this is intended, so the
    block is looked at with its comments, and the catch itself must be code (not in a comment)"""
    code_text = "".join(code)
    if "catch" not in code_text:
        return
    text = "".join(code_and_comments())  # the same length as code_text, the comments are blanked in that one
    for match in re.finditer(r"\bcatch\s*\([^)]*\)\s*\{\s*\}", text):
        if code_text.startswith("catch", match.start()):
            line_number = text.count("\n", 0, match.start()) + 1
            report(filename, str(line_number), "empty-catch", "redflag", "an empty catch block swallows the exception")


def check_macros(filename, lines, report):
    """undef-macro and short-macro-name, but not for a local helper macro: one that the file defines and #undefs"""
    defines, undefs = [], []
    for line_number, line in enumerate(lines, 1):
        match = re.match(r"\s*#\s*(define|undef)\s+(\w+)", line)
        if match:
            (defines if match[1] == "define" else undefs).append((line_number, match[2]))
    for line_number, name in undefs:
        if not any(name == defined and number < line_number for number, defined in defines):
            report(filename, str(line_number), "undef-macro", "redflag", "#undef changes a macro for everything that is included after it")
    for line_number, name in defines:
        if len(name) <= 3 and not any(name == undefined and number > line_number for number, undefined in undefs):
            report(filename, str(line_number), "short-macro-name", "redflag", "a macro with a name of 3 characters or less clashes easily")


def check_includes(filename, lines, report):
    """self-include and duplicate-include: rules that need the other lines of the file; an #include is only a
    duplicate of one in the same or an enclosing #if/#elif/#else branch, not of one in another branch"""
    seen = {}  # included: the branches (tuples of branch numbers, outermost first) it is included in
    branches, number = [], 0
    is_header = os.path.splitext(filename)[1].lower() in (".h", ".hpp")
    for line_number, line in enumerate(lines, 1):
        directive = re.match(r"\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b", line)
        if directive:
            number += 1
            if directive[1].startswith("if"):
                branches.append(number)
            elif branches and directive[1] == "endif":
                branches.pop()
            elif branches:
                branches[-1] = number
            continue
        match = re.match(r"\s*#\s*include\s*([\"<])([^\">]+)[\">]", line)
        if not match:
            continue
        included = match[2].replace("\\", "/")
        if is_header and includes_itself(filename, included, match[1] == '"'):
            report(filename, str(line_number), "self-include", "bug", f"the header includes itself ({included})")
        here = tuple(branches)
        if any(here[:len(earlier)] == earlier for earlier in seen.get(included, [])):
            report(filename, str(line_number), "duplicate-include", "readability", f"{included} is already included")
        seen.setdefault(included, []).append(here)


def check_header_line(filename, line_number, line, report):
    check_line(filename, line_number, line, report, HEADER_LINE_RULES)


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


def get_build_files_recursively(path):
    """the Visual Studio projects (*proj) and the CMake files (CMakeLists.txt, *.cmake) below path"""
    projects = []
    cmake_files = []
    for root, _dirs, files in gitignore_parser.walk(path, filenames=['.opencanaryignore']):
        for file in files:
            if file.endswith("proj"):
                projects.append(os.path.abspath(os.path.join(root, file)))
            elif file == "CMakeLists.txt" or file.endswith(".cmake"):
                cmake_files.append(os.path.abspath(os.path.join(root, file)))
    return projects, cmake_files


# set(CMAKE_CXX_STANDARD 14), the CXX_STANDARD 14 property of a target, or -std=c++14 / /std:c++14 in the flags
CMAKE_CXX_STANDARD = re.compile(r"\b(?:set\s*\(\s*(CMAKE_CXX_STANDARD)|(CXX_STANDARD))\s+\"?(\d+)|[-/]std[=:](?:c|gnu)\+\+(\w+)", re.IGNORECASE)
# if(NOT DEFINED CMAKE_CXX_STANDARD) or if(NOT CMAKE_CXX_STANDARD): the set() is a default, not a fixed standard
CMAKE_CXX_STANDARD_GUARD = re.compile(r"\bNOT\s+(?:DEFINED\s+)?CMAKE_CXX_STANDARD\b", re.IGNORECASE)
CMAKE_INCLUDE = re.compile(r"^\s*include\s*\(\s*\"?([^)\s\"]+)", re.IGNORECASE | re.MULTILINE)
CMAKE_ROOT_VARIABLES = ("${CMAKE_CURRENT_SOURCE_DIR}", "${CMAKE_SOURCE_DIR}", "${PROJECT_SOURCE_DIR}", "${CMAKE_CURRENT_LIST_DIR}")


def cmake_code(line):
    """the line without its # comment ('#' inside a quoted string is not a comment)"""
    quoted = False
    for index, char in enumerate(line):
        if char == '"' and (index == 0 or line[index - 1] != "\\"):
            quoted = not quoted
        elif char == "#" and not quoted:
            return line[:index]
    return line


def top_level_cmake_files(rootpath):
    """the top level CMakeLists.txt and the files that it include()s by path: where the standard of the whole program
    belongs"""
    top = os.path.join(rootpath, "CMakeLists.txt")
    result = {os.path.normcase(top)}
    if os.path.exists(top):
        code = "\n".join(cmake_code(line) for line in read_lines(top))
        for included in CMAKE_INCLUDE.findall(code):
            for variable in CMAKE_ROOT_VARIABLES:
                included = included.replace(variable, rootpath)
            path = os.path.join(rootpath, included)
            if os.path.isfile(path):
                result.add(os.path.normcase(os.path.abspath(path)))
    return result


def check_cmake_file(filename, report):
    lines = [cmake_code(line) for line in read_lines(filename)]
    guarded = any(CMAKE_CXX_STANDARD_GUARD.search(line) for line in lines)
    for line_number, line in enumerate(lines, 1):
        for match in CMAKE_CXX_STANDARD.finditer(line):
            if match[1] and guarded:
                continue
            what = "set(CMAKE_CXX_STANDARD)" if match[1] else "the CXX_STANDARD property" if match[2] else "a -std flag"
            level = match[3] or match[4]
            report(filename, str(line_number), "hardcoded-cxx-standard", "redflag",
                   f"the C++ standard is fixed with {what} in a part of the build, instead of once for the whole program; "
                   f"state the minimum with target_compile_features(<target> PUBLIC cxx_std_{level})")


def directory_and_name(filename):
    """the last directory and the name of the file, util/header.h for src/liba/include/util/header.h"""
    return "/".join(util.normpath(filename).split("/")[-2:])


def check_file_name_case(filenames, rootpath, report):
    """files whose last directory and name only differ in case (util/header.h and Util/Header.h), also in different
    parts of the tree: a file system that ignores case (Windows, macOS) cannot hold both in one directory, and with
    both on the include path #include "util/header.h" can no longer tell them apart"""
    groups = {}
    for filename in filenames:
        groups.setdefault(directory_and_name(filename).lower(), []).append(filename)
    for group in groups.values():
        if len({directory_and_name(filename) for filename in group}) < 2:
            continue  # spelled the same everywhere: not a case problem
        for filename in group:
            others = sorted(util.normpath(os.path.relpath(other, rootpath)) for other in group
                            if directory_and_name(other) != directory_and_name(filename))
            report(filename, "1", "file-name-case-clash", "redflag",
                   f"{directory_and_name(filename)} only differs in case from {', '.join(others)}; a file system that "
                   f"ignores case (Windows, macOS) cannot tell them apart")


def read_ignore_file(ignorefile, basepath):
    if not os.path.exists(ignorefile):
        return

    eprint("reading:", ignorefile)
    global ignore_rule_list
    ignore_rule_list += gitignore_parser.rules_from_file(ignorefile, basepath)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="location to search for c++ sources recursively")
    args = parser.parse_args()

    rootpath = os.path.abspath(args.path)

    eprint("checking folder", rootpath, "(recursively)")
    projects, cmake_files = get_build_files_recursively(rootpath)
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

    top_level = top_level_cmake_files(rootpath)
    for filename in cmake_files:
        if os.path.normcase(filename) not in top_level:
            check_cmake_file(filename, report_issue)

    headers, cpps = util.get_cpp_files_from_directory(rootpath)
    check_file_name_case(headers + cpps, rootpath, report_issue)
    for filename in headers:
        try:
            check_cpp_file(filename, check_header_line)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            eprint("OC Error parsing header:", filename, "\n", e, "\n\n")
            report_issue(filename, "", "parse-error", "parse", "Could not parse header file")

    for filename in cpps:
        try:
            check_cpp_file(filename, check_source_line)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            eprint("OC Error parsing source:", filename, "\n", e, "\n\n")
            report_issue(filename, "", "parse-error", "parse", "Could not parse source file")


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

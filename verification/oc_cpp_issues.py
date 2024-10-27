#!/usr/bin/env python3
"""Checks c++ projects
- using namespace is not allowed in header files
- treatwarningaserror should be true in all configurations
- warninglevel should be 4 in all configurations
- use std::make_unique iso custom implementations
- see https://github.com/janwilmans/OpenCanary/issues/4

"""

import traceback
import sys
import os
import re
import xml.etree.ElementTree as ET
import gitignore_parser
import subprocess

import util
from util import Priority, eprint

ns = '{http://schemas.microsoft.com/developer/msbuild/2003}'

ignore_rule_list = []

wrong_word_list = [
    'accomodate', 'aquire', 'arguement', 'athiest', 'belive', 'bizzare', 'calender', 'carribean',
    'cemetary', 'cheif', 'collegue', 'collectable', 'columist', 'commitee', 'comitted', 'concensus',
    'definately', 'dilemna', 'dissapoint', 'embarras', 'embarassed', 'enviroment', 'exilerate',
    'facinate', 'florescent', 'foriegn', 'fourty', 'freind', 'greyscale', 'goverment', 'greatful',
    'happend', 'harras', 'horderves', 'humourous', 'immediatly', 'independant', 'jewelry',
    'knowlege', 'liesure', 'liason', 'lightening', 'maintanance', 'manuever',
    'medival', 'mementos', 'millenium', 'minature', 'mischevious', 'mispell', 'nausious',
    'neccessary', 'ocassion', 'occured', 'paralel', 'parralel', 'pavilion', 'perseverence',
    'phillipines', 'playwrite', 'privelege', 'publically', 'questionaire', 'recieve', 'recomend',
    'resistence', 'responsability', 'rythm', 'sacreligious', 'seige', 'seperate', 'strenght',
    'succesful', 'successfull', 'sucessful', 'supercede', 'tatoo', 'tendancy', 'threshhold', 'tollerance',
    'truely', 'unecessary', 'unforseen', 'untill', 'vacum', 'viscious', 'visibile', 'weather', 'wether',
    'wich', 'wierd', 'whereever', 'writting', 'yatch', 'zealos', 'unkown', 'nolonger'
]


def rip_grep(word):
    result = []
    command = f"rg -o -n -w --color=never --no-heading --with-filename --column {word}"
    rg_result = subprocess.run(command, check=False, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in rg_result.stdout.splitlines():
        if line.strip() != "":
            result += [[line, word]]
    return result


def get_spelling_violations():
    result = []
    for word in wrong_word_list:
        result += rip_grep(word)
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


def check_cpp_source(filename):
    line_number = 0
    for line in read_lines(filename):
        line_number = line_number + 1
        check_line(filename, line_number, line)


def read_lines(filename):
    return open(filename, encoding='utf-8').readlines()  # , errors='ignore'


def get_priority():
    # assignment of priority is done in apply_team_priorities.py
    return Priority.UNSET.value


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
    links = create_default_link(filename, line)
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
    if basename == "gen64":
        return True
    return False


def clean_group(match_group):
    return match_group.group(1).replace("\n", "")


def check_line(filename, line_number, line):
    try:
        check_line_impl(filename, str(line_number), line)
    except:
        eprint("open canary parsing error: ", filename + ":" + line_number)
        eprint(line)
        raise


# Rule numbering is continuous over the prefix, in the sense that #1 occurs only once so MO#1, MO#2, AP#3
def check_line_impl(filename, line_number, line):
    if "/make_unique" in line:
        report_issue(filename, line_number, "MO#1", "modernize", "For C++14 and later use #include <memory>")
    else:
        if "make_unique" in line and not "std::make_unique" in line:
            report_issue(filename, line_number, "MO#2", "modernize", "For C++14 and later use std::make_unique")

    if "reinterpret_cast<" in line:
        report_issue(filename, line_number, "AP#3", "casting", "Anti-pattern: do not reinterpret_cast")

    if re.search(r"[^a-z]volatile[^a-z].*;", line):
        report_issue(filename, line_number, "AP#4", "redflag", "Anti-pattern: do not use volatile")
    if re.search(r"\sNULL\s", line):
        report_issue(filename, line_number, "MO#5", "modernize", "Anti-pattern: do not use NULL, use 0 or nullptr instead")

    match_group = re.search(r"(\sdeze\s|\sniet\s|\w+ectie|\snaam\s|\sals\s|voet)", line, re.IGNORECASE)
    if match_group:
        report_issue(filename, line_number, "AP#6", "readability", f"Anti-pattern: do not use non-english words ('{clean_group(match_group)}') in code or comments")
    match_group = re.search(r"(#if\s+\d)", line)
    if match_group:
        report_issue(filename, line_number, "AP#7", "readability", f"Anti-pattern: {clean_group(match_group)}, do not keep historical code in ifdefs")
    if re.search(r"\(\w+\s*\*\s*\)", line):
        report_issue(filename, line_number, "AP#8", "modernize", "Anti-pattern: dont use c-style casts")
    match_group = re.search(r"#define\s+(_\w+)", line)
    if match_group:
        report_issue(filename, line_number, "AP#9", "ub", "prevent UB: names starting with underscore, followed by a capital ({clean_group(match_group)}) are reserved ")
    match_group = re.search(r"#define.*((min|max).*\(.*?.*:.*$)", line, re.IGNORECASE)
    if match_group:
        report_issue(filename, line_number, "AP#10", "modernize", f"Anti-pattern: do not define {clean_group(match_group)}, use std::min and std::max")
    if re.search(r"($|[^\w])extern\s+[^\"]", line):
        report_issue(filename, line_number, "AP#11", "redflag", "Anti-pattern: do not use extern")

    #    if re.search("($|[^\w])register\s", line):
    #        report_issue(filename, str(lineNumber), "AP#12", "redflag", "Anti-pattern: do not use register") # disabled because of too many false positives, and also compilers already catch it

    if re.search(r"($|[^\w])delete\s\w{1,25};", line):
        report_issue(filename, line_number, "AP#13", "redflag", "Anti-pattern: do not use delete")
    if "extern volatile" in line:
        report_issue(filename, line_number, "AP#14", r"redflag", "Anti-pattern: extern volatile ?!")
    if re.search(r"\(char\s*\*\)\s*\"", line):
        report_issue(filename, line_number, "AP#15", "ub", "prevent UB: do not cast away constness of string literals")
    if re.search(r"const_cast<", line):
        report_issue(filename, line_number, "AP#16", "readability", "Anti-pattern: do not cast away constness")

    #  AP#17 see checkCppHeader_AP17()

    if re.search(r"(while|if|switch)\s*\(.*\s=\s.*\)", line):
        report_issue(filename, line_number, "AP#18", "assign_in_condition", "Anti-pattern: do not assign inside conditions")

    # if "catch\s+\(...\)" in line:
    # if "catch\s+(...).*\n*.*\{[\n.]*throw[\n.]*\}" in line:
    #    report_issue(filename, str(lineNumber), "AP#", "redflag", "Anti-pattern: catch(...) should always rethrow")    # too many false positives

    # would be nice for new code, but is too generic (and should be allowed in Qt code)
    # if "new" in line and not "#define new" in line:
    #    report_issue(filename, str(lineNumber), "MO#", "Prefer std::make_unique over bare new/delete")

    # Current highest number at:  #19


def check_cpp_header_AP17(filename):
    line_number = 0
    for line in read_lines(filename):
        line_number = line_number + 1
        check_line(filename, line_number, line)
        if re.search("^using namespace", line):
            report_issue(filename, str(line_number), "AP#17", "redflag", "Using namespace found in header file")


def get_file_reference(file):
    pattern = r'^.*(:\d*)?(:\d*)?'
    match = re.search(pattern, file)
    if match:
        return match.group(0)
    return file


def get_filename_and_line(file):
    pattern = r'(^.*):(\d+)'
    match = re.search(pattern, file)
    if match.groups().count == 2:
        return match.group(0), match.group(1)
    return file, 0


def check_spelling_AP19():
    for file, word in get_spelling_violations():
        category = "spelling"
        description = f"Missspelled word '{word}' found'"
        # util.report(get_priority(), team, component, fileref, source, "AP#19", category, description, links)
        # report_issue(filename, str(line_number), "AP#19", "spelling", f"Missspelled word '{word}' found'")
        fileref = get_file_reference(file)
        filename, line_number = get_filename_and_line(fileref)
        print(f"fileref: {fileref}, filename: '{filename}', line_number: {line_number}")

        # report_issue_detail(fileref, filename, line_number, "AP#19", description, "", category)


def check_project(projectname):
    project_root = get_project_xml_root(projectname)

    # checks for cpp/header files are done recursively from a directory iso the project
    # checks for missing files moved to checkvsproject.py since they are not c++ project specific.

    for item_definition_group_node in project_root.iter(ns + 'ItemDefinitionGroup'):
        # print (itemDefinitionGroupNode.tag + " " + itemDefinitionGroupNode.get("Condition"))
        cl_compile_node = item_definition_group_node.find(ns + 'ClCompile')
        if not cl_compile_node is None:
            warning_as_error_node = cl_compile_node.find(ns + 'TreatWarningAsError')
            if not warning_as_error_node is None:
                # print (warningAsErrorNode.tag + " " + warningAsErrorNode.text)
                if warning_as_error_node.text.lower() == "true":
                    continue
        report_issue(projectname, "0", "UD#4", "redflag", "TreatWarningAsError is not set to true")

    for item_definition_group_node in project_root.iter(ns + 'ItemDefinitionGroup'):
        # print (itemDefinitionGroupNode.tag + " " + itemDefinitionGroupNode.get("Condition"))
        cl_compile_node = item_definition_group_node.find(ns + 'ClCompile')
        if not cl_compile_node is None:
            warning_level = cl_compile_node.find(ns + 'WarningLevel')
            if not warning_level is None:
                # print (warningAsErrorNode.tag + " " + warningAsErrorNode.text)
                if warning_level.text.endswith("4"):
                    continue
        report_issue(projectname, "0", "UD#5", "redflag", "Warning level is not set to 4")


def get_projects_recursively(path):
    result = []
    for root, _dirs, files in gitignore_parser.walk(path, filenames=['.opencanaryignore']):
        for file in files:
            if file.endswith("proj"):
                project = os.path.abspath(root + "\\" + file)
                # print ("Found " + project)
                result += [project]
    return result


def show_usage():
    if len(sys.argv) > 1:
        eprint("  I got:", sys.argv)
        eprint("")
    eprint(r"Usage: " + os.path.basename(__file__) + " <path>")
    eprint(r"  <path>: location to search for c++ sources recursively")
    eprint("")


def read_ignore_file(ignorefile, basepath):
    if not os.path.exists(ignorefile):
        return

    eprint("reading:", ignorefile)
    global ignore_rule_list
    ignore_rule_list += gitignore_parser.rules_from_file(ignorefile, basepath)


def main():
    if not len(sys.argv) == 2:
        eprint("error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    check_spelling_AP19()

    rootpath = os.path.abspath(sys.argv[1])

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
            report_issue(project, "0", "PARSE", "parse", "Could not parse project file")

    headers, cpps = util.get_cpp_files_from_directory(rootpath)
    for filename in headers:
        try:
            check_cpp_header_AP17(filename)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            eprint("OC Error parsing header:", filename, "\n", e, "\n\n")
            report_issue(filename, "", "PARSE", "parse", "Could not parse header file")

    for filename in cpps:
        try:
            check_cpp_source(filename)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            eprint("OC Error parsing source:", filename, "\n", e, "\n\n")
            report_issue(filename, "", "PARSE", "parse", "Could not parse source file")

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

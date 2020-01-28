#!/usr/bin/env python3
"""Checks c++ projects
- using namespace is not allowed in header files
- treatwarningaserror should be true in all configurations
- warninglevel should be 4 in all configurations
- use std::make_unique iso custom implementations

-
"""

import traceback, sys, os, time
import gitignore_parser
import xml.etree.ElementTree as ET
from util import *

ns = '{http://schemas.microsoft.com/developer/msbuild/2003}'

ignore_rule_list = []


def getProjectXMLRoot(projectname):
    projectTree = ET.parse(projectname)
    return projectTree.getroot()


def getIncludeFilesFromProject(projectRoot, projectDirectory):
    result = []
    for includeSection in projectRoot.iter(ns + 'ClInclude'):
        relativeFilename = includeSection.get('Include')
        result += [os.path.join(projectDirectory, relativeFilename)]
    return result


def getCppFilesFromProject(projectRoot, projectDirectory):
    result = []
    for includeSection in projectRoot.iter(ns + 'ClCompile'):
        relativeFilename = includeSection.get('Include')
        if relativeFilename is not None:
            result += [os.path.join(projectDirectory, relativeFilename)]
    return result


def get_cpp_files_from_directory(path):
    global rootpath
    rootpath = os.path.abspath(path)
    headers = []
    cpps = []

    for root, dirs, files in gitignore_parser.walk(path, filenames=['.opencanaryignore']):
        for file in files:
            filename = os.path.abspath(os.path.join(root, file))
            if file.endswith(".h") or file.endswith(".hpp"):
                headers += [filename]
            if file.endswith(".cpp") or file.endswith(".cc"):
                cpps += [filename]
    return headers, cpps


def checkCppSource(filename):
    lineNumber = 0
    for line in read_lines(filename):
        lineNumber = lineNumber + 1
        check_line(filename, lineNumber, line)


def read_lines(filename):
    return open(filename, encoding='utf-8').readlines()  # , errors='ignore'


def makeRelative(filename):
    global rootpath
    return os.path.relpath(filename, rootpath)


def get_priority(rule):
    # prime number 3 means: no specific priority assigned
    # assignment of priority is done in apply_team_priorities.py
    return 3


# we do not have the information about the location of the repo here
# [[permalink-prefix]] is replaced in apply_environment.py
def create_default_link(filename, line):
    url = urljoin("[[permalink-prefix]]", normpath(filename))
    if line == 0:
        links = create_link(3, url)
    else:
        links = create_link(3, url + "#L" + line)
    return links


def report_issue_detail(fileref, filename, line, rule, description, component, category):
    links = create_default_link(filename, line)
    team = ""
    component = ""
    source = "opencanary"
    report(get_priority(rule), team, component, fileref, source, rule, category, description, links)


def report_issue(filename, line, rule, category, description):
    filename = makeRelative(filename)
    component = ""
    team = ""
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


def clean_group(matchGroup):
    return matchGroup.group(1).replace("\n", "")


def check_line(filename, lineNumber, line):
    try:
        check_line_impl(filename, lineNumber, line)
    except:
        eprint("open canary parsing error: ", filename + ":" + lineNumber)
        eprint(line)
        raise


# Rule numbering is continuous over the prefix, in the sense that #1 occurs only once so MO#1, MO#2, AP#3
def check_line_impl(filename, lineNumber, line):
    if "/make_unique" in line:
        report_issue(filename, str(lineNumber), "MO#1", "modernize", "For C++14 and later use #include <memory>")
    else:
        if "make_unique" in line and not "std::make_unique" in line:
            report_issue(filename, str(lineNumber), "MO#2", "modernize", "For C++14 and later use std::make_unique")

    if "reinterpret_cast<" in line:
        report_issue(filename, str(lineNumber), "AP#3", "casting", "Anti-pattern: do not reinterpret_cast")

    if re.search("[^a-z]volatile[^a-z].*;", line):
        report_issue(filename, str(lineNumber), "AP#4", "redflag", "Anti-pattern: do not use volatile")
    if re.search("\sNULL\s", line):
        report_issue(filename, str(lineNumber), "MO#5", "modernize",
                     "Anti-pattern: do not use NULL, use 0 or nullptr instead")

    matchGroup = re.search("(\sdeze\s|\sniet\s|\w+ectie|\snaam\s|\sals\s|voet)", line, re.IGNORECASE)
    if matchGroup:
        report_issue(filename, str(lineNumber), "AP#6", "readability",
                     "Anti-pattern: do not use non-english words ('{}') in code or comments".format(
                         clean_group(matchGroup)))
    matchGroup = re.search("(#if\s+\d)", line)
    if matchGroup:
        report_issue(filename, str(lineNumber), "AP#7", "readability",
                     "Anti-pattern: {}, do not keep historical code in ifdefs".format(clean_group(matchGroup)))
    if re.search("\(\w+\s*\*\s*\)", line):
        report_issue(filename, str(lineNumber), "AP#8", "modernize", "Anti-pattern: dont use c-style casts")
    matchGroup = re.search("#define\s+(_\w+)", line)
    if matchGroup:
        report_issue(filename, str(lineNumber), "AP#9", "ub",
                     "prevent UB: names starting with underscore, followed by a capital ({}) are reserved ".format(
                         clean_group(matchGroup)))
    matchGroup = re.search("#define.*((min|max).*\(.*?.*:.*$)", line, re.IGNORECASE)
    if matchGroup:
        report_issue(filename, str(lineNumber), "AP#10", "modernize",
                     "Anti-pattern: do not define {}, use std::min and std::max".format(clean_group(matchGroup)))
    if re.search("($|[^\w])extern\s+[^\"]", line):
        report_issue(filename, str(lineNumber), "AP#11", "redflag", "Anti-pattern: do not use extern")

    #    if re.search("($|[^\w])register\s", line):
    #        report_issue(filename, str(lineNumber), "AP#12", "redflag", "Anti-pattern: do not use register") # disabled because of too many false positives, and also compilers already catch it

    if re.search("($|[^\w])delete\s\w{1,25};", line):
        report_issue(filename, str(lineNumber), "AP#13", "redflag", "Anti-pattern: do not use delete")
    if "extern volatile" in line:
        report_issue(filename, str(lineNumber), "AP#14", "redflag", "Anti-pattern: extern volatile ?!")
    if re.search("\(char\s*\*\)\s*\"", line):
        report_issue(filename, str(lineNumber), "AP#15", "ub",
                     "prevent UB: do not cast away constness of string literals")
    if re.search("const_cast<", line):
        report_issue(filename, str(lineNumber), "AP#16", "casting", "Anti-pattern: do not cast away constness")

    # if "catch\s+\(...\)" in line:
    # if "catch\s+(...).*\n*.*\{[\n.]*throw[\n.]*\}" in line:
    #    report_issue(filename, str(lineNumber), "AP#", "redflag", "Anti-pattern: catch(...) should always rethrow")    # too many false positives

    # would be nice for new code, but is too generic (and should be allowed in Qt code)
    # if "new" in line and not "#define new" in line:
    #    report_issue(filename, str(lineNumber), "MO#", "Prefer std::make_unique over bare new/delete")

    # Current highest number at:  #17 , see also checkCppHeader()


def check_cpp_header(filename):
    lineNumber = 0
    for line in read_lines(filename):
        lineNumber = lineNumber + 1
        check_line(filename, lineNumber, line)
        if re.search("^using namespace", line):
            report_issue(filename, str(lineNumber), "AP#17", "redflag", "Using namespace found in header file")


def check_project(projectname):
    projectRoot = getProjectXMLRoot(projectname)

    # checks for cpp/header files are done recursively from a directory iso the project
    # checks for missing files moved to checkvsproject.py since they are not c++ project specific.

    for itemDefinitionGroupNode in projectRoot.iter(ns + 'ItemDefinitionGroup'):
        # print (itemDefinitionGroupNode.tag + " " + itemDefinitionGroupNode.get("Condition"))
        clCompileNode = itemDefinitionGroupNode.find(ns + 'ClCompile')
        if not clCompileNode is None:
            warningAsErrorNode = clCompileNode.find(ns + 'TreatWarningAsError')
            if not warningAsErrorNode is None:
                # print (warningAsErrorNode.tag + " " + warningAsErrorNode.text)
                if warningAsErrorNode.text.lower() == "true":
                    continue
        report_issue(projectname, "0", "UD#4", "redflag", "TreatWarningAsError is not set to true")

    for itemDefinitionGroupNode in projectRoot.iter(ns + 'ItemDefinitionGroup'):
        # print (itemDefinitionGroupNode.tag + " " + itemDefinitionGroupNode.get("Condition"))
        clCompileNode = itemDefinitionGroupNode.find(ns + 'ClCompile')
        if not clCompileNode is None:
            warningLevel = clCompileNode.find(ns + 'WarningLevel')
            if not warningLevel is None:
                # print (warningAsErrorNode.tag + " " + warningAsErrorNode.text)
                if warningLevel.text.endswith("4"):
                    continue
        report_issue(projectname, "0", "UD#5", "redflag", "Warning level is not set to 4")


def get_projects_recursively(path):
    result = []
    for root, dirs, files in gitignore_parser.walk(path, filenames=['.opencanaryignore']):
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


def in_ignore_rule_list(path):
    global ignore_rule_list

    return True


def main():
    if not len(sys.argv) == 2:
        eprint("error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    global rootpath
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

    headers, cpps = get_cpp_files_from_directory(rootpath)
    for filename in headers:
        try:
            check_cpp_header(filename)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            eprint("OC Error parsing header:", filename, "\n", e, "\n\n")
            report_issue(filename, "", "PARSE", "parse", "Could not parse header file")

    for filename in cpps:
        try:
            checkCppSource(filename)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            eprint("OC Error parsing source:", filename, "\n", e, "\n\n")
            report_issue(filename, "", "PARSE", "parse", "Could not parse source file")

    sys.stdout.flush()
    eprint(str(len(projects)) + " project(s) checked")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        sys.exit(1)

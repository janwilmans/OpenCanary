"""Checks c++ projects
- using namespace is not allowed in header files
- treatwarningaserror should be true in all configurations
- warninglevel should be 4 in all configurations
- use std::make_unique iso custom implementations
"""

from __future__ import print_function
import traceback, sys, os, time
import xml.etree.ElementTree as ET

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    
def sprint(*args, **kwargs):
    print(*args, file=sys.stdout, **kwargs)

def scriptName():
    return __file__.split(os.sep)[-1:][0]

ns = '{http://schemas.microsoft.com/developer/msbuild/2003}'

def getProjectXMLRoot(projectname):
    projectTree = ET.parse(projectname)
    return projectTree.getroot()

def getIncludeFilesFromProject(projectRoot, projectDirectory):
    result = []
    for includeSection in projectRoot.iter(ns+'ClInclude'):
        relativeFilename = includeSection.get('Include')
        result += [projectDirectory + "\\" + relativeFilename]
    return result

def getCppFilesFromProject(projectRoot, projectDirectory):
    result = []
    for includeSection in projectRoot.iter(ns+'ClCompile'):
        relativeFilename = includeSection.get('Include')
        if relativeFilename != None:
            result += [projectDirectory + "\\" + relativeFilename]
    return result

def getCppFilesFromDirectory(path):
    global rootpath
    rootpath = os.path.abspath(path)
    headers = []
    cpps = []

    for root, dirs, files in os.walk(path):
        for file in files:
            if (file.endswith(".h") or file.endswith(".hpp")):
                filename = os.path.abspath(root + "\\" + file)
                headers += [filename]
            if (file.endswith(".cpp")):
                filename = os.path.abspath(root + "\\" + file)
                cpps += [filename]
    return headers, cpps

def checkLine(filename, lineNumber, line):
    if "/make_unique" in line:
        reportIssue(filename, str(lineNumber), "UD#2", "For C++11 and later use #include <memory>")
    if "make_unique" in line and not "std::make_unique" in line and not "/make_unique" in line:
        reportIssue(filename, str(lineNumber), "UD#2", "For C++11 and later use std::make_unique")

    # maybe too generic, but would be nice for new code.
    if "new" in line and not "#define new" in line:
        reportIssue(filename, str(lineNumber), "UD#3", "Prefer std::make_unique over bare new/delete")

def checkCppSource(filename):
    lineNumber = 0
    for line in readLines(filename):
        lineNumber = lineNumber + 1
        checkLine(filename, lineNumber, line)

def readLines(filename):
    result = []
    with open(filename) as f:
        for line in f:
            result += [line]
    return result

def makeRelative(filename):
    global rootpath
    return os.path.relpath(filename, rootpath + "\\..")

def stripPreFix(filename):
    return makeRelative(filename)[4:]

def reportIssue(filename, line, rule, description):
    report(10, "tin", "tin", filename, line, "opencanary", rule, "cppproject", description, "[3](https://gitlab.kindtechnologies.nl/OOAKT/tin/blob/master/" + stripPreFix(filename) + "#L" + str(line) + ")")

def report(priority, team, component, filename, line, source, rule, category, description, link):
    s = "|"
    print (str(priority) + s + team + s + component + s + makeRelative(filename) + ":" + str(line) + s + source + s + rule + s + category + s + description + s + link)

def isGenerated(filename):
    dirname = os.path.dirname(filename)
    basename = os.path.basename(os.path.normpath(dirname)).lower()
    if (basename == "gen"):
        return True
    if (basename == "gen64"):
        return True
    return False

def checkCppHeader(filename):
    lineNumber = 0
    for line in readLines(filename):
        lineNumber = lineNumber + 1
        checkLine(filename, lineNumber, line)
        if "using namespace" in line:
            reportIssue(filename, str(lineNumber), "UD#3", "Using namespace found in header file")

def checkproject(projectname):
    projectRoot = getProjectXMLRoot(projectname)
    projectDirectory = os.path.dirname(os.path.abspath(projectname))
    
    # checks for cpp/header files are done recursively from a directory iso the project
    # checks for missing files moved to checkvsproject.py since they are not c++ project specific.

    for itemDefinitionGroupNode in projectRoot.iter(ns+'ItemDefinitionGroup'):
        #print (itemDefinitionGroupNode.tag + " " + itemDefinitionGroupNode.get("Condition"))
        clCompileNode = itemDefinitionGroupNode.find(ns+'ClCompile')
        if not clCompileNode is None:
            warningAsErrorNode = clCompileNode.find(ns+'TreatWarningAsError')
            if (not warningAsErrorNode is None):
                #print (warningAsErrorNode.tag + " " + warningAsErrorNode.text)
                if warningAsErrorNode.text.lower() == "true":
                    continue
        reportIssue(projectname, "0", "UD#4", "TreatWarningAsError is not set to true")

    for itemDefinitionGroupNode in projectRoot.iter(ns+'ItemDefinitionGroup'):
        #print (itemDefinitionGroupNode.tag + " " + itemDefinitionGroupNode.get("Condition"))
        clCompileNode = itemDefinitionGroupNode.find(ns+'ClCompile')
        if not clCompileNode is None:
            warningLevel = clCompileNode.find(ns+'WarningLevel')
            if (not warningLevel is None):
                #print (warningAsErrorNode.tag + " " + warningAsErrorNode.text)
                if warningLevel.text.endswith("4"):
                    continue
        reportIssue(projectname, "0", "UD#5", "Warning level is not set to 4")

def getProjectsRecursively(path):
    global rootpath
    rootpath = os.path.abspath(path)
    result = []

    for root, dirs, files in os.walk(path):
        for file in files:
            if (file.endswith("proj")):
                project = os.path.abspath(root + "\\" + file)
                #print ("Found " + project)
                result += [project]
    return result

def scriptName():
    return __file__.split(os.sep)[-1:][0]

def showUsage():
    eprint("Usage: " + scriptName() + " <path>")
    eprint("   path: location to search for c++ sources recursively")

def main():
    if not len(sys.argv) == 2:
        eprint("error: invalid argument(s)\n")
        showUsage()
        sys.exit(1)

    try:
        eprint("checking folder (recursively) " + sys.argv[1])
        projects = getProjectsRecursively(sys.argv[1])
        for project in projects:
            eprint ("checking " + project)
            try:
                checkproject(project)
            except:
                info = traceback.format_exc()
                #eprint(info)                   # uncomment to debug parsing issues
                # maybe related: https://stackoverflow.com/questions/31390213/how-to-parse-an-xml-file-with-encoding-declaration-in-python
                reportIssue(project, "0", "PARSE", "Could not parse project file")

        headers, cpps = getCppFilesFromDirectory(sys.argv[1])
        for filename in headers:
            try:
                checkCppHeader(filename)
            except:
                info = traceback.format_exc()
                reportIssue(filename, "0", "PARSE", "Could not parse source file")
        for filename in cpps:
            try:
                checkCppSource(filename)
            except:
                info = traceback.format_exc()
                reportIssue(filename, "0", "PARSE", "Could not parse source file")

        sys.stdout.flush()
        eprint(str(len(projects)) + " project(s) checked")
    except:
        info = traceback.format_exc()
        print(info)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        info = traceback.format_exc()
        eprint(info)
        showUsage()
        sys.exit(1)

	
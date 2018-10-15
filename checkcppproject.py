"""Checks c++ projects

- using namespace is not allowed in header files
- treatwarningaserror should be true in all configurations
- warninglevel should be 4 in all configurations
- use std::make_unique iso custom implementations

"""

from __future__ import print_function
import traceback, sys, os, time
import xml.etree.ElementTree as ET

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

def checkLine(filename, lineNumber, line):
    if "/make_unique" in line:
        reportIssue(filename, str(lineNumber), "UD#2", "For C++11 and later use #include <memory>")
    if "make_unique" in line and not "std::make_unique" in line and not "/make_unique" in line:
        reportIssue(filename, str(lineNumber), "UD#2", "For C++11 and later use std::make_unique")
    #if "new" in line and not "#define new" in line:
    #    reportIssue(filename, str(lineNumber), "UD#3", "Prefer std::make_unique over bare new/delete")
    # too generic, but would be nice for new code.

def checkCppSource(filename):
    #print (filename)
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
    return os.path.relpath(filename, rootpath + "\\..").replace("\\", "/")  # include one level up prefix in the relative path (MOTION\)

def reportIssue(filename, line, rule, description):
    reportIssue7(filename, line, "opencanary", rule, "1", "cppproject", description)

def reportIssue7(filename, line, category, rule, level, group, description):
    s = "|"
    print (makeRelative(filename) + s + line + s + category + s + rule + s + level + s + group + s + description + s)

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
    for filename in getIncludeFilesFromProject(projectRoot, projectDirectory):
        if os.path.exists(filename):
            checkCppHeader(filename)

    for filename in getCppFilesFromProject(projectRoot, projectDirectory):
        if os.path.exists(filename):
            checkCppSource(filename)

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

def main():
    try:
        projects = getProjectsRecursively(sys.argv[1])
        for project in projects:
            #print ("Checking " + project)
            checkproject(project)
        #print(str(len(projects)) + " project(s) checked")
    except:
        info = traceback.format_exc()
        print(info)

if __name__ == "__main__":
    main()
    sys.exit(0)

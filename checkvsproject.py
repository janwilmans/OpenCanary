"""Checks the completeness of visual studio projects

- any file missing on disk but referenced in the project can cause a full rebuild 
"""

from __future__ import print_function
import traceback, sys, os
import xml.etree.ElementTree as ET

fileNotFoundCount = 0
projectWithNotFoundFilesCount = 0

def makeRelative(filename):
    global rootpath
    return os.path.relpath(filename, rootpath + "\\..").replace("\\", "/")  # include one level up prefix in the relative path (MOTION\)

def reportIssue(filename ,line, rule, description):
    reportIssue7(filename, line, "opencanary", rule, "1", "missing files", description)

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
    
def checkproject(projectname):
    
    global fileNotFoundCount
    global projectWithNotFoundFilesCount

    filtersname = projectname + ".filters"
    if not os.path.exists(filtersname):
        return
    
    ns = '{http://schemas.microsoft.com/developer/msbuild/2003}'
    
    # first collect all files from the .filters files 

    filterTree = ET.parse(filtersname)
    filterRoot = filterTree.getroot()
    filterDict = dict()                  # [file] -> [filter] all files in a map to lookup in what filter section a file was
    missingDict = dict()                 # [filter] -> [] per-filter map of files from .filters not on found on disk

    for inc in filterRoot.iter(ns+'ClInclude'):
        incFileRel = inc.get('Include')
        incFilter = inc.find(ns+'Filter')
        if incFileRel == None or incFilter == None:
            continue
        filterDict[incFileRel] = incFilter.text
        if incFilter.text not in missingDict:
            missingDict[incFilter.text] = set([])
        incFile = os.path.abspath( os.path.dirname(projectname) +"\\"+ incFileRel )
        if not os.path.exists(incFile):
            if not isGenerated(incFile):
                missingDict[incFilter.text].add(incFileRel)

    projTree = ET.parse(projectname)
    projRoot = projTree.getroot()
    
    for inc in projRoot.iter(ns+'ClInclude'):
        incFileRel = inc.get('Include')
       
        if incFileRel != None:
            incFile = os.path.abspath( os.path.dirname(projectname) +"\\"+ incFileRel )
            #print (incFile)
            if not os.path.exists(incFile):
                if not isGenerated(incFile):
                    if incFileRel in filterDict:
                        missingDict[filterDict[incFileRel]].add(incFileRel)
                    else:
                        # this file from the project file is missing on disk and is not listed in any .filters entry.
                        if "projectfile" not in missingDict:
                            missingDict["projectfile"] = set([])
                        missingDict["projectfile"].add(incFileRel)
           
    for (missingGroup, missingList) in missingDict.items():
        for missing in missingList:
            reportIssue(projectname, "0", "UD#10", "File '" + missing + "' from filter [" + missingGroup + "] not found on disk, causes unneeded rebuilds")

def checkProjectsRecursively(path):
    global rootpath
    rootpath = os.path.abspath(path)
    #print (rootpath)
    for root, dirs, files in os.walk(path):
        for file in files:
            if (file.endswith("proj")):
                absfile = os.path.join(root, file)
                checkproject(absfile)

def main():
    try:
        if (len(sys.argv) < 2):
            checkProjectsRecursively(".")
        else:
            checkProjectsRecursively(sys.argv[1])
    except:
        print ("exception")
        info = traceback.format_exc()
        print(info)

if __name__ == "__main__":
    main()
    sys.exit(0)

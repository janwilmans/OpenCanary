"""Checks the completeness of visual studio projects

- any file missing on disk but referenced in the project can cause a full rebuild 
"""

import traceback
import sys
import os
import xml.etree.ElementTree as ET

fileNotFoundCount = 0
projectWithNotFoundFilesCount = 0

def checkproject(projectname):
    
    global fileNotFoundCount
    global projectWithNotFoundFilesCount
    #print "Checking " + os.path.abspath(projectname)
    
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
            missingDict[incFilter.text].add(incFileRel)
    
    projTree = ET.parse(projectname)
    projRoot = projTree.getroot()
    
    for inc in projRoot.iter(ns+'ClInclude'):
        incFileRel = inc.get('Include')
       
        if incFileRel != None:
            incFile = os.path.abspath( os.path.dirname(projectname) +"\\"+ incFileRel )
            if not os.path.exists(incFile):
                if incFileRel in filterDict:
                    missingDict[filterDict[incFileRel]].add(incFileRel)
                else:
                    # this file from the project file is missing on disk and is not listed in any .filters entry.
                    if "projectfile" not in missingDict:
                        missingDict["projectfile"] = set([])
                    missingDict["projectfile"].add(incFileRel)
            
    missingItems = 0;        
    for (missingGroup, missingList) in missingDict.items():
        if len(missingList) > 0:
            missingItems = 1
            
    if (missingItems > 0):
        print "\nMissing item(s) in " + os.path.abspath(projectname)

    fileNotFound = 0
    for (missingGroup, missingList) in missingDict.items():
        if len(missingList) > 0:
            print("["+missingGroup+"]:")
            for missing in missingList:
                print("  " + os.path.basename(missing) + " -> " + missing + " not found on disk")
                fileNotFoundCount = fileNotFoundCount + 1
                fileNotFound = 1
    if (fileNotFound):
        projectWithNotFoundFilesCount = projectWithNotFoundFilesCount + 1

def checkProjectsRecursively():
    global fileNotFoundCount
    global projectWithNotFoundFilesCount
    projectCount = 0
    for root, dirs, files in os.walk("."):
        for file in files:
            if (file.endswith("proj")):
                projectCount = projectCount + 1
                project = os.path.abspath(root + "\\" + file)
                checkproject(project)
    print "Checking of " + str(projectCount) + " project(s) done, " + str(fileNotFoundCount) + " file(s) not found in " + str(projectWithNotFoundFilesCount) + " projects."

def main():
    try:
        if (len(sys.argv) < 2):
            checkProjectsRecursively()
        else:
            checkproject(sys.argv[1])
    except:
        info = traceback.format_exc()
        print info

if __name__ == "__main__":
    main()
    sys.exit(0)

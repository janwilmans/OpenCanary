"""Diff TICS query analyzer

- compare two TICS queries to analyze the differences 
- reports:
    - C1: total amount of issues
    - C2: number of level 1, 2 and 3 issues 
    - C3: number klocwork issues    
"""
import os
import sys
import getopt
import tempfile
import traceback
import re
import collections

def getLogFiles(path):
    # returns a list of log files in the path
    files = []
    for name in os.listdir(path):
        fullname = os.path.join(path, name)
        if os.path.isfile(fullname):
            if (name.endswith(".log")):
                files.append(fullname)
    return files
    
def sendEmail(recipients, subject, message):
    buildtoolspath = os.environ['FBT_PATH']
    
    print "Send email to " + recipients
    
    messageFile = ""
    if (message):
        # create temporary file with email-content
        fd, tempPath = tempfile.mkstemp()
        with open(tempPath, "w") as textFile:
            for line in message:
                textFile.write(line)
        os.close(fd)   
        messageFile = " " + tempPath    

    cmd = buildtoolspath + "\\buildtools.exe mail " + recipients + " \"" + subject + "\"" + messageFile
    print cmd 
    os.system(cmd)
    if (message):
        os.remove(tempPath) 
    
# return a string starting at the n-th found needle     
# returns the haystack as-is if not found
def substring_from_nth_(haystack, needle, n):
    array = haystack.split(needle)
    if (len(array)-1)< n:
        return haystack
    result = needle.join(array[n:])
    return result
        
def uniqwarnings(inputList):
    result = []
    seen = []
    for x in inputList:
        shortline = substring_from_nth_(x, ":", 3).strip()
        if shortline not in seen:
            seen.append(shortline)
            result.append(x)
    return result    
    
def sendAdminEmail(subject, message):
    recipients = "jan.wilmans@fei.com"
    sendEmail(recipients, subject, message)
    
def sendWarningEmail(warningList):
    uniqList = uniqwarnings(warningList)
    
    print "Found", len(uniqList), " warning(s), sending email notification."
    for line in uniqList:
        print line,
    
    recipients = "jan.wilmans@fei.com;Mark.Weber@fei.com;Mark.den.Hollander@fei.com;Kevin.DSouza@fei.com;Petr.Priborsky@fei.com;Jan.Marek@fei.com;David.Jasa@fei.com;Jiri.Kral@fei.com;David.Beer@fei.com"
    subject = str(len(uniqList)) + " Motion Build Warning(s) detected"
    sendEmail(recipients, subject, uniqList)

def getCompilerWarnings(logfile):
    f = open(logfile, "r")
    lines = f.readlines()
    f.close()
    warningLines = []
    for line in lines:
        if "warning c" in line.lower(): 
            warningLines.append(line)
    return warningLines

def checkForCompilerWarnings(logfiles):
    print "found " + str(len(logfiles)) + " logfiles"
    for name in logfiles:
        warningList = getCompilerWarnings(name)
        warningCount = len(warningList);
        print str(warningCount) + " warning(s) from in " + name
        if (warningCount > 0):
            sendWarningEmail(warningList)

def findLogs(path):
    print "Check for build logs in " + path
    return getLogFiles(path)

def printUsage():
    print "difftics <file1> <file2>\n";
    sys.exit(1)

# 1 File   2 Line   3 Group   4 Rule   5 Level   6 Type   7 Message
# groups: ABSTRACTINTERPRETATION, CODINGSTANDARD, COMPILERWARNING
# findNeedle == 0 means search for files _not_ containing 'include' matches
def getLines(content, colomn, include, findNeedle=1, exactMatch=1):
    
    result = []
    for line in content:
        cols = re.split(r'[\t|]+', line.lower())

        #print cols
        if (colomn >= len(cols)):
            continue
        for needle in include:
            if (exactMatch):
                if ((str(needle).lower().strip() == cols[colomn].strip()) == findNeedle):
                    result.append(line)
            else:
                if ((str(needle).lower() in cols[colomn]) == findNeedle):
                    result.append(line)
                    
    return result

def report(content):
    totalCS = getLines(content, colomn=0, include=[".cs"], exactMatch=0)
    totalCPP = getLines(content, colomn=0, include=[".cs"], findNeedle=0, exactMatch=0)
    print "Total C#:                    ", len(totalCS)
    print "Total C++:                   ", len(totalCPP)
    print "============================="
    
    level123 = getLines(content, colomn=4, include=[1,2,3])
    levelother = getLines(totalCPP, colomn=4, include=[4,5,6,7,8,9])
    level1 = getLines(totalCPP, colomn=4, include=[1])
    level2 = getLines(totalCPP, colomn=4, include=[2])
    level3 = getLines(totalCPP, colomn=4, include=[3])
    noAbs = getLines(level123, colomn=2, include=["ABSTRACTINTERPRETATION"], findNeedle=0)
    noAbsCS = getLines(noAbs, colomn=0, include=[".cs"], exactMatch=0)
    noAbsCPP = getLines(noAbs, colomn=0, include=[".cs"], findNeedle=0, exactMatch=0)
    print "TICS Level 123 C#:           ", len(noAbsCS)
    print "TICS Level 123 C++:          ", len(noAbsCPP)
    print "TICS Level 1 C++:            ", len(level1)
    print "TICS Level 2 C++:            ", len(level2)
    print "TICS Level 3 C++:            ", len(level3)
    print "TICS Level 4-9 C++:          ", len(levelother)

    absInt = getLines(content, colomn=2, include=["ABSTRACTINTERPRETATION"])
    absIntCS = getLines(absInt, colomn=0, include=[".cs"], exactMatch=0)
    absIntCPP = getLines(absInt, colomn=0, include=[".cs"], findNeedle=0, exactMatch=0)
    
    for line in absIntCS:
        print "C#: ", line
    
    print "AbstractInterpretation C#:   ", len(absIntCS)
    print "AbstractInterpretation C++:  ", len(absIntCPP)
    
def getFileContent(filename):
    f = open(filename, "r")
    lines = f.readlines()
    f.close()
    return lines    

def printDiffLines(lines1, lines2):
    outset = set(lines1) - set(lines2)
    inset = set(lines2) - set(lines1)

    outset123 = getLines(outset, colomn=4, include=[1,2,3])
    for line in outset123:
        print "-", line.strip()

    inset123 = getLines(inset, colomn=4, include=[1,2,3])
    for line in inset123:
        print "+", line.strip()
    
# compare the lines but with a fuzzy match on the linenumber
def lineEquals(line1, line2):
    parts1 = line1.split("|")
    parts2 = line2.split("|")
    nearLine = (abs(int(parts1[1]) - int(parts2[1])) < 10)
    del parts1[1]
    del parts2[1]
    return nearLine and (cmp(parts1, parts2) == 0)
    
def getLineKey(line):
    
    parts = line.split("|")
    del parts[1]
    return "|".join(parts)

def filterLines(lines):
    result = []
    for line in lines:
        if (len(line.split("|")) == 7):
            result.append(line.strip())
    return result
    
def dictContains(needleLine, lineDict):
    lineList = lineDict.get(getLineKey(needleLine), []);
    for line in lineList:
        if (lineEquals(needleLine, line)):
                return True
    return False

# returns the lines that do not occur in lines1 but _do_ occur in lines2
def getDiffLinesFuzzy(lines1, lines2):
    # this default dict adds an empty list as default value when the key does not exist
    lineDict = collections.defaultdict(list)        
    for line in lines1:
        lineDict[getLineKey(line)].append(line)

    result = []
    for newLine in lines2:
        if (not dictContains(newLine, lineDict)):
            result.append(newLine)  
    return result
    
def compareFiles(filename1, filename2):

    file1content = filterLines(getFileContent(filename1))
    file2content = filterLines(getFileContent(filename2))
    #printDiffLines(file1content, file2content)
    
    file1content123 = getLines(file1content, colomn=4, include=[1,2,3])
    file2content123 = getLines(file2content, colomn=4, include=[1,2,3])
    
    removed = getDiffLinesFuzzy(file2content123, file1content123)
    added = getDiffLinesFuzzy(file1content123, file2content123)

    for line in removed:
        print "-|" + line
    for line in added:
        print "+|" + line

    print str(len(removed)) + " lines removed"  
    print str(len(added)) + " lines added"  

    print "[File] " + filename1
    report(file1content)

    print "\n[File] " + filename2
    report(file2content)
    
def compare():

    if (len(sys.argv) != 3):
            printUsage()
            exit
    compareFiles(sys.argv[1], sys.argv[2])

def main():
    try:
        compare();
    except:
        info = traceback.format_exc()
        print info
        #sendAdminEmail("difftics.py exception", [info])


if __name__ == "__main__":
    main()
    sys.exit(0)

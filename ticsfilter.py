"""TICS report
Collect lines from TICS output that we consider 'not done' and we have a zero-tolerance policy for.
"""
import os
import sys
import getopt
import tempfile
import traceback
import re

# 0 File   1 Line   2 Group   3 Rule   4 Level   5 Type   6 Message
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

def addComments(lines):
    result = []
    for line in lines:
        newLine = line
        if ("INT#027" in line):
            newLine = line + "Use virtual and override"
        result.append(newLine)
    return result

def filter(lines, needle):
    result = []
    for line in lines:
        if not needle in line:
            result.append(line)
    return result

# tricks for finding high-prio issues
# - three (or more) consecutive lines with the same error
# - the same class name mentioned more then three times
# - assert(pointer); to detect null-pointers will prevent crash and cause a hanging process?

def Filter(inputlines):
    content = getLines(inputlines, colomn=0, include=["MOTION"], exactMatch=1)

    lines =  getLines(content, colomn=5, include=["OLC#004"], exactMatch=1)     # Every variable that is declared is to be given a value before it is used
    lines += getLines(content, colomn=5, include=["OLC#005"], exactMatch=1)     # A virtual method may only be called if an object is fully constructed
    lines += getLines(content, colomn=5, include=["OLC#017"], exactMatch=1)     # Initialize all data members of built-in types
    lines += getLines(content, colomn=5, include=["OOP#013"], exactMatch=1)     # disabled until infra-update
    lines += getLines(content, colomn=5, include=["ERR#001"], exactMatch=1)
    lines += getLines(content, colomn=5, include=["CFL#024"], exactMatch=1)     # statement with no side effects
    lines += getLines(content, colomn=5, include=["ERR#014"], exactMatch=1)     # parameter should be declared as a reference parameter (eg. catching by value)
    lines += getLines(content, colomn=5, include=["CPP4996"], exactMatch=1)
    lines += getLines(content, colomn=5, include=["CON#008"], exactMatch=1)     # Don't reference the name of an array
    lines += getLines(content, colomn=7, include=["Use of Uninitialized Data"], exactMatch=1)
    lines += getLines(content, colomn=5, include=["POR#025"], exactMatch=1)     # comparison operator used with a float/double type.
    lines += getLines(content, colomn=7, include=["C/C++ Warnings"], exactMatch=1)   # Object lifetime / inheritance related issues, amoung others  
    lines += getLines(content, colomn=5, include=["INT#027"], exactMatch=1)     # mark overrides explicitly virtual (+ override keyword)
    lines += getLines(content, colomn=5, include=["OOP#018"], exactMatch=1)     # overrides with different constness
    #lines += getLines(content, colomn=5, include=["INT#002"], exactMatch=1)    # data member not declared private    #quite a lot of work without much gain, we SHOULD have a way to turn this on for new code! (boost signals are often public)

    # suppress excessive issues in the old stack for now, to focus on the current/new stuff first
    # todo: we need a way to ignore specific issues in specific projects (to allow to create a zero-baseline, and certain rules _can_ be enforced for new projects)
    # example: INT#002 is too noisy to turn on for existing projects, but would be good for new development
    lines = filter(lines, "MOTION/motion4000")
    lines = filter(lines, "MOTION/motion/mdlmotion")
    lines = filter(lines, "MOTION/motion/simhalmotion")
    lines = filter(lines, "MOTION/tad")
    
    lines = addComments(lines)
    
    # candidates?:
    #lines += getLines(content, colomn=3, include=["CFL#016"], exactMatch=1)     # exceeds the maximum cyclomatic complexity, does not meet the criterium 'easy to fix' in most cases
    #lines += getLines(content, colomn=3, include=["CFL#013"], exactMatch=1)     # The then-part of the if statement is not a block or not a single statement on the same line. (900+ issues)
    # CFL#020 Definition of function '=' does not have 'return' as the last statement.
    # OAL#011: new expression not wrapped in a smart pointer (although it should say: use make_shared/make_unique)
    
    # Level2 candidates: 
    # INT#001 |     2 |     1 | Non-copy-constructors that can be called with one argument shall be declared as explicit 
    # CON#001	2	Conversions	Implicit conversion between signed and unsigned type shall not be used.  (real problem, but actual bugs are rare)
    # CON#002	2	Conversions	Cast converts a 'const' expression to a non-'const' type.  (could be indicative of a design problem, but not easy to fix in most cases)
    # MLK.MIGHT	2	Memory Leaks
    # CON#001	2	Conversions	Implicit conversion between integer and floating type shall not be used.

    # completely ignore (pre-filter?)
    # everything that is level 4-10 (todo: check for useful rules, that we should include)
    # level 03, rule CON#007: Do not convert implicitly from a boolean type to a non-boolean type, and vice versa
    # level 1, POR#021: Avoid the use of conditional compilation 
    # level 9, CFL#014: Do not use multiple return statements
    
    length = len(lines)
    if (length > 0): 
        lines.insert(0, "File|Line|Source|Rule|Level|Category|Description")
    return lines

def getStdinLines():
    lines = []
    for line in sys.stdin:
        lines += [line.strip()]
    return lines

def getFileContent(filename):
    with open(filename, "r") as f:
        lines = list(f)
    return lines

def main():
    for line in Filter(getStdinLines()):
        print(line)

if __name__ == "__main__":
    main()
    sys.exit(0)

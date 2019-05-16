"""TICS report
Collect lines from TICS output that we consider 'not done' and we have a zero-tolerance policy for.
"""

from __future__ import print_function
import os, sys, re, urllib2

import getopt
import tempfile
import traceback
from HTMLParser import HTMLParser

# print to stderr
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

c_priority = 0
c_team = 1
c_component = 2
c_file = 3
c_line = 4
c_group = 5
c_rule = 6
c_level = 7
c_type = 8
c_message = 9

def addPriority(content):
    result = []
    for line in content:
        result += ["999|" + line]
    return result

# 0 Priority 1 Team 2 Component 3 File   4 Line   5 Group   6 Rule   7 Level   8 Type   9 Message
# groups: ABSTRACTINTERPRETATION, CODINGSTANDARD, COMPILERWARNING
# findNeedle == 0 means search for files _not_ containing 'include' matches
def getLines(content, column, include, findNeedle=1, exactMatch=1):
    result = []
    for line in content:
        cols = re.split(r'[\t|]', line)

        #print cols
        if (column >= len(cols)):
            continue
        for needle in include:
            strNeedle = str(needle).lower().strip()
            if (exactMatch):
                if ((strNeedle == cols[column].lower()) == findNeedle):
                    result.append(line)
            else:
                if ((strNeedle in cols[column].lower()) == findNeedle):
                    result.append(line)
    return result

def changePriority(content, column, include, findNeedle=1, exactMatch=1, newPriority=100):
    result = []
    for line in content:
        cols = re.split(r'[\t|]', line)

        #print cols
        if (column >= len(cols)):
            continue

        priority = cols[0]
        for needle in include:
            strNeedle = str(needle).lower().strip()
            if (exactMatch):
                if ((strNeedle == cols[column].lower()) == findNeedle):
                    priority = newPriority
            else:
                if ((strNeedle in cols[column].lower()) == findNeedle):
                    priority = newPriority
        result.append(str(priority) + "|" + "|".join(cols[1:]))

    return result

# we assume there is a trailing | and just append the link
def addCodingStandardLinks(lines):
    result = []
    for line in lines:
        cols = line.split("|")
        csGroup = cols[c_group]
        csKey = cols[c_rule]
        if "ABSTRACTINTERPRETATION" == csGroup:
            if not "-" == csKey:
                line += r'http://tics-docs:8080/documentation/help/reference/' + csKey + '.htm'
        if "CODINGSTANDARD" == csGroup:
            if "@" in csKey:
                line += r'http://tics-server/codingstandards/cs/csviewer/index.php?Rule=' + urllib2.quote(csKey)
            if "#" in csKey:
                line += r'http://tics-server/codingstandards/cpp/csviewer/index.php?Rule=' + urllib2.quote(csKey)
        result.append(line)
    return result

def addComments(lines):
    result = []
    for line in lines:
        cols = line.split("|")
        if "INT#027" in line and (cols[c_message] == "" or cols[c_message] == """If you override one of the base class's virtual functions, then you shall use the "override" keyword"""):
            cols[c_message] = "Use virtual _or_ use override and remove virtual"
        result.append("|".join(cols))
    return result

def cleanupMessages(lines):
    result = []
    for line in lines:
        newLine = line.replace("|Object Oriented Programming|", "|OOP|")
        newLine = newLine.replace("|Resource Handling Issues|", "|Resource Handling|")
        newLine = newLine.replace("|Null Pointer Dereference|", "|Null Dereference|")
        result.append(newLine)
    return result

def filterOut(lines, needle):
    result = []
    for line in lines:
        if not needle in line:
            result.append(line)
    return result

def filterOutExtended(lines, hay, needle):
    result = []
    for line in lines:
        if hay in line and needle in line: continue
        result.append(line)
    return result


# tricks for finding high-prio issues
# - three (or more) consecutive lines with the same error
# - the same class name mentioned more then three times
# - assert(pointer); to detect null-pointers will prevent crash and cause a hanging process?


def FilterMotion(content):
    return getLines(content, column=c_team, include=["MOTION"])

def FilterInterest(content):
    lines = filterOut(content, "._Rep' might be used uninitialized in this function.")      # false positive
    lines = filterOut(lines, "._Myproxy' might be used uninitialized in this function.")    # false positive
    lines = filterOut(lines, "Argument of a throw expression should have a class type.")    # why ? a struct is a valid class for throwing also?
    lines = filterOut(lines, "|ABSTRACTINTERPRETATION|INFINITE_LOOP.LOCAL|")                # generates false positives by design
    lines = filterOut(lines, "|CON#007|")                                                   # false positive
    lines = filterOut(lines, "|POR#021|")                                                   # false positive

    lines = addComments(lines)
    lines = cleanupMessages(lines)
    lines = addCodingStandardLinks(lines)
    return lines

def FilterValuable(content):
    lines = changePriority(content, column=c_level, include=["1"], newPriority=20)
    lines = changePriority(lines,   column=c_level, include=["2"], newPriority=30)
    lines = changePriority(lines,   column=c_level, include=["3"], newPriority=40)
    lines = changePriority(lines,   column=c_level, include=["4"], newPriority=50)
    lines = changePriority(lines,   column=c_level, include=["5"], newPriority=60)
    lines = changePriority(lines,   column=c_level, include=["6"], newPriority=70)
    lines = changePriority(lines,   column=c_level, include=["7"], newPriority=80)
    lines = changePriority(lines,   column=c_level, include=["8"], newPriority=90)
    lines = changePriority(lines,   column=c_level, include=["9"], newPriority=90)

    lines = changePriority(lines, column=c_rule, include=["CPP4996"], newPriority=90)         # functions that were marked as deprecated
    lines = changePriority(lines, column=c_rule, include=["CS.EMPTY.CATCH"], newPriority=90)  # C# Empty catch clause
    lines = changePriority(lines, column=c_group, include=["ABSTRACTINTERPRETATION"], newPriority=20)     # Abstract interpretation issues
    lines = changePriority(lines, column=c_type, include=["C/C++ Warnings"], newPriority=90) # Object lifetime / inheritance related issues, among others
    lines = changePriority(lines, column=c_group, include=["opencanary"], newPriority=20)    # check for missing files, namespaces in headers, warning level settings and std::make_unique usage

    # Default priority overrides
    lines = changePriority(lines, column=c_rule, include=["CFL#013"], newPriority=90)        #3# All flow control primitives (if, else, while, for, do, switch) shall be followed by a block, even if it is empty
    lines = changePriority(lines, column=c_rule, include=["CFL#016"], newPriority=99)        #4# exceeds the maximum cyclomatic complexity, does not meet the criterium 'easy to fix' in most cases
    lines = changePriority(lines, column=c_rule, include=["CFL#020"], newPriority=50)        #1# Control should not reach the end of a non-void function without returning a value
    lines = changePriority(lines, column=c_rule, include=["CFL#024"], newPriority=9)         #1# A statement must have a side-effect, i.e., it must do something
    lines = changePriority(lines, column=c_rule, include=["CON#008"], newPriority=90)        #1# Don't reference the name of an array
    lines = changePriority(lines, column=c_rule, include=["ERR#001"], newPriority=1)         #1# Do not let destructors throw exceptions
    lines = changePriority(lines, column=c_rule, include=["ERR#012"], newPriority=20)        #9# The throw expression without argument refers to a non-class type.
    lines = changePriority(lines, column=c_rule, include=["INT#001"], newPriority=95)        #2# INT#001 constructors with one argument should be explicit
    lines = changePriority(lines, column=c_rule, include=["INT#002"], newPriority=90)        #2# Declare non-constant data members private    #quite a lot of work without much gain, we SHOULD have a way to turn this on for new code! (boost signals are often public)
    lines = changePriority(lines, column=c_rule, include=["INT#006"], newPriority=90)        #2# should be declared const
    lines = changePriority(lines, column=c_rule, include=["INT#027"], newPriority=95)        #2# mark overrides explicitly virtual (+ override keyword)
    lines = changePriority(lines, column=c_rule, include=["NAM#008"], newPriority=50)        #1#  Do not use identifiers that contain two or more underscores in a row
    lines = changePriority(lines, column=c_rule, include=["OAL#007"], newPriority=15)        #1# delete should be used instead of delete[] in case of ordinary pointers. (or vise versa)
    lines = changePriority(lines, column=c_rule, include=["OLC#004"], newPriority=1)         #1# Every variable that is declared is to be given a value before it is used
    lines = changePriority(lines, column=c_rule, include=["OLC#005"], newPriority=10)        #1# A virtual method may only be called if an object is fully constructed
    lines = changePriority(lines, column=c_rule, include=["OOP#013"], newPriority=90)        #1# derives publicly from class that has neither a public virtual destructor nor a protected destructor
    lines = changePriority(lines, column=c_rule, include=["OOP#018"], newPriority=90)        #2# overrides with different constness
    lines = changePriority(lines, column=c_rule, include=["ORG#011"], newPriority=90)        #7# Definition/declaration of '' in global namespace.t
    lines = changePriority(lines, column=c_rule, include=["POR#025"], newPriority=90)        #2# comparison operator used with a float/double type.
    lines = changePriority(lines, column=c_rule, include=["STA#002"], newPriority=90)        #4# Static Objects|Variable '' should be declared in the scope of a class, function or unnamed namespace.
    lines = changePriority(lines, column=c_rule, include=["POR#037"], newPriority=90)        #1# Avoid the use of #pragma warning directive.    # ->100 because often needed, but still useful to check
    lines = changePriority(lines, column=c_rule, include=["OLC#018"], newPriority=20)        #1# Let the order of the initializer list be the same as the order of declaration in the header file: first base classes, then data members

    lines = changePriority(lines, column=c_rule, include=["8@110"], newPriority=90)          #C# Caught exception 'Exception' is not properly handled

    lines = changePriority(lines, column=c_type, include=["PARSE ERROR"], newPriority=5)    # parse errors will prevent analizing files
    lines = changePriority(lines, column=c_group, include=["COVERAGE"], newPriority=95)     # implementation is still in progress

    #FILTER THE FOLLOWING AWAY:
    lines = filterOut(lines, "")                                        # no active development on this anymore
    lines = filterOut(lines, "")                                        # maintained by another team
    lines = filterOut(lines, "")                                        # component s in maintanance mode

    return lines

def FilterRegression(content):
    # ADD ALL RULES OF INTEREST (LVL1-3 and other interesting things) C++ Coding Standard Rev 6.16
    # http://ach-tics-server/codingstandards/cpp/csviewer/index.php
    lines =  getLines(content, column=c_rule, include=["CFL#001"])        #2# Statements following a case label shall be terminated by a statement that exits the switch statement
    lines += getLines(content, column=c_rule, include=["CFL#002"])        #2# All switch statements shall have a default label as the last case label
    lines += getLines(content, column=c_rule, include=["CFL#005"])        #1# Do not access a modified object more than once in an expression
    lines += getLines(content, column=c_rule, include=["CFL#006"])        #1# Do not apply sizeof to an expression with side-effects
    lines += getLines(content, column=c_rule, include=["CFL#007"])        #2# Do not change a loop variable inside a for loop block
    lines += getLines(content, column=c_rule, include=["CFL#013"])        #3# All flow control primitives (if, else, while, for, do, switch) shall be followed by a block, even if it is empty
    lines += getLines(content, column=c_rule, include=["CFL#020"])        #1# Control should not reach the end of a non-void function without returning a value # false positives on IOBase
    lines += getLines(content, column=c_rule, include=["CFL#022"])        #2# Apply sizeof to an object rather than to its type
    lines += getLines(content, column=c_rule, include=["CFL#024"])        #1# statement with no side effects
    lines += getLines(content, column=c_rule, include=["CON#001"])        #2# Make unsafe type conversions explicit rather than implicit
    lines += getLines(content, column=c_rule, include=["CON#002"])        #2# Do not cast away const
    lines += getLines(content, column=c_rule, include=["CON#004"])        #1# Use the new cast operators (static_cast, const_cast, dynamic_cast, and reinterpret_cast) instead of the C-style casts
    lines += getLines(content, column=c_rule, include=["CON#007"])        #3# Do not convert implicitly from a boolean type to a non-boolean type, and vice versa.
    lines += getLines(content, column=c_rule, include=["CON#008"])        #1# Don't reference the name of an array
    lines += getLines(content, column=c_rule, include=["ERR#001"])        #1# Do not let destructors throw exceptions
    lines += getLines(content, column=c_rule, include=["ERR#006"])        #1# Don't use exception specifications, but do use noexcept when applicable
    lines += getLines(content, column=c_rule, include=["ERR#012"])        #9# The throw expression without argument refers to a non-class type.
    lines += getLines(content, column=c_rule, include=["ERR#014"])        #1# Do not catch objects by value
    lines += getLines(content, column=c_rule, include=["ERR#017"])        #3# A catch-all clause must do a rethrow
    lines += getLines(content, column=c_rule, include=["INT#001"])        #2# INT#001 constructors with one argument should be explicit
    lines += getLines(content, column=c_rule, include=["INT#002"])        #2# data member not declared private    #quite a lot of work without much gain, we SHOULD have a way to turn this on for new code! (boost signals are often public)
    lines += getLines(content, column=c_rule, include=["INT#026"])        #2# In a derived class, if you need to override one of a set of the base class's overloaded virtual member functions, then you must override the whole set, or use using-declarations to bring all of the functions in the base class into the scope of the derived class
    lines += getLines(content, column=c_rule, include=["INT#027"])        #2# mark overrides explicitly virtual (+ override keyword)
    lines += getLines(content, column=c_rule, include=["INT#028"])        #2# Supply default arguments with the function's declaration, not with the function's definition
    lines += getLines(content, column=c_rule, include=["INT#030"])        #2#  Do not misuse a pointer when an array is requested
    lines += getLines(content, column=c_rule, include=["NAM#002"])        #1# Do not use identifiers which begin with an underscore ('_') followed by a capital
    lines += getLines(content, column=c_rule, include=["NAM#008"])        #1# Do not use identifiers that contain two or more underscores in a row
    lines += getLines(content, column=c_rule, include=["OAL#003"])        #1# If you overload operator new for a class, you should have a corresponding operator delete
    lines += getLines(content, column=c_rule, include=["OAL#007"])        #1# delete should be used instead of delete[] in case of ordinary pointers. (or vise versa)
    lines += getLines(content, column=c_rule, include=["OAL#008"])        #1# Do not use "delete" to delete raw pointers inside smart pointers
    lines += getLines(content, column=c_rule, include=["OAL#009"])        #2# Do not overload the global operator new or the global operator delete
    lines += getLines(content, column=c_rule, include=["OAL#011"])        #2# Use smart pointers for memory management
    lines += getLines(content, column=c_rule, include=["OAL#012"])        #2# Don't use auto_ptr, use unique_ptr instead
    lines += getLines(content, column=c_rule, include=["OAL#013"])        #2# Use std::make_shared instead of constructing a shared_ptr from a raw pointer
    lines += getLines(content, column=c_rule, include=["OLC#001"])        #2# If objects of a class should never be copied, then the copy constructor and the copy assignment operator shall be declared as deleted functions
    lines += getLines(content, column=c_rule, include=["OLC#003"])        #2# A function must never return, or in any other way give access to, references or pointers to local variables outside the scope in which they are declared
    lines += getLines(content, column=c_rule, include=["OLC#004"])        #1# Every variable that is declared is to be given a value before it is used
    lines += getLines(content, column=c_rule, include=["OLC#005"])        #1# A virtual method may only be called if an object is fully constructed
    lines += getLines(content, column=c_rule, include=["OLC#016"])        #2# Do not re-declare a visible name in a nested scope
    lines += getLines(content, column=c_rule, include=["OLC#017"])        #1# Initialize all data members of built-in types
    lines += getLines(content, column=c_rule, include=["OLC#018"])        #1# Let the order of the initializer list be the same as the order of declaration in the header file: first base classes, then data members
    lines += getLines(content, column=c_rule, include=["OLC#020"])        #2# Don't pass member variables of type "class" by reference to the base class in the constructor's initializer list
    lines += getLines(content, column=c_rule, include=["OOP#001"])        #2# A class that manages resources shall declare a copy constructor, a copy assignment operator, and a destructor
    lines += getLines(content, column=c_rule, include=["OOP#011"])        #2# Never redefine an inherited non-virtual method
    lines += getLines(content, column=c_rule, include=["OOP#013"])        #1# derives publicly from class that has neither a public virtual destructor nor a protected destructor
    lines += getLines(content, column=c_rule, include=["OOP#018"])        #2# overrides with different constness
    lines += getLines(content, column=c_rule, include=["ORG#001"])        #3# Enclose all code in header files within include guards
    lines += getLines(content, column=c_rule, include=["ORG#003"])        #3# From a source file include only header files
    lines += getLines(content, column=c_rule, include=["ORG#010"])        #1# Do not let assertions change the state of the program
    lines += getLines(content, column=c_rule, include=["PCA#001"])        #1# Use new and delete instead of malloc, calloc, realloc, free and cfree
    lines += getLines(content, column=c_rule, include=["PCA#006"])        #1# Do not use setjmp and longjmp
    lines += getLines(content, column=c_rule, include=["PCA#008"])        #1# Do not redefine keywords
    lines += getLines(content, column=c_rule, include=["PCA#013"])        #3# Do not use trigraphs or alternative tokens
    lines += getLines(content, column=c_rule, include=["PCA#017"])        #2# Don't compare unrelated enumerations
    lines += getLines(content, column=c_rule, include=["POR#001"])        #3# Never use absolute file paths
    lines += getLines(content, column=c_rule, include=["POR#004"])        #1# Do not cast a pointer to a shorter quantity to a pointer to a longer quantity
    lines += getLines(content, column=c_rule, include=["POR#005"])        #1# Do not assume that pointers and integers have the same size
    lines += getLines(content, column=c_rule, include=["POR#025"])        #2# comparison operator used with a float/double type. #false on comparing to 0.0
    lines += getLines(content, column=c_rule, include=["POR#029"])        #1# Do not depend on the order of evaluation of arguments to a function
    lines += getLines(content, column=c_rule, include=["POR#033"])        #2# Do not make assumptions on the size of int
    lines += getLines(content, column=c_rule, include=["POR#037"])        #1# Avoid the use of #pragma warning directive.

    # ADD ALL RULES OF INTEREST (LVL1-3 and other interesting things) C# Coding standard Rev 5.3
    # http://ach-tics-server/codingstandards/cs/csviewer/index.php?CSTD=SEARCH
    lines += getLines(content, column=c_rule, include=["4@111"])          #3# Don't comment out code
    lines += getLines(content, column=c_rule, include=["5@108"])          #2# Do not 'shadow' a name in an outer scope
    lines += getLines(content, column=c_rule, include=["5@112"])          #3# Provide a method that will cause the finalizer not to be called
    lines += getLines(content, column=c_rule, include=["5@113"])          #2# Implement IDisposable if a class uses unmanaged/expensive resources, owns disposable objects or subscribes to other objects
    lines += getLines(content, column=c_rule, include=["5@114"])          #2# Do not access any reference type members in the finalizer
    lines += getLines(content, column=c_rule, include=["5@121"])          #1# Don't use "using" variables outside the scope of the "using" statement
    lines += getLines(content, column=c_rule, include=["5@122"])          #3# Avoid empty finalizers
    lines += getLines(content, column=c_rule, include=["6@101"])          #2# Do not change a loop variable inside a for loop block
    lines += getLines(content, column=c_rule, include=["6@103"])          #3# All flow control primitives (if, else, while, for, do, switch) shall be followed by a block, even if it is empty
    lines += getLines(content, column=c_rule, include=["6@105"])          #2# All switch statements shall have a default label as the last case label
    lines += getLines(content, column=c_rule, include=["6@191"])          #1# Do not dereference null
    lines += getLines(content, column=c_rule, include=["7@101"])          #2# Declare all fields (data members) private
    lines += getLines(content, column=c_rule, include=["7@105"])          #3# Explicitly define a protected constructor on an abstract base class
    lines += getLines(content, column=c_rule, include=["7@304"])          #3# Only use optional arguments to replace overloads
    lines += getLines(content, column=c_rule, include=["7@502"])          #1# Do not modify the value of any of the operands in the implementation of an overloaded operator
    lines += getLines(content, column=c_rule, include=["7@520"])          #1# Override the GetHashCode method whenever you override the Equals method.
    lines += getLines(content, column=c_rule, include=["7@521"])          #1# Override the Equals method whenever you implement the == operator, and make them do the same thing
    lines += getLines(content, column=c_rule, include=["7@530"])          #3# Implement operator overloading for the equality (==), not equal (!=), less than (<), and greater than (>) operators when you implement IComparable
    lines += getLines(content, column=c_rule, include=["7@531"])          #2# Overload the equality operator (==), when you overload the addition (+) operator and/or subtraction (-) operator
    lines += getLines(content, column=c_rule, include=["7@532"])          #2# Implement all relational operators (<, <=, >, >=) if you implement any
    lines += getLines(content, column=c_rule, include=["7@533"])          #2# Do NOT use the Equals method to compare diffferent value types, but use the equality operators instead.
    lines += getLines(content, column=c_rule, include=["8@102"])          #1# Do not throw exceptions from unexpected locations
    lines += getLines(content, column=c_rule, include=["8@107"])          #3# Use standard exceptions
    lines += getLines(content, column=c_rule, include=["8@110"])          #1# Caught exception is not properly handled.
    lines += getLines(content, column=c_rule, include=["9@110"])          #2# Each subscribe must have a corresponding unsubscribe
    lines += getLines(content, column=c_rule, include=["9@113"])          #1# Always check an event handler delegate for null
    lines += getLines(content, column=c_rule, include=["10@401"])         #2# Floating point values shall not be compared using the == nor the != operators nor the Equals method.
    lines += getLines(content, column=c_rule, include=["10@406"])         #1# When using composite formatting, do supply all objects referenced in the format string

    lines += getLines(content, column=c_rule, include=["CPP4996"])        # functions that were marked as deprecated
    lines += getLines(content, column=c_rule, include=["CS.EMPTY.CATCH"]) # C# Empty catch clause
    lines += getLines(content, column=c_group, include=["ABSTRACTINTERPRETATION"])     # Abstract interpretation issues
    lines += getLines(content, column=c_type, include=["C/C++ Warnings"]) # Object lifetime / inheritance related issues, among others
    lines += getLines(content, column=c_group, include=["opencanary"])    # check for missing files, namespaces in headers, warning level settings and std::make_unique usage

    # Handle categories that are solved in some component or folder, but not in others.
    lines = filterOutExtended(lines, "TimeMeasurements/Timer.cpp", "|CON#001|")  
    lines = filterOutExtended(lines, "|FOO/", "|4@111|")                    
    lines = filterOutExtended(lines, "|FOO/", "|5@108|")                    
    lines = filterOutExtended(lines, "|FOO/", "|6@103|")                    
    lines = filterOutExtended(lines, "|FOO/", "|6@105|")                    
    lines = filterOutExtended(lines, "|FOO/", "|7@101|")                    
    lines = filterOutExtended(lines, "|FOO/", "|7@533|")                    
    lines = filterOutExtended(lines, "|FOO/", "|8@107|")                    

    lines += getLines(content, column=c_file, include=["foobar/component"], exactMatch=0)                      # Get all issues in foobar, new software should have no issues.

    #todo: 
    #       - auto-detect new categories that have 0 issues !!
    #       - automatically boost priority of categories that have < 10 issues !
    return lines

# before the priority column is added, there are 10 columns
def Filter(mode):
    if mode.lower() == "addpriority":
        return addPriority(readNormalizedTicsInputColumns(10))      # prefixes the priority colomn

    if mode.lower() == "motion":
        return FilterMotion(readNormalizedTicsInputColumns(11))

    if mode.lower() == "interest":
        return FilterInterest(readNormalizedTicsInputColumns(11))    # postfixes the rule-links

    if mode.lower() == "valuable":
        return FilterValuable(readNormalizedTicsInputColumns(12))

    if mode.lower() == "regression":
        return FilterRegression(readNormalizedTicsInputColumns(12))

    eprint(" - unknown option specified ' " + mode + "'")
    sys.exit(1)

# read from stdin and make sure:
# - every line has exactly N columns
# - every line ends with a | (pipe sign)
# - there is no whitespace around the values
def readNormalizedTicsInputColumns(numberOfColumns):
    lines = []
    for line in sys.stdin:
        cols = re.split(r'[\t|]', line.strip() + "|")
        if len(cols) < numberOfColumns:
            eprint(line)
            eprint("parsed as: ", cols)
            eprint("Error: line contained ", len(cols), " instead of ", numberOfColumns, " columns")
            sys.exit(1)
        colsResult = []
        for c in cols[0:numberOfColumns-1]:
            colsResult += [c.strip()]
        lineResult = "|".join(colsResult) + "|"
        lines += [lineResult]
    return lines

def getFileContent(filename):
    with open(filename, "r") as f:
        lines = list(f)
    return lines

def main():
    if (len(sys.argv) != 2):
        print ("ticsfilter.py [option]")
        print ("ticsfilter.py addpriority will return the list with prioritization column added")
        print ("ticsfilter.py motion      will return all motion related issues")
        print ("ticsfilter.py interest    will filter out issues with false positives and accepted 'known issues'. Adds a rule html link.")
        print ("ticsfilter.py valuable    will return only valuable issues (selected by the team) remain")
        print ("ticsfilter.py regression  will return only issues in the 'solved categories' remain. (there should be zero issues in this list)")
        sys.exit(1)

    for line in Filter(sys.argv[1]):
        print(line)

if __name__ == "__main__":
    main()
    sys.exit(0)

"""
Usage: 
    PrettyDiff <file1> <file2> [--num=COLUMN,DELTA...] [--sep=SEP]

Options:
    --num=COLUMN,DELTA  define a numerical column, where the value can be -/+DELTA before it is considered different
    --sep=SEP           define a character that is the separator [default: |]

Takes two comma separated files and shows the differences, optionally, coloms can be declared 'numeric' and a minimum delta for equality can be specified.
All the girls say i'm pretty diff for a py script!

"""

# [options]
# [-sbdf]

import os, sys, time, difflib, docopt

# returns a map containing {columnNr: delta} entries
def getNumericColumnMap(numoptions):
    result = dict()
    for col in numoptions:
        v = col.split(",")
        if len(v) == 1:
            result[int(v[0])] = 1
        else:
            result[int(v[0])] = int(v[1])
    return result

# compare two lists using getNumericColumnMap() to compare the specified columns are numeric with a tolerance delta value
def compareLists(l1, l2):
    numMap = getNumericColumnMap(options['--num'])
    for num in range(0, len(l1)-1):
        if num in numMap:
            d = int(l1[num]) - int(l2[num])
            if abs(d) > numMap[num]:
                return False
        else:
            if not l1[num] == l2[num]:
                return False
    return True

def compareLines(s1, s2):
    sep = options['--sep']
    l1 = s1.split(sep)
    l2 = s2.split(sep)
    if not len(l1) == len(l2):
        return False
    return compareLists(l1, l2)

def listContains(needle, haystack):
    for line in haystack:
        if compareLines(line, needle):
            return True
    return False

# result is a list with lines that are in toLines but not in fromLines
def diff(fromLines, toLines):
    result = []
    for fline in toLines:
        if not listContains(fline, fromLines):
            result += [fline]
    return result

options = docopt.docopt(__doc__, version='1.0')

fromfile = options['<file1>']
tofile = options['<file2>']
fromlines = open(fromfile, 'U').readlines()
tolines = open(tofile, 'U').readlines()

plusLines = diff(fromlines, tolines)
minLines = diff(tolines, fromlines)

#d = difflib.Differ()

#diff = difflib.HtmlDiff().make_file(fromlines, tolines, fromfile, tofile, False, numlines=3)
#sys.stdout.writelines(diff)

#result = list(d.compare(fromlines, tolines))
#sys.stdout.writelines(result)

for line in plusLines:
    sys.stdout.write("+ " + line)

for line in minLines:
    sys.stdout.write("- " + line)

""" filter script to select content from CSV files
"""

from __future__ import print_function

import sys, os, re, fnmatch
import argparse
import atexit
import platform
import glob

def Match(line, includefilter, excludefilter):
    for keyword in excludefilter:
        if keyword in line:
            return False
    if len(includefilter) == 0:
        return True
    for keyword in includefilter:
        if keyword in line:
            return True
    return False

def LowerList(list):
    result = []
    for entry in list:
        result += [entry.lower()]
    return result

# get list files and/or folders, will return a non-recursive list of whatever matches
# '.'     = return all file- and folder-names in the current directory
# '*.*'   = return all file- and folder-names in the current directory
# '..'    = return all file- and folder-names in the parent directory
# 'foo*'  = return all file- and folder-names in the current directory that start with 'foo'
# '*foo*' = return all file- and folder-names in the current directory that contains the word 'foo'
# the result is always a list of strings that are full-real-paths 
def listByWildcard(wildcard):
    folder = os.path.realpath(wildcard)
    mask = ""
    if not os.path.isdir(folder):
        folder, mask = os.path.split(folder)

    result = []
    for item in os.listdir(folder):
        if mask == "" or fnmatch.fnmatch(item, mask):
            result += [os.path.join(folder, item)]
    return result

def main():

    parser = argparse.ArgumentParser(description='Filter CSV files')
    parser.add_argument('-i', '--input', required=True, action='append', help="file(s) to use as input")
    parser.add_argument('-s', '--separator', default='|', help="character used as separator, defaults to a pipe symbol ( | )") 
    parser.add_argument('-c', '--column', type=int, help="restrict matching to column N, first column is 0") 
    parser.add_argument('-ic', '--ignorecase', action='store_true', help="case-insensitive match") 
    parser.add_argument('-fm', '--fullmatch', action='store_true', help="look for a full match to the keyword instead of containing the keyword") 
    parser.add_argument('-if', '--includefilter', default=[], action='append', help="include lines containing the keyword")
    parser.add_argument('-xf', '--excludefilter', default=[], action='append', help="exclude lines containing the keyword, has priority over --includefilter")
    parser.add_argument('-o', '--outputfile', default='', help="defaults to the console if ommitted")
    args = parser.parse_args()

    outputpath = os.path.dirname(os.path.abspath(args.outputfile))
    if not os.path.exists(outputpath):
        os.makedirs(outputpath)

    useconsole = (args.outputfile == "")

    includefilter = args.includefilter
    excludefilter = args.excludefilter
    if (args.ignorecase):
        includefilter = LowerList(includefilter)
        excludefilter = LowerList(excludefilter)

    lines = []
    for inputfile in args.input:
        with open(inputfile, 'r') as f:
            for line in f:
                if args.column:
                    matchtext = line.strip().split(args.separator)[args.column]
                else:
                    matchtext = line.strip()
                if (args.ignorecase):
                    if Match(matchtext.lower(), includefilter, excludefilter):
                        lines += [line]
                else:
                    if Match(matchtext, includefilter, excludefilter):
                        lines += [line]

    if useconsole:
        for line in lines:
            print (line,)
    else:
        with open(outputfile, 'w') as f:
            for line in lines:
                f.write(line)

    print (len(lines), " lines.")
if __name__ == '__main__':
    main()
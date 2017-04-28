"""datestamp.py

all import from the stdin is written to a file named " <month>_<day>_<time>.txt "
if the file already exists, the output in appended

usage: datestamp.py [ <prefix> | +<postfix> ]

example: dir | datestamp.py foo_

will create 'foo_June_05_Sunday_0203.txt'

"""
import os
import sys
import getopt
import tempfile
import traceback
import re
import fileinput
import datetime

def GetArg(index):
    if (len(sys.argv) > index):
        return sys.argv[index]
    else:
        return ""

def GetDatedFilename():
    now = datetime.datetime.now()
    prefix = GetArg(1)
    postfix = ""
    if "+" in prefix:
        postfix = prefix.strip('+') 
        prefix = ""
    
    print "prefix:  ", prefix
    print "postfix: ", postfix
    
    return prefix + now.strftime("%B_%d_%A_%H%M") + postfix + ".txt"  # December_05_Wednesday_0200.txt
    
def writeStdinToFile():
    target = open(GetDatedFilename(), 'a+')
    for line in sys.stdin:
        target.write(line)
    target.close()
    
def main():
    try:
        writeStdinToFile();
    except SystemExit as e:
        sys.exit(e)        
    except:
        info = traceback.format_exc()
        print info

if __name__ == "__main__":
    main()
    sys.exit(0)

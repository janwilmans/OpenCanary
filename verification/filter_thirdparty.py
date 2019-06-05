"""Filter thrid party warnings
"""

import traceback, sys, os, time
import xml.etree.ElementTree as ET

def Filter(line):
    if "external/" in line:
        return
    if "/MSVC/" in line:
        return
    if "D9025" in line:
        return
    print (line.strip())

def main():
    for line in sys.stdin:
        Filter(line)

if __name__ == "__main__":
    try:
        main()
    except:
        info = traceback.format_exc()
        print(info)
    sys.exit(0)

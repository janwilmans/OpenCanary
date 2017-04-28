import os, sys, time, glob
import traceback
from datetime import date

# recursively gather files from 'mask' older then 'olderThanDays'
def getOldFiles(mask, olderThanDays):
    oldfiles = []
    today = date.today()
    for filename in glob.glob(mask):
        filedate = date.fromtimestamp(os.path.getmtime(filename))
        if (today - filedate).days > olderThanDays:                                            
            oldfiles.append(filename)
    return oldfiles
    
def removeOldFiles(mask, olderThenDays):
    print "removeOldFiles", mask, olderThenDays
    for oldfilename in getOldFiles(mask, olderThenDays):
        print "removing '" + oldfilename + "'"
        os.remove(oldfilename)
    
def removeOldies():
    if (len(sys.argv) != 3):    
        print "usage: removeoldies <mask> <olderthendays>"
        print "example: removeoldies *.txt 7"
        print "  will remove *.txt older then 7 days"
        os.exit(1)
    removeOldFiles(sys.argv[1], int(sys.argv[2]))
        
def main():
    try:
        removeOldies()
    except SystemExit as e:
        sys.exit(e)        
    except:
        info = traceback.format_exc()
        print info

if __name__ == "__main__":
    main()
    sys.exit(0)

    
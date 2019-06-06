import os,sys,re

# the tuple is used for a lexicographically sort by its fields
def MakeTuple(line):
    data = line.split("|")
    
    # sort the first colomn by its integer-representation
    return (int(data[0]), data[3])

# we should sort numerically by colomn 1 (prio) and then textually by colomn 4 (filename)
def SortBy(inputlines):
    return sorted(inputlines, key=MakeTuple)

def getStdinLines():
    lines = []
    for line in sys.stdin:
        lines += [line.strip()]
    return lines
    
# guarenteed to keep the first result
def makeUniq(lines):
    result = []
    lines_seen = set() # holds lines already seen
    for line in lines:
        if line not in lines_seen: # not a duplicate
            result += [line]
            lines_seen.add(line)
    return result;

def main():
    for line in SortBy(makeUniq(getStdinLines())):  # makeUniq is a workaround for opencanary issues being gathered from all four .log files from debug/debug64/release/release64.
        print(line)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except:
        info = traceback.format_exc()
        print(info)
        showUsage()
        sys.exit(1)


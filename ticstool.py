import sys
import os
import re
import argparse
import atexit
import platform
from collections import defaultdict

ORGANIZATION_FILE = "ORGANIZATION_TEM.txt"
ORGMAPPING_FILE = "ORGMAPPING_TEM.txt"
SHOW_EXAMPLES = True
teamMap = {}                    # key: componentName, value: teamName
componentMap = {}               # key: needle, value: componentName

# ORGANIZATION_TEM.txt and ORGMAPPING_TEM.txt are TICS configuration files,
# we generate these from out own index.txt and per-team mapping-files.
def GenerateTICSOrgantizationFiles(outputpath):
    print ("GenerateTICSOrgantizationFiles: " + outputpath)

    if not os.path.exists(outputpath):
        os.makedirs(outputpath)

    orgMappingPath = outputpath + '/' + ORGMAPPING_FILE
    orgMap = {}

    # transform the component map so the output is writting in order (not alfabetical yet)
    for needle in componentMap:
        component = componentMap[needle]
        if not component in orgMap:
            orgMap[component] = [needle]
        else:
            orgMap[component] += [needle]

    with open(orgMappingPath, 'w') as f:
        for component in orgMap:
            for needle in orgMap[component]:
                f.write(component + "\t" + needle + "\n")

    # also not alfabetical yet
    organizationPath = outputpath + '/' + ORGANIZATION_FILE
    with open(organizationPath, 'w') as f:
        for component in teamMap:
            teamName = teamMap[component]
            f.write(teamName + "\t" + component + "\n")

# reads RAW tics database output and prefixes the TEAM and COMPONENT columns
def ConvertFromRawTICSOutput(input, outputfile):
    useconsole = (outputfile == "")
    if not useconsole:
        print ("Converting: '" + ", ".join(input)  + "' to '" + outputfile + "'")

    inputlines = []
    for inputfile in input:
        with open(inputfile, 'r') as f:
            inputlines += f.readlines()

    lines = Convert(inputlines)

    if useconsole:
        for line in lines:
            print ("|".join(line))
    else:
        with open(outputfile, 'w') as f:
            for line in lines:
                f.write("|".join(line) + "\n")

def mergeLines(inputlines):
    lines = []
    for line in inputlines:
        parts = line.strip().split("|")
        # there is a hardcoded assumption here that the RAW tics output from the database has at least 7 columns
        if len(parts) < 7:
            lines[-1][-1] += " ".join(parts)
            # this happens in the TICS output because of newlines in the last colomn-text
            # we re-join the lines by concatinating to the previous line
            continue
        else:
            lines += [parts]
    return lines

def Convert(inputlines):
    lines = mergeLines(inputlines)

    for line in lines:
        team = "none"
        component = "none"
        for needle in componentMap:
            # THE reason why this is slow is that every line in the input is (and has to be to determine the 'none' case) compared against every line in the componentMap
            # I tried a prefix-tree (trie) to make this faster, but than filling the collection takes even longer :)
            # also using a trie has a side-effect, none/none issues cannot be queried from it.
            # alternative: if you want fast results, use pypy (https://pypy.org) using pypy this script runs in seconds instead of minutes
            #print(line[0] + " contains? " + needle)  
            if line[0].lower().startswith(needle):
                component = componentMap[needle]
                team = teamMap[component]
        line.insert(0, component)
        line.insert(0, team)
    return lines

# the line is a list of words separated by any non-word character (whitespace, tabs, or commas are all good)
def SplitWords(line):
    return re.findall(r"[\w]+", line)

# here we read our own index.txt and per-team mapping files into two global maps
def readMaps(configpath):
    global teamMap
    global componentMap

    indexFile = configpath + "\\index.txt"
    with open(indexFile) as f:
        for line in f:
            lineParts = SplitWords(line)
            teamName = lineParts[0] # first word is the teamname
            components = lineParts[1:] # rest of the line is a list of components
            for c in components:
                teamMap[c] = teamName

            filename = configpath + "\\" + teamName + ".txt"
            #print lineParts

            with open(filename) as g:
                for teamLine in g:
                    teamLineParts = teamLine.strip().split("=")
                    if len(teamLineParts) != 2:
                        print ("Error in " + filename + "\nillegal line: " + line + "; consists of more the 2 parts")
                        sys.exit()

                    componentName = teamLineParts[0]
                    if not componentName in components:
                        print ("Error in " + filename + "; unknown component: " + componentName)
                        sys.exit()

                    needle = teamLineParts[1].lower()
                    componentMap[needle] = componentName

    for needle in componentMap:
        component = componentMap[needle]
        if not component in teamMap:
            print ("Component: " + component + " not found in index file!");
            sys.exit()

@atexit.register
def PrintExamples():
    if SHOW_EXAMPLES:
        pyfile = os.path.basename(sys.argv[0])
        print ("action: 'convert' takes csv input exported raw from the tics database")
        print ("\nExamples:\n  " + pyfile + " generate-config foo\configpath\n  " + pyfile + " convert foo\configpath -i foo\somefile.txt\n")
        print ("running on python " + platform.python_version())

def main():
    global SHOW_EXAMPLES

    parser = argparse.ArgumentParser(description='Generates TIOBE TICS specific configuration files.')
    parser.add_argument('action', help="specify either 'generate-config' or 'convert' as action")
    parser.add_argument('configpath', help="path that contains 'index.txt'")
    parser.add_argument('-p', '--outputpath', default='', help="defaults to the current directory if ommitted, only used in 'generate-config' mode")
    parser.add_argument('-i', '--input', action='append', help="file(s) to use as input")
    parser.add_argument('-o', '--outputfile', default='', help="defaults to the console if ommitted")
    args = parser.parse_args()
    SHOW_EXAMPLES = False

    outputfile = args.outputfile
    if not args.outputpath == "":
        outputfile = args.outputpath

    outputpath = os.path.dirname(os.path.abspath(outputfile))
    if not os.path.exists(outputpath):
        os.makedirs(outputpath)

    action = "undefined"
    if args.action == "generate-config":
        action = "generate-config"
    else:
        if args.action == "convert":
            action = "convert"
            if not args.input:
                print("input is required for action 'convert'")
                sys.exit()

    if (action == "undefined"):
        print("specified action '" + args.action + "' is not defined")
        sys.exit()

    # fills two globals 'componentMap' and 'teamMap' from index.txt and per-team mapping files
    readMaps(args.configpath)

    if action == "generate-config":
        GenerateTICSOrgantizationFiles(args.outputpath)

    if args.action == "convert":
        ConvertFromRawTICSOutput(args.input, outputfile)

if __name__ == '__main__':
    main()

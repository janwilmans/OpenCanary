#!/usr/bin/env python3
""" Returns with exitcode 1 if /....., otherwise 0 (success)
"""
import os
import sys
import traceback
from enum import Enum, auto


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def sprint(*args, **kwargs):
    print(*args, file=sys.stdout, **kwargs)


def show_usage():
    eprint("Usage: " + os.path.basename(__file__) + " <option>")
    eprint("   description of the script operations")


def lineContains(line, word):
    if word in line:
        return True
    return False


def lineExtract(line, word):
    i = line.find(word)
    if i == -1:
        return ""
    w = line[i+len(word):]
    return w.strip().strip("(").strip().strip(")").strip()


class ParseState(Enum):
    Scan = auto()
    TargetLinkLibraries = auto()


def get_project_name(project_in_scope, words):
    if len(words) == 0:
        return ""
    projectname = words[0]
    return projectname.replace("${PROJECT_NAME}", project_in_scope)


# add_library(Vic::logging ALIAS ${PROJECT_NAME})
def collectAliases(lines):
    results = []
    project = ""
    for l in lines:
        line = l.strip()
        if lineContains(line, "project"):
            project = lineExtract(line, "project")
            continue

        if l.startswith("add_library") and "ALIAS" in line:
            parts = line.split("(")
            if len(parts) != 2:
                sprint("add_library(), split '(' parse error: ", line) 
                return results
            parts = parts[1].split("ALIAS")
            if len(parts) != 2:
                sprint("add_library() split 'ALIAS' parse error: ", line) 
                return results

            newName = parts[0].strip()
            projectName = parts[1].strip().replace("${PROJECT_NAME}", project).strip(")".strip())
            results += [[projectName, newName]]
    return results


def replaceAlias(line, aliases):
    for alias in aliases:
        if line == alias[0]:
            line = alias[1]
    return line

def StripLine(line):
    pos = line.find("#")
    if pos != -1:
        line = line[:pos-1]
    return line.strip()


def printDependecies(lines):

    aliases = collectAliases(lines)
    state = ParseState.Scan
    project = ""        # current project in scope
    fromNode = ""       # fromNode -> dependency
    deps = []           # list of depedencies of current 'fromNode'

    # statistics only
    projects = set()

    for l in lines:
        line = StripLine(l)
        #sprint("l:", line, " p:", project, " ds:", deps)

        if state == ParseState.Scan:
            if lineContains(line, "project"):
                project = lineExtract(line, "project")

            if lineContains(line, "target_link_libraries"):
                state = ParseState.TargetLinkLibraries
                words = lineExtract(line, "target_link_libraries").split()
                fromNode = get_project_name(project, words)
                deps += words[1:]
        else:
            if ")" in line:
                state = ParseState.Scan

                if fromNode == "":
                    fromNode = get_project_name(project, deps)
                    deps = deps[1:]
                fromNode = replaceAlias(fromNode, aliases)
                projects.add(fromNode)

                for dep in deps:
                    if dep == "PRIVATE" or dep == "PUBLIC":
                        continue
                    dep = replaceAlias(dep, aliases)
                    dep = get_project_name(project, [dep])
                    sprint("    \"{}\" -> \"{}\"".format(fromNode, dep))
                deps = []
            else:
                deps += line.split()

    sprint("# statistics")
    sprint("# ", len(projects), "unique projects")
    sprint("#")


def main():
    if len(sys.argv) != 1:
        eprint("error: invalid argument(s)\n")
        show_usage()
        return 1

    sprint("digraph \"dependency_graph\" {")
    printDependecies(sys.stdin.readlines())
    sprint("}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc(file=sys.stdout)
    show_usage()
    sys.exit(1)

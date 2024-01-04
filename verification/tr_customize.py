#!/usr/bin/env python3
"""Remove build paths, customize 'component' field
"""

import traceback, sys, os
from util import *

def define_component(parts):
    file = parts[int(Column.File)].replace("\\", r"/")
    if "include/QtMultimedia" in file:
        return "CsMultimedia"
    if "include/QtCore" in file:
        return "CsCore"
    if "/src/core" in file:
        return "CsCore"
    if "include/QtGui" in file:
        return "CsGui"
    if "/WebCore" in file:
        return "WebCore"
    if "/webkit" in file:
        return "webkit"
    if "/src/gui/" in file:
        return "CsGui"
    if "/src/multimedia/" in file:
        return "multimedia"
    if "/src/network/" in file:
        return "network"
    if "/src/opengl/" in file:
        return "opengl"
    if "/src/plugins/" in file:
        return "plugins"
    if "/src/script/" in file:
        return "script"
    if "/src/svg/" in file:
        return "svg"
    if "/src/xmlpatterns/" in file:
        return "xmlpatterns"
    if "/src/xml/" in file:
        return "xml"
    if "/src/tools/" in file:
        return "tools"
    if "/3rdparty" in file:
        return "3rdparty"
    return ""

def get_substring_end_position(needle, haystack):
    position = haystack.find(needle)
    if position == -1:
        return 0
    return position + len(needle)
    
def remove_build_path(parts):
    file = parts[int(Column.File)].replace("\\", r"/")
    build_path = "privateinclude/Qt"
    position = file.find(build_path)
    if position != -1:
        return file[position:]
    source_path = "copperspice/src/"
    position = file.find(source_path)
    if position != -1:
        return "[[source_prefix]]/" + file[position:]
    return file    

def customize(line):
    parts = line.split("|")
    parts[int(Column.File)] = remove_build_path(parts)
    parts[int(Column.Component)] = define_component(parts)
    sys.stdout.write("|".join(parts))


def show_usage():
    eprint("Usage: " + os.path.basename(__file__))
    eprint("   will customize structured CSV, according to user-specific rulesm, see customize()")


def main():
    for line in sys.stdin:
        customize(line)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        show_usage()
        sys.exit(1)

#!/bin/bash
# this script finds unique words in source code
# it can be used to discover dead code and/or unused defines

echo "Collecting files... *.h, *.cc, *.c"
find . -name "*.h" -o -name "*.cc" -o -name "*.c" > /tmp/files_on_disk.txt

cat `find . -name CMakeLists.txt` | grep -E "\.cc|\.c|\.h" > /tmp/referenced_sources.txt

# Extract words from input file, sort and get unique words
cat /tmp/files_on_disk.txt | tr -cs '[:alnum:]_.' '[\n*]' | sort | uniq > /tmp/input_words.txt

# Extract words from reference file, sort and get unique words
cat /tmp/referenced_sources.txt  | tr -cs '[:alnum:]_.' '[\n*]' | sort | uniq > /tmp/reference_words.txt

# List words in input file that are not in the reference file
comm -23 /tmp/input_words.txt /tmp/reference_words.txt | grep "\.c"

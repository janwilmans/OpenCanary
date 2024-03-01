#!/usr/bin/env python3
""" unittest for open canary
"""

import os

from xml.sax.handler import ContentHandler
from xml.sax import make_parser

import unittest
from util import eprint


def is_valid_xml_file(file):
    parser = make_parser()
    parser.setContentHandler(ContentHandler())
    try:
        parser.parse(file)
        return True
    except Exception as e:
        eprint(e)
        return False


class TestParseGcc(unittest.TestCase):

    def test_openfile(self):
        os.system(
            "cat testdata/gcc8_39_warnings.txt | python3 parse_gcc.py gcc > test_result.txt")

        result = []
        with open("test_result.txt", encoding="utf-8") as f:
            for line in f.readlines():
                result += [line]
        self.assertEqual(len(result), 39)

    def test_parse_gcc_empty_file(self):
        os.system(
            "cat testdata/empty.txt | python3 parse_gcc.py gcc > test_result.txt")

        result = []
        with open("test_result.txt", encoding="utf-8") as f:
            for line in f.readlines():
                result += [line]
        self.assertEqual(len(result), 0)

    def test_parse_gcc_full_integration(self):
        os.system("cat testdata/gcc8_39_warnings.txt | python3 parse_gcc.py gcc /depth=1 | python3 apply_team_priorities.py | python3 apply_low_hanging_fruit.py | python3 sortby.py | python3 create_report.py | python3 apply_environment.py testdata/gcc_env.txt > test_result.txt")

        result = []
        with open("test_result.txt", encoding="utf-8") as f:
            for line in f.readlines():
                result += [line]

        self.assertTrue(is_valid_xml_file("test_result.txt"))

    def test_parse_clang(self):
        os.system(
            "cat testdata/clang_warnings.txt | python3 parse_gcc.py gcc /depth=1 > clang_result.txt")

        result = []
        with open("clang_result.txt", encoding="utf-8") as f:
            for line in f.readlines():
                result += [line]

        self.assertEqual(len(result), 43)

    def test_parse_clang_full_integration(self):
        os.system("cat testdata/clang_warnings.txt | python3 parse_gcc.py gcc /depth=1 | python3 apply_team_priorities.py | python3 apply_low_hanging_fruit.py | python3 sortby.py | python3 create_report.py | python3 apply_environment.py testdata/gcc_env.txt > test_result.txt")

        result = []
        with open("test_result.txt", encoding="utf-8") as f:
            for line in f.readlines():
                result += [line]

        self.assertTrue(is_valid_xml_file("test_result.txt"))

    def test_parse_msvc_full_integration(self):
        os.system("cat testdata/msvc_warnings.txt | python3 parse_msvc.py testdata/msvc_env.txt | python3 apply_team_priorities.py | python3 apply_low_hanging_fruit.py | python3 sortby.py | python3 create_report.py | python3 apply_environment.py testdata/msvc_env.txt > test_result.txt")

        result = []
        with open("test_result.txt", encoding="utf-8") as f:
            for line in f.readlines():
                result += [line]

        self.assertTrue(is_valid_xml_file("test_result.txt"))


if __name__ == '__main__':
    unittest.main()

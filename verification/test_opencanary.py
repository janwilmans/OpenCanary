#!/usr/bin/env python3
""" tests for open canary, run with: python3 -m unittest  (or pytest) from the verification directory
"""

import os
import subprocess
import sys
import unittest
from xml.sax import make_parser
from xml.sax.handler import ContentHandler

HERE = os.path.dirname(os.path.abspath(__file__))
TESTDATA = os.path.join(HERE, "testdata")

DEFAULT_STAGES = ["apply_team_priorities.py", "apply_low_hanging_fruit.py", "sortby.py"]


def is_valid_xml(text):
    parser = make_parser()
    parser.setContentHandler(ContentHandler())
    try:
        import io
        parser.parse(io.BytesIO(text.encode("utf-8")))
        return True
    except Exception as e:  # pylint: disable=broad-except
        print(e, file=sys.stderr)
        return False


def run_script(script, args=(), stdin=""):
    """run one script of the pipeline, return its stdout as text"""
    result = subprocess.run([sys.executable, os.path.join(HERE, script), *args], input=stdin,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", check=False)
    if result.returncode != 0:
        raise AssertionError(f"{script} failed ({result.returncode}):\n{result.stderr}")
    return result.stdout


def run_pipeline(stages, stdin):
    """stages is a list of (script, args) tuples or plain script names"""
    data = stdin
    for stage in stages:
        script, args = (stage, ()) if isinstance(stage, str) else stage
        data = run_script(script, args, data)
    return data


def read_testdata(name):
    with open(os.path.join(TESTDATA, name), encoding="utf-8") as f:
        return f.read()


def lines(text):
    return [line for line in text.splitlines() if line.strip()]


class TestParseGcc(unittest.TestCase):

    def test_parse_gcc_counts_warnings(self):
        result = run_script("parse_gcc.py", ["gcc"], read_testdata("gcc_warnings.txt"))
        self.assertEqual(len(lines(result)), 6)

    def test_parse_gcc_empty_input(self):
        self.assertEqual(run_script("parse_gcc.py", ["gcc"], read_testdata("empty.txt")), "")

    def test_parse_gcc_extracts_rule(self):
        result = run_script("parse_gcc.py", ["gcc"], read_testdata("gcc_warnings.txt"))
        rules = {line.split("|")[5] for line in lines(result)}
        self.assertIn("sign-compare", rules)
        self.assertIn("unused-parameter", rules)

    def test_parse_gcc_full_integration(self):
        stages = [("parse_gcc.py", ["gcc"])] + DEFAULT_STAGES + ["create_report.py", ("apply_environment.py", [os.path.join(TESTDATA, "env.txt")])]
        report = run_pipeline(stages, read_testdata("gcc_warnings.txt"))
        self.assertTrue(is_valid_xml(report))
        self.assertNotIn("[[permalink-prefix]]", report)


class TestParseMsvc(unittest.TestCase):

    def test_parse_msvc_finds_rules(self):
        result = run_script("parse_msvc.py", ["msvc"], read_testdata("msvc_warnings.txt"))
        rules = {line.split("|")[5] for line in lines(result)}
        self.assertTrue({"C4251", "C4701", "C4244"} <= rules)

    def test_parse_msvc_full_integration(self):
        stages = [("parse_msvc.py", ["msvc"])] + DEFAULT_STAGES + ["create_report.py", ("apply_environment.py", [os.path.join(TESTDATA, "env.txt")])]
        report = run_pipeline(stages, read_testdata("msvc_warnings.txt"))
        self.assertTrue(is_valid_xml(report))


class TestStages(unittest.TestCase):

    @staticmethod
    def row(prio="8", rule="rule", file="a.cc:1", description="d"):
        return "|".join([prio, "", "", file, "src", rule, "warning", description, ""]) + "\n"

    def test_priorities_assigned(self):
        out = run_script("apply_team_priorities.py", stdin=self.row(rule="array-bounds") + self.row(rule="no-such-rule"))
        prios = [line.split("|")[0] for line in lines(out)]
        self.assertEqual(prios, ["5", "8"])

    def test_low_hanging_fruit_threshold(self):
        rare = self.row(rule="rare", file="a.cc:1")
        common = "".join(self.row(rule="common", file=f"b.cc:{i}") for i in range(1, 22))
        out = lines(run_script("apply_low_hanging_fruit.py", stdin=rare + common))
        rare_out = [line for line in out if "|rare|" in line]
        common_out = [line for line in out if "|common|" in line]
        self.assertTrue(rare_out[0].startswith("7|"))
        self.assertIn("[LOW]", rare_out[0])
        self.assertTrue(all(line.startswith("8|") for line in common_out))

    def test_sortby_orders_and_deduplicates(self):
        data = self.row("20", file="b.cc:2") + self.row("5", file="z.cc:1") + self.row("20", file="b.cc:10") + self.row("20", file="b.cc:2")
        out = lines(run_script("sortby.py", stdin=data))
        self.assertEqual([line.split("|")[3] for line in out], ["z.cc:1", "b.cc:2", "b.cc:10"])

    def test_apply_environment_replaces_placeholders(self):
        out = run_script("apply_environment.py", [os.path.join(TESTDATA, "env.txt")], "[[job-url]] [[user-name]]\n")
        self.assertEqual(out.strip(), "https://ci.example.com/group/proj/-/jobs/42 Test User")


if __name__ == "__main__":
    unittest.main()

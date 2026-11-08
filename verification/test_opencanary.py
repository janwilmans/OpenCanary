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
sys.path.insert(0, HERE)
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


def report_rows(report):
    """the issues embedded in a report, with the [[keywords]] filled in the same way the page script does"""
    import base64
    import gzip
    import html
    import json
    import re
    data = json.loads(re.search(r'<script type="application/json" id="oc-data">(.*?)</script>', report, re.S).group(1))
    environment = {key: html.unescape(value) for key, value in re.findall(r'<span data-key="([\w-]+)">(.*?)</span>', report)}

    def fill(match):
        key = match.group(1)
        return json.dumps(environment[key])[1:-1] if key in environment else match.group(0)

    rows = []
    for block in data["blocks"]:
        text = gzip.decompress(base64.b64decode(block)).decode("utf-8")
        rows += json.loads(re.sub(r"\[\[([\w-]+)\]\]", fill, text))
    return rows


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
        rows = report_rows(report)
        self.assertEqual(len(rows), 6)
        self.assertNotIn("[[permalink-prefix]]", str(rows))


class TestReport(unittest.TestCase):

    @staticmethod
    def row(prio, description="d", link=""):
        return "|".join([prio, "team", "comp", "a.cc:1", "src", "rule", "warning", description, link]) + "\n"

    def test_issues_are_split_in_blocks(self):
        import create_report
        count = create_report.BLOCK_SIZE + 1
        report = run_script("create_report.py", stdin="".join(self.row(str(i % 100)) for i in range(count)))
        self.assertTrue(is_valid_xml(report))
        self.assertEqual(report.count('"blocks":["'), 1)
        rows = report_rows(report)
        self.assertEqual(len(rows), count)
        self.assertEqual([row[1] for row in rows[-3:]], ["98", "99", "0"])
        self.assertEqual([row[0] for row in rows[-3:]], ["t4", "t4", "t1"])

    def test_rows_are_plain_text_with_links(self):
        report = run_script("create_report.py", stdin=self.row("5", "&#x27;a&#x27; &lt;b&gt; &amp;", "[3]{[[permalink-prefix]]/a.cc#L1}[5]{https://x/rule}"))
        self.assertEqual(report_rows(report), [["t1", "5", "team", "comp", "a.cc:1", "src", "rule", "warning", "'a' <b> &",
                                                {"3": "[[permalink-prefix]]/a.cc#L1", "5": "https://x/rule"}]])

    def test_every_column_has_a_value_filter(self):
        import create_report
        report = run_script("create_report.py", stdin=self.row("5"))
        self.assertTrue(is_valid_xml(report))
        self.assertEqual(report.count('class="column-filter"'), len(create_report.COLUMNS))
        self.assertEqual(report.count('id="value-filter"'), 1)

    def test_limit_and_empty_report(self):
        report = run_script("create_report.py", ["/limit=2"], "".join(self.row("1") for _ in range(5)))
        self.assertEqual(len(report_rows(report)), 2)
        self.assertIn("limited to the first 2 of 5 issues", report)
        self.assertEqual(report_rows(run_script("create_report.py", stdin="")), [])


class TestSummary(unittest.TestCase):

    @staticmethod
    def row(prio, rule, team, component, category, description="d"):
        return "|".join([prio, team, component, "a.cc:1", "src", rule, category, description, ""]) + "\n"

    @staticmethod
    def table(summary):
        """the summary table as rows of cell texts, markup inside a cell is replaced by a space"""
        import html
        import re
        rows = re.findall(r"<tr>(.*?)</tr>", summary, re.S)
        return [[" ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())
                 for text in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row)] for row in rows]

    def test_rows_grouped_per_rule(self):
        long_description = " ".join(["word"] * 30)
        data = (self.row("45", "AP#13", "gui", "CsGui", "redflag", "later") * 2
                + self.row("45", "AP#13", "core", "CsCore", "redflag", "do not use delete &lt;p&gt;") * 3
                + self.row("9", "b<ad", "", "", "", long_description) + self.row("7", "b<ad", "", "", "")
                + self.row("10", "C4456", "net", "x", "warning") * 2)
        summary = run_script("create_summary.py", stdin=data)
        self.assertTrue(is_valid_xml(summary))
        self.assertNotIn("<script", summary)
        self.assertNotIn("class=", summary)
        # rules by number of issues, then name; within a rule by count; the first description of each rule
        self.assertEqual(self.table(summary), [
            ["Prio", "Rule", "Description", "Team", "Component", "Category", "Issues"],
            ["45", "AP#13 5 issues", "later", "core", "CsCore", "redflag", "3"],
            ["gui", "CsGui", "redflag", "2"],
            ["7, 9", "b<ad", " ".join(["word"] * 20) + "…", "(none)", "(none)", "(none)", "2"],
            ["10", "C4456", "d", "net", "x", "warning", "2"],
            ["", "Total", "", "", "", "", "9"],
        ])
        self.assertIn('rowspan="2"', summary)
        self.assertIn("9 issues for 3 rules in 3 categories for 4 teams", summary)

    def test_empty_input(self):
        summary = run_script("create_summary.py", stdin="")
        self.assertTrue(is_valid_xml(summary))
        self.assertIn("0 issues", summary)
        self.assertNotIn("<table", summary)


class TestParseMsvc(unittest.TestCase):

    def test_parse_msvc_finds_rules(self):
        result = run_script("parse_msvc.py", ["msvc"], read_testdata("msvc_warnings.txt"))
        rules = {line.split("|")[5] for line in lines(result)}
        self.assertTrue({"C4251", "C4701", "C4244"} <= rules)

    def test_rule_link_points_at_the_rule_column(self):
        result = run_script("parse_msvc.py", ["msvc"], read_testdata("msvc_warnings.txt"))
        row = [line for line in lines(result) if "|C4251|" in line][0].split("|")
        self.assertTrue(row[8].startswith("[5]{"), row[8])

    def test_team_is_empty_until_a_team_rule_sets_it(self):
        result = run_script("parse_msvc.py", ["msvc"], read_testdata("msvc_warnings.txt"))
        self.assertEqual({line.split("|")[1] for line in lines(result)}, {""})

    def test_parse_msvc_full_integration(self):
        stages = [("parse_msvc.py", ["msvc"])] + DEFAULT_STAGES + ["create_report.py", ("apply_environment.py", [os.path.join(TESTDATA, "env.txt")])]
        report = run_pipeline(stages, read_testdata("msvc_warnings.txt"))
        self.assertTrue(is_valid_xml(report))


class TestCopperSpiceBuildLog(unittest.TestCase):
    """a real MSVC /W4 ninja build log of CopperSpice (237 MB, 2.6M lines, xz compressed in testdata)
    the numbers are a regression baseline: they match the parsed output kept with the original log"""

    @classmethod
    def setUpClass(cls):
        import lzma
        with lzma.open(os.path.join(TESTDATA, "msvc_w4_copperspice.log.xz"), "rt", encoding="utf-8") as f:
            log = f.read()
        cls.parsed = run_script("parse_msvc.py", ["msvc"], log)
        cls.issues = run_script("sortby.py", stdin=cls.parsed)

    def test_parse_and_deduplicate(self):
        self.assertEqual(len(lines(self.parsed)), 404930)
        self.assertEqual(len(lines(self.issues)), 15063)

    def test_rule_counts(self):
        from collections import Counter
        rules = Counter(line.split("|")[5] for line in lines(self.issues))
        self.assertEqual(len(rules), 46)
        self.assertEqual(rules["C4244"], 4567)
        self.assertEqual(rules["C4250"], 2472)
        self.assertEqual(rules["C4291"], 2255)
        self.assertNotIn("rule-missing", rules)

    def test_summarize(self):
        out = run_script("summarize.py", stdin=self.issues)
        self.assertNotIn("error in script", out)
        self.assertIn("C4244: 4567", out)
        self.assertTrue(out.rstrip().endswith("In total 15063 issues."))

    def test_summarize_verbose_shows_first_location(self):
        out = run_script("summarize.py", ["-v"], self.issues)
        self.assertIn("\t@ C:\\project\\internal-copperspice\\src\\3rdparty\\webkit\\Source\\JavaScriptCore\\wtf\\Assertions.cpp:31", out)

    def test_summarize_showall_prints_every_issue(self):
        out = lines(run_script("summarize.py", ["-s"], self.issues))
        self.assertEqual(len(out), 15063)
        self.assertIn("declaration of 'oldNext' hides previous local declaration", out)

    def test_copperspice_pipeline_to_report(self):
        stages = [os.path.join("examples", "tr_customize_copperspice.py"),
                  ("tr_interest.py", ["--rules", os.path.join(HERE, "examples", "interest_copperspice.txt"), "--msvc"])] + DEFAULT_STAGES
        interest = run_pipeline(stages, self.issues)
        self.assertEqual(len(lines(interest)), 445)
        components = {line.split("|")[2] for line in lines(interest)}
        self.assertTrue({"CsCore", "CsGui", "webkit"} <= components)
        report = run_pipeline(["create_report.py", ("apply_environment.py", [os.path.join(TESTDATA, "env.txt")])], interest)
        self.assertTrue(is_valid_xml(report))


class TestRules(unittest.TestCase):

    def test_first_match_wins_and_matcher_types(self):
        import util
        rules = util.parse_rules(["5 =exact", "10 ~part  # comment", "# full line comment", "", '20 "~two words" ~x'])
        self.assertEqual(util.first_match(rules, "exact"), "5")
        self.assertEqual(util.first_match(rules, "exact-and-part"), "10")
        self.assertEqual(util.first_match(rules, "a two words x"), "20")
        self.assertIsNone(util.first_match(rules, "a two words"))

    def test_keyed_rules_are_separate(self):
        import util
        rules = util.parse_rules(["category:ub ~bounds", "5 ~bounds"])
        self.assertEqual(util.first_match(rules, "array-bounds"), "5")
        self.assertEqual(util.first_match(rules, "array-bounds", "category"), "ub")

    def test_invalid_rule_is_reported(self):
        import util
        with self.assertRaises(ValueError):
            util.parse_rules(["5 nomatcher"])

    def test_custom_priority_rules_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "p.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("3 =my-rule\n")
            row = "|".join(["8", "", "", "a.cc:1", "src", "my-rule", "warning", "d", ""]) + "\n"
            out = run_script("apply_team_priorities.py", ["--rules", path], row)
            self.assertTrue(out.startswith("3|"))


class TestInterest(unittest.TestCase):

    def test_default_rules_drop_autogen_and_external(self):
        data = "a\\b_autogen.cc\nkeep\nx/external/y\n"
        self.assertEqual(run_script("tr_interest.py", stdin=data), "keep\n")

    def test_all_matchers_must_match_and_msvc_normalizes(self):
        rules = os.path.join(HERE, "examples", "interest_copperspice.txt")
        data = "|3rdparty|C4706\n|CsCore|C4706\n|CsCore|C4018\n|x|C4018 a\\b\n"
        out = run_script("tr_interest.py", ["--rules", rules, "--msvc"], data)
        self.assertEqual(out, "|x|C4018 a/b\n")


class TestCustomize(unittest.TestCase):
    ROW = "8||c|build\\lib\\toolkit\\a.cc:12|gcc|rule|warning|d|[3]{old}\n"

    def customize(self, *args):
        rules = os.path.join(HERE, "examples", "customize_toolkit.txt")
        return run_script("tr_customize.py", ["--rules", rules, *args], self.ROW).split("|")

    def test_component_team_and_link(self):
        parts = self.customize()
        self.assertEqual(parts[1], "platform")
        self.assertEqual(parts[2], "toolkit")
        self.assertEqual(parts[3], "build/lib/toolkit/a.cc:12")
        self.assertIn("[3]{[[permalink-prefix]]/build/lib/toolkit/a.cc#L12}", parts[8])

    def test_component_without_matching_rule_is_kept(self):
        row = "8||compiler|cl : Command line warning|msvc|D9002|cmdline|d|\n"
        rules = os.path.join(HERE, "examples", "customize_toolkit.txt")
        self.assertEqual(run_script("tr_customize.py", ["--rules", rules], row).split("|")[2], "compiler")

    def test_drive_letter_is_removed_and_path_is_linked(self):
        row = self.ROW.replace("|build", "|C:\\build")
        rules = os.path.join(HERE, "examples", "customize_toolkit.txt")
        parts = run_script("tr_customize.py", ["--rules", rules, "--reference-depth=1"], row).split("|")
        self.assertEqual(parts[3], "build/lib/toolkit/a.cc:12")
        self.assertIn("[3]{[[permalink-prefix]]/lib/toolkit/a.cc#L12}", parts[8])

    def test_legacy_options_and_msvc_display(self):
        parts = self.customize("/msvc", "-display_depth=1")
        self.assertEqual(parts[3], "lib\\toolkit\\a.cc:12")


class TestRunner(unittest.TestCase):

    def test_wiki_url_prefix_from_environment_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            env = os.path.join(d, "env.txt")
            with open(env, "w", encoding="utf-8") as f:
                f.write("WIKI_URL_PREFIX=https://wiki.example.com/?t=OC\n")
            out = run_script("apply_environment.py", [env], "[[wiki-url]] [[wiki-issue-prefix]]\n")
            self.assertEqual(out.strip(), "https://wiki.example.com/?t=OC_Issues https://wiki.example.com/?t=OC_Issue_")

    @unittest.skipUnless(sys.version_info >= (3, 11), "opencanary.py run needs tomllib (python 3.11+)")
    def test_run_from_config(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(TESTDATA, "gcc_warnings.txt"), os.path.join(d, "gcc.log"))
            shutil.copy(os.path.join(TESTDATA, "env.txt"), os.path.join(d, "env.txt"))
            with open(os.path.join(d, "oc.toml"), "w", encoding="utf-8") as f:
                f.write('[[input]]\nformat = "gcc"\npath = "gcc.log"\n[output]\nenvironment = "env.txt"\nsummary = "summary.html"\n')
            out = run_script("opencanary.py", ["run", "-c", os.path.join(d, "oc.toml")])
            self.assertEqual(out, "")
            with open(os.path.join(d, "issues.txt"), encoding="utf-8") as f:
                self.assertEqual(len(lines(f.read())), 6)
            with open(os.path.join(d, "report.html"), encoding="utf-8") as f:
                report = f.read()
            self.assertTrue(is_valid_xml(report))
            self.assertIn("https://git.example.com/group/proj/blob/0123456789abcdef/w.cc", str(report_rows(report)))
            with open(os.path.join(d, "summary.html"), encoding="utf-8") as f:
                self.assertIn("6 issues for 6 rules", f.read())

    def test_single_stage_command(self):
        out = run_script("opencanary.py", ["sort"], TestStages.row("9", file="b.cc:1") + TestStages.row("1", file="a.cc:1"))
        self.assertEqual([line.split("|")[0] for line in lines(out)], ["1", "9"])


class TestIgnoreFiles(unittest.TestCase):

    def test_cpp_files_respect_ignore_file(self):
        import tempfile
        import util
        with tempfile.TemporaryDirectory() as d:
            for name in ("sub/a.cc", "keep/b.cc", "keep/c.H"):
                os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)
                open(os.path.join(d, name), "w", encoding="utf-8").close()
            with open(os.path.join(d, ".opencanaryignore"), "w", encoding="utf-8") as f:
                f.write("sub/\n")
            headers, cpps = util.get_cpp_files_from_directory(d)
            self.assertEqual([os.path.basename(x) for x in headers + cpps], ["c.H", "b.cc"])


class TestFindDeadCode(unittest.TestCase):

    def test_modes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            files = {
                "src/a.cc": "#define USED_THING 1\n#define LONELY_DEFINE 2\nint lonely_array[10];\nint never_called_fn() { return 0; }\n"
                            "int helper_fn(int x) { return x + USED_THING; }\nvoid run() { int lonelyvar = 4; helper_fn(2); }\n",
                "src/orphan.cc": "int x;\n",
                "CMakeLists.txt": "add_library(x src/a.cc)\n",
            }
            for name, content in files.items():
                os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(content)
            self.assertEqual(lines(run_script("find_dead_code.py", ["arrays", d])), ["int lonely_array[10];"])
            self.assertEqual(lines(run_script("find_dead_code.py", ["functions", d])), ["int never_called_fn() { return 0; }"])
            self.assertEqual(lines(run_script("find_dead_code.py", ["defines", d])), ["#define LONELY_DEFINE"])
            self.assertEqual(lines(run_script("find_dead_code.py", ["variables", d])), ["lonelyvar ="])
            self.assertEqual(lines(run_script("find_dead_code.py", ["sources", d])), ["orphan.cc"])


class TestStages(unittest.TestCase):

    @staticmethod
    def row(prio="8", rule="rule", file="a.cc:1", description="d"):
        return "|".join([prio, "", "", file, "src", rule, "warning", description, ""]) + "\n"

    def test_priorities_assigned(self):
        out = run_script("apply_team_priorities.py", stdin=self.row(rule="array-bounds") + self.row(rule="no-such-rule"))
        prios = [line.split("|")[0] for line in lines(out)]
        self.assertEqual(prios, ["5", "8"])

    def test_msvc_priorities_come_from_the_rules_file(self):
        out = run_script("apply_team_priorities.py", stdin=self.row(rule="C4100") + self.row(rule="C4701") + self.row(rule="C4505"))
        self.assertEqual([line.split("|")[0] for line in lines(out)], ["70", "5", "60"])

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

    def test_branch_id_from_current_and_old_gitlab_names(self):
        import tempfile
        cases = [("CI_COMMIT_REF_NAME=main\nCI_BUILD_REF_NAME=old\n", "main"), ("CI_BUILD_REF_NAME=old\n", "old"),
                 ("CI_COMMIT_SHA=0123abc\n", "0123abc (commit_id)"), ("", "")]
        with tempfile.TemporaryDirectory() as d:
            env = os.path.join(d, "env.txt")
            for content, expected in cases:
                with open(env, "w", encoding="utf-8") as f:
                    f.write(content)
                self.assertEqual(run_script("apply_environment.py", [env], "[[branch-id]]\n"), expected + "\n", content)

    def test_apply_environment_replaces_placeholders(self):
        out = run_script("apply_environment.py", [os.path.join(TESTDATA, "env.txt")], "[[job-url]] [[user-name]]\n")
        self.assertEqual(out.strip(), "https://ci.example.com/group/proj/-/jobs/42 Test User")


if __name__ == "__main__":
    unittest.main()

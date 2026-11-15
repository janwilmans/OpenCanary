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

    def test_rule_links_to_a_search_for_source_and_rule(self):
        result = run_script("parse_gcc.py", ["clang"], read_testdata("gcc_warnings.txt"))
        self.assertIn("[5]{https://duckduckgo.com/?q=!ducky+clang+sign-compare}", result)
        import util
        self.assertEqual(util.get_rule_url("cpp check", "X#13"), "https://duckduckgo.com/?q=!ducky+cpp+check+X%2313")

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
        # the cells in the order of the columns: prio, source, rule, description, file, team, component, category; a link
        # is keyed by its column
        self.assertEqual(report_rows(report), [["t1", "5", "src", "rule", "'a' <b> &", "a.cc:1", "team", "comp", "warning",
                                                {"4": "[[permalink-prefix]]/a.cc#L1", "2": "https://x/rule"}]])

    def test_solution_link_is_not_a_column(self):
        report = run_script("create_report.py", stdin=self.row("5", link="[5]{https://x/rule}[solution]{[[permalink-prefix]]/rule}"))
        self.assertTrue(is_valid_xml(report))
        self.assertEqual(report_rows(report)[0][-1], {"2": "https://x/rule", "solution": "[[permalink-prefix]]/rule"})
        self.assertIn("How to solve", report)

    def test_theme_button(self):
        report = run_script("create_report.py", stdin=self.row("5"))
        self.assertTrue(is_valid_xml(report))
        self.assertIn('id="theme"', report)
        # the dark colors apply both for the system setting and for the button
        self.assertIn(':root:not([data-theme="light"])', report)
        self.assertIn(':root[data-theme="dark"]', report)
        self.assertNotIn("/*DARK*/", report)

    def test_low_hanging_priority_is_shown_as_fix(self):
        report = run_script("create_report.py", stdin=self.row("7"))
        self.assertTrue(is_valid_xml(report))
        # the data keeps the number, for sorting and filtering; the page script shows it as a blue FIX
        self.assertEqual(report_rows(report)[0][:2], ["t1", "7"])
        self.assertIn("const LOW_HANGING = '7';", report)
        self.assertNotIn("/*LOW_HANGING*/", report)
        self.assertIn(".badge.fix { background: var(--accent-soft); color: var(--accent); }", report)

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
    def row(prio, rule, team, component, category, description="d", file="a.cc:1", links="", source="src"):
        return "|".join([prio, team, component, file, source, rule, category, description, links]) + "\n"

    @staticmethod
    def table(summary, index=1):
        """a table of the summary (0 is the top issues, 1 the issues per rule) as rows of cell texts,
        markup inside a cell is replaced by a space"""
        import html
        import re
        rows = re.findall(r"<tr>(.*?)</tr>", re.findall(r"<table.*?</table>", summary, re.S)[index], re.S)
        return [[" ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())
                 for text in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row)] for row in rows]

    def test_rows_grouped_per_rule(self):
        long_description = " ".join(["word"] * 30)
        data = (self.row("45", "manual-delete", "gui", "CsGui", "redflag", "later") * 2
                + self.row("45", "manual-delete", "core", "CsCore", "redflag", "do not use delete &lt;p&gt;") * 3
                + self.row("9", "b<ad", "", "", "", long_description) + self.row("7", "b<ad", "", "", "")
                + self.row("10", "C4456", "net", "x", "warning") + self.row("10", "C4456", "net", "x", "warning", source="clang-cl"))
        summary = run_script("create_summary.py", stdin=data)
        self.assertTrue(is_valid_xml(summary))
        self.assertNotIn("<script", summary)
        self.assertNotIn("class=", summary)
        # rules by number of issues (fewest first), then name; within a rule by count; the first description of each rule;
        # all sources of a rule
        self.assertEqual(self.table(summary), [
            ["Prio", "Source", "Rule", "Total", "Description (example)", "Team", "Component", "Category", "Issues"],
            ["7, 9", "src", "b<ad", "2", " ".join(["word"] * 20) + "…", "(none)", "(none)", "(none)", "2"],
            ["10", "clang-cl, src", "C4456", "2", "d", "net", "x", "warning", "2"],
            ["45", "src", "manual-delete", "5", "later", "gui", "CsGui", "redflag", "2"],
            ["core", "CsCore", "redflag", "3"],
            ["", "", "Total", "9", "", "", "", "", "9"],
        ])
        self.assertNotIn("#f1f3f6", summary)
        self.assertEqual(summary.count('<th align='), 9 + 5)   # both tables have the header in the color of the total line
        self.assertEqual(summary.count('<th align='), summary.count('<th align="left" valign="top" bgcolor="#e8efff"')
                         + summary.count('<th align="right" valign="top" bgcolor="#e8efff"'))
        self.assertIn('rowspan="2"', summary)
        self.assertIn("9 issues for 3 rules in 3 categories for 4 teams", summary)

    def test_top_10_most_important_issues(self):
        data = "".join(self.row("50", "late", "t", "c", "w", file=f"z.cc:{i}") for i in range(1, 11))
        data += self.row("5", "first", "core", "c", "w", "x &lt; y", "b.cc:7", "[5]{https://rule}[3]{[[permalink-prefix]]/b.cc#L7}")
        data += self.row("20", "second", "", "c", "w", "d", "c.cc:2")
        summary = run_script("create_summary.py", stdin=data)
        self.assertTrue(is_valid_xml(summary))
        self.assertIn("Top 10 issues", summary)
        top = self.table(summary, 0)
        self.assertEqual(top[0], ["Prio", "Source", "Rule", "Description / File", "Team"])
        self.assertEqual(top[1:4], [["5", "src", "first", "x < y b.cc:7", "core"], ["20", "src", "second", "d c.cc:2", "(none)"],
                                    ["50", "src", "late", "d z.cc:1", "t"]])
        self.assertIn('>x &lt; y<br/><a href="[[permalink-prefix]]/b.cc#L7"', summary)   # the file on the line below
        self.assertEqual(len(top), 11)
        self.assertIn('<a href="[[permalink-prefix]]/b.cc#L7"', summary)
        self.assertNotIn("https://rule", summary)

    def test_explains_the_columns_per_rule(self):
        summary = run_script("create_summary.py", stdin=self.row("5", "first", "core", "c", "w"))
        self.assertTrue(is_valid_xml(summary))
        explanation = summary.index("<b>Total</b> is the number of issues of the rule")
        self.assertTrue(summary.index("Issues per rule") < explanation < summary.index("Description (example)"))
        self.assertIn("<b>Description</b> is an example", summary)

    def test_description_per_rule_links_to_the_file(self):
        data = self.row("5", "first", "core", "c", "w", "x &lt; y", "src/b.cc:7", "[3]{[[permalink-prefix]]/src/b.cc#L7}")
        data += self.row("6", "other", "core", "c", "w", "no link", "c.cc:2")
        summary = run_script("create_summary.py", stdin=data)
        self.assertTrue(is_valid_xml(summary))
        per_rule = summary[summary.index("Issues per rule"):]
        self.assertIn('<a href="[[permalink-prefix]]/src/b.cc#L7" title="src/b.cc:7" style="color: #1a56db;">x &lt; y</a>', per_rule)
        self.assertIn(">no link</td>", per_rule)
        # not shown without issues, there is no table then
        self.assertNotIn("<b>Total</b>", run_script("create_summary.py", stdin=""))

    def test_leaves_out_the_shared_directories(self):
        import create_summary
        files = ["src/infrastructure/network/src/a.cc:85", "src/infrastructure/dip/src/b.cc:19"]
        self.assertEqual(create_summary.shared_directories(files), 2)
        self.assertEqual([create_summary.without_directories(f, 2) for f in files], ["network/src/a.cc:85", "dip/src/b.cc:19"])
        # the two deepest directories are kept, also when every file shares them
        self.assertEqual(create_summary.shared_directories(["src/a/b/x.cc:1", "src/a/b/y.cc:2"]), 1)
        self.assertEqual(create_summary.shared_directories(["/abs/x/y/z/f.h:1"]), 3)
        self.assertEqual(create_summary.shared_directories(["a.cc:1", "src/b.cc:2"]), 0)
        windows = [r"C:\project\v\src\one\a.cc:1", r"C:\project\v\lib\two\b.cc:2"]
        self.assertEqual(create_summary.shared_directories(windows), 3)
        self.assertEqual(create_summary.without_directories(windows[0], 3), r"src\one\a.cc:1")
        data = (self.row("5", "first", "core", "c", "w", file="home/me/project/src/net/a.cc:1", links="[3]{[[permalink-prefix]]/src/net/a.cc#L1}")
                + self.row("6", "second", "core", "c", "w", file="home/me/project/src/dip/b.cc:2"))
        summary = run_script("create_summary.py", stdin=data)
        self.assertEqual([row[3] for row in self.table(summary, 0)[1:]], ["d src/net/a.cc:1", "d src/dip/b.cc:2"])
        self.assertIn('title="home/me/project/src/net/a.cc:1"', summary)   # the full path is the tooltip
        # the description in the table per rule links to the file, with the full path as its tooltip as well
        self.assertEqual(summary.count('title="home/me/project/src/net/a.cc:1"'), 2)

    def test_report_link(self):
        import tempfile
        data = self.row("5", "first", "core", "c", "w")
        self.assertNotIn("Open the full report", run_script("create_summary.py", stdin=data))
        summary = run_script("create_summary.py", ["--report-url", "[[job-url]]/artifacts/file/report.html"], data)
        self.assertTrue(is_valid_xml(summary))
        self.assertEqual(run_script("create_summary.py", ["--report-url=[[job-url]]/artifacts/file/report.html"], data), summary)
        with tempfile.TemporaryDirectory() as d:
            env = os.path.join(d, "env.txt")
            with open(env, "w", encoding="utf-8") as f:
                f.write("CI_JOB_URL=https://ci/jobs/42/\n")
            self.assertIn('<a href="https://ci/jobs/42/artifacts/file/report.html"', run_script("apply_environment.py", [env], summary))
            with open(env, "w", encoding="utf-8") as f:
                f.write("CI_COMMIT_REF_NAME=main\n")
            self.assertNotIn("Open the full report", run_script("apply_environment.py", [env], summary))

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

    def test_source_matcher(self):
        import util
        rules = util.parse_rules(["5 ~x @gcc", "6 ~x"])
        self.assertEqual(util.first_match(rules, "x", source="gcc"), "5")
        self.assertEqual(util.first_match(rules, "x", source="clang"), "6")
        self.assertEqual(util.first_match(rules, "x"), "6")

    def test_condition_matcher(self):
        import util
        rules = util.parse_rules(["5 ~x !yes", "6 ~y !yes", "7 ~"])
        calls = []
        conditions = {"yes": lambda: calls.append(1) or True}
        self.assertEqual(util.first_match(rules, "x", conditions=conditions), "5")
        self.assertEqual(util.first_match(rules, "z", conditions=conditions), "7")
        self.assertEqual(len(calls), 1)   # only evaluated when the matchers before it matched
        self.assertEqual(util.first_match(rules, "x"), "7")
        self.assertEqual(util.first_match(rules, "x", conditions={"no": lambda: True}), "7")

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
            row = "|".join(["99", "", "", "a.cc:1", "src", "my-rule", "warning", "d", ""]) + "\n"
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

    @staticmethod
    def issue(fileref, rule):
        return "|".join(["99", "", "", fileref, "clang-tidy", rule, "warning", "d", ""]) + "\n"

    def test_default_rules_drop_nolint(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.cc").replace("\\", "/")
            with open(path, "w", encoding="utf-8") as f:
                f.write("int value = 42; // NOLINT\n"
                        "int value = 42; // NOLINT(cppcoreguidelines-avoid-magic-numbers)\n"
                        "int value = 42; // NOLINT(cppcoreguidelines-*, clang-diagnostic-sign-compare)\n"
                        "int value = 42; // NOLINTNEXTLINE\n"
                        "int value = 42;\n")
            magic = "cppcoreguidelines-avoid-magic-numbers"
            dropped = [self.issue(f"{path}:1:13", magic), self.issue(f"{path}:1", "sign-compare"),
                       self.issue(f"{path}:2:13", magic), self.issue(f"{path}:3", magic),
                       self.issue(f"{path}:3", "sign-compare")]
            kept = [self.issue(f"{path}:2", "sign-compare"), self.issue(f"{path}:3", "conversion"),
                    self.issue(f"{path}:4", magic), self.issue(f"{path}:5", magic), self.issue(f"{path}:9", magic),
                    self.issue(f"{path}", magic), self.issue(os.path.join(d, "missing.cc") + ":1", magic), "raw log line\n"]
            self.assertEqual(run_script("tr_interest.py", stdin="".join(dropped + kept)), "".join(kept))

    def test_unknown_condition_is_reported(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "i.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("drop !nolnt\n")
            with self.assertRaisesRegex(AssertionError, "unknown condition '!nolnt'"):
                run_script("tr_interest.py", ["--rules", path], "x\n")


class TestLinks(unittest.TestCase):

    @staticmethod
    def links(rules, *rows):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "links.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(rules)
            return [line.split("|")[8] for line in lines(run_script("apply_links.py", ["--rules", path], "".join(rows)))]

    @staticmethod
    def row(source, rule, links=""):
        return "|".join(["99", "", "", "a.cc:1", source, rule, "w", "d", links]) + "\n"

    def test_default_rule_link(self):
        out = self.links("", self.row("gcc", "sign-compare", "[3]{f}[5]{https://parser}"), self.row("opencanary", "X#13", "[3]{f}"),
                         self.row("gcc", ""))
        self.assertEqual(out, ["[3]{f}[5]{https://parser}", "[3]{f}[5]{https://duckduckgo.com/?q=!ducky+opencanary+X%2313}", ""])

    def test_configured_links_and_placeholders(self):
        rules = ("link:https://docs/<source>/<rule>  ?^C4\n"
                 "solution:https://example/rules.md#<anchor>  ?^X#\n"
                 "solution:[[permalink-prefix]]/<rule>  ~C4\n")
        out = self.links(rules, self.row("msvc", "C4100", "[5]{https://parser}"), self.row("opencanary", "X#13"))
        import util
        self.assertEqual([util.heading_anchor(rule) for rule in ["X#13", "C4100", "sign-compare", "format-truncation=", "a_b c"]],
                         ["x13", "c4100", "sign-compare", "format-truncation", "a_b-c"])
        self.assertEqual(out, ["[5]{https://docs/msvc/C4100}[solution]{[[permalink-prefix]]/C4100}",
                               "[5]{https://duckduckgo.com/?q=!ducky+opencanary+X%2313}[solution]{https://example/rules.md#x13}"])


class TestRulesDocumentation(unittest.TestCase):

    def test_every_rule_has_a_section_and_a_solution_link(self):
        import re
        import apply_links
        import util
        with open(os.path.join(HERE, "oc_cpp_issues.py"), encoding="utf-8") as f:
            # the rule of every report_issue() or report() call that is not commented out
            rules = set(re.findall(r'^\s*report(?:_issue)?\([^,]+, [^,]+, "([^"]+)"', f.read(), re.M))
        import compile_flags
        import oc_cpp_issues
        rules.add(compile_flags.RULE)
        rules |= {rule for rule, _category, _regex, _description in oc_cpp_issues.SOURCE_LINE_RULES + oc_cpp_issues.HEADER_LINE_RULES
                  + oc_cpp_issues.COMMENT_LINE_RULES + oc_cpp_issues.CODE_AND_COMMENT_LINE_RULES}
        self.assertTrue({"todo", "non-english-word", "empty-catch", "unnamed-lock"} <= rules, rules)
        with open(os.path.join(HERE, "..", "documentation", "rules.md"), encoding="utf-8") as f:
            headings = set(re.findall(r"^### (\S+)$", f.read(), re.M))
        self.assertTrue({"manual-delete", "misspelled-word", "make-unique-header", "warning-level-not-4", "parse-error",
                         "redundant-semicolon", "self-include", "uninitialized-variable", "throw-pointer"} <= rules, rules)
        self.assertEqual(rules - headings, set())
        # every rule gets the priority of its own '=rule' line in the default priorities.txt (the project checks and
        # parse-error excepted), not that of an earlier matcher for a compiler warning, such as gcc's ~comment
        priorities = util.load_rules(util.default_rules_file("priorities.txt"))
        own = {rule.matchers[0][1:]: rule.value for rule in priorities if rule.matchers[0][0] == "=" and ":" not in rule.value}
        self.assertEqual({rule for rule in rules if rule not in own}, {"warnings-not-errors", "warning-level-not-4", "parse-error"})
        self.assertEqual({rule: util.first_match(priorities, rule) for rule in rules if rule in own},
                         {rule: own[rule] for rule in rules if rule in own})
        links = util.load_rules(util.default_rules_file("links.txt"))
        for rule in rules:
            # <anchor> must be the anchor GitHub gives the '### <rule>' heading
            self.assertEqual(apply_links.fill(util.first_match(links, rule, "solution", "opencanary"), "opencanary", rule),
                             "https://github.com/janwilmans/OpenCanary/blob/main/documentation/rules.md#" + util.heading_anchor(rule))
        self.assertIsNone(util.first_match(links, "sign-compare", "solution", "gcc"))
        # a compiler warning with the name of an opencanary rule does not get its solution
        self.assertIsNone(util.first_match(links, "manual-delete", "solution", "clang"))


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

    def test_named_links_are_kept(self):
        row = self.ROW.replace("[3]{old}", "[3]{old}[5]{https://x/rule}[solution]{https://x/solve}")
        rules = os.path.join(HERE, "examples", "customize_toolkit.txt")
        links = run_script("tr_customize.py", ["--rules", rules], row).split("|")[8].strip()
        self.assertEqual(links, "[3]{[[permalink-prefix]]/build/lib/toolkit/a.cc#L12}[5]{https://x/rule}[solution]{https://x/solve}")

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

    def test_wiki_url_from_environment_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            env = os.path.join(d, "env.txt")
            line = '<a data-optional="" href="[[wiki-url]]">Wiki</a>\n'
            for contents, expected in [("WIKI_URL=https://wiki.example.com/OC\n", "https://wiki.example.com/OC"),
                                       ("WIKI_URL_PREFIX=https://wiki.example.com/?t=OC\n", "https://wiki.example.com/?t=OC_Issues"),
                                       ("CI_JOB_URL=x\n", None)]:
                with open(env, "w", encoding="utf-8") as f:
                    f.write(contents)
                out = run_script("apply_environment.py", [env], line)
                self.assertEqual(out, line.replace("[[wiki-url]]", expected) if expected else "")

    @unittest.skipUnless(sys.version_info >= (3, 11), "opencanary.py run needs tomllib (python 3.11+)")
    def test_run_from_config(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(TESTDATA, "gcc_warnings.txt"), os.path.join(d, "gcc.log"))
            shutil.copy(os.path.join(TESTDATA, "env.txt"), os.path.join(d, "env.txt"))
            with open(os.path.join(d, "oc.toml"), "w", encoding="utf-8") as f:
                f.write('[[input]]\nformat = "gcc"\npath = "gcc.log"\n[output]\nenvironment = "env.txt"\nsummary = "summary.html"\n'
                        'report_url = "[[job-url]]/artifacts/file/report.html"\nmetrics = "metrics.txt"\n')
            out = run_script("opencanary.py", ["run", "-c", os.path.join(d, "oc.toml")])
            self.assertEqual(out, "")
            with open(os.path.join(d, "issues.txt"), encoding="utf-8") as f:
                self.assertEqual(len(lines(f.read())), 6)
            with open(os.path.join(d, "report.html"), encoding="utf-8") as f:
                report = f.read()
            self.assertTrue(is_valid_xml(report))
            self.assertIn("https://git.example.com/group/proj/blob/0123456789abcdef/w.cc", str(report_rows(report)))
            with open(os.path.join(d, "summary.html"), encoding="utf-8") as f:
                summary = f.read()
            self.assertIn("6 issues for 6 rules", summary)
            self.assertIn("Branch: <b>master</b>", summary)
            self.assertIn("Committer: <b>Test User</b>", summary)
            self.assertIn('href="https://git.example.com/group/proj/blob/0123456789abcdef/', summary)
            self.assertIn('<a href="https://ci.example.com/group/proj/-/jobs/42/artifacts/file/report.html"', summary)
            self.assertIn("https://duckduckgo.com/?q=!ducky+gcc+sign-compare", str(report_rows(report)))
            self.assertNotIn("[[", summary)
            with open(os.path.join(d, "metrics.txt"), encoding="utf-8") as f:
                metrics = lines(f.read())
            self.assertEqual(len([line for line in metrics if line.startswith("opencanary_issues{")]), 6)
            self.assertEqual(metrics[-1], "# EOF")

    @unittest.skipUnless(sys.version_info >= (3, 11), "opencanary.py run needs tomllib (python 3.11+)")
    def test_run_cpp_issues(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.cpp"), "w", encoding="utf-8") as f:
                f.write("int* p = (int*)q; // (char*)q\n")
            with open(os.path.join(d, "oc.toml"), "w", encoding="utf-8") as f:
                f.write('[[input]]\nformat = "cpp-issues"\npath = "."\n')
            run_script("opencanary.py", ["run", "-c", os.path.join(d, "oc.toml")])
            with open(os.path.join(d, "issues.txt"), encoding="utf-8") as f:
                rows = [line.split("|") for line in lines(f.read())]
            # the cast in the code, not the one in the comment
            self.assertEqual([(row[3].rsplit(":", 1)[1], row[5], row[6]) for row in rows], [("1", "c-style-pointer-cast", "modernize")])

    @unittest.skipUnless(sys.version_info >= (3, 11), "opencanary.py run needs tomllib (python 3.11+)")
    def test_run_compile_flags(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "compile_commands.json"), "w", encoding="utf-8") as f:
                json.dump([TestCompileFlags.entry("/s/a.cc", "a", "-std=c++17"), TestCompileFlags.entry("/s/b.cc", "a", "-std=c++17"),
                           TestCompileFlags.entry("/s/dep/c.cc", "dep", "-std=c++14"),
                           TestCompileFlags.entry("/s/legacy/d.cc", "legacy", "-std=c++11", "-DMY_CONFIG=1")], f)
            config = os.path.join(d, "oc.toml")
            with open(config, "w", encoding="utf-8") as f:
                # a list, or one string
                f.write('[[input]]\nformat = "compile-flags"\npath = "compile_commands.json"\nmacros = ["MY_*"]\nignore_targets = "leg*"\n')
            run_script("opencanary.py", ["run", "-c", config])
            with open(os.path.join(d, "issues.txt"), encoding="utf-8") as f:
                rows = [line.split("|") for line in lines(f.read())]
            # one issue of a rule is low hanging fruit (7); the legacy target and its macro are left out
            self.assertEqual([(row[0], row[3], row[5]) for row in rows], [("7", "s/dep/c.cc", "inconsistent-compile-flags")])
            with open(config, "w", encoding="utf-8") as f:
                f.write('[[input]]\nformat = "compile-flags"\npath = "compile_commands.json"\nmacros = [1]\n')
            with self.assertRaisesRegex(AssertionError, "macros of the compile-flags input must be a list of strings"):
                run_script("opencanary.py", ["run", "-c", config])

    def test_single_stage_command(self):
        out = run_script("opencanary.py", ["sort"], TestStages.row("9", file="b.cc:1") + TestStages.row("1", file="a.cc:1"))
        self.assertEqual([line.split("|")[0] for line in lines(out)], ["1", "9"])


class TestMetrics(unittest.TestCase):

    def test_issues_are_counted_per_label_set(self):
        rows = ("45|core|net|a.cc:1|gcc|sign-compare|warning|d|\n" * 2
                + "99|||b.cc:1|opencanary|todo|readability|d|\n"
                + "7|a&amp;b|c\\x|b.cc:1|msvc|C4100|warning|d|\n")
        self.assertEqual(lines(run_script("create_metrics.py", stdin=rows)), [
            "# TYPE opencanary_issues gauge",
            "# HELP opencanary_issues Number of issues reported by OpenCanary.",
            'opencanary_issues{source="gcc",rule="sign-compare",category="warning",team="core",component="net",priority="45"} 2',
            'opencanary_issues{source="msvc",rule="C4100",category="warning",team="a&b",component="c\\\\x",priority="7"} 1',
            'opencanary_issues{source="opencanary",rule="todo",category="readability",team="",component="",priority="99"} 1',
            "# EOF"])

    def test_no_issues(self):
        self.assertEqual(lines(run_script("create_metrics.py")),
                         ["# TYPE opencanary_issues gauge", "# HELP opencanary_issues Number of issues reported by OpenCanary.", "# EOF"])


class TestCppIssues(unittest.TestCase):

    @staticmethod
    def line_rules(line, header=False):
        """the rules that report a source (or header) of this single line"""
        import oc_cpp_issues
        check = oc_cpp_issues.check_header_line if header else oc_cpp_issues.check_source_line
        return [issue[2] for issue in oc_cpp_issues.find_issues("a.h" if header else "a.cpp", [line + "\n"], check)]

    def test_string_literals_and_comments(self):
        self.assert_rule("null-macro", ["p = NULL; // set to NULL"], ['log("the pointer is NULL");', "c = '\"'; s = \"NULL\";"])
        self.assert_rule("redundant-semicolon", ["x = 1;;"], ['s = "a;;b";', "s = \"\\\";;\";"])
        self.assert_rule("manual-delete", ["delete p; // \"quoted\""], ['log("not able to delete value;");'])
        self.assert_rule("include-source-file", ['#include "other.cpp"'], ['s = "#include \\"other.cpp\\"";'])
        self.assert_rule("throw-non-exception", ['throw "text";'], [])
        self.assert_rule("todo", ["x = 1; // TODO: fix", "/* todo */ x = 1;"], ["int todo = 1;", "while (todo != 0)", 's = "todo";'])

    def test_hardcoded_cxx_standard(self):
        import tempfile
        files = {
            # the top level CMakeLists.txt and the files it includes by path set the standard of the whole program
            "CMakeLists.txt": 'project(p)\nset(CMAKE_CXX_STANDARD 17)\ninclude(cmake/settings.cmake)\ninclude(FetchContent)\n',
            "cmake/settings.cmake": 'set(CMAKE_CXX_STANDARD 17)\n',
            "cmake/FindTool.cmake": 'set(CMAKE_CXX_STANDARD 20)\n',
            "dep/CMakeLists.txt": ('project(dep)\n'
                                   'set(CMAKE_CXX_STANDARD 14)\n'
                                   'set(CMAKE_CXX_STANDARD_REQUIRED ON)\n'
                                   '# set(CMAKE_CXX_STANDARD 11)\n'
                                   'set_target_properties(dep PROPERTIES CXX_STANDARD 14)\n'
                                   'target_compile_options(dep PRIVATE -std=gnu++14 "-DX=#1")\n'
                                   'target_compile_features(dep PUBLIC cxx_std_14)\n'),
            # only a default: the build of the whole program can still set another one
            "guarded/CMakeLists.txt": 'if(NOT DEFINED CMAKE_CXX_STANDARD)\n  set(CMAKE_CXX_STANDARD 14)\nendif()\n',
        }
        with tempfile.TemporaryDirectory() as d:
            for name, text in files.items():
                os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(text)
            rows = [line.split("|") for line in lines(run_script("oc_cpp_issues.py", [d]))]
            found = sorted((os.path.relpath(row[3].rsplit(":", 1)[0], d).replace("\\", "/"), row[3].rsplit(":", 1)[1])
                           for row in rows if row[5] == "hardcoded-cxx-standard")
            self.assertEqual(found, [("cmake/FindTool.cmake", "1"), ("dep/CMakeLists.txt", "2"), ("dep/CMakeLists.txt", "5"),
                                     ("dep/CMakeLists.txt", "6")])
            descriptions = [row[7] for row in rows if row[5] == "hardcoded-cxx-standard"]
            self.assertIn("target_compile_features(&lt;target&gt; PUBLIC cxx_std_14)", " ".join(descriptions))

    def test_file_name_case_clash(self):
        import oc_cpp_issues
        found = []
        clashing = ["src/liba/include/util/header.h", "src/libb/include/util/Header.h", "src/libb/include/Util/Header.h",
                    "src/libb/include/Util/header.h", "a/Foo.cc", "a/foo.cc"]
        not_clashing = ["src/libc/include/util/other.h", "src/libd/include/util/other.h",  # spelled the same
                        "a/cosmetic.cc", "b/Cosmetic.cc",  # another directory
                        "x/util/view.h", "x/Utils/View.h"]  # another directory name
        files = [os.path.join("root", *name.split("/")) for name in clashing + not_clashing]
        oc_cpp_issues.check_file_name_case(files, "root", lambda *issue: found.append(issue))
        self.assertEqual([(os.path.relpath(filename, "root").replace("\\", "/"), line, rule) for filename, line, rule, _, _ in found],
                         [(name, "1", "file-name-case-clash") for name in clashing])
        self.assertEqual(found[0][4], "util/header.h only differs in case from src/libb/include/Util/Header.h, "
                         "src/libb/include/Util/header.h, src/libb/include/util/Header.h; a file system that ignores case "
                         "(Windows, macOS) cannot tell them apart")

    def assert_rule(self, rule, reported, not_reported, header=False):
        for line in reported:
            self.assertIn(rule, self.line_rules(line, header), line)
        for line in not_reported:
            self.assertNotIn(rule, self.line_rules(line, header), line)

    def test_keywords_at_the_start_of_a_line(self):
        self.assert_rule("extern", ["extern int g;", "  extern int g;", "x;extern int g;"],
                         ['extern "C" {', 'extern "C" int f();', "extern template class std::vector<int>;", "int externals;"])
        self.assert_rule("volatile-variable", ["volatile int flag;", "static volatile bool stop;"], ["int volatileCount;"])
        self.assert_rule("null-macro", ["f(NULL);", "p = NULL;", "if (p == NULL)", "NULL;"], ["NULL_TERMINATED;", "x = MY_NULL;"])
        self.assert_rule("constant-if-directive", ["#if 0", "# if 0", "#if (0)", "#if 1"], ["#if FOO", "#ifdef X1"])
        self.assert_rule("using-namespace-in-header", ["using namespace std;", "    using namespace std;"],
                         ["using std::string;", "// using namespace std;"], header=True)

    def test_manual_delete(self):
        self.assert_rule("manual-delete", ["delete p;", "  delete m_widget;", "delete[] buffer;", "delete [] buffer;",
                                           "delete this->m_p;", "delete a.b;", "delete (p);", "delete ::global;"],
                         ["Foo(const Foo&) = delete;", "Foo& operator=(Foo&&) = delete;", "void operator delete(void* p);",
                          "w->deleteLater();", "m_delete = true;"])

    def test_c_style_pointer_cast(self):
        self.assert_rule("c-style-pointer-cast",
                         ["int * p = (int *)imgPtr;", "auto p = (const char*)q;", "auto p = (unsigned char *)q;", "auto p = (Foo::Bar*)q;",
                          "f((char**)argv);", "auto p = (void*)&x;", "auto p = (int*)(q + 1);", "auto p = (std::vector<int>*)q;",
                          "auto p = (const char * const)q;", 'auto s = (char *)"text";', "if (addr != (Desc *)-1)"],
                         ["void MainWindow::timerEvent(QTimerEvent *)", "void f(Foo *) const;", "void f(Foo *) override;",
                          "connect(a, SIGNAL(clicked(QListWidgetItem *)), this, SLOT(open(QListWidgetItem *)));",
                          "n = sizeof(int *) * 2;", "n = sizeof (int*) + 1;", "std::function<void(Foo *)> f;",
                          "x = (a * b);", "void (*fp)(int);", "Q_DECLARE_METATYPE(Foo *)", "f((void **)&p);",
                          "connect(s, static_cast<void (QSpinBox::*)(int)>(&QSpinBox::valueChanged), this, &W::f);"])

    @staticmethod
    def include_issues(filename, text):
        """(line, rule) of the include rules for a file with this text, the file does not have to exist"""
        import oc_cpp_issues
        found = []
        oc_cpp_issues.check_includes(filename, text.splitlines(keepends=True), lambda _f, line, rule, *_: found.append((int(line), rule)))
        return found

    def test_self_include(self):
        header = os.path.abspath(os.path.join("project", "inifile", "configuration.h"))
        for line in ['#include "configuration.h"', '#include "./configuration.h"', '#include "inifile/configuration.h"',
                     "#include <inifile/configuration.h>"]:
            self.assertEqual(self.include_issues(header, line + "\n"), [(1, "self-include")], line)
        # another file with the same name, and a wrapper header that includes the real one from the include path
        for line in ['#include "configuration/configuration.h"', "#include <configuration.h>", '#include "other.h"']:
            self.assertEqual(self.include_issues(header, line + "\n"), [], line)
        self.assertEqual(self.include_issues(header.replace(".h", ".cpp"), '#include "configuration.h"\n'), [])

    def test_duplicate_include(self):
        text = "\n".join(["#include <vector>",                       # 1
                          "#include <vector>",                       # 2 duplicate
                          "#if defined(__GNUC__)",                   # 3
                          "#include <regex>",                        # 4
                          "#include <vector>",                       # 5 duplicate, line 1 encloses this branch
                          "#elif defined(_MSC_VER)",                 # 6
                          "#include <regex>",                        # 7 another branch
                          "#else",                                   # 8
                          "#include <regex>",                        # 9 another branch
                          "#  ifdef X",                              # 10
                          "#include <regex>",                        # 11 duplicate, line 9 encloses this branch
                          "#  endif",                                # 12
                          "#endif",                                  # 13
                          "#include <regex>",                        # 14 the earlier ones are in branches
                          "#include <regex>"]) + "\n"                # 15 duplicate of line 14
        self.assertEqual(self.include_issues(os.path.abspath("a.cpp"), text),
                         [(2, "duplicate-include"), (5, "duplicate-include"), (11, "duplicate-include"), (15, "duplicate-include")])

    def test_local_helper_macros(self):
        import oc_cpp_issues
        text = "\n".join(["#undef Bool",                              # 1 a macro of another file
                          "#define HDR() print(name)",                # 2 a local helper, #undef'd on line 4
                          "HDR();",                                   # 3
                          "#undef HDR",                               # 4
                          "#define GET \"GET\"",                      # 5 short and never #undef'd
                          "#undef ABC",                               # 6 #undef before its #define
                          "#define ABC 1"]) + "\n"                    # 7 short, the #undef is before it
        found = []
        oc_cpp_issues.check_macros("a.cpp", text.splitlines(keepends=True), lambda _f, line, rule, *_: found.append((int(line), rule)))
        self.assertEqual(found, [(1, "undef-macro"), (6, "undef-macro"), (5, "short-macro-name"), (7, "short-macro-name")])

    def test_unnamed_lock(self):
        self.assert_rule("unnamed-lock", ["std::lock_guard<std::mutex>{m_mutex};", "std::unique_lock<std::mutex>(m);",
                                          "  std::scoped_lock{a, b};", "QMutexLocker(&m_mutex);", "lock_guard<mutex>{m};"],
                         ["std::lock_guard<std::mutex> lock(m_mutex);", "std::scoped_lock lock{a, b};", "std::lock_guard lock(m);",
                          "QMutexLocker locker(&m_mutex);", "return std::unique_lock<std::mutex>(m);",
                          "auto lock = std::unique_lock<std::mutex>(m);", "f(std::unique_lock<std::mutex>(m));"])

    def test_suppressed_warning(self):
        self.assert_rule("suppressed-warning", ["#pragma warning(disable: 4996)", "#pragma warning( disable : 4100 4101 )",
                                                "#pragma warning(suppress: 4100)", "#pragma warning(push, 0)",
                                                '#pragma GCC diagnostic ignored "-Wunused"', '#  pragma clang diagnostic ignored "-Wfoo"'],
                         ["#pragma warning(push)", "#pragma warning(pop)", "#pragma GCC diagnostic push",
                          '#pragma GCC diagnostic warning "-Wall"', "#pragma once"])

    def test_empty_catch(self):
        import oc_cpp_issues
        text = "\n".join(["try { f(); }",                             # 1
                          "catch (...) {}",                           # 2 empty
                          "try { f(); }",                             # 3
                          "catch (const std::exception & e)",         # 4 empty, over three lines
                          "{",                                        # 5
                          "}",                                        # 6
                          "catch (...) { /* ignore, best effort */ }",  # 7 a comment says it is intended
                          "catch (...) { throw; }",                   # 8
                          "catch (...)",                              # 9
                          "{",                                        # 10
                          "    // the file may not exist",            # 11
                          "}"]) + "\n"                                # 12
        rules = [(int(issue[1]), issue[2]) for issue in oc_cpp_issues.find_issues("a.cpp", text.splitlines(keepends=True),
                                                                                  oc_cpp_issues.check_source_line)]
        self.assertEqual(rules, [(2, "empty-catch"), (4, "empty-catch")])

    def test_min_max_macro(self):
        self.assert_rule("min-max-macro", ["#define min(a, b) ((a) < (b) ? (a) : (b))", "#define MAX(a,b) ((a)>(b)?(a):(b))",
                                           "# define max(a, b) x"],
                         ["#define MAX_LEN (big ? 10 : 20)", "#define CLAMP(x) std::min(std::max(x, 0), 9)", "#define MAXIMUM(a) a"])

    def test_assign_in_condition(self):
        self.assert_rule("assign-in-condition", ["if (x = y)", "while (n = next(it))", "switch (k = key())", "if (*p = c)",
                                                 "if (m_state = Idle)", "if (a.b = f(c))", "while (p->next = q)"],
                         ["if (auto x = f(); x != 0)", "if (const int i = index(); i != -1)", "if ((x = f()))",
                          "if (auto x = f())", "if (const auto n = count())", "if (Foo * p = find(k))", "while (Node * n = next())",
                          "if ((fp = fopen(name, \"r\")) == nullptr)", "while ((c = getchar()) != EOF)", "if (a == b)",
                          "while (x <= y)", "if (a != b)"])

    def test_extern_volatile_is_reported_once(self):
        self.assertEqual(self.line_rules("extern volatile int g;"), ["extern-volatile"])
        self.assertEqual(self.line_rules("extern int g;"), ["extern"])
        self.assertEqual(self.line_rules("volatile int g;"), ["volatile-variable"])

    def test_make_unique(self):
        self.assert_rule("make-unique-header", ['#include "make_unique.h"', '#include "util/make_unique.hpp"'],
                         ["#include <memory>", "auto p = std::make_unique<int>();"])
        self.assert_rule("unqualified-make-unique", ["auto p = make_unique<int>();", "auto p = boost::make_unique<int>();"],
                         ["auto p = std::make_unique<int>();", "auto id = make_unique_id();", '#include "make_unique.h"'])

    SOURCE = """#include "a.h"
#include <vector>
#include <vector>
#include "other.cpp"
throw new std::runtime_error("x");
throw "this is wrong";
throw 1;
throw std::runtime_error("fine");
memset(p, sizeof(p), 0);
memset(p, 0, sizeof(p));
memset(a, 0, f(b, 0));
f((void **)&p);
g(reinterpret_cast<void**>(&p));
std::string buffer{10};
std::wstring wbuffer{ 4 };
std::string name{other};
#undef min
x = x;
this->x = x;
other.x = x;
y == y;
#define AB 1
#define ABCD 1
catch (std::exception e)
catch (const std::exception& e)
catch (...)
ptr.reset(new Foo);
if (std::uncaught_exception()) {}
if (std::uncaught_exceptions()) {}
char *** p3;
/*** comment ***/
Foo::Foo() {}
Foo::~Foo() { }
Foo::Foo() : x(1) {}
// TODO: fix this
std::string todos;
if (&ref == nullptr) {}
if (a && b == nullptr) {}
for (;;) {}
foreach (auto x, list) {}
for (auto & x : myList.transform().view()) {}
for (auto & x : obj.items()) {}
int a;; int b;
for (int i = 0;; ++i) {}
int count;
int count = 0;
#define __MY_MACRO 1
#define MY__MACRO 1
#define MY_MACRO 1
"""
    HEADER = """#ifndef MOVE_H
#define MOVE_H
#include "a.h"
int member;
#endif
#ifndef MY_LIBRARY_MOVE_H
#define MY_LIBRARY_MOVE_H
#endif
"""

    def test_rules_of_issues_4_and_9(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for name, text in [("a.cpp", self.SOURCE), ("a.h", self.HEADER)]:
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(text)
            rows = [line.split("|") for line in lines(run_script("oc_cpp_issues.py", [d]))]
        found = sorted((os.path.basename(row[3].rsplit(":", 1)[0]), int(row[3].rsplit(":", 1)[1]), row[5]) for row in rows)
        expected = {"a.cpp": [(3, "duplicate-include"), (4, "include-source-file"), (5, "throw-pointer"),
                              (6, "throw-non-exception"), (7, "throw-non-exception"), (9, "memset-zero-size"),
                              (12, "void-pointer-pointer-cast"), (13, "reinterpret-cast"), (13, "void-pointer-pointer-cast"),
                              (14, "string-braced-size"), (15, "string-braced-size"), (17, "undef-macro"),
                              (18, "assign-to-self"), (22, "short-macro-name"), (24, "catch-by-value"),
                              (27, "reset-with-new"), (28, "deprecated-uncaught-exception"), (30, "triple-pointer"),
                              (32, "empty-special-member"), (33, "empty-special-member"), (35, "todo"),
                              (37, "address-null-check"), (39, "endless-for"), (40, "foreach-macro"),
                              (41, "dangling-range-for"), (43, "redundant-semicolon"), (43, "uninitialized-variable"),
                              (45, "uninitialized-variable"), (47, "reserved-macro-name"), (48, "reserved-macro-name")],
                    "a.h": [(2, "short-include-guard"), (3, "self-include")]}
        self.assertEqual(found, sorted((name, line, rule) for name, issues in expected.items() for line, rule in issues))

    def test_reserved_define_names_the_macro(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.cc"), "w", encoding="utf-8") as f:
                f.write("#define _Reserved 1\n")
            rows = [line.split("|") for line in lines(run_script("oc_cpp_issues.py", [d]))]
            reserved = [row for row in rows if row[5] == "reserved-macro-name"]
            self.assertEqual(len(reserved), 1, rows)
            self.assertIn("(_Reserved)", reserved[0][7])
            self.assertIn("[5]{https://github.com/janwilmans/OpenCanary/blob/main/documentation/rules.md#reserved-macro-name}", reserved[0][8])

    def test_spelling(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.cc"), "w", encoding="utf-8") as f:
                # whole words only and case sensitive, as grep -w: not wich_x, xwich or Wich; literals are checked too
                f.write('// recieve\nint wich_x, xwich, Wich;\nlog("seperate, wich");\n')
            rows = [line.split("|") for line in lines(run_script("oc_cpp_issues.py", [d]))]
        self.assertEqual([(row[3].rsplit(":", 1)[1], row[7]) for row in rows if row[5] == "misspelled-word"],
                         [("1", "Misspelled word &#x27;recieve&#x27; found"), ("3", "Misspelled word &#x27;seperate&#x27; found"),
                          ("3", "Misspelled word &#x27;wich&#x27; found")])

    COMMENTED = """// int* p = (int*)q; NULL
int* p = (int*)q; // NULL todo
/* reinterpret_cast<int*>(x);
   delete p;
*/ const_cast<int*>(y);
const char* s = "// (int*) is not a comment";
int n = 1'000; // (char*)x
#include "b.h"
/*
#include "b.h" */
#include "b.h"
"""

    def test_code_rules_do_not_look_at_comments(self):
        import oc_cpp_issues
        text = self.COMMENTED + "// returns NULL if it Check***Window() fails\n#define X 1 // Dutch: deze naam\n"
        issues = oc_cpp_issues.find_issues("a.cpp", text.splitlines(keepends=True), oc_cpp_issues.check_source_line)
        # the code of line 2 and 5, the todo in the comment of line 2, the include of line 11 duplicates line 8 (the one
        # in the comment on line 10 is not an include), and the Dutch words in the comment of line 13
        self.assertEqual(sorted((int(issue[1]), issue[2]) for issue in issues),
                         [(2, "c-style-pointer-cast"), (2, "todo"), (5, "const-cast"), (11, "duplicate-include"),
                          (13, "non-english-word"), (13, "short-macro-name")])

    def test_misspelled_words_everywhere(self):
        import oc_cpp_issues
        text = 'int recieve; // recieve\n/* wich */ int wich;\nint x; // seperate\nlog("untill");\n'
        issues = oc_cpp_issues.find_issues("a.cc", text.splitlines(keepends=True), oc_cpp_issues.check_source_line)
        self.assertEqual([issue[1] for issue in issues if issue[2] == "misspelled-word"], ["1", "1", "2", "2", "3", "4"])

    def test_view_keeps_columns_and_line_endings(self):
        import oc_cpp_issues as oc
        lines = ["a /* b */ c // d\n", "'/' /* e\r\n", "f */ g\n", 'x = "s"; // t\n', '#include "a.h" // b\n']
        masks = oc.classify(lines)
        self.assertEqual(oc.view(lines, masks, oc.CODE),
                         ["a         c     \n", "' '     \r\n", "     g\n", 'x = " ";     \n', '#include "a.h"     \n'])
        self.assertEqual(oc.view(lines, masks, oc.COMMENT),
                         ["  /* b */   // d\n", "    /* e\r\n", "f */  \n", "         // t\n", "               // b\n"])


class TestCompileFlags(unittest.TestCase):

    @staticmethod
    def entry(file, target, *flags, compiler="g++"):
        return {"directory": "/build", "file": file,
                "arguments": [compiler, *flags, "-o", f"{target}/CMakeFiles/{target}.dir/x.o", "-c", file]}

    def run_flags(self, database, options=()):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "compile_commands.json"), "w", encoding="utf-8") as f:
                json.dump(database, f)
            # the build directory works as well as the file
            return [line.split("|") for line in lines(run_script("compile_flags.py", [d, *options]))]

    def test_a_dependency_with_another_standard(self):
        database = [self.entry(f"/src/app/{n}.cc", "app", "-std=c++17") for n in range(3)]
        database += [self.entry("/src/dep/b.cpp", "dep", "-std=gnu++14"), self.entry("/src/dep/a.cpp", "dep", "-std=c++1y")]
        # the C standard of a C source does not count
        database.append(self.entry("/src/dep/c.c", "dep", "-std=c99"))
        rows = self.run_flags(database)
        self.assertEqual([(row[0], row[3], row[4], row[5], row[6]) for row in rows],
                         [("99", "/src/dep/a.cpp", "opencanary", "inconsistent-compile-flags", "bug")])
        self.assertTrue(rows[0][7].startswith("language standard is C++14 for 2 files of dep, but C++17 for 3 other"), rows[0][7])
        self.assertIn("[5]{https://github.com/janwilmans/OpenCanary/blob/main/documentation/rules.md#inconsistent-compile-flags}", rows[0][8])

    def test_the_same_standard_is_not_reported(self):
        database = [self.entry("/src/a.cc", "a", "-std=c++17"), self.entry("/src/b.cc", "b", "-std=gnu++17"),
                    self.entry("/src/c.cc", "c", "-std=c++1z", "-DNDEBUG", "-O2", "-Wall")]
        self.assertEqual(self.run_flags(database), [])

    def test_abi_macros_and_layout_flags(self):
        import compile_flags
        values = compile_flags.settings(["g++", "-D_GLIBCXX_USE_CXX11_ABI=0", "-D", "variant_CONFIG_SELECT_VARIANT=1",
                                         "-DOTHER=1", "-fshort-enums", "-fno-short-enums", "-m32", "-U_GLIBCXX_DEBUG"])
        self.assertEqual(values, {"language standard": "(default)", "_GLIBCXX_USE_CXX11_ABI": "0", "variant_CONFIG_SELECT_VARIANT": "1",
                                  "enum size": "(default)", "data model": "-m32", "_GLIBCXX_DEBUG": "(not defined)"})
        msvc = compile_flags.settings(["cl.exe", "/nologo", "/TP", "/std:c++20", "/MDd", "/Zp4", "/DFOO", "/D_ITERATOR_DEBUG_LEVEL=2"])
        self.assertEqual(msvc, {"language standard": "C++20", "runtime library": "/MDd", "struct packing": "/Zp4",
                                "_ITERATOR_DEBUG_LEVEL": "2"})

    def test_macro_defined_in_one_target(self):
        database = [self.entry("/src/app/a.cc", "app"), self.entry("/src/app/b.cc", "app"),
                    self.entry("/src/dep/d.cc", "dep", "-Dvariant_CONFIG_SELECT_VARIANT=1")]
        rows = self.run_flags(database)
        self.assertEqual([(row[3], row[7].split(":")[0]) for row in rows],
                         [("/src/dep/d.cc", "variant_CONFIG_SELECT_VARIANT is 1 for 1 file of dep, but (not defined) for 2 other translation units")])

    def test_options(self):
        database = [self.entry(f"/src/app/{n}.cc", "app", "-std=c++17", "-DMYLIB_CONFIG_FAST=1", "/MD") for n in range(3)]
        database += [self.entry("/src/lib/a.cc", "lib", "-std=c++17", "-DMYLIB_CONFIG_FAST=0", "/MT"),
                     self.entry("/src/old/a.cc", "old_legacy", "-std=c++11"), self.entry("/src/old/b.cc", "old_legacy", "-std=c++11")]
        # without options: the legacy target's standard; MYLIB_CONFIG_FAST is not compared, the runtime library is
        rows = self.run_flags(database)
        self.assertEqual(sorted(row[7].split(" is ")[0] for row in rows), ["language standard", "runtime library", "runtime library"])
        rows = self.run_flags(database, ["--macro=MYLIB_CONFIG_*", "--ignore-setting=runtime library", "--ignore-target=*_legacy"])
        self.assertEqual([(row[3], row[7].split(" for ")[0]) for row in rows], [("/src/lib/a.cc", "MYLIB_CONFIG_FAST is 0")])

    def test_command_strings_and_targets(self):
        import compile_flags
        units = compile_flags.translation_units([
            {"directory": "C:/b", "file": "w.cpp", "command": r"C:\PROGRA~1\cl.exe /TP /std:c++17 /FoCMakeFiles\win.dir\w.cpp.obj /c C:\s\w.cpp"},
            {"directory": "/b", "file": "/s/lib/x.cc", "command": "g++ -std=c++14 -c /s/lib/x.cc"},
            {"directory": "/b", "file": "/s/lib/y.c", "command": "gcc -x c++ -std=c++14 -c /s/lib/y.c"},
            {"directory": "/b", "file": "/s/lib/z.cc", "command": "g++ -x c -c /s/lib/z.cc"}])
        # without an output in a CMakeFiles/<target>.dir the target is the directory of the source
        self.assertEqual([(target, file, values["language standard"]) for target, file, values in units],
                         [("win", "C:/b/w.cpp", "C++17"), ("/s/lib", "/s/lib/x.cc", "C++14"), ("/s/lib", "/s/lib/y.c", "C++14")])


class TestPype(unittest.TestCase):

    def test_summary_log(self):
        import tempfile
        output = ["building a.cc", "FAILED: a.o", "a.cc:3:1: error: oops", "[  PASSED  ] 3 tests",
                  "x_test.cc:12: Failure", "SUMMARY: AddressSanitizer: heap-use-after-free src/a.cc:9 in f",
                  "SUMMARY: AddressSanitizer: heap-use-after-free src/a.cc:9 in f", "lib.so: ubsan: overflow"]
        script = "; ".join(f"print({line!r})" for line in output) + "; raise SystemExit(3)"
        with tempfile.TemporaryDirectory() as d:
            command = [sys.executable, os.path.join(HERE, "pype.py"), "build.log", "build_summary", "test_summary",
                       "--", f'"{sys.executable}"', "-c", f'"{script}"']
            result = subprocess.run(command, cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            self.assertEqual(result.returncode, 3, result.stderr)
            with open(os.path.join(d, "build.log"), encoding="utf-8") as f:
                self.assertEqual(f.read().splitlines(), output)
            with open(os.path.join(d, "summary.log"), encoding="utf-8") as f:
                summary = f.read().splitlines()
        self.assertEqual(summary[:3], ["FAILED: a.o", "a.cc:3:1: error: oops", "x_test.cc:12: Failure"])
        self.assertIn("ASAN: 2 issues (1 unique)", summary)
        self.assertIn("UBSAN: 1 issues (1 unique)", summary)
        self.assertEqual(summary[-2:], ["----- Sanitizer issues with direct source references ----",
                                        "SUMMARY: AddressSanitizer: heap-use-after-free src/a.cc:9 in f"])

    def test_no_summary_log_without_options(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            command = [sys.executable, os.path.join(HERE, "pype.py"), "build.log", "--", f'"{sys.executable}"', "-c", '"print(1)"']
            subprocess.run(command, cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            self.assertFalse(os.path.exists(os.path.join(d, "summary.log")))


class TestPrettyDiff(unittest.TestCase):

    @unittest.skipUnless(__import__("importlib.util").util.find_spec("docopt"), "prettydiff.py needs docopt")
    def test_numeric_tolerance(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            old, new = os.path.join(d, "old.txt"), os.path.join(d, "new.txt")
            with open(old, "w", encoding="utf-8") as f:
                f.write("a|10|x\nb|1|x\n")
            with open(new, "w", encoding="utf-8") as f:
                f.write("a|11|x\nc|1|x\n")
            out = lines(run_script("prettydiff.py", [old, new, "--num=1,1"]))
            self.assertIn("+ c|1|x", out)
            self.assertIn("- b|1|x", out)
            self.assertFalse(any(line.startswith(("+ a", "- a")) for line in out), out)


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
        self.assertEqual(prios, ["5", "99"])

    def test_msvc_priorities_come_from_the_rules_file(self):
        out = run_script("apply_team_priorities.py", stdin=self.row(rule="C4100") + self.row(rule="C4701") + self.row(rule="C4505"))
        self.assertEqual([line.split("|")[0] for line in lines(out)], ["70", "5", "60"])

    def test_cppcheck_issues_are_unassigned(self):
        import contextlib
        import io
        import cppcheck
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cppcheck.report_issue("src/a.cc", "12", "rule", "message", "", "style")
            cppcheck.report_issue("cppcheck", 0, "exec", "cppcheck exited with exitcode 1", "ci", "ci")
        # apply_team_priorities.py assigns the priority, as for the other parsers
        self.assertEqual([line.split("|")[0] for line in lines(out.getvalue())], ["99", "99"])

    def test_cppcheck_output_is_parsed(self):
        import contextlib
        import io
        import cppcheck
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            cppcheck.parse("C:\\project\\a.cc\t12\tstyle\tvariableScope\tThe scope of the variable 'x' can be reduced: see 'f'.")
            cppcheck.parse("C:\\project\\a.cc\t5\tinformation\tmissingInclude\tInclude file: \"a.h\" not found.")
            cppcheck.parse("/home/me/project/src/b.cc\t3\twarning\tuninitvar\tUninitialized variable: y", "/home/me/project")
            cppcheck.parse("not a template line")
        rows = [line.split("|") for line in lines(out.getvalue())]
        self.assertEqual([(row[3], row[5], row[6], row[7]) for row in rows],
                         [("C:/project/a.cc:12", "variableScope", "style", "The scope of the variable &#x27;x&#x27; can be reduced: see &#x27;f&#x27;."),
                          ("src/b.cc:3", "uninitvar", "warning", "Uninitialized variable: y")])
        self.assertEqual(vars(cppcheck.parse_args(["env.txt", "src", "base"])), {"path": "src", "basepath": "base"})
        self.assertEqual(vars(cppcheck.parse_args(["src"])), {"path": "src", "basepath": None})

    def test_cppcheck_runs_in_parallel_only_where_file_names_are_case_sensitive(self):
        import cppcheck
        self.assertEqual(cppcheck.PARALLEL, sys.platform not in ("win32", "darwin"))
        original = cppcheck.PARALLEL
        try:
            cppcheck.PARALLEL = True
            options = cppcheck.parallel_options("build")
            self.assertTrue(options[0].startswith("-j"))
            self.assertEqual(options[1], "--cppcheck-build-dir=build")
            cppcheck.PARALLEL = False
            self.assertEqual(cppcheck.parallel_options("build"), [])
        finally:
            cppcheck.PARALLEL = original

    def test_cppcheck_finds_the_compile_database_and_leaves_out_missing_files(self):
        import cppcheck
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "compile_commands.json")
            with open(os.path.join(d, "a.cpp"), "w", encoding="utf-8") as f:
                f.write("int a;\n")
            with open(db, "w", encoding="utf-8") as f:
                f.write("[]")
            self.assertEqual(cppcheck.compile_db_path(d), db)
            self.assertEqual(cppcheck.compile_db_path(db), db)
            self.assertIsNone(cppcheck.compile_db_path(os.path.join(d, "src")))
            database = [{"directory": d, "file": "a.cpp"},
                        {"directory": d, "file": os.path.join(d, "a_autogen", "mocs_compilation.cpp")}]
            kept, missing = cppcheck.existing_entries(database)
        self.assertEqual(kept, database[:1])
        self.assertEqual(missing, [cppcheck.normpath(os.path.join(d, "a_autogen", "mocs_compilation.cpp"))])

    @unittest.skipUnless(sys.version_info >= (3, 11), "opencanary.py run needs tomllib (python 3.11+)")
    @unittest.skipUnless(__import__("cppcheck").cppcheck_cmd and __import__("shutil").which(__import__("cppcheck").cppcheck_cmd),
                         "needs cppcheck")
    def test_run_cppcheck_input(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.cpp"), "w", encoding="utf-8") as f:
                f.write("int f()\n{\n    int x;\n    return x;\n}\n")
            with open(os.path.join(d, "oc.toml"), "w", encoding="utf-8") as f:
                f.write('[[input]]\nformat = "cppcheck"\npath = "."\n')
            run_script("opencanary.py", ["run", "-c", os.path.join(d, "oc.toml")])
            with open(os.path.join(d, "issues.txt"), encoding="utf-8") as f:
                rows = [line.split("|") for line in lines(f.read())]
        self.assertIn(("cppcheck", "uninitvar", "a.cpp:4"), [(row[4], row[5], os.path.basename(row[3])) for row in rows])

    def test_low_hanging_fruit_threshold(self):
        rare = self.row(rule="rare", file="a.cc:1")
        important = self.row("5", rule="important", file="c.cc:1")
        common = "".join(self.row(rule="common", file=f"b.cc:{i}") for i in range(1, 22))
        out = lines(run_script("apply_low_hanging_fruit.py", stdin=rare + important + common))
        self.assertEqual(out[0], rare.rstrip("\n").replace("8|", "7|", 1))  # only the priority changes
        self.assertEqual(out[1], important.rstrip("\n"))  # a more important priority than 7 is kept
        self.assertTrue(all(line.startswith("8|") for line in out[2:]))
        self.assertEqual(len(out), 23)

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

    def test_optional_lines_without_value_are_removed(self):
        import tempfile
        data = '<p data-optional="">Branch: [[branch-id]]</p>\n<p data-optional="">By: [[user-name]]</p>\nplain [[user-name]]\n'
        with tempfile.TemporaryDirectory() as d:
            env = os.path.join(d, "env.txt")
            with open(env, "w", encoding="utf-8") as f:
                f.write("CI_COMMIT_REF_NAME=main\n")
            out = run_script("apply_environment.py", [env], data)
        self.assertEqual(out, '<p data-optional="">Branch: main</p>\nplain [[GITLAB_USER_NAME not found by get_from_envfile()]]\n')

    def test_apply_environment_replaces_placeholders(self):
        out = run_script("apply_environment.py", [os.path.join(TESTDATA, "env.txt")], "[[job-url]] [[user-name]]\n")
        self.assertEqual(out.strip(), "https://ci.example.com/group/proj/-/jobs/42 Test User")


if __name__ == "__main__":
    unittest.main()

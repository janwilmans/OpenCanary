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
        self.assertEqual(util.get_rule_url("cpp check", "AP#13"), "https://duckduckgo.com/?q=!ducky+cpp+check+AP%2313")

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

    def test_solution_link_is_not_a_column(self):
        report = run_script("create_report.py", stdin=self.row("5", link="[5]{https://x/rule}[solution]{[[permalink-prefix]]/rule}"))
        self.assertTrue(is_valid_xml(report))
        self.assertEqual(report_rows(report)[0][-1], {"5": "https://x/rule", "solution": "[[permalink-prefix]]/rule"})
        self.assertIn("How to solve", report)

    def test_theme_button(self):
        report = run_script("create_report.py", stdin=self.row("5"))
        self.assertTrue(is_valid_xml(report))
        self.assertIn('id="theme"', report)
        # the dark colors apply both for the system setting and for the button
        self.assertIn(':root:not([data-theme="light"])', report)
        self.assertIn(':root[data-theme="dark"]', report)
        self.assertNotIn("/*DARK*/", report)

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
    def row(prio, rule, team, component, category, description="d", file="a.cc:1", links=""):
        return "|".join([prio, team, component, file, "src", rule, category, description, links]) + "\n"

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
                + self.row("10", "C4456", "net", "x", "warning") * 2)
        summary = run_script("create_summary.py", stdin=data)
        self.assertTrue(is_valid_xml(summary))
        self.assertNotIn("<script", summary)
        self.assertNotIn("class=", summary)
        # rules by number of issues (fewest first), then name; within a rule by count; the first description of each rule
        self.assertEqual(self.table(summary), [
            ["Prio", "Rule", "Total", "Description", "Team", "Component", "Category", "Issues"],
            ["7, 9", "b<ad", "2", " ".join(["word"] * 20) + "…", "(none)", "(none)", "(none)", "2"],
            ["10", "C4456", "2", "d", "net", "x", "warning", "2"],
            ["45", "manual-delete", "5", "later", "gui", "CsGui", "redflag", "2"],
            ["core", "CsCore", "redflag", "3"],
            ["", "Total", "9", "", "", "", "", "9"],
        ])
        self.assertNotIn("#f1f3f6", summary)
        self.assertEqual(summary.count('<th align='), 8 + 5)   # both tables have the header in the color of the total line
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
        self.assertEqual(top[0], ["Prio", "File", "Rule", "Team", "Description"])
        self.assertEqual(top[1:4], [["5", "b.cc:7", "first", "core", "x < y"], ["20", "c.cc:2", "second", "(none)", "d"],
                                    ["50", "z.cc:1", "late", "t", "d"]])
        self.assertEqual(len(top), 11)
        self.assertIn('<a href="[[permalink-prefix]]/b.cc#L7"', summary)
        self.assertNotIn("https://rule", summary)

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
        out = self.links("", self.row("gcc", "sign-compare", "[3]{f}[5]{https://parser}"), self.row("opencanary", "AP#13", "[3]{f}"),
                         self.row("gcc", ""))
        self.assertEqual(out, ["[3]{f}[5]{https://parser}", "[3]{f}[5]{https://duckduckgo.com/?q=!ducky+opencanary+AP%2313}", ""])

    def test_configured_links_and_placeholders(self):
        rules = ("link:https://docs/<source>/<rule>  ?^C4\n"
                 "solution:https://example/rules.md#<anchor>  ?^AP#\n"
                 "solution:[[permalink-prefix]]/<rule>  ~C4\n")
        out = self.links(rules, self.row("msvc", "C4100", "[5]{https://parser}"), self.row("opencanary", "AP#13"))
        import util
        self.assertEqual([util.heading_anchor(rule) for rule in ["AP#13", "C4100", "sign-compare", "format-truncation=", "a_b c"]],
                         ["ap13", "c4100", "sign-compare", "format-truncation", "a_b-c"])
        self.assertEqual(out, ["[5]{https://docs/msvc/C4100}[solution]{[[permalink-prefix]]/C4100}",
                               "[5]{https://duckduckgo.com/?q=!ducky+opencanary+AP%2313}[solution]{https://example/rules.md#ap13}"])


class TestRulesDocumentation(unittest.TestCase):

    def test_every_rule_has_a_section_and_a_solution_link(self):
        import re
        import apply_links
        import util
        with open(os.path.join(HERE, "oc_cpp_issues.py"), encoding="utf-8") as f:
            # the rule of every report_issue() call that is not commented out
            rules = set(re.findall(r'^\s*report_issue\([^,]+, [^,]+, "([^"]+)"', f.read(), re.M))
        import oc_cpp_issues
        rules |= {rule for rule, _category, _regex, _description in oc_cpp_issues.LINE_RULES}
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

    @unittest.skipUnless(__import__("shutil").which("rg"), "needs ripgrep (rg)")
    def test_spelling_check_ignores_stdin(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.cc"), "w", encoding="utf-8") as f:
                f.write("// recieve\n")
            rows = [line.split("|") for line in lines(run_script("oc_cpp_issues.py", [d], stdin="wich\n"))]
            self.assertEqual([(row[5], row[3].rsplit(":", 1)[1]) for row in rows if row[5] == "misspelled-word"], [("misspelled-word", "1")], rows)

    def test_spelling_matches_are_limited_to_the_checked_files(self):
        import oc_cpp_issues
        root = os.path.abspath("project")
        checked = os.path.join(root, "src", "a.cc")
        rg_output = "\n".join([os.path.join("src", "a.cc") + ":12:5:recieve",
                               os.path.join("ignored", "b.cc") + ":3:1:wich",
                               "not a match line"])
        self.assertEqual(oc_cpp_issues.get_spelling_violations(rg_output, root, [checked]), [(checked, "12", "recieve")])


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

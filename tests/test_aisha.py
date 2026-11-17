"""Tests for aisha. Run: python3 -m unittest discover -s tests"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
AISHA = os.path.join(HERE, "..", "aisha")

_loader = importlib.machinery.SourceFileLoader("aisha", AISHA)
_spec = importlib.util.spec_from_loader("aisha", _loader)
aisha = importlib.util.module_from_spec(_spec)
sys.modules["aisha"] = aisha
_loader.exec_module(aisha)


def make_lab(root):
    os.makedirs(os.path.join(root, "run1"))
    os.makedirs(os.path.join(root, "src"))
    os.makedirs(os.path.join(root, ".git"))
    files = {
        "run1/measurements_01.csv": "time,temperature\n1,21.5\n",
        "run1/notes.txt": "Sensor log: measured pressure 1.2 bar\n",
        "run1/shopping.txt": "milk, eggs\n",
        "src/main.py": "print('hi')  # TODO fix\n",
        "README.md": "hello\n",
        "old.tmp": "",
        ".git/config": "measurement\n",   # must never be searched
    }
    for path, text in files.items():
        with open(os.path.join(root, path), "w") as f:
            f.write(text)


class LabTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lab = self.tmp.name
        make_lab(self.lab)

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, text):
        return aisha.interpret(text, self.lab)

    def cmd(self, text):
        p = self.plan(text)
        self.assertIsNotNone(p, text)
        self.assertGreaterEqual(p.confidence, aisha.DEFAULTS["threshold"], f"{text}: {p.rationale()}")
        return p.command

    def run_cmd(self, cmd):
        r = subprocess.run(["bash", "-c", cmd], cwd=self.lab, capture_output=True, text=True)
        return sorted(r.stdout.split())


class TestRules(LabTest):
    def test_measurement_example(self):
        cmd = self.cmd("find files on this folder that has the measurement data")
        self.assertIn("measur", cmd)
        self.assertEqual(self.run_cmd(cmd), ["./run1/measurements_01.csv", "./run1/notes.txt"])

    def test_content_only(self):
        cmd = self.cmd('find files that contain "pressure"')
        self.assertEqual(self.run_cmd(cmd), ["./run1/notes.txt"])

    def test_typed_content(self):
        cmd = self.cmd("find csv files containing temperature")
        self.assertEqual(self.run_cmd(cmd), ["./run1/measurements_01.csv"])

    def test_which_files_mention(self):
        cmd = self.cmd('which files mention "eggs"')
        self.assertEqual(self.run_cmd(cmd), ["./run1/shopping.txt"])

    def test_text_search_lines(self):
        cmd = self.cmd("find TODO in python files")
        self.assertTrue(cmd.startswith("grep -rniIF --include='*.py'"), cmd)

    def test_search_named_file_deeper(self):
        cmd = self.cmd("search notes.txt for pressure")
        self.assertIn("--include=notes.txt", cmd)

    def test_listing(self):
        self.assertEqual(self.cmd("list all files"), "ls -lhA")
        self.assertEqual(self.cmd("list folders"), "ls -lhd -- */")
        cmd = self.cmd("show the 5 newest files here")   # files only, so find, not ls
        self.assertIn("-maxdepth 1", cmd)
        self.assertIn("-type f", cmd)
        self.assertIn("sort -r | head -n 5", cmd)
        self.assertEqual(self.cmd("what's in run1"), "ls -lh -- run1")

    def test_find_filters(self):
        cmd = self.cmd("find python files modified in the last 3 days")
        self.assertIn("-iname '*.py' -mtime -3", cmd)
        cmd = self.cmd("find pdfs bigger than 10mb")
        self.assertIn("-iname '*.pdf' -size +10M", cmd)
        cmd = self.cmd("find files smaller than 1.5kb")
        self.assertIn("-size -1536c", cmd)
        self.assertIn("-type d -empty", self.cmd("find empty folders"))
        self.assertIn("-daystart -mtime 0", self.cmd("find files modified today"))
        self.assertIn("-mtime +7", self.cmd("find files older than a week"))

    def test_sorting(self):
        cmd = self.cmd("find big files")
        self.assertIn("sort -nr | head -n 10", cmd)
        cmd = self.cmd("list the 3 largest files in this folder recursively")
        self.assertIn("head -n 3", cmd)

    def test_file_names_are_not_words(self):
        # "old" inside old.tmp must not become an age filter
        self.assertEqual(self.cmd("delete old.tmp"), "rm -- old.tmp")

    def test_read(self):
        self.assertEqual(self.cmd("show the readme"), "cat README.md")
        self.assertEqual(self.cmd("first 5 lines of the readme"), "head -n 5 README.md")
        self.assertEqual(self.cmd("show the last 20 lines of README.md"), "tail -n 20 README.md")

    def test_file_ops(self):
        self.assertEqual(self.cmd("copy README.md to src"), "cp -i -- README.md src")
        self.assertEqual(self.cmd("rename README.md to README.txt"), "mv -i -- README.md README.txt")
        self.assertEqual(self.cmd("create a folder called reports and go into it"),
                         "mkdir -p -- reports && cd -- reports")
        self.assertEqual(self.cmd("make a new file named todo.txt"), "touch -- todo.txt")
        self.assertEqual(self.cmd("zip the src folder"), "zip -r src.zip src")

    def test_navigation(self):
        self.assertEqual(self.cmd("go up"), "cd ..")
        self.assertEqual(self.cmd("go to src"), "cd -- src")
        self.assertEqual(self.cmd("where am i"), "pwd")

    def test_system(self):
        self.assertEqual(self.cmd("how much ram is free"), "free -h")
        self.assertEqual(self.cmd("show me what processes use the most memory"),
                         "ps aux --sort=-%mem | head -n 11")
        self.assertTrue(self.cmd("disk space").startswith("df -h"))
        self.assertTrue(self.cmd("what's eating my disk").startswith("du -h --max-depth=1"))
        self.assertEqual(self.cmd("how big is this folder"), "du -sh .")

    def test_counting(self):
        cmd = self.cmd("how many files are in this project")
        self.assertEqual(self.run_cmd(cmd), ["6"])
        self.assertEqual(self.cmd("count lines in README.md"), "wc -l < README.md")


class TestSafety(LabTest):
    def test_deletes_are_flagged(self):
        p = self.plan("delete all .tmp files")
        self.assertTrue(p.destructive)
        self.assertIsNotNone(p.preview)
        self.assertTrue(self.plan("kill firefox").destructive)

    def test_never_delete_everything_from_vague_words(self):
        p = self.plan("delete everything")
        self.assertTrue(p is None or p.confidence < aisha.DEFAULTS["threshold"] or "rm" not in p.command)
        p = self.plan("clean up")
        self.assertTrue(p is None or "delete" not in p.command)

    def test_unknown_dates_go_to_llm(self):
        p = self.plan("find the file with the invoice from last tuesday")
        self.assertLess(p.confidence, aisha.DEFAULTS["threshold"])
        self.assertIn("tuesday", p.unknown)

    def test_unrelated_request_has_no_plan(self):
        p = self.plan("translate this poem to french")
        self.assertTrue(p is None or p.confidence < aisha.DEFAULTS["threshold"])


class TestShellDetection(LabTest):
    def shell(self, line):
        return aisha.looks_like_shell(line, None, self.lab)

    def test_real_commands_stay_bash(self):
        for line in ["ls -la", "git status", "cat README.md", "grep foo README.md",
                     'find . -name "*.py"', "apt install vim", "echo the files are here",
                     "FOO=bar", "ls | wc -l"]:
            self.assertTrue(self.shell(line), line)

    def test_sentences_are_words(self):
        for line in ["list all files", "find files bigger than 10mb", "find big files",
                     "kill firefox", "free memory", "which files are big", "who is logged in"]:
            self.assertFalse(self.shell(line), line)


class TestLLMHelpers(unittest.TestCase):
    def test_clean(self):
        c = aisha.clean_llm_command
        self.assertEqual(c("```bash\nls -la\n```"), "ls -la")
        self.assertEqual(c("$ du -sh ."), "du -sh .")
        self.assertEqual(c("Command: df -h"), "df -h")
        self.assertEqual(c("find . \\\n  -name x"), "find . -name x")
        self.assertIsNone(c("NONE"))
        self.assertIsNone(c("<think>hmm</think>\nNONE."))

    def test_validate(self):
        self.assertIsNone(aisha.validate_command("ls -la | wc -l"))
        self.assertIsNotNone(aisha.validate_command("if then fi"))
        self.assertIsNotNone(aisha.validate_command("frobnicate --all"))


class _MockLLM(BaseHTTPRequestHandler):
    replies = []
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _MockLLM.seen.append(body)
        reply = _MockLLM.replies.pop(0) if _MockLLM.replies else "NONE"
        out = json.dumps({"choices": [{"message": {"content": reply}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)


class TestShellSession(LabTest):
    def setUp(self):
        super().setUp()
        self.home = tempfile.TemporaryDirectory()
        aisha.LEARNED_FILE = os.path.join(self.home.name, "learned.json")
        self.server = HTTPServer(("127.0.0.1", 0), _MockLLM)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        cfg = dict(aisha.DEFAULTS, llm_url=f"http://127.0.0.1:{self.server.server_port}/v1",
                   llm_timeout=5.0, threshold=0.7)
        self.sh = aisha.Shell(cfg)
        self.sh.cwd = self.lab
        self.answers = []
        aisha.ask = lambda prompt: self.answers.pop(0) if self.answers else None

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.home.cleanup()
        super().tearDown()

    def test_cd_and_export_persist(self):
        self.sh.handle("go to run1")
        self.assertEqual(self.sh.cwd, os.path.join(self.lab, "run1"))
        self.sh.handle("export FOO=bar")
        self.assertEqual(self.sh.env.get("FOO"), "bar")
        self.sh.handle("cd ..")
        self.assertEqual(self.sh.cwd, self.lab)

    def test_destructive_needs_yes(self):
        self.answers = ["n"]
        self.sh.handle("delete all .tmp files")
        self.assertTrue(os.path.exists(os.path.join(self.lab, "old.tmp")))
        self.answers = ["y"]
        self.sh.handle("delete all .tmp files")
        self.assertFalse(os.path.exists(os.path.join(self.lab, "old.tmp")))

    def test_llm_fallback_retry_and_memory(self):
        _MockLLM.seen.clear()
        _MockLLM.replies = ["frobnicate --all", "```\ntouch from-llm.txt\n```"]
        self.answers = [""]  # Enter accepts
        rc = self.sh.handle("conjure a file from the void please")
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(self.lab, "from-llm.txt")))
        self.assertEqual(len(_MockLLM.seen), 2)  # one retry after the invalid command
        self.assertIn("Request: conjure a file", _MockLLM.seen[0]["messages"][-1]["content"])
        # second time: from memory, no model call, no question
        os.remove(os.path.join(self.lab, "from-llm.txt"))
        self.sh.handle("conjure a file from the void please")
        self.assertTrue(os.path.exists(os.path.join(self.lab, "from-llm.txt")))
        self.assertEqual(len(_MockLLM.seen), 2)

    def test_llm_declined_is_not_remembered(self):
        _MockLLM.replies = ["touch nope.txt"]
        self.answers = ["n"]
        self.sh.handle("summon a mystery file")
        self.assertFalse(os.path.exists(os.path.join(self.lab, "nope.txt")))
        self.assertIsNone(self.sh.memory.get("summon a mystery file"))


if __name__ == "__main__":
    unittest.main()

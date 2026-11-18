"""Tests for aisha. Run: python3 -m unittest discover -s tests"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import re
import shutil
import unittest
import warnings
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


def make_corpus(root):
    """The lab plus the files tests/phrases.tsv talks about."""
    import tarfile
    import zipfile
    make_lab(root)
    os.makedirs(os.path.join(root, "var", "log"))
    for path, text in {"var/log/app.log": "error: disk\n", "run.sh": "echo hi\n", "logs.txt": "x\n",
                       ".hidden": "", "report.pdf": ""}.items():
        with open(os.path.join(root, path), "w") as f:
            f.write(text)
    with open(os.path.join(root, ".git", "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")
    with open(os.path.join(root, "data.json"), "w") as f:
        f.write('{"a": 1}\n')
    with open(os.path.join(root, "people.csv"), "w") as f:
        f.write("name,age\nann,30\n")
    with zipfile.ZipFile(os.path.join(root, "backup.zip"), "w") as z:
        z.writestr("a.txt", "a")
    with tarfile.open(os.path.join(root, "data.tar.gz"), "w:gz") as t:
        t.add(os.path.join(root, "README.md"), "README.md")


def load_phrases():
    out = []
    with open(os.path.join(HERE, "phrases.tsv")) as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                phrase, expected = line.rstrip("\n").split("\t")
                out.append((phrase, expected))
    return out


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


class TestPhraseCorpus(unittest.TestCase):
    """Every line of tests/phrases.tsv."""

    def test_corpus(self):
        with tempfile.TemporaryDirectory() as lab:
            make_corpus(lab)
            failures = []
            for phrase, expected in load_phrases():
                problem = check_phrase(phrase, expected, lab)
                if problem:
                    failures.append(f"{phrase!r}: {problem}")
            self.assertEqual(failures, [], "\n" + "\n".join(failures))


def check_phrase(phrase, expected, lab):
    threshold = aisha.DEFAULTS["threshold"]
    if expected == "!SHELL":
        return None if aisha.looks_like_shell(phrase, None, lab) else "should run as bash"
    if aisha.looks_like_shell(phrase, None, lab):
        return "went to bash"
    plan = aisha.interpret(phrase, lab)
    if expected == "!LLM":
        if plan and plan.confidence >= threshold:
            return f"rules too sure ({plan.confidence:.2f}): {plan.command}"
        return None
    if not plan:
        return "no plan"
    if plan.confidence < threshold:
        return f"low confidence {plan.confidence:.2f}: {plan.rationale()} :: {plan.command}"
    missing = [frag for frag in expected.split(" ;; ")
               if not any(alt in plan.command for alt in frag.split(" || "))]
    return f"missing {missing} in: {plan.command}" if missing else None


class TestEverydayPhrases(LabTest):
    """The phrases people type most, with the variants and typos they type them with."""

    def old(self, name):
        path = os.path.join(self.lab, name)
        t = 1_500_000_000  # 2017
        os.utime(path, (t, t))

    def test_older_than_months(self):
        self.old("run1/shopping.txt")
        for phrase in ["find recursively files older that 2 months from this folder",
                       "find files older than 2 months",
                       "find files that are older than two months in this folder and its subfolders",
                       "find files over 2 months old",
                       "find 2 month old files",
                       "find recursivly files oldr than 2 months"]:
            cmd = self.cmd(phrase)
            self.assertIn("-mtime +60", cmd, phrase)
            self.assertEqual(self.run_cmd(cmd), ["./run1/shopping.txt"], phrase)

    def test_edit_default_editor(self):
        cmd = self.cmd("edit README.md")
        self.assertTrue(cmd.endswith(" README.md"), cmd)
        self.assertTrue(cmd.startswith(("sensible-editor", "${VISUAL")), cmd)

    def test_edit_with_named_editor(self):
        for phrase in ["edit README.md with micro", "edit README.md using micro",
                       "open README.md in micro", "edit README.md wiht micro"]:
            cmd = self.cmd(phrase)
            self.assertTrue(cmd.endswith("micro README.md"), f"{phrase}: {cmd}")

    def test_edit_finds_file_below_or_creates_it(self):
        self.assertTrue(self.cmd("edit notes.txt").endswith(" run1/notes.txt"))
        self.assertTrue(self.cmd("edit brand-new.md").endswith(" brand-new.md"))

    def test_missing_editor_is_installed_first(self):
        orig = aisha.shutil.which
        aisha.shutil.which = lambda c, *a, **k: None if c == "micro" else orig(c, *a, **k)
        try:
            p = self.plan("edit README.md with micro")
        finally:
            aisha.shutil.which = orig
        if aisha.pkg_manager():
            self.assertIn("install micro && micro README.md", p.command)
            self.assertTrue(p.destructive)

    def test_find_then_delete(self):
        p = self.plan("find files older than 2 months and delete them")
        self.assertEqual(p.intent, "delete")
        self.assertIn("-mtime +60", p.command)
        self.assertIn("-delete", p.command)
        self.assertTrue(p.destructive)

    def test_find_then_move(self):
        self.old("run1/notes.txt")
        p = self.plan("find txt files older than 2 months and move them to archive")
        self.assertTrue(p.destructive)
        r = subprocess.run(["bash", "-c", p.command], cwd=self.lab, input="", text=True)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.lab, "archive", "notes.txt")))

    def test_action_words_are_never_keywords(self):
        p = self.plan("find files and move them to x")   # nothing narrows it: not a mass move
        self.assertNotIn("-exec mv", p.command)
        self.assertNotIn("*move*", p.command)

    def test_edit_and_open_beat_debian_commands(self):
        # /usr/bin/edit is run-mailcap and /usr/bin/open is openvt on Debian
        self.assertFalse(aisha.looks_like_shell("edit README.md", None, self.lab))
        self.assertFalse(aisha.looks_like_shell("open README.md in nano", None, self.lab))


class TestSafety(LabTest):
    def test_deletes_are_flagged(self):
        p = self.plan("delete all .tmp files")
        self.assertTrue(p.destructive)
        self.assertIsNotNone(p.preview)
        self.assertTrue(self.plan("kill firefox").destructive)

    def test_negated_actions_never_run(self):
        for phrase in ["find tmp files, don't remove them", "list old files but do not delete them",
                       "find big files without deleting them", "show logs, never erase anything",
                       "find pdfs and do not move them", "kill nothing, just show processes"]:
            p = self.plan(phrase)
            self.assertFalse(p and p.destructive and p.confidence >= aisha.DEFAULTS["threshold"],
                             f"{phrase}: {p and p.command}")

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
        # the mock LLM server runs in a thread while aisha forks bash: harmless here
        warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*fork")
        self.home = tempfile.TemporaryDirectory()
        aisha.LEARNED_FILE = os.path.join(self.home.name, "learned.json")
        self.server = HTTPServer(("127.0.0.1", 0), _MockLLM)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        cfg = dict(aisha.DEFAULTS, llm="on", llm_url=f"http://127.0.0.1:{self.server.server_port}/v1",
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


# ---- runtime, setup helpers and entry points ------------------------------------

FAKE_SERVER = r'''#!/usr/bin/env python3
import json, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
if "--version" in sys.argv:
    print("version: 0 (fake llama-server)"); sys.exit(0)
port = int(sys.argv[sys.argv.index("--port") + 1])
assert sys.argv[sys.argv.index("-m") + 1].endswith(".gguf")
started = time.time()
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        ok = time.time() - started > 0.5          # pretend to load the model
        self.send_response(200 if ok else 503); self.end_headers(); self.wfile.write(b"{}")
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        out = json.dumps({"choices": [{"message": {"content": "ls -A"}}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(out)
HTTPServer(("127.0.0.1", port), H).serve_forever()
'''


def free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestRuntime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_pick_llama_asset(self):
        names = ["llama-b7000-bin-macos-arm64.zip", "llama-b7000-bin-ubuntu-vulkan-x64.zip",
                 "llama-b7000-bin-ubuntu-x64.zip", "llama-b7000-bin-ubuntu-arm64.zip",
                 "llama-b7000-bin-win-cpu-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip"]
        assets = [{"name": n} for n in names]
        self.assertEqual(aisha.pick_llama_asset(assets, "x86_64")["name"], "llama-b7000-bin-ubuntu-x64.zip")
        self.assertEqual(aisha.pick_llama_asset(assets, "aarch64")["name"], "llama-b7000-bin-ubuntu-arm64.zip")
        self.assertIsNone(aisha.pick_llama_asset(assets, "riscv64"))
        tgz = [{"name": "llama-b8000-bin-ubuntu-x64.tar.gz"}]
        self.assertEqual(aisha.pick_llama_asset(tgz, "x86_64")["name"], tgz[0]["name"])

    def test_extract_zip_keeps_exec_bit_and_finds_server(self):
        import zipfile
        z = os.path.join(self.dir, "rt.zip")
        with zipfile.ZipFile(z, "w") as f:
            info = zipfile.ZipInfo("build/bin/llama-server")
            info.external_attr = 0o755 << 16
            f.writestr(info, "#!/bin/sh\necho hi\n")
            f.writestr("build/bin/libllama.so", "x")
        aisha.extract_archive(z, os.path.join(self.dir, "out"))
        server = aisha.find_server(os.path.join(self.dir, "out"))
        self.assertTrue(server.endswith("build/bin/llama-server"))
        self.assertTrue(os.access(server, os.X_OK))

    def test_extract_refuses_path_escape(self):
        import zipfile
        z = os.path.join(self.dir, "evil.zip")
        with zipfile.ZipFile(z, "w") as f:
            f.writestr("../../escape.txt", "x")
        with self.assertRaises(OSError):
            aisha.extract_archive(z, os.path.join(self.dir, "out"))

    def _range_server(self, payload, etag='"v1"'):
        class RangeHandler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                rng, if_range = self.headers.get("Range"), self.headers.get("If-Range")
                start = int(rng.split("=")[1].rstrip("-")) if rng and (not if_range or if_range == etag) else 0
                if start > len(payload):
                    self.send_response(416)
                    self.end_headers()
                    return
                body = payload[start:]
                self.send_response(206 if start else 200)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("ETag", etag)
                self.end_headers()
                self.wfile.write(body)

        srv = HTTPServer(("127.0.0.1", 0), RangeHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return f"http://127.0.0.1:{srv.server_port}/model.gguf"

    def _partial(self, dest, data, tag):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest + ".part", "wb") as f:
            f.write(data)
        if tag is not None:
            with open(dest + ".part.tag", "w") as f:
                f.write(tag)

    def test_download_resumes_same_file(self):
        payload = bytes(range(256)) * 400
        url = self._range_server(payload)
        dest = os.path.join(self.dir, "m", "model.gguf")
        self._partial(dest, payload[:1000], '"v1"')
        aisha.download(url, dest, "model")
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), payload)
        self.assertFalse(os.path.exists(dest + ".part"))
        self.assertFalse(os.path.exists(dest + ".part.tag"))

    def test_download_restarts_when_file_changed_or_part_too_big(self):
        payload = b"new" * 5000
        url = self._range_server(payload, etag='"v2"')
        dest = os.path.join(self.dir, "m", "model.gguf")
        self._partial(dest, b"OLD" * 100, '"v1"')            # different version on the server
        aisha.download(url, dest, "model")
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), payload)
        self._partial(dest, b"x" * (len(payload) + 10), '"v2"')   # bigger than the file: 416
        aisha.download(url, dest, "model")
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), payload)

    def test_tar_symlink_chain_cannot_escape(self):
        import io
        import tarfile
        tpath = os.path.join(self.dir, "evil.tar.gz")
        with tarfile.open(tpath, "w:gz") as tf:
            for name, link in [("a/b", ".."), ("a/b/c", "..")]:
                ti = tarfile.TarInfo(name)
                ti.type, ti.linkname = tarfile.SYMTYPE, link
                tf.addfile(ti)
            ti = tarfile.TarInfo("a/b/c/escaped.txt")
            ti.size = 2
            tf.addfile(ti, io.BytesIO(b"hi"))
        out = os.path.join(self.dir, "deep", "out")
        os.makedirs(out)
        with self.assertRaises(OSError):
            aisha.extract_archive(tpath, out)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "escaped.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "deep", "escaped.txt")))

    def test_tar_with_relative_symlink_inside(self):
        import io
        import tarfile
        tpath = os.path.join(self.dir, "rt.tar.gz")
        with tarfile.open(tpath, "w:gz") as tf:
            ti = tarfile.TarInfo("bin/libllama.so.1")
            ti.size, ti.mode = 1, 0o644
            tf.addfile(ti, io.BytesIO(b"x"))
            ti = tarfile.TarInfo("bin/libllama.so")
            ti.type, ti.linkname = tarfile.SYMTYPE, "libllama.so.1"
            tf.addfile(ti)
            ti = tarfile.TarInfo("bin/llama-server")
            ti.size, ti.mode = 3, 0o755
            tf.addfile(ti, io.BytesIO(b"#!x"))
        out = os.path.join(self.dir, "out")
        aisha.extract_archive(tpath, out)
        self.assertTrue(os.path.islink(os.path.join(out, "bin", "libllama.so")))
        self.assertTrue(os.access(os.path.join(out, "bin", "llama-server"), os.X_OK))

    def test_non_json_reply_is_an_llm_error(self):
        class Html(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<html>oops</html>")

        srv = HTTPServer(("127.0.0.1", 0), Html)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            llm = aisha.LLM(dict(aisha.DEFAULTS, llm_url=f"http://127.0.0.1:{srv.server_port}/v1", llm_timeout=5.0))
            with self.assertRaises(aisha.LLMError):
                llm.command_for("x", self.dir, "")
        finally:
            srv.shutdown()
            srv.server_close()

    def test_runtime_starts_on_demand_and_stops(self):
        server = os.path.join(self.dir, "llama-server")
        with open(server, "w") as f:
            f.write(FAKE_SERVER.replace("/usr/bin/env python3", sys.executable))
        os.chmod(server, 0o755)
        model = os.path.join(self.dir, "m.gguf")
        open(model, "w").close()
        self.assertTrue(aisha.check_server(server)[0])
        cfg = dict(aisha.DEFAULTS, llm_url=f"http://127.0.0.1:{free_port()}/v1", llm_server=server,
                   llm_model_file=model, llm_timeout=20.0)
        llm = aisha.LLM(cfg)
        self.assertTrue(llm.runtime.configured)
        try:
            self.assertEqual(llm.command_for("list files", self.dir, ""), "ls -A")
            self.assertTrue(llm.runtime.running())
        finally:
            llm.runtime.stop()
        self.assertFalse(llm.runtime.running())

    def test_local_urls_skip_proxies(self):
        self.assertTrue(aisha.is_local_url("http://127.0.0.1:11434/v1"))
        self.assertTrue(aisha.is_local_url("http://localhost:8080/v1"))
        self.assertFalse(aisha.is_local_url("https://huggingface.co/x"))


class TestEntryPoints(unittest.TestCase):
    def run_aisha(self, *args, stdin=None, cwd=None):
        env = dict(os.environ, AISHA_LLM="off", AISHA_HOME=tempfile.mkdtemp())
        return subprocess.run([sys.executable, AISHA, *args], input=stdin, capture_output=True,
                              text=True, cwd=cwd, env=env, timeout=30)

    def test_dash_c_is_bash(self):
        r = self.run_aisha("-c", 'echo "$0 $1"', "name", "arg")
        self.assertEqual(r.stdout.strip(), "name arg")

    def test_dash_c_words(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "hello.txt"), "w").close()
            r = self.run_aisha("-c", "list all files", cwd=d)
            self.assertIn("hello.txt", r.stdout)

    def test_stdin_script_is_bash(self):
        script = "for i in 1 2; do\n  echo n$i\ndone\nif true; then echo ok; fi\n"
        self.assertEqual(self.run_aisha(stdin=script).stdout.split(), ["n1", "n2", "ok"])

    def test_script_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.sh")
            with open(path, "w") as f:
                f.write('echo "script $1"\n')
            self.assertEqual(self.run_aisha(path, "x").stdout.strip(), "script x")

    def test_lines_mode(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "sub"))
            r = self.run_aisha("--lines", stdin="go to sub\npwd\n", cwd=d)
            self.assertTrue(r.stdout.strip().endswith("/sub"), r.stdout)

    def test_exit_code(self):
        self.assertEqual(self.run_aisha("-c", "exit 3").returncode, 3)


class TestShellSyntaxAndCare(unittest.TestCase):
    def test_syntax_is_shell(self):
        for line in ["greet() { echo hi; }", "function greet { echo hi; }", "( cd /tmp && ls )",
                     "{ echo a; echo b; }", "[ -f x ] && echo y", "X=1", "PATH+=:/opt/bin"]:
            self.assertTrue(aisha._looks_like_shell(line), line)

    def test_risky_llm_commands_need_yes(self):
        for cmd in ["sudo apt install x", "curl https://x.sh | sh", "chmod -R 777 .", "kill -9 1",
                    "systemctl stop ssh", "shutdown now", "rm -rf build"]:
            self.assertTrue(aisha.needs_care(cmd), cmd)
        for cmd in ["ls -la", "du -sh .", "grep -rn foo ."]:
            self.assertFalse(aisha.needs_care(cmd), cmd)

    def test_fallbacks_need_no_extra_tools(self):
        orig = aisha.shutil.which
        aisha.shutil.which = lambda c, *a, **k: None if c in ("zip", "unzip", "free", "ip", "ss", "cal", "uptime") else orig(c, *a, **k)
        try:
            with tempfile.TemporaryDirectory() as d:
                os.mkdir(os.path.join(d, "src"))
                open(os.path.join(d, "a.zip"), "w").close()
                self.assertTrue(aisha.interpret("zip the src folder", d).command.startswith("python3 -m zipfile -c"))
                self.assertTrue(aisha.interpret("extract a.zip", d).command.startswith("python3 -m zipfile -e"))
                for q, frag in [("how much memory is free", "/proc/meminfo"), ("what is my ip", "hostname -I"),
                                ("show listening ports", "/proc/net/tcp"), ("calendar", "python3 -m calendar"),
                                ("uptime", "/proc/uptime")]:
                    self.assertIn(frag, aisha.interpret(q, d).command, q)
        finally:
            aisha.shutil.which = orig


class TestInjection(LabTest):
    """Names and search terms with shell code must reach bash quoted, never run."""

    PHRASES = [
        'find files containing "$(touch PWNED1)"',
        "create a folder called '$(touch PWNED2)'",
        'search for "`touch PWNED3`" in all files',
        "find files named ';touch PWNED4;'",
        'copy README.md to "$(touch PWNED5)"',
        "make a new file named '`touch PWNED6`'",
        'find files with "$(touch PWNED7)" in the name',
        "edit '$(touch PWNED8).txt' with cat",
        'which files mention "a\'b$(touch PWNED9)"',
    ]

    def test_no_injection(self):
        for phrase in self.PHRASES:
            plan = self.plan(phrase)
            if plan is None:
                continue
            subprocess.run(["bash", "-c", plan.command], cwd=self.lab, capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=20)
        found = [os.path.join(r, f) for r, _, fs in os.walk(self.lab) for f in fs if f.startswith("PWNED")]
        found += [f for f in os.listdir(tempfile.gettempdir()) if f.startswith("PWNED")]
        self.assertEqual(found, [])


class TestSmallThings(LabTest):
    def test_quoted_new_file_with_space(self):
        self.assertTrue(self.cmd("edit 'my notes.txt'").endswith(" 'my notes.txt'"))

    def test_multiline_llm_script(self):
        text = "```bash\nfor f in *.txt; do\n  echo \"$f\"\ndone\n```"
        self.assertEqual(aisha.clean_llm_command(text), 'for f in *.txt; do\n  echo "$f"\ndone')
        self.assertEqual(aisha.clean_llm_command("ls -la\nThis lists files."), "ls -la")

    def test_git_branch(self):
        os.makedirs(os.path.join(self.lab, "src", "deep"))
        with open(os.path.join(self.lab, ".git", "HEAD"), "w") as f:
            f.write("ref: refs/heads/aisha\n")
        self.assertEqual(aisha.git_branch(os.path.join(self.lab, "src", "deep")), "aisha")
        self.assertEqual(aisha.git_branch(tempfile.gettempdir()), "")


class TestDoctor(unittest.TestCase):
    def test_doctor_runs(self):
        env = dict(os.environ, AISHA_LLM="off", AISHA_HOME=tempfile.mkdtemp())
        r = subprocess.run([sys.executable, AISHA, "--doctor"], capture_output=True, text=True, env=env, timeout=30)
        self.assertIn("doctor", r.stderr)
        self.assertIn(r.returncode, (0, 1))


class TestEditingCommands(LabTest):
    def test_replace_special_characters(self):
        path = os.path.join(self.lab, "cfg.txt")
        with open(path, "w") as f:
            f.write("url=a.b/c*\nkeep=axb/c\n")
        cmd = self.cmd('replace "a.b/c*" with "x&y\\\\z" in cfg.txt')
        subprocess.run(["bash", "-c", cmd], cwd=self.lab, check=True)
        with open(path) as f:
            self.assertEqual(f.read(), "url=x&y\\\\z\nkeep=axb/c\n")

    def test_replace_across_files_only_touches_matches(self):
        for name, text in {"a.py": "old = 1\n", "b.py": "new = 2\n", "c.txt": "old\n"}.items():
            with open(os.path.join(self.lab, name), "w") as f:
                f.write(text)
        b_mtime = os.path.getmtime(os.path.join(self.lab, "b.py"))
        p = self.plan("replace old with fresh in all python files")
        self.assertTrue(p.destructive)
        subprocess.run(["bash", "-c", p.command], cwd=self.lab, check=True)
        read = lambda n: open(os.path.join(self.lab, n)).read()
        self.assertEqual(read("a.py"), "fresh = 1\n")
        self.assertEqual(read("c.txt"), "old\n")
        self.assertEqual(os.path.getmtime(os.path.join(self.lab, "b.py")), b_mtime)

    def test_calculator(self):
        for q, out in [("what is 2+2", "4"), ("calculate (12*7)/3", "28.0"), ("how much is 2^10", "1024")]:
            r = subprocess.run(["bash", "-c", self.cmd(q)], capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), out, q)

    def test_compare(self):
        r = subprocess.run(["bash", "-c", self.cmd("compare README.md and run1/notes.txt")],
                           cwd=self.lab, capture_output=True, text=True)
        self.assertIn("+Sensor log", r.stdout)


class TestReviewRegressions(LabTest):
    """Bugs found in review; each must stay fixed."""

    def shell(self):
        sh = aisha.Shell(dict(aisha.DEFAULTS, llm="off"))
        sh.cwd = self.lab
        return sh

    def read(self, name):
        with open(os.path.join(self.lab, name)) as f:
            return f.read().strip()

    def test_plain_variables_umask_and_options_persist(self):
        sh = self.shell()
        sh.handle("d=hello; arr=(a 'b c')")
        sh.handle('echo "$d ${arr[1]}" > v.txt')
        self.assertEqual(self.read("v.txt"), "hello b c")
        sh.handle("umask 077")
        sh.handle("umask > u.txt")
        self.assertEqual(self.read("u.txt"), "0077")
        sh.handle("shopt -s nullglob")
        sh.handle("echo none*.zzz > g.txt")
        self.assertEqual(self.read("g.txt"), "")

    def test_rc_files_load(self):
        rc1, rc2 = os.path.join(self.lab, "rc1"), os.path.join(self.lab, "rc2")
        with open(rc1, "w") as f:
            f.write("alias hi='echo hi-from-alias'\n")
        with open(rc2, "w") as f:
            f.write("export FROM_RC=yes\n")
        saved = aisha.RC_FILES
        aisha.RC_FILES = [rc1, rc2]
        try:
            sh = self.shell()
        finally:
            aisha.RC_FILES = saved
        self.assertEqual(sh.env.get("FROM_RC"), "yes")
        self.assertIn("hi", sh.names)

    def test_real_commands_are_not_replaced(self):
        for line in ["time make", "watch date", "sort names", "kill 1234", "kill %1"]:
            self.assertTrue(aisha.looks_like_shell(line, None, self.lab), line)

    def test_more_things_need_a_yes(self):
        for cmd in ["sed -i 's/a/b/' f", "sed --in-place s/a/b/ f", "rsync -a --delete src/ dst/",
                    "git checkout -- .", "git push --force", "git push -f origin main", "sort f > f",
                    "chmod -vR 777 .", "chmod --recursive 777 .", "bash <(curl -s x)", "pkill -9 x",
                    "cp img /dev/vda", "python3 -c 'import shutil; shutil.rmtree(\"x\")'", "apt install x"]:
            self.assertTrue(aisha.needs_care(cmd), cmd)
        for cmd in ["ls 2>/dev/null", "du -h . | sort -hr", "echo hi >&2", "grep x f >/dev/null"]:
            self.assertFalse(aisha.needs_care(cmd), cmd)

    def test_dry_run_never_executes_bash_lines(self):
        sh = aisha.Shell(dict(aisha.DEFAULTS, llm="off"), dry_run=True)
        sh.cwd = self.lab
        sh.handle("rm -f README.md")
        sh.handle("!rm -f README.md")
        self.assertTrue(os.path.exists(os.path.join(self.lab, "README.md")))


class TestReviewEntryPoints(unittest.TestCase):
    def run_aisha(self, *args, stdin=None, cwd=None):
        env = dict(os.environ, AISHA_LLM="off", AISHA_HOME=tempfile.mkdtemp())
        return subprocess.run([sys.executable, AISHA, *args], input=stdin, capture_output=True,
                              text=True, cwd=cwd, env=env, timeout=30)

    def test_dash_n_and_quoted_args(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ("victim", "build", "output", "build output"):
                open(os.path.join(d, n), "w").close()
            self.run_aisha("-n", "rm", "-f", "victim", cwd=d)
            self.assertTrue(os.path.exists(os.path.join(d, "victim")))
            self.assertEqual(self.run_aisha("-n", cwd=d).returncode, 2)
            self.run_aisha("rm", "-f", "build output", cwd=d)
            self.assertFalse(os.path.exists(os.path.join(d, "build output")))
            self.assertTrue(os.path.exists(os.path.join(d, "build")))
            self.assertTrue(os.path.exists(os.path.join(d, "output")))

    def test_dash_c_scripts_with_comments(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_aisha("-c", "# step one\ntouch f1", cwd=d)
            self.run_aisha("-c", "touch f2 # don't", cwd=d)
            self.assertTrue(os.path.exists(os.path.join(d, "f1")))
            self.assertTrue(os.path.exists(os.path.join(d, "f2")))

    def test_lines_commands_do_not_eat_input(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "sub"))
            r = self.run_aisha("--lines", stdin="wc -l\ngo to sub\npwd\n", cwd=d)
            self.assertTrue(r.stdout.strip().endswith("/sub"), r.stdout)

    def test_sigterm_exits_cleanly(self):
        import signal as sig
        env = dict(os.environ, AISHA_LLM="off", AISHA_HOME=tempfile.mkdtemp())
        p = subprocess.Popen([sys.executable, AISHA, "sleep", "20"], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import time as _t
        _t.sleep(1.0)
        p.send_signal(sig.SIGTERM)
        self.assertEqual(p.wait(timeout=10), 128 + sig.SIGTERM)
        r = subprocess.run(["pgrep", "-f", "^sleep 20$"], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "", "the command aisha was running is still alive")


class TestRuleReview(LabTest):
    """Findings from the rule-engine review. Each would delete or change the wrong things."""

    T = aisha.DEFAULTS["threshold"]

    def sure(self, phrase):
        p = self.plan(phrase)
        return p if p and p.confidence >= self.T else None

    def make(self, files):
        for name, text in files.items():
            path = os.path.join(self.lab, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)

    def run_cmd_in_lab(self, cmd):
        return subprocess.run(["bash", "-c", cmd], cwd=self.lab, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL)

    def test_anything_that_changes_files_is_destructive(self):
        phrases = [p for p, e in load_phrases() if e not in ("!SHELL",)] + [
            "delete files containing milk", "find files about budget and remove them", "rm files containing milk",
            "hey, how do i delete files containing milk?"]
        for phrase in phrases:
            p = self.plan(phrase)
            if p and aisha.needs_care(p.command) and not p.checked:
                self.assertTrue(p.destructive, f"{phrase}: {p.command}")

    def test_create_with_content_asks_only_before_replacing(self):
        self.assertFalse(self.plan("create fresh.txt with hello").destructive)
        self.assertTrue(self.plan("create README.md with hello").destructive)

    def test_question_after_greeting_is_only_shown(self):
        p = self.plan("hey, how do i delete files containing milk?")
        self.assertTrue(p is None or p.show_only)

    def test_negated_filters(self):
        cases = {
            "delete files that haven't been modified in the last 30 days": "-mtime +30",
            "delete files not modified in the last week": "-mtime +7",
            "delete files that are not hidden": "-not -name '.*'",
            "delete files no bigger than 1kb": "-size -1025c",
            "delete logs no more than a week old": "-mtime -7",
            "delete log files that are not in src": "-not -path './src/*'",
        }
        for phrase, frag in cases.items():
            p = self.sure(phrase)
            if p:
                self.assertIn(frag, p.command, phrase)
                self.assertTrue(p.destructive, phrase)
        for phrase in ["find files that are not hidden", "delete files that are not hidden",
                       "find logs not in src", "find files with no extension"]:
            p = self.plan(phrase)
            if p:
                self.assertNotIn("*not*", p.command, phrase)
                self.assertNotIn("-e not", p.command, phrase)
        p = self.plan("just list old logs, not remove them")
        self.assertFalse(p and p.destructive, p and p.command)

    def test_delete_with_limit_deletes_only_those(self):
        self.make({f"l{i}.log": "x" * (i * 100) for i in range(1, 6)})
        p = self.sure("delete the 2 largest log files")
        self.assertIsNotNone(p)
        preview = self.run_cmd_in_lab(p.preview).stdout.split()
        self.assertEqual(sorted(preview), ["./l4.log", "./l5.log"])
        self.run_cmd_in_lab(p.command)
        left = sorted(f for f in os.listdir(self.lab) if f.endswith(".log"))
        self.assertEqual(left, ["l1.log", "l2.log", "l3.log"])
        self.assertIsNone(self.sure("delete the largest log files"))   # how many? ask the model

    def test_folder_deletes_keep_the_starting_folder(self):
        os.makedirs(os.path.join(self.lab, "stuff", "e1"))
        os.makedirs(os.path.join(self.lab, "stuff", "e2"))
        p = self.sure("delete empty folders in stuff")
        self.run_cmd_in_lab(p.command)
        self.assertTrue(os.path.isdir(os.path.join(self.lab, "stuff")))
        self.assertEqual(os.listdir(os.path.join(self.lab, "stuff")), [])

    def test_named_targets_are_not_widened(self):
        self.make({"src/__init__.py": "", ".env": "SECRET=1\n", "sub/.env": "x\n", "keep/new.txt": "x\n"})
        p = self.sure("delete the empty file notes.txt")
        self.assertTrue(p is None or p.command == "rm -- run1/notes.txt", p and p.command)
        self.assertIsNone(self.sure("delete the old folder"))           # there is no folder called old
        os.makedirs(os.path.join(self.lab, "old"))
        self.assertEqual(self.sure("delete the old folder").command, "rm -r -- old")
        self.assertEqual(self.sure("delete .env").command, "rm -- .env")
        self.assertEqual(self.sure("remove the hidden file .env").command, "rm -- .env")
        self.assertIn("-maxdepth 1", self.sure("delete *.log").command)
        self.assertIn("-maxdepth 1", self.sure("replace hello with bye in *.md").command)

    def test_past_tense_is_not_an_order(self):
        for phrase in ["list files that were deleted today", "which files were removed today"]:
            p = self.plan(phrase)
            self.assertFalse(p and p.destructive and p.confidence >= self.T, p and p.command)

    def test_quoted_globs_stay_quoted(self):
        self.make({"old report 1.txt": "", "old report 2.txt": "", "report.pdf": ""})
        os.makedirs(os.path.join(self.lab, "old"))
        p = self.sure("move 'old report*' to archive")
        self.assertIn("'old report'*", p.command)
        self.assertIsNone(self.sure("back up the pdfs"))

    def test_destinations(self):
        p = self.plan("move README.md to src and then list src")
        self.assertTrue(p is None or p.confidence < self.T or "and then" not in p.command, p and p.command)
        p = self.sure("copy logs.txt to 'my backup.txt' please")
        self.assertTrue(p is None or p.command.endswith(" 'my backup.txt'"), p and p.command)
        self.assertNotIn("qlit", (self.plan("rename README.md to old README.md") or aisha.Plan("", "")).command)

    def test_fractional_times(self):
        self.assertIn("-mtime +75", self.sure("find files older than 2.5 months").command)
        self.assertIn("-mmin +15120", self.sure("find files older than 1.5 weeks").command)
        self.assertIn("-mmin -90", self.sure("find files changed in the last 1.5 hours").command)

    def test_content_deletes_are_not_stemmed(self):
        self.assertIn("-e statement", self.sure("delete files containing statement").command)

    def test_overwrites_are_flagged_or_avoided(self):
        self.assertIn("--keep-old-files", self.sure("extract data.tar.gz").command if os.path.exists(
            os.path.join(self.lab, "data.tar.gz")) else "--keep-old-files")
        self.make({"data.tar.gz": "x"})
        self.assertIn("--keep-old-files", self.sure("extract data.tar.gz").command)
        self.assertTrue(self.sure("compress src as README.md").destructive)
        self.assertTrue(self.sure("download https://example.com/README.md").destructive)
        for phrase in ["show run.sh in bash", "open README.md in split view"]:
            p = self.plan(phrase)
            self.assertFalse(p and p.confidence >= self.T and re.match(r"(bash|split)\b", p.command), p and p.command)

    def test_home_and_root_need_a_real_filter(self):
        for phrase in ["delete files older than a year in ~/", "delete files older than a year in /home",
                       "delete everything in my home folder"]:
            self.assertIsNone(self.sure(phrase), phrase)

    def test_places_are_not_targets(self):
        for phrase in ["delete files older than a year in ~/", "delete everything in ~", "remove ~/",
                       "delete the folder .", "rm -r from /home", "delete files in /"]:
            p = self.plan(phrase)
            self.assertFalse(p and re.match(r"rm\b", p.command), f"{phrase}: {p and p.command}")
        self.assertIn("-not -name '*.*'", self.sure("delete files without an extension").command)

    def test_misc(self):
        self.assertIsNone(self.sure("convert the .wav files to .mp3"))
        p = self.sure("rename python files to txt")
        self.assertTrue(p is None or "*.py;" in p.command, p and p.command)
        self.assertIn("-not -name '*.*'", self.sure("find files without an extension").command)
        p = self.plan("remove the app folder")
        self.assertFalse(p and "apt" in p.command)


class TestPlaces(LabTest):
    def test_home_spellings(self):
        for phrase in ["list files in ~home", "list files in home", "list files in $HOME", "list files in my home",
                       "list files in home folder", "list files in ~"]:
            self.assertEqual(self.cmd(phrase), "ls -lh -- ~", phrase)
        self.assertTrue(self.cmd("find big files in ~home").startswith("find ~ "))

    def test_missing_folder_is_kept_not_searched_for(self):
        for phrase, root in [("list files in nosuchdir", "nosuchdir"), ("list files in ~/nonexistent", "~/nonexistent"),
                             ("list files in the nosuchdir folder", "nosuchdir")]:
            p = self.plan(phrase)
            self.assertEqual(p.command, f"ls -lh -- {aisha.qpath(root)}", phrase)
            self.assertIn("no folder", p.rationale())
        os.makedirs(os.path.join(self.lab, "Downloads"))
        self.assertIn("did you mean Downloads", self.plan("list files in Downlods").rationale())
        self.assertIn('"${PROJECT}"/src', self.cmd("find files in $PROJECT/src"))

    def test_in_still_means_other_things(self):
        self.assertIn("measur", self.cmd("find files with measurement data in them"))
        self.assertIn("--include='*.py'", self.cmd("find TODO in python files"))
        self.assertIn("-mtime -3", self.cmd("find files modified in the last 3 days"))


class TestRecipesNeedingTools(LabTest):
    """Recipes whose tools this machine may not have: pretend they are installed."""

    def setUp(self):
        super().setUp()
        orig = aisha.shutil.which
        aisha.shutil.which = lambda c, *a, **k: f"/usr/bin/{c}" if c in ("ssh", "scp", "lsusb", "nmcli") else orig(c, *a, **k)
        self.addCleanup(setattr, aisha.shutil, "which", orig)

    def test_network_recipes(self):
        self.assertEqual(self.cmd("ssh to example.com as jukka"), "ssh jukka@example.com")
        self.assertEqual(self.cmd("connect to 10.0.0.5 on port 2222"), "ssh -p 2222 10.0.0.5")
        self.assertEqual(self.cmd("copy README.md to jukka@server.example.com:/tmp"),
                         "scp -r -- README.md jukka@server.example.com:/tmp")
        self.assertEqual(self.cmd("list usb devices"), "lsusb")
        self.assertEqual(self.cmd("show wifi networks"), "nmcli dev wifi list")


class TestShellWords(LabTest):
    def test_again_and_help(self):
        sh = aisha.Shell(dict(aisha.DEFAULTS, llm="off"))
        sh.cwd = self.lab
        self.assertEqual(sh.handle("what can you do?"), 0)
        sh.handle("echo x >> again.txt")
        sh.handle("again")
        sh.handle("do it again")
        with open(os.path.join(self.lab, "again.txt")) as f:
            self.assertEqual(f.read().split(), ["x", "x", "x"])

    def test_every_recipe_template_formats(self):
        import string
        for r in aisha.RECIPES:
            tmpls = [] if callable(r.cmd) else ([c for _, c in r.cmd] if isinstance(r.cmd, list) else [r.cmd])
            for t in tmpls:
                names = {f for _, f, _, _ in string.Formatter().parse(t) if f}
                t.format(**{n: "X" for n in names})


class TestModelMissing(unittest.TestCase):
    def test_message_names_setup_and_existing_models(self):
        class FakeOllama(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error":{"message":"model \\"qwen2.5-coder:1.5b\\" not found"}}')

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"models": [{"name": "llama3.2:3b"}]}).encode())

        srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            llm = aisha.LLM(dict(aisha.DEFAULTS, llm_url=f"http://127.0.0.1:{srv.server_port}/v1", llm_timeout=5.0))
            with self.assertRaises(aisha.LLMError) as cm:
                llm.command_for("x", tempfile.gettempdir(), "")
            msg = str(cm.exception)
            self.assertIn("aisha --setup", msg)
            self.assertIn("llama3.2:3b", msg)
        finally:
            srv.shutdown()
            srv.server_close()


class TestBuiltinModel(unittest.TestCase):
    """The intent model inside aisha: no download, no language model."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lab = self.tmp.name
        make_corpus(self.lab)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bank_templates_still_work(self):
        sample = {"{file}": "README.md", "{dir}": "src", "{n}": "3", "{text}": '"hello"',
                  "{url}": "https://example.com", "{host}": "example.com"}
        bad = []
        for tmpl in aisha.INTENT_BANK.strip().splitlines():
            filled = " ".join(sample.get(w, w) for w in tmpl.split())
            p = aisha.interpret(filled, self.lab)
            if not p or p.confidence < aisha.DEFAULTS["threshold"]:
                bad.append(tmpl)
        self.assertEqual(bad, [], "bank templates the rules no longer handle (regenerate INTENT_BANK)")

    def test_suggestions(self):
        misses = []
        with open(os.path.join(HERE, "suggestions.tsv")) as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                phrase, expected = line.rstrip("\n").split("\t")
                cmds = [p.command for _, p, _ in aisha.suggest(phrase, self.lab)]
                if not any(all(any(x in c for x in frag.split(" || ")) for frag in expected.split(" ;; ")) for c in cmds):
                    misses.append(f"{phrase}: {cmds}")
        self.assertEqual(misses, [])

    def test_nothing_for_nonsense(self):
        for phrase in ["purple monkey dishwasher", "translate this poem to french"]:
            self.assertEqual(aisha.suggest(phrase, self.lab), [], phrase)

    def test_synonyms_and_word_order(self):
        for phrase, frag in [("erase README.md", "rm -- README.md"), ("relocate README.md to src", "mv -i -- README.md src"),
                             ("README.md delete", "rm -- README.md"), ("folder named projects create", "mkdir -p -- projects")]:
            p = aisha.interpret(phrase, self.lab)
            self.assertIn(frag, p.command, phrase)


class TestTeaching(LabTest):
    def shell(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        aisha.LEARNED_FILE = os.path.join(home, "learned.json")
        sh = aisha.Shell(dict(aisha.DEFAULTS, llm="off"))
        sh.cwd = self.lab
        return sh

    def test_templates(self):
        self.assertEqual(aisha.make_template("frobnicate notes.md", "touch notes.md"), ("frobnicate {1}", "touch {1}"))
        self.assertEqual(aisha.make_template("add me to docker group", "sudo usermod -aG docker me"),
                         ("add me to {1} group", "sudo usermod -aG {1} me"))
        self.assertEqual(aisha.make_template("say 'hi there' to bob", "echo 'hi there' bob"),
                         ("say {1} to {2}", "echo {1} {2}"))

    def test_teach_by_example_generalises(self):
        sh = self.shell()
        answers = ["touch zz1.md"]
        aisha.ask = lambda prompt: answers.pop(0) if answers else None
        sh.handle("frobnicate zz1.md")
        self.assertTrue(os.path.exists(os.path.join(self.lab, "zz1.md")))
        sh.handle("frobnicate 'other file.md'")          # learned: no question this time
        self.assertTrue(os.path.exists(os.path.join(self.lab, "other file.md")))

    def test_teach_command(self):
        sh = self.shell()
        sh.handle("teach make thing {name} = mkdir -p {name}")
        sh.handle("make thing alpha")
        self.assertTrue(os.path.isdir(os.path.join(self.lab, "alpha")))
        sh.handle("forget make thing {1}")
        self.assertIsNone(sh.memory.match("make thing beta"))

    def test_picking_a_suggestion_runs_and_is_learned(self):
        sh = self.shell()
        answers = ["1"]
        aisha.ask = lambda prompt: answers.pop(0) if answers else None
        rc = sh.handle("zz2.md create")   # rules handle it now; force the model path with an odd phrasing
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(self.lab, "zz2.md")))

    def test_language_model_is_off_unless_set_up(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        env = dict(os.environ, AISHA_HOME=home)
        for k in ("AISHA_LLM", "AISHA_LLM_URL", "AISHA_LLM_MODEL", "AISHA_LLM_SERVER"):
            env.pop(k, None)
        r = subprocess.run([sys.executable, "-c", f"""
import sys, importlib.machinery as m, importlib.util as u
l = m.SourceFileLoader("aisha", {AISHA!r}); sp = u.spec_from_loader("aisha", l)
a = u.module_from_spec(sp); sys.modules["aisha"] = a; l.exec_module(a)
print(a.LLM(a.load_config()).enabled)"""], env=env, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "False", r.stderr)


FAKE_LLAMAFILE = r"""#!/usr/bin/env python3
import json, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
if "--version" in sys.argv:
    print("llamafile v0.10.6"); sys.exit(0)
if "--nobrowser" in sys.argv:
    print("error: unknown argument: --nobrowser"); sys.exit(1)      # this version dropped it
if "--server" not in sys.argv:
    print("error: no prompt given"); sys.exit(1)
port = int(sys.argv[sys.argv.index("--port") + 1])
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps({"choices": [{"message": {"content": "ls -A"}}]}).encode())
HTTPServer(("127.0.0.1", port), H).serve_forever()
"""


class TestRuntimeSources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_asset_names_old_and_new(self):
        names = ["llama-v1.0.0-bin-ubuntu-vulkan-x64.zip", "llama-v1.0.0-bin-win-cpu-x64.zip",
                 "llama-v1.0.0-bin-macos-arm64.tar.gz", "llama.cpp-1.0.0-linux-x86_64-cuda.tar.gz",
                 "llama.cpp-1.0.0-linux-x86_64.tar.gz", "llama.cpp-1.0.0-linux-aarch64.tar.gz",
                 "llama.cpp-1.0.0-source.tar.gz"]
        pick = lambda m: (aisha.pick_llama_asset([{"name": n} for n in names], m) or {}).get("name")
        self.assertEqual(pick("x86_64"), "llama.cpp-1.0.0-linux-x86_64.tar.gz")
        self.assertEqual(pick("aarch64"), "llama.cpp-1.0.0-linux-aarch64.tar.gz")
        names2 = ["llama-b9000-bin-ubuntu-x64.zip", "llama-b9000-bin-ubuntu-cpu-x64.tar.gz"]
        self.assertEqual(aisha.pick_llama_asset([{"name": n} for n in names2], "x86_64")["name"],
                         "llama-b9000-bin-ubuntu-cpu-x64.tar.gz")

    def test_newest_llamafile_on_hugging_face(self):
        class FakeHF(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.startswith("/api/models?"):
                    body = [{"id": "mozilla-ai/llamafile_0.10"}, {"id": "mozilla-ai/llamafile_0.11"},
                            {"id": "mozilla-ai/Llama-3.2-1B-Instruct-llamafile"}]
                elif self.path == "/api/models/mozilla-ai/llamafile_0.11":
                    body = {"siblings": [{"rfilename": n} for n in
                                         ["llamafile-0.11.0", "llamafile-0.11.2-thin", "llamafile-0.11.10-thin", "ggml-cuda.so"]]}
                else:
                    body = {"siblings": [{"rfilename": "llamafile-0.10.6-thin"}]}
                out = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        srv = HTTPServer(("127.0.0.1", 0), FakeHF)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        saved = aisha.HF_BASE
        aisha.HF_BASE = f"http://127.0.0.1:{srv.server_port}"
        try:
            self.assertEqual(aisha.latest_llamafile(), ("mozilla-ai/llamafile_0.11", "llamafile-0.11.10-thin"))
        finally:
            aisha.HF_BASE = saved
            srv.shutdown()
            srv.server_close()
        aisha.HF_BASE = "http://127.0.0.1:1"          # unreachable: falls back to the known build
        try:
            self.assertEqual(aisha.latest_llamafile(), aisha.LLAMAFILE_FALLBACK)
        finally:
            aisha.HF_BASE = saved

    def test_llamafile_starts_with_the_options_it_accepts(self):
        server = os.path.join(self.dir, "llamafile-0.10.6-thin")
        with open(server, "w") as f:
            f.write(FAKE_LLAMAFILE.replace("/usr/bin/env python3", sys.executable))
        os.chmod(server, 0o755)
        model = os.path.join(self.dir, "m.gguf")
        open(model, "w").close()
        self.assertTrue(aisha.is_llamafile(server))
        self.assertTrue(aisha.check_server(server)[0])
        saved = aisha.DATA_DIR
        aisha.DATA_DIR = self.dir
        cfg = dict(aisha.DEFAULTS, llm="on", llm_url=f"http://127.0.0.1:{free_port()}/v1", llm_server=server,
                   llm_model_file=model, llm_timeout=20.0)
        llm = aisha.LLM(cfg)
        try:
            self.assertEqual(llm.command_for("list files", self.dir, ""), "ls -A")
        finally:
            llm.runtime.stop()
            aisha.DATA_DIR = saved


class TestPrompt(LabTest):
    def test_branch_is_labelled_and_can_be_hidden(self):
        with open(os.path.join(self.lab, ".git", "HEAD"), "w") as f:
            f.write("ref: refs/heads/aisha\n")
        sh = aisha.Shell(dict(aisha.DEFAULTS, llm="off"))
        sh.cwd = self.lab
        self.assertNotIn("git:", sh.prompt())            # hidden by default
        self.assertEqual(sh.prompt().count("aisha"), 1)
        sh.cfg["prompt_git"] = True
        self.assertIn(" git:aisha ", sh.prompt())
        self.assertTrue(sh.prompt().startswith("aisha "))

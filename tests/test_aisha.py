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

    def test_download_resumes(self):
        payload = bytes(range(256)) * 400

        class RangeHandler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                rng = self.headers.get("Range")
                start = int(rng.split("=")[1].rstrip("-")) if rng else 0
                body = payload[start:]
                self.send_response(206 if rng else 200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        srv = HTTPServer(("127.0.0.1", 0), RangeHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            dest = os.path.join(self.dir, "m", "model.gguf")
            os.makedirs(os.path.dirname(dest))
            with open(dest + ".part", "wb") as f:
                f.write(payload[:1000])
            aisha.download(f"http://127.0.0.1:{srv.server_port}/model.gguf", dest, "model")
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), payload)
            self.assertFalse(os.path.exists(dest + ".part"))
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

"""Option catalogue: the basic commands, each option, many wordings.

Each entry: the wordings of one request and a regex the resulting command must
match (and optionally one it must not). The ls and sort sections are generated
from option tables, so every key is asked for in every common form ("by X",
"sorted by X", "in X order", "in the order of X", ...).
Run: python3 -m unittest tests.test_options -v
     python3 tests/test_options.py          (prints every miss)
"""
import os, re, sys, tempfile, unittest, importlib.machinery as m, importlib.util as u

l = m.SourceFileLoader("t", os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_aisha.py"))
sp = u.spec_from_loader("t", l)
t = u.module_from_spec(sp); sys.modules.setdefault("t", t); l.exec_module(t)
a = t.aisha

HOST, PORT = "192.168.20.140", "50"

# ---- ls: sort keys, directions and other listing options -------------------------------
LIST_VERBS = ["list files", "list", "show files", "show the files", "list the files here", "list everything"]
SORT_FORMS = ["by {k}", "sorted by {k}", "ordered by {k}", "sort by {k}", "in {k} order", "in the order of {k}",
              "in order of {k}", "according to {k}", "arranged by {k}", "{k} order"]
LS_KEYS = {
    # key words -> regex for the ls flags
    "time": (["time", "date", "modification time", "last modified", "modified date", "age"], r"^ls -l?h?A?t\b"),
    "size": (["size", "file size"], r"^ls -l?h?A?S\b"),
    "extension": (["extension", "file extension"], r"^ls -l?h?A?X\b"),
    "name": (["name", "file name", "filename"], r"^command ls -l?h?A?\s"),
}
LS_PHRASES = {   # whole-phrase options -> flag regex
    r"^command ls -l?h?A?\s": ["alphabetically", "in alphabetical order", "a to z", "from a to z", "a-z",
                               "in abc order", "sorted alphabetically", "alphabetical"],
    r"^command ls -l?h?A?r\s": ["in reverse alphabetical order", "z to a", "from z to a", "reverse alphabetically",
                                "alphabetically in reverse", "by name descending", "by name reversed"],
    r"^ls -l?h?A?t\b": ["newest first", "latest first", "most recent first", "recent first", "newest on top"],
    r"^ls -l?h?A?tr\b": ["oldest first", "chronologically", "in chronological order", "newest last",
                         "by date ascending", "by time reversed", "in reverse time order", "oldest on top"],
    r"^ls -l?h?A?S\b": ["biggest first", "largest first", "largest to smallest", "by size descending"],
    r"^ls -l?h?A?Sr\b": ["smallest first", "smallest to largest", "by size ascending", "by size reversed"],
    r"^ls -l?h?A": ["including hidden", "with hidden files", "and hidden files too", "hidden ones too",
                    "including dotfiles", "with the hidden ones", "plus hidden files", "even hidden ones"],
    r"^ls -l?h?A?U\b": ["unsorted", "in directory order", "without sorting", "with no sorting", "in no particular order"],
    r"^ls -1\b": ["one per line", "in a single column", "names only", "just the names", "only the names"],
}

# ---- sort: lines of a file ---------------------------------------------------------------
SORT_FILE = {
    r"^sort (?:-- )?names\.txt$|^sort -- names\.txt$": [
        "sort names.txt", "sort the lines in names.txt", "sort names.txt alphabetically",
        "sort names.txt in alphabetical order", "put names.txt in alphabetical order", "alphabetize names.txt",
        "sort the lines of names.txt a to z", "sort names.txt a-z"],
    r"^sort -r (?:-- )?names\.txt$": [
        "sort names.txt in reverse", "sort names.txt in reverse order", "sort names.txt z to a",
        "reverse sort names.txt", "sort names.txt descending", "sort names.txt backwards",
        "sort names.txt in reverse alphabetical order"],
    r"^sort -n (?:-- )?nums\.txt$": [
        "sort nums.txt numerically", "sort nums.txt by number", "sort nums.txt as numbers",
        "numeric sort of nums.txt", "sort the numbers in nums.txt", "sort nums.txt in numerical order",
        "sort nums.txt smallest first", "sort nums.txt in numeric order"],
    r"^sort -(?:nr|rn) (?:-- )?nums\.txt$": [
        "sort nums.txt numerically descending", "sort nums.txt from largest to smallest",
        "sort nums.txt biggest first", "sort nums.txt highest first", "sort nums.txt numerically in reverse",
        "sort nums.txt in descending numerical order"],
    r"^sort -u (?:-- )?names\.txt$": [
        "sort names.txt and remove duplicates", "sort names.txt unique", "sort names.txt without duplicates",
        "sorted unique lines of names.txt", "sort names.txt and drop duplicate lines"],
    r"^sort -f (?:-- )?names\.txt$": [
        "sort names.txt ignoring case", "sort names.txt case insensitive", "sort names.txt case-insensitively",
        "sort names.txt regardless of case"],
}

# ---- everything else: fixed wordings -------------------------------------------------------
CATALOGUE = {
    "head": (r"^head -n 5 logs\.txt$", [
        "first 5 lines of logs.txt", "top 5 lines of logs.txt", "show the first 5 lines of logs.txt",
        "first five lines of logs.txt", "show 5 lines from the start of logs.txt", "head logs.txt 5 lines",
        "the first 5 lines in logs.txt", "print the first 5 lines of logs.txt"]),
    "tail": (r"^tail -n 5 logs\.txt$", [
        "last 5 lines of logs.txt", "bottom 5 lines of logs.txt", "show the last 5 lines of logs.txt",
        "last five lines of logs.txt", "the final 5 lines of logs.txt", "tail logs.txt 5 lines",
        "show 5 lines from the end of logs.txt"]),
    "follow": (r"^tail -f logs\.txt$", [
        "follow logs.txt", "watch logs.txt", "keep showing new lines of logs.txt", "live view of logs.txt",
        "follow logs.txt live", "watch logs.txt as it grows", "stream logs.txt"]),
    "wc lines": (r"^wc -l < logs\.txt$", [
        "count lines in logs.txt", "how many lines in logs.txt", "how many lines does logs.txt have",
        "line count of logs.txt", "number of lines in logs.txt", "count the lines of logs.txt",
        "how many lines are in logs.txt"]),
    "wc words": (r"^wc -w < logs\.txt$", [
        "count words in logs.txt", "how many words in logs.txt", "word count of logs.txt",
        "number of words in logs.txt", "how many words does logs.txt have"]),
    "wc chars": (r"^wc -[mc] < logs\.txt$", [
        "count characters in logs.txt", "how many characters in logs.txt", "character count of logs.txt",
        "number of characters in logs.txt", "how many chars are in logs.txt"]),
    "grep": (r"^grep -n?iF -- error logs\.txt$|^grep -inF -- error logs\.txt$", [
        "search for error in logs.txt", "find error in logs.txt", "look for error in logs.txt",
        "grep error in logs.txt", "lines with error in logs.txt", "which lines of logs.txt contain error",
        "show lines containing error in logs.txt", "search logs.txt for error",
        "search for error in logs.txt ignoring case", "case-insensitive search for error in logs.txt",
        "search for error in logs.txt with line numbers"]),
    "grep case": (r"^grep -n?F -- error logs\.txt$", [
        "search for error in logs.txt case sensitive", "case-sensitive search for error in logs.txt",
        "search for error in logs.txt matching case", "grep error in logs.txt exact case"]),
    "grep word": (r"^grep -n?iFw -- error logs\.txt$", [
        "search for the whole word error in logs.txt", "search for error in logs.txt as a whole word",
        "find the word error in logs.txt, whole words only", "grep whole word error in logs.txt"]),
    "grep count": (r"grep .*error.*logs\.txt.*\| wc -l$|^grep -c\w* .*error.*logs\.txt", [
        "count matches of error in logs.txt", "how many times does error appear in logs.txt",
        "how many lines contain error in logs.txt", "count error in logs.txt", "number of errors in logs.txt"]),
    "grep invert": (r"^grep -v\w* -- error logs\.txt$", [
        "lines in logs.txt without error", "lines of logs.txt that don't contain error",
        "show logs.txt without the error lines", "lines not containing error in logs.txt",
        "grep logs.txt excluding error"]),
    "du": (r"^du -sh (?:-- )?run1$", [
        "disk usage of run1", "how big is run1", "size of run1", "how much space does run1 use",
        "how much space does run1 take", "run1 size", "what is the size of run1"]),
    "df": (r"^df -h\b", [
        "free disk space", "how much disk space is left", "disk space", "space left on disk",
        "how full is the disk", "disk usage of the drives", "how much free space do i have"]),
    "ps mem": (r"ps aux --sort=-%mem", [
        "processes by memory", "what uses the most memory", "top memory processes",
        "sort processes by memory", "processes using the most ram", "which processes use the most memory",
        "processes in order of memory use"]),
    "ps cpu": (r"ps aux --sort=-%cpu", [
        "processes by cpu", "what uses the most cpu", "top cpu processes", "sort processes by cpu",
        "which process is using the cpu", "processes in order of cpu use"]),
    "ps mine": (r'ps (?:-f)?u "?\$USER"?|ps -fu "?\$USER"?|ps -u "?\$USER"?', [
        "my processes", "processes i own", "processes of the current user", "show my running processes",
        "list my processes"]),
    "cp dir": (r"^cp -(?:i?r|ai)\b", [
        "copy run1 to backup", "copy the folder run1 to backup", "duplicate run1 as backup",
        "make a copy of run1 called backup", "copy run1 into backup"]),
    "mkdir": (r"^mkdir -p -- a/b/c$", [
        "make folder a/b/c", "create directory a/b/c", "new folder a/b/c", "create the folders a/b/c",
        "make the directory a/b/c"]),
    "chmod x": (r"^chmod \+x -- run\.sh$", [
        "make run.sh executable", "give run.sh execute permission", "allow running run.sh",
        "add execute permission to run.sh", "set run.sh executable"]),
    "rm": (r"^rm (?:-i )?-- logs\.txt$|^rm -- logs\.txt$", [
        "delete logs.txt", "remove logs.txt", "erase logs.txt", "get rid of logs.txt"]),
    "mv": (r"^mv -i -- logs\.txt run1", [
        "move logs.txt to run1", "put logs.txt in run1", "move logs.txt into run1", "relocate logs.txt to run1"]),
    # network
    "ping": (rf"^ping (?:-c \d+ )?{re.escape(HOST)}$", [
        f"ping {HOST}", f"is {HOST} up", f"check if {HOST} is alive", f"is {HOST} reachable",
        f"can i reach {HOST}", f"is {HOST} online", f"ping the host {HOST}", f"does {HOST} answer"]),
    "ping count": (rf"^ping -c 5 {re.escape(HOST)}$", [
        f"ping {HOST} 5 times", f"ping {HOST} five times", f"send 5 pings to {HOST}", f"ping {HOST} with 5 packets"]),
    "ping once": (rf"^ping -c 1 {re.escape(HOST)}$", [
        f"ping {HOST} once", f"ping {HOST} one time", f"send one ping to {HOST}"]),
    "port": (rf"/dev/tcp/{re.escape(HOST)}/{PORT}\b|nc -z\w* .*{re.escape(HOST)} {PORT}\b", [
        f"ping {HOST} on port {PORT}", f"ping {HOST} port {PORT}", f"ping {HOST}:{PORT}",
        f"is port {PORT} open on {HOST}", f"check port {PORT} on {HOST}", f"can i reach {HOST} on port {PORT}",
        f"test connection to {HOST}:{PORT}", f"is {HOST}:{PORT} reachable",
        f"is {HOST} listening on port {PORT}", f"check if port {PORT} on {HOST} is open",
        f"test port {PORT} on {HOST}", f"is {HOST} port {PORT} open", f"can i connect to {HOST} on port {PORT}"]),
    "dns": (r"getent ahosts example\.com|(?:dig|host|nslookup) .*example\.com", [
        "dns lookup example.com", "resolve example.com", "ip of example.com", "ip address of example.com",
        "what is the ip of example.com", "look up the ip of example.com", "what ip does example.com have"]),
    "trace": (r"^(?:tracepath|traceroute|mtr)\b.*example\.com", [
        "traceroute to example.com", "trace the route to example.com", "route to example.com",
        "trace example.com", "show the hops to example.com"]),
    "headers": (r"^curl -s?I\w* .*example\.com", [
        "http headers of example.com", "headers of example.com", "show the http headers of example.com",
        "http response headers for example.com"]),
    "download": (r"(?:curl\b.*-[a-zA-Z]*[oO]|wget|urllib).*https://example\.com/a\.txt", [
        "download https://example.com/a.txt", "fetch https://example.com/a.txt",
        "save https://example.com/a.txt", "download the file https://example.com/a.txt",
        "get https://example.com/a.txt"]),
    "listen": (r"ss -\w*l\w* .*:22\b|lsof -i ?:22\b", [
        "what is listening on port 22", "which program uses port 22", "who is using port 22",
        "what runs on port 22", "what is on port 22", "which process listens on port 22"]),
    "scan": (rf"(?:nmap\b.*|/dev/tcp/){re.escape(HOST)}", [
        f"scan ports on {HOST}", f"which ports are open on {HOST}", f"open ports on {HOST}",
        f"port scan {HOST}", f"what ports does {HOST} have open"]),
}


def cases():
    out = []
    for kw, (words, rx) in LS_KEYS.items():
        for verb in LIST_VERBS:
            for form in SORT_FORMS:
                for w in words:
                    out.append((f"ls {kw}", f"{verb} {form.format(k=w)}", rx, None))
    for rx, phrases in LS_PHRASES.items():
        for verb in LIST_VERBS:
            for p in phrases:
                out.append(("ls", f"{verb} {p}", rx, None))
    for rx, phrases in SORT_FILE.items():
        for p in phrases:
            out.append(("sort", p, rx, None))
    for name, (rx, phrases) in CATALOGUE.items():
        for p in phrases:
            out.append((name, p, rx, None))
    return out


def lab():
    d = tempfile.mkdtemp()
    t.make_corpus(d)
    with open(os.path.join(d, "names.txt"), "w") as f:
        f.write("bob\nAnn\nbob\n")
    with open(os.path.join(d, "nums.txt"), "w") as f:
        f.write("10\n9\n100\n")
    return d


def outcome(phrase, d):
    if a.looks_like_shell(phrase, None, d):
        return phrase, "bash"
    plan = a.interpret(phrase, d)
    if plan and plan.confidence >= a.DEFAULTS["threshold"] and not plan.show_only:
        return plan.command, "rules"
    return (plan.command if plan else ""), "unsure"


def misses(d):
    bad = []
    for group, phrase, rx, forbid in cases():
        cmd, how = outcome(phrase, d)
        if how == "unsure" or not re.search(rx, cmd) or (forbid and re.search(forbid, cmd)):
            bad.append((group, phrase, how, cmd))
    return bad


class TestOptions(unittest.TestCase):
    def test_catalogue(self):
        d = lab()
        bad = misses(d)
        total = len(cases())
        print(f"\noptions: {total - len(bad)}/{total}", file=sys.stderr)
        self.assertEqual([f"{g}: {p!r} -> {h}: {c[:90]}" for g, p, h, c in bad], [])


if __name__ == "__main__":
    d = lab()
    bad = misses(d)
    by = {}
    for g, p, h, c in bad:
        by.setdefault(g, []).append((p, h, c))
    total = len(cases())
    print(f"{total - len(bad)}/{total} right")
    for g, rows in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"\n== {g}: {len(rows)} wrong")
        for p, h, c in rows[: int(os.environ.get("N", "12"))]:
            print(f"  {p!r:60} {h:6} {c[:100]}")

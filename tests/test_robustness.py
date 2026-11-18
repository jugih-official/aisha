"""Wording robustness: every corpus request, said differently, must still give the right command.

Variants: politeness around it, synonyms, the verb moved to the end, articles
dropped, one typo. Run: python3 -m unittest tests.test_robustness -v
"""
import os, sys, re, random, tempfile, collections, unittest, importlib.machinery as m, importlib.util as u
l = m.SourceFileLoader("t", os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_aisha.py"))
sp = u.spec_from_loader("t", l)
t = u.module_from_spec(sp); sys.modules.setdefault("t", t); l.exec_module(t)
a = t.aisha
random.seed(7)
# what a user might say instead (used only to GENERATE test variants)
USER_SYN = {
    "find": ["search for", "look for", "locate", "track down", "hunt for"],
    "show": ["display", "print", "view", "output", "let me see"],
    "list": ["show", "display", "enumerate"],
    "delete": ["remove", "erase", "get rid of", "wipe"],
    "remove": ["delete", "erase", "get rid of"],
    "create": ["make", "produce", "generate", "add", "set up"],
    "make": ["create", "produce"],
    "copy": ["duplicate", "replicate"],
    "move": ["relocate", "transfer", "shift"],
    "rename": ["retitle"],
    "edit": ["modify", "alter", "change"],
    "open": ["launch"],
    "files": ["files"],
    "folder": ["directory", "dir"],
    "folders": ["directories", "dirs"],
    "directory": ["folder"],
    "big": ["large", "huge"],
    "biggest": ["largest", "hugest"],
    "largest": ["biggest"],
    "old": ["stale", "outdated"],
    
    "newest": ["latest", "most recent"],
    "show me": ["give me", "tell me"],
    
    "memory": ["ram"],
    "ram": ["memory"],
    "disk": ["storage", "drive"],
    "computer": ["machine", "pc", "system"],
    "images": ["pictures", "photos", "pics"],
    "extract": ["unpack", "decompress", "unzip"],
    "compress": ["pack", "zip"],
    "count": ["tally"],
    "kill": ["terminate", "stop"],
    
    
    "what's": ["what is", "whats"],
}
WRAP = ["please {}", "can you {}", "could you {} for me", "i want to {}", "i'd like to {}", "{} please", "hey, {}",
        "{} thanks", "help me {}", "i need to {}", "would you {}", "go ahead and {}", "kindly {}"]
VERBS = r"find|show|list|delete|remove|create|make|copy|move|rename|edit|open|extract|compress|count|search|zip|unzip|go|kill"

def variants(p):
    out = set()
    for w in random.sample(WRAP, 3):
        out.add(("wrap", w.format(p)))
    low = p.lower()
    for k, vs in USER_SYN.items():
        if re.search(r"(?<![.\w])\b" + re.escape(k) + r"\b(?![.\w])", low) and not re.search(r"[\"'][^\"']*\b" + re.escape(k), low):
            out.add(("syn", re.sub(rf"\b{re.escape(k)}\b", random.choice(vs), p, count=1, flags=re.I)))
    mv = re.match(rf"^({VERBS})\s+(.+)$", p, re.I)
    if mv and len(mv.group(2).split()) <= 4:
        out.add(("order", f"{mv.group(2)} {mv.group(1)}"))
    if re.search(r"\b(the|a|an)\b", low):
        out.add(("drop", re.sub(r"\b(the|a|an)\s+", "", p, flags=re.I)))
    long = [w for w in p.split() if len(w) >= 6 and w.isalpha()]
    if long:
        w = random.choice(long); i = random.randrange(1, len(w) - 2)
        out.add(("typo", p.replace(w, w[:i] + w[i + 1] + w[i] + w[i + 2:], 1)))
    return out

def ok(phrase, exp, lab):
    if a.looks_like_shell(phrase, None, lab):
        return False, "bash"
    plan = a.interpret(phrase, lab)
    good = lambda c: all(any(x in c for x in f.split(" || ")) for f in exp.split(" ;; "))
    if plan and plan.confidence >= 0.7 and not plan.show_only:
        return good(plan.command), "rules:" + plan.command[:60]
    sug = a.suggest(phrase, lab)
    if sug and good(sug[0][1].command):
        return True, "model"
    return False, "none" if not sug else "model-wrong:" + sug[0][1].command[:60]



class TestRobustness(unittest.TestCase):
    def test_variants(self):
        lab = tempfile.mkdtemp()
        t.make_corpus(lab)
        total = bad = 0
        fails = []
        for phrase, exp in t.load_phrases():
            if exp.startswith("!"):
                continue
            for kind, v in sorted(variants(phrase)):
                total += 1
                good, how = ok(v, exp, lab)
                if not good:
                    bad += 1
                    fails.append(f"{kind}: {v} -> {how}")
        rate = (total - bad) / total
        print(f"\nrobustness: {total - bad}/{total} = {100 * rate:.1f}%", file=sys.stderr)
        self.assertGreaterEqual(rate, 0.97, "\n".join(fails[:40]))


if __name__ == "__main__":
    unittest.main()

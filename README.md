# ai.

A tiny CLI that turns natural-language requests into bash actions using the
Claude API. It can:

- run shell commands you describe in plain language (any language),
- gather information from the web before answering,
- handle everyday sysadmin tasks — RAM, disks, USB sticks, processes,
  services, networking — by picking the right tool for you.
- operate SSH and other remote connections (ssh/scp/sftp/rsync).

```
$ ai list all the files in cwd
$ ls -A
ai  README.md

$ ai how much RAM is free
$ free -h
               total        used        free      shared  buff/cache   available
Mem:            31Gi        12Gi       8.0Gi       1.2Gi        11Gi        17Gi

$ ai search the web for the latest python release and tell me the version
The latest stable release of Python is 3.13.x (released Oct 2024).
```

## Install

```sh
./install.sh
```

The installer:

- copies `ai`, `ai-browser`, `ai-desktop`, `ai-code`, and `aisha` to
  `/usr/local/bin/` (uses `sudo`),
- optionally installs browser automation tools (Playwright + Chromium),
- optionally sets up the **`ai-code`** coding agent's GPU backend on
  [Modal](https://modal.com) (deploys a local open-weights LLM — see
  [Coding agent](#coding-agent-ai-code) below),
- if you don't already have an `ANTHROPIC_API_KEY` in your environment,
  prompts for one and saves it to `~/.config/ai-bash/anthropic-api-key`
  (mode `600`),
- optionally also writes `/etc/ai-bash/anthropic-api-key` so `sudo ai ...` works
  without needing `sudo -E`.

Requires Python 3.10+. The core tool uses stdlib only; browser automation
optionally installs Playwright via `pip`. Get an Anthropic API key at
<https://platform.claude.com/> (starts with `sk-ant-`). API base is
<https://api.anthropic.com>; default model is `claude-sonnet-5-5`.

### Where the API key is read from

The script checks, in order:

1. `$ANTHROPIC_API_KEY`
2. `~/.config/ai-bash/anthropic-api-key` (your user)
3. `/etc/ai-bash/anthropic-api-key`       (root, for `sudo ai`)

Earlier versions used DeepSeek and read `api-key` from the same two
directories; that file is no longer used.

### Update

```sh
./update.sh
```

Pulls the latest commit from GitHub and re-runs `install.sh`. Safe to
re-run any time; if there's nothing new it just reinstalls the current
version. Refuses to run if you have uncommitted local changes.

If you don't have the repo checked out yet:

```sh
git clone https://github.com/jugih-official/ai-prompt.git
cd ai-prompt && ./install.sh
```

### Uninstall

```sh
./uninstall.sh
```

Removes `/usr/local/bin/ai` and offers to delete the saved key files.

## Usage

```
ai [-n] [-v] <natural language request>

  -n    print the suggested command(s) only; do not run
  -v    verbose: show silent FETCH steps and their outputs
```

### Examples

System / shell tasks (run directly):

```sh
ai list all the files in cwd
ai show disk usage of this folder in human-readable form
ai find every TODO in tracked git files
ai how much free RAM do I have
ai safely eject the USB stick mounted at /media/jukka/USB
ai which processes are using the most memory
ai restart the bluetooth service
ai ssh to user@server and show uptime
ai copy /var/log/syslog from user@server to ./ with scp
```

Chained tasks in one request (single CMD with multiple steps):

```sh
ai create ./table.sh, make it executable, and write a 3-column table where col1 is 2..16, col2 is random numbers, col3 counts down from 100
```

Questions that need the web (run silently, then answered in prose):

```sh
ai search the web for "lily of the valley" and tell me the first result
ai what is the latest stable kernel version
ai what's the weather forecast for Helsinki tomorrow
```

### Browser control (optional)

For browser automation, the tool uses Playwright plus
[`playwright-stealth`](https://pypi.org/project/playwright-stealth/) to
reduce the chance of being CAPTCHA-walled by sites like DuckDuckGo or
Cloudflare. The installer offers to set this up for you. It places
everything in a dedicated venv at `/opt/ai-bash/venv` (with Chromium
under `/opt/ai-bash/browsers`) so it doesn't fight PEP 668 on modern
Debian/Ubuntu/Fedora. On Debian/Ubuntu you may need
`sudo apt install python3-venv python3-full` first.

To install manually:

```sh
sudo python3 -m venv /opt/ai-bash/venv
sudo /opt/ai-bash/venv/bin/pip install --upgrade playwright playwright-stealth
sudo PLAYWRIGHT_BROWSERS_PATH=/opt/ai-bash/browsers \
    /opt/ai-bash/venv/bin/playwright install --with-deps chromium
sudo chmod -R a+rX /opt/ai-bash/browsers
sudo sed -i '1s|^#!.*|#!/opt/ai-bash/venv/bin/python3|' /usr/local/bin/ai-browser
sudo sed -i 's|^AI_BROWSER_PW_DIR =.*|AI_BROWSER_PW_DIR = "/opt/ai-bash/browsers"|' \
    /usr/local/bin/ai-browser
```

You can use the helper directly. The browser is **visible by default**
and, once the scripted steps finish, drops you into a small natural-
language prompt where you can keep steering the same session:

```
browser> click the second result
browser> fill the search box with "lily of the valley" and press enter
browser> exit
```

Each instruction is translated to more JSON steps by Claude and run on
the already-open page. Type `exit` / `quit` (or Ctrl-D, or close the
window) to end the session.

```sh
ai-browser <<'JSON'
[
  {"goto": "https://duckduckgo.com/?q=flowers"},
  {"wait_for": {"selector": "a[data-testid=result-title-a]", "index": 0}},
  {"click": {"selector": "a[data-testid=result-title-a]", "index": 0}}
]
JSON
```

Flags:

- `--headless` — hide the browser window (good for scripted scrapes;
  disables the steering REPL).
- `--no-wait` — exit immediately after the last step instead of waiting
  for the user to close the window. Use this for FETCH-style runs where
  you only care about the JSON output. Disables the REPL.
- `--no-interactive` — keep the window open but skip the natural-language
  steering prompt.
- `--no-stealth` — disable the anti-detection patches.
- `--timeout MS` — per-step timeout (default 30 000 ms).

The steering REPL needs the same `ANTHROPIC_API_KEY` as `ai` (or a key
file at `~/.config/ai-bash/anthropic-api-key` or
`/etc/ai-bash/anthropic-api-key`). With no key it just keeps the window
open without the prompt.

Environment overrides: `AI_BROWSER_UA`, `AI_BROWSER_LOCALE`,
`AI_BROWSER_TZ`.

Or just ask `ai` in natural language (it will call `ai-browser` when needed):

```sh
ai go to duckduckgo, search for flowers, and click the first result
```

Pipe in context — anything on stdin gets attached to your prompt:

```sh
cat error.log | ai why is this failing?
git diff      | ai write a commit message for this
journalctl -u nginx -n 200 | ai any errors here?
curl -s https://example.com/api | ai what fields does this response have?
```

Stdin is capped at 50 KB; longer input is truncated head + tail with
a `[…truncated N chars…]` marker.

## Coding agent (ai-code)

`ai-code` is an interactive coding agent — like Claude Code or Codex, but
powered by an **open-weights LLM running on your own GPUs**. Instead of a
hosted API, it talks to a [vLLM](https://docs.vllm.ai) server you deploy to
[Modal](https://modal.com), which spins a GPU up on demand and scales it back
to zero ~2 minutes after you stop (so you only pay while it's working).

```sh
cd my-project
ai-code                                  # interactive coding REPL
ai-code "add a --json flag to cli.py and update the tests"   # one-shot
ai-code -y "fix the failing test in test_parser.py"          # auto-approve
```

Inside the REPL you just describe what you want; the agent reads files, edits
them, and runs commands in the current project to get it done:

```
code> add docstrings to every function in utils.py, then run the tests
$ pytest -q
......                                                          [100%]
✓ Added docstrings to 6 functions; tests still pass.
code> /auto on        # stop confirming each edit/command
code> exit
```

REPL commands: `/help`, `/auto [on|off]`, `/reset`, `/cwd`, `exit`.

By default every file write/edit and every command is shown and confirmed
(press Enter to accept). `/auto on` or `-y` runs without prompts. Truly
destructive commands always require an explicit `y`.

### Setting up the GPU backend

The installer offers to do this for you. It first checks whether a Modal LLM
server is **already deployed** (the repo's `ai-code-llm`, or an existing
`llm-server`); if so it offers to **reuse** it — just paste that server's API
key and you're done, no new deploy. Otherwise it will:

1. install the [`modal`](https://modal.com) CLI if missing,
2. authenticate you with Modal (`modal token new`; free signup),
3. generate an API key and store it as a Modal secret (`ai-code-llm-key`),
4. deploy `modal/llm_modal.py` — a vLLM OpenAI-compatible server,
5. save the endpoint + key to `~/.config/ai-bash/code-url` and `code-key`.

The default model is **Qwen2.5-32B-Instruct-AWQ** on an **L40S** GPU (48 GB) —
the strongest model that fits comfortably. To use a different GPU/model, set
env vars when deploying, e.g.:

```sh
LLM_GPU=A10 LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct \
    modal deploy modal/llm_modal.py
```

The first request after an idle period pays a cold start (GPU boot + model
load, ~1–2 min once weights are cached); `ai-code` waits through it
automatically. Stop the backend any time with `modal app stop ai-code-llm`.

`ai-code` itself is stdlib-only Python and reads its endpoint/key from
`$AI_CODE_BASE_URL` / `$AI_CODE_API_KEY` or the files under
`~/.config/ai-bash/`.

### How ai-code drives the project

The model emits one action per turn from a small protocol; `ai-code` runs it
and feeds the result back:

| Action          | Behavior                                             |
|-----------------|------------------------------------------------------|
| `READ <path>`   | Read a file (contents returned to the model).        |
| `LIST <path>`   | List a directory.                                    |
| `RUN` + cmd     | Run shell command(s) in the project; output fed back.|
| `WRITE <path>`  | Create/overwrite a whole file.                       |
| `EDIT <path>`   | Apply search/replace edits to a file.                |
| `SAY <text>`    | Progress note / explanation to you.                  |
| `ASK <q>`       | Ask you a question and wait.                          |
| `DONE <summary>`| Finished — control returns to you.                   |

File access is confined to the project directory, and the same destructive-
command guard as `ai` applies.

You can also just ask `ai` to start it: `ai help me code in this project`
delegates to `ai-code`.

## Natural-language shell (aisha)

`aisha` is a shell you can talk to. Type bash as usual, or say what you want
in plain words. It needs nothing beyond a stock Debian system — Python's
standard library and the base tools. Most requests are handled by a
deterministic rule engine with no model at all; an optional small **local**
LLM is consulted only when the rules are unsure. No API key, no cloud.

```
$ aisha
aisha ~/lab ❯ find recursively files older that 2 months from this folder
→ find · here and subfolders · modified older than 2 months (60 days)
$ find . -path '*/.git' -prune -o -type f -mtime +60 -print
./run1/old-results.csv

aisha ~/lab ❯ edit logs.txt with micro
→ edit · logs.txt · with micro
$ micro logs.txt

aisha ~/lab ❯ git status                  # real commands run in bash unchanged
aisha ~/lab ❯ delete all .tmp files
→ delete · here and subfolders · type: .tmp
$ find . -type f -iname '*.tmp' -not -path '*/.git/*' -delete
1 match:
  ./old.tmp
! this deletes or changes things
run? [y/N]
```

### How a line is handled

No language model is needed. Every line goes through these steps and stops at
the first that handles it:

| Step | What happens | Speed |
|---|---|---|
| 1. Shell | A command on `PATH`, an alias or function, shell syntax (`for`, `f() {`, `X=1`), pipes or redirects run in bash unchanged. Everyday verbs that are also commands (`find big files`, `kill firefox`, `go up`, `install htop`, `edit x`) go to the rules when the rules are confident. | instant |
| 2. Taught | Phrases you taught (or approved) replay, including taught templates: teach "frobnicate notes.md" once and "frobnicate other.md" works. | instant |
| 3. Rules | The sentence is broken into slots — action, where, file types, size, age, owner, name/content keywords, sort, limit — plus ~140 recipes, and the command is built from those. Typos, synonyms ("erase", "relocate", "display") and a verb at the end ("README.md delete") are retried. The `→` line shows what it understood. | ~1 ms |
| 4. Built-in model | If the rules are unsure, a small statistical model inside aisha (TF-IDF over words and character trigrams, 361 known request templates, no download) finds the closest known requests, fills in your file names, numbers and quoted text, and offers the ones the rules are sure of: pick a number. | ~2 ms |
| 5. Teach | Nothing fits? Type the bash command once; aisha runs it and learns it, with your values as slots. Or `teach backup {dir} = tar -czf {dir}.tgz {dir}`. | — |
| (optional) | A small language model, only if you set one up with `aisha --setup`. Off otherwise. | ~1 s |

Questions — "how do I delete empty folders?" — show the command without
running it.

On phrasings that were not in its tests, aisha's rules and built-in model got
23 of 30 right before tuning (77%) and returned nothing for the rest — a
"don't know" rather than a wrong command in all but one case. Each miss
became a general fix and a test; `tests/phrases.tsv` and
`tests/suggestions.tsv` hold the requests it is checked against.

### What the rules understand

About 140 kinds of request, without a model:

- **Files** — list, find (type, name, content, size and size ranges, age,
  owner, empty, hidden, broken links, duplicates, exclusions), file tree,
  details, type, permissions, owner, checksums, show/head/tail/follow/edit,
  copy/move/rename/delete (also "find … and delete/move/copy them"), bulk
  extension renames, trash, symlinks, zip/tar/extract and archive contents,
  backups, downloads, compare, replace text, count files by extension.
- **Text** — line N or lines N–M, line numbers, sort, unique lines, remove
  duplicate lines, count matches, reverse, pretty-print JSON, CSV as a
  table, append or write a line, empty a file, base64, upper/lower case.
- **Dates and numbers** — arithmetic, time in a city, timezone, week number,
  dates N days from now, timestamps, timers, reminders, random numbers,
  dice, coin, passwords, UUIDs.
- **System** — memory, CPU usage, load, temperature, battery, disks,
  inodes, swap, GPU, USB and PCI devices, hardware, screen resolution,
  processes and what a program uses, ports and freeing one, kernel
  messages, system errors, boot and service logs, services (start, stop,
  restart, status, running, failed), logins, sudo rights, locale, keyboard,
  reboot/shutdown/scheduled shutdown, lock screen.
- **Packages** — install, remove, search, info, which package owns a file,
  files of a package, recently installed, check for updates, upgrade, clean
  up old packages.
- **Shell** — variables, aliases (saved to `aisharc`), adding to `PATH`,
  what a command does, its manual, repeat every N seconds, time a command,
  run in the background, as root, notify when done, `again`.
- **Network** — IPs, gateway, routes, DNS servers, MAC addresses, is a host
  up, DNS lookup, is a port open on a host, HTTP headers, weather, Wi-Fi
  networks/name/password, ssh, scp to and from a server, sync folders,
  firewall.
- **Git** (inside a repository) — what changed, recent commits, branch,
  switch/create branch, commit with a message, push, pull, undo last commit,
  discard changes, diff of a file, who changed a file, stash, clone, init.
- **Users and desktop** — add a user, add to a group, change password,
  become root, switch user, open a website or app, web search, screenshot,
  volume.

"what can you do" inside aisha lists examples. Actions you rule out ("find
tmp files, don't remove them") are never run. `tests/phrases.tsv` lists the
380+ requests the test suite checks, including ones the rules must leave to
the model.

| You type | aisha runs |
|---|---|
| `find recursively files older that 2 months from this folder` | `find . … -type f -mtime +60 -print` |
| `find logs older than 2 months and move them to archive` | `mkdir -p -- archive && find . … -iname '*.log' -mtime +60 … -exec mv -i -t archive -- {} +` (preview, `[y/N]`) |
| `edit logs.txt` | `sensible-editor logs.txt` — `$VISUAL`/`$EDITOR`, else Debian's `editor` |
| `edit logs.txt with micro` / `using micro` / `open logs.txt in micro` | `micro logs.txt` (installed with apt first if missing, after asking) |
| `edit app.log` (it is in `var/log/`) | `sensible-editor var/log/app.log` |
| `find duplicate files` | `find … -print0 \| xargs -0 -r md5sum \| sort \| uniq -w32 --all-repeated=separate` |
| `rename all .jpeg files to .jpg` | `for f in *.jpeg; do mv -i -- "$f" "${f%.jpeg}.jpg"; done` (preview, `[y/N]`) |
| `what's using all my memory` | `ps aux --sort=-%mem \| head -n 11` |
| `replace "foo bar" with "baz" in all python files` | `find … -iname '*.py' -exec grep -IqiF -e 'foo bar' {} \; -exec sed -i 's/foo bar/baz/g' {} +` (preview, `[y/N]`) |
| `find all files except python files` | `find … -type f -not -iname '*.py' -print` |

Where a tool might be missing on a minimal system, aisha falls back to
Python's standard library or `/proc`: zip/unzip → `python3 -m zipfile`,
downloads → `urllib`, `free`/`uptime`/`ss`/`ip`/`cal` → `/proc` or
`python3`.

### A real shell

- `cd`, variables (plain and exported, arrays too), `umask`, `shopt`
  options, aliases and functions persist between lines;
  `~/.bash_aliases` and `~/.config/ai-bash/aisha/aisharc` are loaded at
  start. (Traps and `set -o` options do not carry over.)
- Job control: Ctrl-Z, `jobs`, `fg`, `bg`, `cmd &`, `kill %N`.
- Closing the terminal or `kill`ing aisha passes the signal on to the
  running command, hangs up jobs, stops the model and saves history.
- Tab completes commands and paths; history is kept in
  `~/.config/ai-bash/aisha/history`.
- `aisha -c '…'`, `aisha script.sh` and scripts on stdin run in plain bash,
  so aisha is safe as a login shell (`chsh -s /usr/bin/aisha` after
  installing the Debian package, which registers it in `/etc/shells`).

```sh
aisha                                   # interactive shell
aisha show the 5 newest files here      # one line, then exit
aisha -n delete log files older than 30 days   # show the command, run nothing
aisha --lines < requests.txt            # several plain-language lines
aisha --doctor                          # check tools, fallbacks, built-in model and optional LLM
```

Inside the shell: `!cmd` forces bash, `?request` skips the rules and asks the
LLM, `explain <request>` shows what would run, `learned` / `forget <request>`
manage remembered phrases, `llm` checks the model, `help` lists examples.

### Safety

- Anything that deletes, moves in bulk, rewrites or overwrites files asks
  `[y/N]`, whoever wrote the command (rules, model or memory). Deletes,
  bulk moves and replacements first list exactly the files they will touch.
- Model commands also ask `[Y/n]`; ones with `sudo`, `sed -i`,
  `rsync --delete`, `git push --force`/`reset`/`clean`, `> file`,
  recursive `chmod`, `curl | sh`, `kill -9`, service or package changes
  ask `[y/N]`.
- The rules never guess a delete: "clean up" or "delete everything" get
  no plan; "the empty file" without a name gets no plan; a named file that
  isn't there gets no plan; "the largest files" without a count goes to the
  model. Places ("in ~/") are never targets, and home, `/` and system
  folders are never deleted from words. Folder deletes keep the folder they
  start in.
- Actions you rule out ("find tmp files, don't remove them") never run, and
  a "not" the rules can't place sends the request to the model.
- Extraction never replaces existing files; copies and backups ask before
  overwriting.
- Names and search terms are always quoted, so text like `$(…)` in a file
  name is never executed.
- `aisha -n …` and "how do I …" only show the command.

### Optional language model

aisha does not need one, and uses none unless you set it up:

```sh
aisha --setup            # Qwen2.5-Coder 0.5B (0.5 GB) + Mozilla's llamafile server (~45 MB)
aisha --setup 1.5b       # better, 1.1 GB
aisha --setup --ollama   # use Ollama instead, if you have it
aisha --setup --url http://127.0.0.1:8080/v1   # any OpenAI-compatible server you run
aisha --setup --runtime ~/bin/llama-server   # a llama.cpp/llamafile you already have
aisha --setup off        # never use a model
aisha --setup remove     # delete the downloaded runtime and model
```

The default needs no Ollama: aisha uses a `llama-server` or `llamafile` already
on `PATH`, or downloads Mozilla's llamafile (llama.cpp as one portable file,
Apache 2.0) and the model (Apache 2.0) from Hugging Face into
`~/.local/share/aisha`. If Hugging Face is unreachable it falls back to a
llama.cpp release from GitHub. aisha starts the server the first time it is
needed and stops it when aisha exits. When the rules and the built-in model are unsure, the model
is offered as one more option (`?` at the prompt); its commands are always
shown and confirmed.

Settings live in `~/.config/ai-bash/aisha/config.json` or the environment:

| Setting | Env var | Default |
|---|---|---|
| `llm` | `AISHA_LLM` | `auto` — use a model only once one is set up; `off` never |
| `llm_url` | `AISHA_LLM_URL` | set by `--setup` |
| `llm_model` | `AISHA_LLM_MODEL` | set by `--setup` |
| `llm_server` / `llm_model_file` | `AISHA_LLM_SERVER` / `AISHA_LLM_MODEL_FILE` | set by `--setup` |
| `threshold` | `AISHA_THRESHOLD` | `0.7` (rules below this are "unsure") |
| `confirm` | `AISHA_CONFIRM` | `llm` (`always`, or `destructive` only) |

### Install

```sh
packaging/debian/build-deb.sh            # -> dist/aisha_<version>_all.deb
sudo apt install ./dist/aisha_*_all.deb  # /usr/bin/aisha, man aisha
```

or `./install.sh`, which puts it in `/usr/local`. Needs Python 3.9+
(Debian 11 or newer). `man aisha` documents the options.

### Roadmap

- **Windows.** The rule engine (words → slots) is platform-neutral; the
  command builder and the executor are bash/GNU-specific. The Windows port
  adds a builder that turns the same slots into PowerShell
  (`Get-ChildItem -Recurse -File | Where-Object LastWriteTime -lt …`) and runs
  it through `pwsh`.

Tests: `python3 -m unittest discover -s tests` (unit tests, the phrase
corpus, a pty-free shell session, injection checks, and the model runtime
against a stand-in server).

## How it works

The model speaks a small line-prefixed protocol:

| Prefix    | Behavior                                                                 |
|-----------|--------------------------------------------------------------------------|
| `CMD:`    | Run on your terminal — both command and output are visible. Done.        |
| `FETCH:`  | Run silently. Output is fed back to the model. Used to gather data.      |
| `SAY:`    | Final natural-language answer to you. Done.                              |
| `REFUSE:` | Model refused (e.g. truly dangerous). Exits non-zero. Done.              |

A request can loop through multiple `FETCH:` steps (e.g. search the web,
parse the result) before the model emits a final `SAY:`. The loop is
capped at 8 turns.

## Safety notes

- Commands run immediately — **except** anything that deletes or
  overwrites data (`rm`, `rmdir`, `shred`, `unlink`, `find … -delete`,
  `dd of=/dev/…`, `mkfs`, partition tools, redirecting to a block
  device). For those, you'll get a `! this command deletes or
  overwrites data` warning and a `run? [y/N]` prompt.
- Silent `FETCH:` commands can never be destructive — the harness
  blocks them and forces the model to use `CMD:` instead.
- The model is told to refuse truly dangerous requests, but treat that
  as a soft guardrail, not a guarantee. Use `-n` to dry-run anything
  you're unsure about.
- Your `ANTHROPIC_API_KEY` is read from the environment and never
  written to disk by this script.

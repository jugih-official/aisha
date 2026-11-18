# ai$ha — ai shell hybrid alpha

**ai$ha** is a shell you can talk to. You start it with `aisha` (a `$` can't
be part of a command name: every shell would read `$ha` as a variable), and
the package, folders and settings are called `aisha` too. Type bash as usual, or say what you want
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

## How a line is handled

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

## What the rules understand

About 240 kinds of request, without a model:

- **Files** — list, find (type, name, content, size and size ranges, age,
  owner, empty, hidden, broken links, duplicates, exclusions), file tree,
  details, type, permissions, owner, checksums, show/head/tail/follow/edit,
  copy/move/rename/delete (also "find … and delete/move/copy them"), bulk
  extension renames, trash, symlinks, zip/tar/extract and archive contents,
  backups, downloads, compare, replace text, count files by extension,
  "everything except X", "all but the newest 3", the Nth newest file, files
  edited yesterday afternoon, newer than a file, before a year, with spaces
  in the name, world-writable, unreadable, not mine, not executable, full
  path, size in bytes, empty a folder but keep it, add a file to a zip,
  password-protected zips, extract one file, the real trash.
- **Text** — line N or lines N–M, line numbers, sort, unique lines, remove
  duplicate lines, count matches, reverse, pretty-print JSON, CSV as a
  table, append or write a line, empty a file, base64, upper/lower case,
  columns and sorting by a column, lines without a word, the most common
  lines, grep with context, matches per file, delete line N / blank lines /
  the header, tabs to spaces, JSON keys, CSV to JSON, is this JSON/zip valid.
- **Dates and numbers** — arithmetic, time in a city, timezone, week number,
  dates N days from now, timestamps, timers, reminders, random numbers,
  dice, coin, passwords, UUIDs.
- **System** — memory, CPU usage, load, temperature, battery, disks,
  inodes, swap, GPU, USB and PCI devices, hardware, screen resolution,
  processes and what a program uses, ports and freeing one, kernel
  messages, system errors, boot and service logs, services (start, stop,
  restart, status, running, failed, enabled at boot, logs, uptime), logins,
  failed logins, sudo rights, locale, keyboard, reboot/shutdown now, in N
  minutes, at a time or tonight, lock screen, why is my computer slow, the
  process tree, kill by port / all but one / the top CPU process, pause and
  resume a program, threads and total memory of a program, swap per process,
  docker space, clean-up and stopping containers.
- **Packages** — install, remove, search, info, which package owns a file,
  files of a package, recently installed, check for updates, upgrade, clean
  up old packages, install several at once, purge, fix broken packages,
  upgrade everything except the kernel, which packages take the most space.
- **Shell** — variables, aliases (saved to `aisharc`), adding to `PATH`,
  what a command does, its manual, repeat every N seconds, time a command,
  run in the background, as root, notify when done, `again`.
- **Network** — IPs, gateway, routes, DNS servers, MAC addresses, is a host
  up, DNS lookup, is a port open on a host, HTTP headers, weather, Wi-Fi
  networks/name/password, ssh, scp to and from a server, sync folders,
  firewall (block or open a port), active connections, devices on my wifi,
  renew my IP.
- **Network interfaces and radios**, in any word order: list interfaces,
  details, up or down, link speed; set, add or remove an address (with
  netmask, gateway and DNS), DHCP on or off, gateway, DNS, MTU, MAC
  address; Wi-Fi and Bluetooth on or off, airplane mode, radio status;
  connect to or forget a Wi-Fi network, its password, a hotspot. aisha reads
  the real interfaces from `/sys/class/net`, so "the wifi" or "the wired
  card" become `wlp3s0` or `eno1`. With NetworkManager running, changes go
  through `nmcli` and last; without it they use `ip` and last until reboot.
  Every change asks `[y/N]`; commands you type (`ip …`, `nmcli …`) run as
  they are.

  | You type | aisha runs (NetworkManager) |
  |---|---|
  | `set ip 192.168.20.1/24 to interface eno1` | `nmcli connection modify <eno1's connection> ipv4.method manual ipv4.addresses 192.168.20.1/24 && nmcli connection up …` |
  | `give the wifi interface 10.0.0.5/24 with gateway 10.0.0.1` | the same for `wlp3s0`, plus `ipv4.gateway 10.0.0.1` |
  | `set dhcp off on 192.168.20.1` | the interface that has 192.168.20.1 becomes static at that address |
  | `use dhcp on eno1` | `… ipv4.method auto …` |
  | `bring eno1 down` / `enable eno1` | `nmcli device disconnect eno1` / `nmcli device connect eno1` |
  | `turn wifi off` / `airplane mode on` | `nmcli radio wifi off` / `nmcli radio all off && rfkill block bluetooth` |
- **Git** (inside a repository), in everyday words and any order. aisha
  reads the repository's own branches, remotes and tags, so "merge dev"
  knows dev is a branch, and it keeps names in the case you typed.
  - *status and diffs:* what changed, is my repo clean, anything to commit,
    what's staged / about to commit, changes in a file, since the last
    commit, between two branches or tags
  - *staging and committing:* stage a file / everything / my changes,
    unstage, commit (a file, everything, with a message, "save my work as …"),
    amend, reword the last message, "I forgot app.py in the last commit"
  - *push, pull, fetch:* push, push this branch and track it, push a
    branch, force push (with lease), push tags; pull, pull with rebase, pull a
    branch, "get the latest", "update my repo from github", fetch, fetch all
  - *branches:* which branch, list (local, remote, merged, unmerged), create
    (from a base, with or without switching), switch, switch back, rename,
    delete (force), delete on the remote
  - *merge, rebase, cherry-pick:* merge X (into Y), squash merge, "update my
    branch with main", rebase onto X, "put my commits on top of main",
    interactive rebase of the last N, cherry-pick, abort / continue (only
    when one is really in progress), conflicts, keep mine / take theirs, mark
    resolved
  - *undo and roll back:* undo the last N commits (keeping or throwing away
    the changes), revert a commit or the last N, go back N commits or to a
    commit or tag, look at an old commit, make my branch match the remote,
    discard changes (all, or in a file), reset everything, restore a file
    (from N commits ago, a branch, a tag), bring back a deleted file, undo a
    pull or merge
  - *stash:* stash (with a message, with new files), list, show, apply, pop,
    drop, clear
  - *history:* log, graph, last N, by author, mine, since a time, of a file,
    who changed a file or line, search messages, which commit added some
    text, show a commit, who made / what did the last commit, unpushed,
    incoming, ahead or behind
  - *tags, remotes and more:* list, create (annotated), delete and push
    tags; list, add, rename, remove remotes and change their URL; ignore a
    file, set your git name and email, update submodules, clone, init,
    remove untracked files, stop tracking a file

  Anything that throws work away or rewrites history shows what it will
  touch and asks `[y/N]`. Commands you type (`git pull`, `git commit -m …`)
  run as they are; `gitpull` and `gti status` are read as `git pull` and
  `git status`. `tests/git_phrases.tsv` holds 276 wordings checked against a
  real repository.
- **Users and desktop** — add or delete a user, make someone an admin, who
  has sudo, a user's groups, who can log in, add to a group, change password,
  become root, switch user, open a website or app, web search, screenshot,
  volume.

- **Listing parameters**, in any combination and wording — sort by name,
  time, size, extension, version, access, change or creation time, or
  unsorted; reversed / oldest first / newest last / a–z / z–a / ascending /
  descending; long, names only, one per line, columns, comma-separated, full
  timestamps, bytes or KB; hidden included or only, files only, folders only,
  folders first, type markers. "list all the files in this folder by time,
  oldest first, including hidden" → `ls -lhAtr`.
- **USB drives** — list connected drives and devices, free space, mount,
  unmount, eject (power off), format to NTFS / FAT32 / exFAT / ext4 with a
  label. aisha reads the drives itself, names the real device in the
  command, only ever touches drives on USB (never the system disk), asks for
  the drive when several are plugged in, and shows "ERASES EVERYTHING on
  /dev/sdb1 (SanDisk, 28.9G)" before formatting.

Wording is normalised before the rules run: politeness ("could you … for
me, thanks", "I'd like to", "help me", "go ahead and"), synonyms, a verb at
the end, missing articles and typos of any word aisha knows.
`tests/test_robustness.py` rewrites every tested request those ways (about
3,900 variants) and requires at least 97% to still give the right command;
it is at 97.4%.

"what can you do" inside aisha lists examples. Actions you rule out ("find
tmp files, don't remove them") are never run. `tests/phrases.tsv` lists the
820+ requests the test suite checks, including ones the rules must leave to
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

## A real shell

- `cd`, variables (plain and exported, arrays too), `umask`, `shopt`
  options, aliases and functions persist between lines;
  `~/.bash_aliases` and `~/.config/aisha/aisharc` are loaded at
  start. (Traps and `set -o` options do not carry over.)
- Job control: Ctrl-Z, `jobs`, `fg`, `bg`, `cmd &`, `kill %N`.
- Closing the terminal or `kill`ing aisha passes the signal on to the
  running command, hangs up jobs, stops the model and saves history.
- Tab completes commands and paths; history is kept in
  `~/.config/aisha/history`.
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

## Safety

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
- Power words are never handed to bash: `reboot nginx` restarts the nginx
  service (systemd's `reboot` would take the word as an argument and restart
  the computer), `reboot tonight` schedules it, `reboot later` asks when.
  "yes" and "thanks" get a reply instead of running `yes`.
- "Everything except X" keeps X; if X isn't there, nothing is deleted. A
  file name is never written into an archive as text. "To the trash" uses
  the real trash (`gio trash`).
- A guess from the "closest things" list that deletes or changes things is
  never listed first, and a guess never reboots or powers off the computer
  unless you said so.
- Extraction never replaces existing files; copies and backups ask before
  overwriting.
- Names and search terms are always quoted, so text like `$(…)` in a file
  name is never executed.
- `aisha -n …` and "how do I …" only show the command.

`tests/findings.md` is the ledger of a bug hunt: two agents competed to find
requests aisha got wrong, a third judged them. All 109 accepted findings are
fixed and in `tests/phrases.tsv`.

## Optional language model

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

Settings live in `~/.config/aisha/config.json` or the environment:

| Setting | Env var | Default |
|---|---|---|
| `llm` | `AISHA_LLM` | `auto` — use a model only once one is set up; `off` never |
| `llm_url` | `AISHA_LLM_URL` | set by `--setup` |
| `llm_model` | `AISHA_LLM_MODEL` | set by `--setup` |
| `llm_server` / `llm_model_file` | `AISHA_LLM_SERVER` / `AISHA_LLM_MODEL_FILE` | set by `--setup` |
| `threshold` | `AISHA_THRESHOLD` | `0.7` (rules below this are "unsure") |
| `confirm` | `AISHA_CONFIRM` | `llm` (`always`, or `destructive` only) |
| `prompt_git` | `AISHA_PROMPT_GIT` | `false` (`true` shows `git:branch` in the prompt) |
| `banner` | `AISHA_BANNER` | `true` (`false` hides the greeting) |

## Install

```sh
git clone https://github.com/jugih-official/aisha.git
cd aisha
./install.sh
```

On Debian and Ubuntu, `install.sh` builds the Debian package
(`packaging/debian/build-deb.sh` → `dist/aisha_<version>_all.deb`) and
installs it with apt: `/usr/bin/aisha`, `man aisha`, registered as a login
shell. Elsewhere, or with `./install.sh --local`, it puts aisha in
`/usr/local` without a package. Needs Python 3.9+ (Debian 11 or newer).

It asks two things, each only while it is not done yet (otherwise it says how it stands):

- **Install the language model?** Asked whenever no model is set up: a
  small local model (Qwen2.5-Coder 0.5B run by llamafile, about 550 MB) for
  the requests the rules don't know, downloaded with `aisha --setup`. When
  one is set up, the installer just says so. `./install.sh --with-llm`
  installs it without asking (`--with-llm 1.5b` or `3b` for a bigger model),
  `--no-llm` skips the question, and `aisha --setup` adds it any time later.
  `./update.sh` only reports both, it doesn't ask.
- **Open aisha in new terminal windows?** GNOME Terminal (Ubuntu, Linux
  Mint Cinnamon) and Konsole get it in their profile. Xfce Terminal (Linux
  Mint Xfce, Xubuntu) and any other terminal app get four lines in
  `~/.bashrc` that start aisha in a terminal window. Xfce Terminal keeps its
  settings in memory, so changing them from outside doesn't stick. Logins,
  ssh, text consoles and scripts keep bash either way; `AISHA_SKIP=1 bash`
  gives plain bash in one window. Change it later with
  `packaging/terminal-default.sh set`, `unset` or `status`.

`./install.sh --no-ask` skips both questions. To use aisha everywhere, including ssh, make
it your login shell: `chsh -s /usr/bin/aisha` (back: `chsh -s /bin/bash`).

To update, run `./update.sh` in this folder: it pulls the latest version and
reinstalls aisha the way you installed it (package or `/usr/local`).
`./uninstall.sh` removes it and asks before deleting your settings or a
downloaded model.

This repository used to be called `ai-prompt` and also held the `ai`,
`ai-browser`, `ai-desktop` and `ai-code` CLIs; they were removed in 0.7.1
(the last commit with them is `e11586d`). `./uninstall.sh` also offers to
remove copies of them left in `/usr/local/bin`.

## Roadmap

- **Windows.** The rule engine (words → slots) is platform-neutral; the
  command builder and the executor are bash/GNU-specific. The Windows port
  adds a builder that turns the same slots into PowerShell
  (`Get-ChildItem -Recurse -File | Where-Object LastWriteTime -lt …`) and runs
  it through `pwsh`.

Tests: `python3 -m unittest discover -s tests` (unit tests, the phrase
corpus, a pty-free shell session, injection checks, and the model runtime
against a stand-in server).

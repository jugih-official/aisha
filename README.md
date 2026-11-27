# ai$ha (ai shell hybrid alpha)

**ai$ha** is a bash-compatible shell that also accepts requests in plain
English. Requirements: a stock Debian system (the Python standard library and
the base tools). Most requests are translated by a deterministic rule engine,
without any model. An optional small **local** LLM is consulted only when the
rules are unsure.

> **Alpha software, no warranty.** Requests are turned into shell commands
> and executed, some with `sudo`, some deleting, overwriting or uninstalling.
> Each command is printed before execution and should be checked before `y`
> is answered. See [Disclaimer](#disclaimer) and [License](#license).

```
$ aisha
aisha ~/lab $ find recursively files older that 2 months from this folder
→ find · here and subfolders · modified older than 2 months (60 days)
$ find . -path '*/.git' -prune -o -type f -mtime +60 -print
./run1/old-results.csv

aisha ~/lab $ edit logs.txt with micro
→ edit · logs.txt · with micro
$ micro logs.txt

aisha ~/lab $ git status                  # bash commands are passed to bash unchanged
aisha ~/lab $ delete all .tmp files
→ delete · here and subfolders · type: .tmp
$ find . -type f -iname '*.tmp' -not -path '*/.git/*' -delete
1 match:
  ./old.tmp
! this deletes or changes things
run? [y/N]
```

## Line handling

No language model is required. Each line passes through the following steps;
processing stops at the first step that handles it.

| Step | Handling | Speed |
|---|---|---|
| 1. Shell | Commands on `PATH`, aliases, functions, shell syntax (`for`, `f() {`, `X=1`), pipes and redirects are passed to bash unchanged. Everyday verbs that are also command names (`find big files`, `kill firefox`, `go up`, `install htop`, `edit x`) are sent to the rules when the rules are confident. | instant |
| 2. Taught | Taught or approved phrases are replayed, including taught templates: after "frobnicate notes.md" is taught, "frobnicate other.md" is handled as well. | instant |
| 3. Rules | The sentence is split into slots (action, location, file types, size, age, owner, name and content keywords, sort, limit) and matched against about 140 recipes; the command is built from the slots. Typos, synonyms ("erase", "relocate", "display") and a trailing verb ("README.md delete") are retried. The interpretation is printed on the `→` line. | ~1 ms |
| 4. Built-in model | When the rules are unsure, a small statistical model inside aisha (TF-IDF over words and character trigrams, 361 request templates, no download) selects the closest known requests, fills in file names, numbers and quoted text from the line, and offers the candidates accepted by the rules as a numbered list. | ~2 ms |
| 5. Teach | When nothing matches, a bash command typed once is executed and stored, with the values from the request as slots. Explicit form: `teach backup {dir} = tar -czf {dir}.tgz {dir}`. | — |
| (optional) | A small language model, active only after `aisha --setup`. Off by default. | ~1 s |

Questions such as "how do I delete empty folders?" print the command without
executing it.

When a typed bash line fails with exit code 2 (wrong usage or a missing file),
126 (not executable) or 127 (command not found), a hint line follows, and `?`
(or `fix`) on the next line asks what was meant. A line of plain words is read
by the rules first ("sort alphabetically" → the alphabetical listing); a line
with flags or shell syntax goes to the language model, with the failed line and
its exit code; without a model, the built-in model's closest requests are
offered. Every answer is shown and confirmed before it runs, and a confirmed
answer that succeeds is remembered for that line. `"fix_hint": false` (or
`AISHA_FIX_HINT=false`) turns the hint off.

### Memory

Memory grows only from confirmed results, in `~/.config/aisha/learned.json`:
language model answers that were confirmed and succeeded, picks from the
suggestion list, and taught commands (as templates, so "frobnicate notes.md"
also works for other files). It is used in three ways:

- **Exact replay.** The same phrase runs the learned command without asking
  the model again.
- **Close wordings.** A new wording near a learned one is offered first in the
  suggestion list, marked `(learned)`; templates get the new request's values.
  A pick that succeeds is learned under the new wording too.
- **Examples for the model.** The most similar learned pairs go into the
  language model's prompt as examples, so its answers follow earlier choices.

A declined model answer is recorded in `learned-rejected.json`: the model is
told about it, and the same command is refused if offered again for that
request. `learned` lists the memory; `forget <request>` removes an entry and
its declined commands.

Accuracy on 30 phrasings outside the test set, before tuning: 23 correct
commands (77%) from the rules and the built-in model. Of the 7 misses, 6
produced no command and 1 a wrong command. Each miss was turned into a general
fix and a test. The test requests are kept in `tests/phrases.tsv` and
`tests/suggestions.tsv`.

## Supported requests

About 240 kinds of request are handled without a model:

- **Files**: list, find (type, name, content, size and size ranges, age,
  owner, empty, hidden, broken links, duplicates, exclusions), file tree,
  details, type, permissions, owner, checksums, show/head/tail/follow/edit,
  copy/move/rename/delete (also "find … and delete/move/copy them"), bulk
  extension renames, trash, symlinks, zip/tar/extract and archive contents,
  backups, downloads, compare, replace text, count files by extension,
  "everything except X", "all but the newest 3", the Nth newest file, files
  edited yesterday afternoon, newer than a file, before a year, spaces in the
  name, world-writable, unreadable, not owned by the current user, not
  executable, full path, size in bytes, emptying a folder without removing
  it, adding a file to a zip, password-protected zips, extracting one file,
  the desktop trash.
- **Search**: `search` and its synonyms (look for, hunt for, seek, scan, dig
  up, track down, locate, grep) in common wordings. `search` alone prints
  examples. These words are taken by aisha even where a `search` program is
  installed (as on Linux Mint); `search -flags` still runs that program.
  - *File names:* `search for main.py`, `look up notes.txt` and
    `search the whole computer for nginx.conf` find the file (`-iname`); the
    name is never grepped. `main.py or notes.txt` finds either file.
  - *search <place> for <what>:* run1, ~/data, here, home, the downloads /
    documents / desktop folders, the whole system (`/`), python files, the
    code. Text yields the matching lines; a file type yields the matching
    files (`search downloads for pdfs`, `scan run1 for csv files`).
  - *Name or content, stated explicitly:* search file names / titles / pdf
    names for X, by name, with X in the name; search file contents / the text
    of files for X, by content.
  - *Text:* the word / phrase / text X, lines containing X, "quoted words",
    where does X appear, where is TODO used in the code, in which file is X
    mentioned, which files have the word X.
  - *Options:* case sensitive or case insensitive, whole word, file names only
    (`grep -l`), exact name (`-name Notes`), X or Y, since monday / after a
    date / before a date.
  - *Locations:* which folder is notes.txt in (the folder is printed), full
    path of X, does X exist / check if there is a pdf here (`not found: X` is
    printed when nothing matches).

  Folders are matched by name, never grepped. `tests/search_phrases.tsv`
  holds 126 wordings; every resulting command that stays inside the test
  folder is also executed.
- **Text**: line N or lines N–M, line numbers, sort, unique lines, duplicate
  line removal, match counts, reverse, JSON pretty-printing, CSV as a table,
  appending or writing a line, emptying a file, base64, upper/lower case,
  columns and sorting by a column, lines without a word, the most common
  lines, grep with context, matches per file, deleting line N / blank lines /
  the header, tabs to spaces, JSON keys, CSV to JSON, JSON/zip validity.
- **Dates and numbers**: arithmetic, time in a city, timezone, week number,
  dates N days ahead, timestamps, timers, reminders, random numbers, dice,
  coin, passwords, UUIDs.
- **System**: memory, CPU usage, load, temperature, battery, disks, inodes,
  swap, GPU, USB and PCI devices, hardware, screen resolution, processes and
  per-program usage, ports and freeing a port, kernel messages, system
  errors, boot and service logs, services (start, stop, restart, status,
  running, failed, enabled at boot, logs, uptime), logins, failed logins,
  sudo rights, locale, keyboard, reboot/shutdown now, in N minutes, at a time
  or tonight, screen lock, "why is my computer slow", the process tree, kill
  by port / all but one / the top CPU process, pausing and resuming a
  program, threads and total memory of a program, swap per process, docker
  space, cleanup and stopping containers.
- **Packages**: install, remove, search, info, owning package of a file,
  files of a package, recently installed, update check, upgrade, cleanup of
  old packages, several packages at once, purge, broken package repair,
  upgrade of everything except the kernel, largest packages.
  `uninstall <software>` (also `purge` or `remove the … package`) searches
  the installed software (system packages, flatpak apps, snaps) and removes
  the nearest match after a `[y/N]`: `uninstall firefx` →
  `sudo apt remove firefox`, `uninstall pinta` →
  `flatpak uninstall com.github.PintaProject.Pinta`, `uninstall node` →
  `nodejs` (the package providing `node`). An inexact match is stated in the
  warning; when nothing installed is close, that is reported instead of a
  guess.
- **Shell**: variables, aliases (saved to `aisharc`), `PATH` additions,
  command descriptions, manuals, repetition every N seconds, timing a
  command, background execution, execution as root, notification on
  completion, `again`.
- **Network**: IPs, gateway, routes, DNS servers, MAC addresses, host
  reachability, ping N times or once, DNS lookup, a TCP port on a host
  ("ping 192.168.20.140 on port 50": ping has no ports, so a TCP connect test
  runs), port scans, traceroute, HTTP headers, weather,
  Wi-Fi networks/name/password, ssh, scp to and from a server, folder sync,
  firewall (blocking or opening a port), active connections, devices on the
  local network, DHCP lease renewal.
- **Network interfaces and radios**, in any word order: interface list,
  details, up or down, link speed; setting, adding or removing an address
  (with netmask, gateway and DNS), DHCP on or off, gateway, DNS, MTU, MAC
  address; Wi-Fi and Bluetooth on or off, airplane mode, radio status;
  connecting to or forgetting a Wi-Fi network, its password, a hotspot.
  Interface names are read from `/sys/class/net`, so "the wifi" and "the
  wired card" resolve to names such as `wlp3s0` and `eno1`. With
  NetworkManager running, changes are made through `nmcli` and persist;
  without it, `ip` is used and changes last until reboot. Every change
  requires `[y/N]`; typed commands (`ip …`, `nmcli …`) are run as typed.

  | Input | Command (NetworkManager) |
  |---|---|
  | `set ip 192.168.20.1/24 to interface eno1` | `nmcli connection modify <eno1's connection> ipv4.method manual ipv4.addresses 192.168.20.1/24 && nmcli connection up …` |
  | `give the wifi interface 10.0.0.5/24 with gateway 10.0.0.1` | the same for `wlp3s0`, plus `ipv4.gateway 10.0.0.1` |
  | `set dhcp off on 192.168.20.1` | the interface holding 192.168.20.1 becomes static at that address |
  | `use dhcp on eno1` | `… ipv4.method auto …` |
  | `bring eno1 down` / `enable eno1` | `nmcli device disconnect eno1` / `nmcli device connect eno1` |
  | `turn wifi off` / `airplane mode on` | `nmcli radio wifi off` / `nmcli radio all off && rfkill block bluetooth` |
- **Git** (inside a repository), in everyday words and any order. Branch,
  remote and tag names are read from the repository, so in "merge dev" the
  word dev is recognised as a branch; names keep the case as typed.
  - *Status and diffs:* what changed, "is my repo clean", anything to commit,
    what is staged, changes in a file, since the last commit, between two
    branches or tags.
  - *Staging and committing:* staging a file / everything / "my changes",
    unstaging, commit (a file, everything, with a message, "save my work as
    …"), amend, rewording the last message, "I forgot app.py in the last
    commit".
  - *Push, pull, fetch:* push, push with tracking, push a branch, force push
    (with lease), push tags; pull, pull with rebase, pull a branch, "get the
    latest", "update my repo from github", fetch, fetch all.
  - *Branches:* current branch, list (local, remote, merged, unmerged), create
    (from a base, with or without switching), switch, switch back, rename,
    delete (force), delete on the remote.
  - *Merge, rebase, cherry-pick:* merge X (into Y), squash merge, "update my
    branch with main", rebase onto X, "put my commits on top of main",
    interactive rebase of the last N, cherry-pick, abort / continue (only
    while one is in progress), conflicts, "keep mine" / "take theirs", mark
    resolved.
  - *Undo and roll back:* undoing the last N commits (with or without keeping
    the changes), reverting a commit or the last N, going back N commits or to
    a commit or tag, viewing an old commit, matching the remote branch,
    discarding changes (all, or in a file), full reset, restoring a file (from
    N commits ago, a branch, a tag), restoring a deleted file, undoing a pull
    or merge.
  - *Stash:* stash (with a message, with new files), list, show, apply, pop,
    drop, clear.
  - *History:* log, graph, last N, by author, own commits, since a time, of a
    file, author of a file or line, message search, the commit that added some
    text, show a commit, author and content of the last commit, unpushed,
    incoming, ahead or behind.
  - *Tags, remotes and more:* list, create (annotated), delete and push tags;
    list, add, rename, remove remotes and change their URL; ignoring a file,
    git user name and email, submodule update, clone, init, removal of
    untracked files, untracking a file.

  Any of these may be prefixed with `git`: `git undo the last commit`,
  `git switch to dev`, `git merge dev into main`, and
  `git commit these "new image"` (a quoted message without `-m`: these, them,
  all or everything commits every change; a file name commits that file).
  Plain words after `git` mark a request; git's own syntax (`git merge dev`,
  `git add .`, `git commit -m "…"`) is run as typed.

  Operations that discard work or rewrite history list what is affected and
  require `[y/N]`. Typed commands (`git pull`, `git commit -m …`) are run as
  typed; `gitpull` and `gti status` are read as `git pull` and `git status`.
  `tests/git_phrases.tsv` holds 335 wordings checked against a real
  repository.
- **Users and desktop**: adding or deleting a user, admin rights, sudo
  members, a user's groups, login-capable users, group membership, password
  change, root shell, user switch, opening a website or app, web search,
  screenshot, volume.
- **Listing parameters**, in any combination and wording: sort by name,
  time, size, extension, version, access, change or creation time, or
  unsorted; reversed / oldest first / newest last / a–z / z–a / ascending /
  descending; long, names only, one per line, columns, comma-separated, full
  timestamps, bytes or KB; hidden files included or only, files only, folders
  only, folders first, type markers. "list all the files in this folder by
  time, oldest first, including hidden" → `ls -lhAtr`; "list files in the order
  of time" and "list files in time order" → `ls -lht`.
- **`ls` output**: one entry per line with only the size (K, M, G), the last
  modified time and the name (no permissions, owner or group); folders first,
  then files, each newest first; in color (folders blue, programs green,
  links cyan; `LS_COLORS` if set). `ls` and `dir` are defined as
  `ls -ogh --group-directories-first -t` without the permissions column, and
  `ll`, `la`, `l` as on Debian; "list files" uses the same format. `ls -1`,
  `ls -C`, `ls -m` still print names only, as does `ls` into a pipe or a file
  (`ls | wc -l`, `$(ls)`), as with plain ls. An explicitly requested sort
  takes precedence (`ls -S`, "by size"); "by name" runs `command ls`,
  bypassing the definition. An `ls` alias or function in `~/.bash_aliases` or
  `aisharc` replaces it; `unset -f ls` disables it.
- **USB drives**: connected drives and devices, free space, mount, unmount,
  eject (power off), format to NTFS / FAT32 / exFAT / ext4 with a label.
  Drives are detected directly and the real device is named in the command.
  Only USB drives are ever touched, never the system disk. With several
  drives connected, the drive is asked for. Before formatting, a warning such
  as "ERASES EVERYTHING on /dev/sdb1 (SanDisk, 28.9G)" is shown.

Wording is normalised before the rules run: politeness ("could you … for me,
thanks", "I'd like to", "help me", "go ahead and"), synonyms, a trailing verb,
missing articles and typos of any known word. `tests/test_robustness.py`
rewrites every tested request in these ways (about 3,900 variants) and
requires at least 97% to still give the right command; the current rate is
97.4%.

Inside aisha, `what can you do` prints examples. `tests/phrases.tsv` lists the
820+ requests checked by the test suite, including requests the rules must
leave to the model.

| Input | Command |
|---|---|
| `find recursively files older that 2 months from this folder` | `find . … -type f -mtime +60 -print` |
| `find logs older than 2 months and move them to archive` | `mkdir -p -- archive && find . … -iname '*.log' -mtime +60 … -exec mv -i -t archive -- {} +` (preview, `[y/N]`) |
| `edit logs.txt` | `sensible-editor logs.txt` (`$VISUAL`/`$EDITOR`, else Debian's `editor`) |
| `edit logs.txt with micro` / `using micro` / `open logs.txt in micro` | `micro logs.txt` (installed with apt first if missing, after confirmation) |
| `edit app.log` (file located in `var/log/`) | `sensible-editor var/log/app.log` |
| `find duplicate files` | `find … -print0 \| xargs -0 -r md5sum \| sort \| uniq -w32 --all-repeated=separate` |
| `rename all .jpeg files to .jpg` | `for f in *.jpeg; do mv -i -- "$f" "${f%.jpeg}.jpg"; done` (preview, `[y/N]`) |
| `what's using all my memory` | `ps aux --sort=-%mem \| head -n 11` |
| `replace "foo bar" with "baz" in all python files` | `find … -iname '*.py' -exec grep -IqiF -e 'foo bar' {} \; -exec sed -i 's/foo bar/baz/g' {} +` (preview, `[y/N]`) |
| `find all files except python files` | `find … -type f -not -iname '*.py' -print` |

On minimal systems, missing tools are replaced by Python's standard library or
`/proc`: zip/unzip → `python3 -m zipfile`, downloads → `urllib`,
`free`/`uptime`/`ss`/`ip`/`cal` → `/proc` or `python3`.

## Shell features

- `cd`, variables (plain and exported, arrays included), `umask`, `shopt`
  options, aliases and functions persist between lines. `~/.bash_aliases`
  and `~/.config/aisha/aisharc` are loaded at start. Traps and `set -o`
  options are not carried over.
- Job control: Ctrl-Z, `jobs`, `fg`, `bg`, `cmd &`, `kill %N`.
- On terminal close or `kill`, the signal is passed to the running command,
  jobs are hung up, the model is stopped and history is saved.
- Tab completion for commands and paths. History is kept in
  `~/.config/aisha/history`.
- `aisha -c '…'`, `aisha script.sh` and scripts on stdin are run in plain
  bash, so aisha is usable as a login shell (`chsh -s /usr/bin/aisha` after
  installation of the Debian package, which registers it in `/etc/shells`).

```sh
aisha                                   # interactive shell
aisha show the 5 newest files here      # one line, then exit
aisha -n delete log files older than 30 days   # print the command, execute nothing
aisha --lines < requests.txt            # several plain-language lines
aisha --doctor                          # check of tools, fallbacks, built-in model and optional LLM
```

Built-in commands: `!cmd` bypasses the rules and runs bash; `?request`
bypasses the rules and queries the LLM; `?` alone right after a failed bash
line asks what was meant; `explain <request>` prints the command
that would run; `learned` / `forget <request>` list and remove remembered
phrases; `llm` checks the model; `help` prints examples.

## Safety

- Commands that delete, move in bulk, rewrite or overwrite files require
  `[y/N]` confirmation, whatever their source (rules, model or memory).
  Deletes, bulk moves and replacements first list every affected file.
- Model commands require `[Y/n]`; those containing `sudo`, `sed -i`,
  `rsync --delete`, `git push --force`/`reset`/`clean`, `> file`, recursive
  `chmod`, `curl | sh`, `kill -9`, or service or package changes require
  `[y/N]`.
- Deletes are never guessed by the rules: "clean up" and "delete everything"
  produce no plan; "the empty file" without a name produces no plan; a named
  file that does not exist produces no plan; "the largest files" without a
  count is passed to the model. Places ("in ~/") are never treated as
  targets, and home, `/` and system folders are never deleted from words.
  Folder deletes keep the starting folder.
- Excluded actions ("find tmp files, don't remove them") are never run; a
  "not" that the rules cannot place sends the request to the model.
- Power words are never passed to bash: `reboot nginx` restarts the nginx
  service (systemd's `reboot` would take the word as an argument and restart
  the computer), `reboot tonight` schedules a reboot, `reboot later` prompts
  for a time. "yes" and "thanks" get a reply instead of running `yes`.
- "Everything except X" keeps X; if X does not exist, nothing is deleted. A
  file name is never written into an archive as text. "To the trash" uses the
  desktop trash (`gio trash`).
- A guess from the "closest things" list that deletes or changes data is
  never listed first, and a guess never reboots or powers off the computer
  unless that was requested.
- Extraction never replaces existing files; copies and backups require
  confirmation before overwriting.
- Names and search terms are always quoted, so text such as `$(…)` in a file
  name is never executed.
- `aisha -n …` and "how do I …" only print the command.

`tests/findings.md` records a bug hunt in which two agents searched for
mishandled requests and a third judged the results. All 109 accepted findings
are fixed and included in `tests/phrases.tsv`.

## Optional language model

Not required; no model is used unless one is set up:

```sh
aisha --setup            # Qwen2.5-Coder 0.5B (0.5 GB) + Mozilla's llamafile server (~45 MB)
aisha --setup 1.5b       # larger model, 1.1 GB
aisha --setup --ollama   # an existing Ollama installation
aisha --setup --url http://127.0.0.1:8080/v1   # any OpenAI-compatible server
aisha --setup --runtime ~/bin/llama-server     # an existing llama.cpp/llamafile binary
aisha --setup off        # no model, ever
aisha --setup remove     # deletion of the downloaded runtime and model
```

The default setup does not require Ollama. A `llama-server` or `llamafile`
already on `PATH` is used; otherwise Mozilla's llamafile (llama.cpp as one
portable file, Apache 2.0) and the model (Apache 2.0) are downloaded from
Hugging Face into `~/.local/share/aisha`. If Hugging Face is unreachable, a
llama.cpp release from GitHub is used instead. The server is started on first
use and stopped when aisha exits. When the rules and the built-in model are
unsure, the model is offered as one more option (`?` at the prompt); its
commands are always shown and confirmed.

Settings are read from `~/.config/aisha/config.json` or the environment:

| Setting | Env var | Default |
|---|---|---|
| `llm` | `AISHA_LLM` | `auto`: a model is used only once one is set up; `off`: never |
| `llm_url` | `AISHA_LLM_URL` | set by `--setup` |
| `llm_model` | `AISHA_LLM_MODEL` | set by `--setup` |
| `llm_server` / `llm_model_file` | `AISHA_LLM_SERVER` / `AISHA_LLM_MODEL_FILE` | set by `--setup` |
| `threshold` | `AISHA_THRESHOLD` | `0.7` (rules below this are "unsure") |
| `confirm` | `AISHA_CONFIRM` | `llm` (`always`, or `destructive` only) |
| `prompt_git` | `AISHA_PROMPT_GIT` | `false` (`true` shows `git:branch` in the prompt) |
| `banner` | `AISHA_BANNER` | `true` (`false` hides the greeting) |
| `fix_hint` | `AISHA_FIX_HINT` | `true` (`false`: no "?" hint after a failed bash line) |

## Installation

```sh
git clone https://github.com/jugih-official/aisha.git
cd aisha
./install.sh
```

On Debian and Ubuntu, `install.sh` builds the Debian package
(`packaging/debian/build-deb.sh` → `dist/aisha_<version>_all.deb`) and
installs it with apt (`/usr/bin/aisha`, `man aisha`, registration as a login
shell). On other systems, or with `./install.sh --local`, aisha is installed
to `/usr/local` without a package. Requirement: Python 3.9+ (Debian 11 or
newer).

Two questions are asked, each only while the item is not yet set up;
otherwise the current state is reported.

- **Language model.** Asked while no model is set up: a small local model
  (Qwen2.5-Coder 0.5B run by llamafile, about 550 MB) for requests unknown to
  the rules, downloaded with `aisha --setup`. An existing model is reported
  instead. `./install.sh --with-llm` installs it without the question
  (`--with-llm 1.5b` or `3b` for a larger model), `--no-llm` skips the
  question, and `aisha --setup` adds a model at any later time.
  `./update.sh` reports both states without asking.
- **aisha in new terminal windows.** For GNOME Terminal (Ubuntu, Linux Mint
  Cinnamon) and Konsole, the profile is changed. For Xfce Terminal (Linux
  Mint Xfce, Xubuntu) and other terminal apps, four lines are added to
  `~/.bashrc` that start aisha in a terminal window; Xfce Terminal keeps its
  settings in memory, so external changes to them do not persist. Logins,
  ssh, text consoles and scripts keep bash in both cases; `AISHA_SKIP=1 bash`
  gives plain bash in one window. Later changes:
  `packaging/terminal-default.sh set`, `unset` or `status`.

`./install.sh --no-ask` skips both questions. For use everywhere, ssh
included, aisha can be set as the login shell: `chsh -s /usr/bin/aisha`
(revert: `chsh -s /bin/bash`).

Update: `./update.sh` in this folder pulls the latest version and reinstalls
aisha in the same way as before (package or `/usr/local`). Removal:
`./uninstall.sh`, with confirmation before settings or a downloaded model are
deleted.

This repository was formerly named `ai-prompt` and also contained the `ai`,
`ai-browser`, `ai-desktop` and `ai-code` CLIs; these were removed in 0.7.1
(last commit containing them: `0c31a02`). `./uninstall.sh` also offers
removal of copies left in `/usr/local/bin`.

## Roadmap

- **Windows.** The rule engine (words → slots) is platform-neutral; the
  command builder and the executor are bash/GNU-specific. A Windows port is
  planned: an additional builder turning the same slots into PowerShell
  (`Get-ChildItem -Recurse -File | Where-Object LastWriteTime -lt …`),
  executed through `pwsh`.

## Tests

`python3 -m unittest discover -s tests`: unit tests, the phrase corpus, a
pty-free shell session, injection checks, and the model runtime against a
stand-in server.

`tests/test_options.py` is the option catalogue: the basic commands (`ls`,
`sort`, `head`, `tail`, `wc`, `grep`, `du`, `df`, `ps`, `cp`, `mv`, `rm`,
`mkdir`, `chmod`, `ping`, port checks, DNS, traceroute, `curl`), each option
asked for in many wordings (1,325 in all). Sort keys are generated in every
form: "by X", "sorted by X", "in X order", "in the order of X", "according to
X". `python3 tests/test_options.py` prints every miss. Words about how to sort
or show (order, sorted, alphabetical, reverse) are never used as file-name
filters; a leftover one lowers confidence, so the request goes to the
suggestions or the language model instead of running the wrong command.

## Disclaimer

ai$ha is alpha software, provided as is, without warranty of any kind (see
[License](#license)). Use is at the user's own risk.

- **Command execution.** Every command printed after `$` is executed by bash
  with the permissions of the current user, and with root permissions when it
  starts with `sudo`. The rules, the built-in model and the optional language
  model can all misinterpret a request. Requests in words that delete,
  overwrite, uninstall, format a drive or rewrite git history require
  `[y/N]` confirmation; other requests run without confirmation, and typed
  commands run as typed, as in bash (see [Safety](#safety)). Each command
  should be read before confirmation, and backups should be kept.
- **Guesses.** `uninstall <name>` removes the *closest* installed match and
  reports it; a typo can match an unintended package.
- **External services.** aisha works offline. A few requests use internet
  services on demand: weather (wttr.in), public IP (ifconfig.me), web search
  (DuckDuckGo, in the browser), connectivity check (deb.debian.org);
  `aisha --setup` downloads from Hugging Face and GitHub. No data is sent
  anywhere else; there is no telemetry.
- **Model licenses.** The default Qwen2.5-Coder 0.5B and the 1.5B model are
  Apache 2.0; llamafile/llama.cpp are Apache 2.0/MIT. The optional **3B**
  model (`--setup 3b`) is under the Qwen Research License, which does not
  permit commercial use. A model is downloaded only on request; none is
  shipped.
- No affiliation with any of the projects or services named here.

## License

[MIT](LICENSE) © 2026 jugih. Use, copying, modification and distribution,
commercial use included, are permitted provided the copyright and license
notice are retained.

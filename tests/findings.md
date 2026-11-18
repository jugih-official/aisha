# aisha bug hunt: official ledger

> Status (aisha 0.7.0): every accepted finding below is fixed. Each phrase, and the judge's paraphrases, is in `tests/phrases.tsv`; the safety items also have tests in `TestFindingsGame` (tests/test_aisha.py).

Judge ruling on rounds A1, B1, A2 and B2. Every finding phrase was re-run with `try-frozen.sh` (frozen aisha, LLM off, dry run in `lab/`); all 116 reproduced as described (a few aisha_today texts differ in detail, noted per row). The read-only correct commands, plus A1-01's delete, were spot-checked on a scratch copy of the fixture.

## Scoreboard

| | A | B |
|---|---|---|
| Accepted findings (after merges) | 52 | 57 |
| of which safety (3 pts each) | 8 → 24 | 16 → 48 |
| other accepted (1 pt each) | 44 → 44 | 41 → 41 |
| Upheld challenges (1 pt each) | 3 (A2-C01, A2-C02, A2-C03) | 3 (B2-C1, B2-C2, B2-C3) |
| Rejected challenges | 1 (A2-C04), 0 pts | 0 |
| Findings rejected by an upheld challenge (−1 each) | 0 | 0 |
| Merged into own earlier entry (0 pts) | 3 (A2-09, A2-16, A2-21) | 4 (B2-01, B1-39, B1-21, B2-09) |
| **Total** | **71** | **92** |

**Verdict: B wins, 92 to 71.** Both players found real, reproducible bugs: no finding was rejected and none was deferred. A was broader (52 accepted entries, strongest on files/text/archives) but most of A's finds are wrong answers to read-only questions. B won on safety: 16 safety items against 8, led by the unconfirmed `reboot <word>` bash passthrough (B1-01) and a run of menus whose first offer is a reboot, poweroff, history rewrite, account change or the wrong kill. A's own top item, `delete everything except report.pdf` → `rm report.pdf` (A1-01), is the single worst file bug. Every challenge was a fair fix of a command, not of a finding, so no −1s: six were upheld (three each) and A2-C04 was rejected. Many items both players marked "DANGEROUS" score 1, not 3, because today aisha does something harmless there (read-only, or a bash line that fails). Their correct commands still carry dangerous=yes.

### How safety was judged

Safety (3 pts) means one of these: **(S1)** aisha's direct plan or bash line would run something destructive, system-changing or wider than asked that the user did not want, whether or not a y/N follows (the prompt confirms what the user believes they asked for); **(S2)** the **first** or only "closest things" offer is destructive or changes system state (deletes data, reboots or powers off, rewrites git history, kills, restarts a service, changes accounts) and does something other than what was asked. A destructive offer ranked #2 or lower (A2-10, B2-02) is accepted at 1 pt with a note. A bash line that fails harmlessly (B1-10, B1-24, B1-27, B2-09) is not safety. Note for the developer: picked menu items do go through needs_care(), but bash lines never do. `>>` appends are in neither RISKY_RE nor DESTRUCTIVE_RE (A2-01).

## Priority: safety

Ordered by severity (unconfirmed or direct first, then first-ranked menu offers).

| # | id | phrase | what aisha does today | correct command | why dangerous |
|---|---|---|---|---|---|
| 1 | B1-01 | reboot nginx | bash `reboot nginx`, unconfirmed: reboots the computer | `sudo systemctl restart nginx` | systemd's reboot takes an optional argument, so the whole machine reboots with no confirmation (bash lines never pass needs_care). |
| 2 | A1-01 | delete everything except report.pdf | rm -- report.pdf (deletes the one file to keep; 'ignored: except') | `find . -mindepth 1 -maxdepth 1 ! -name report.pdf ! -name .git -exec rm -rI -- {} +` | Inverts the request: destroys exactly the file the user said to keep. The y/N names report.pdf, but a user who just said "delete" says yes. |
| 3 | B2-04 | remove README.md from git | rm -- README.md ('ignored: git') | `git rm --cached -- README.md` | Deletes the working file when the user wanted git to stop tracking it; the y/N asks about rm, which the user expects to say yes to. |
| 4 | A2-01 | add notes.txt to backup.zip | printf '%s\n' notes.txt >> backup.zip (unconfirmed) | `zip -j backup.zip run1/notes.txt` | Appends text bytes to a binary zip, corrupting it, with no confirm (>> is neither in RISKY_RE nor DESTRUCTIVE_RE); the file is not added. |
| 5 | B1-04 | restart the network | #1 offer: systemctl reboot | `systemctl is-active --quiet NetworkManager && sudo systemctl restart NetworkManager \|\| sudo systemctl restart networking` | Restart-vs-reboot trap: the top offer reboots the computer. |
| 6 | B2-08 | kill all python processes except 1234 | #1 pkill -- python (kills 1234 too), #2 kill 1234 | `pgrep python \| grep -vxF 1234 \| xargs -r kill` | Both top offers kill exactly the process the user wanted to keep. |
| 7 | B1-09 | update everything except the kernel | apt update && apt upgrade (kernel included; no confirm) | `k=$(dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' 'linux-image-*' \| awk '$1=="ii"{print $2}'); sudo apt-mark hold $k && sudo apt update && sudo apt upgrade; sudo apt-mark unhold $k` | The explicit exclusion is silently dropped, so the system change the user ruled out happens. |
| 8 | A1-03 | move the oldest log to archive | moves EVERY .log into archive/ ('oldest' top-1 dropped) | `f=$(find . -path ./.git -prune -o -type f -name '*.log' -printf '%T@\t%p\n' \| sort -n \| head -n 1 \| cut -f2-); [ -n "$f" ] && mkdir -p archive && mv -i -- "$f" archive/` | Bulk move of every log file (including live app logs such as var/log/app.log) when one was asked; the confirm shows a find command, not the file list. |
| 9 | B2-07 | stop all docker containers | only offer: sudo usermod -aG docker "$USER" | `docker ps -q \| xargs -r docker stop` | The offer grants docker group membership (root-equivalent) instead of stopping anything. |
| 10 | A2-03 | create a password protected zip of report.pdf | zip -r report.pdf.zip report.pdf (no encryption) | `zip -e report.zip report.pdf` | Security trap: encryption silently dropped; the user believes the archive is protected and may share it. |
| 11 | B1-14 | undo my last git pull | only offer: git reset --soft HEAD~1 | `git reset --keep ORIG_HEAD` | Undoes one commit, not the pull (a pull can bring many commits or a merge), leaving a half-undone history. |
| 12 | B1-13 | revert the last commit | only offer: git reset --soft HEAD~1 | `git revert --no-edit HEAD` | The offered reset rewrites history; on pushed work it forces a force-push. |
| 13 | A2-02 | change all tabs to spaces in run.sh | sed -i s/tabs/spaces/g -- run.sh | `sed -i 's/\t/    /g' -- run.sh` | In-place edit of a script that replaces the literal word 'tabs', not tab characters. |
| 14 | A2-08 | remove blank lines from logs.txt | only offer: sort -u -o logs.txt -- logs.txt | `sed -i '/^[[:space:]]*$/d' -- logs.txt` | The only offer reorders and de-duplicates the file in place; for a "clean up lines" request it is a plausible pick. |
| 15 | A1-30 | remove execute permission from run.sh | #1 offer: sort -u -o run.sh -- run.sh | `chmod -x -- run.sh` | Top suggestion for a harmless chmod sorts and de-duplicates the script in place, destroying it. |
| 16 | A2-05 | extract only README.md from data.tar.gz | only offer: sort -u -o README.md -- README.md | `tar --keep-old-files -xzf data.tar.gz README.md` | The only offer rewrites README.md in place. 'get README.md out of data.tar.gz' only offers deleting all *.bak files. |
| 17 | B1-28 | delete user bob | #1 offer: sudo adduser bob | `sudo deluser bob` | The top offer does the opposite and creates an account. |
| 18 | B1-03 | why is my computer slow | #1 offer: systemctl reboot (#3 poweroff) | `uptime; free -h; ps aux --sort=-%cpu \| head -n 6; ps aux --sort=-%mem \| head -n 6` | The top offer for a question reboots the machine (unsaved work, remote sessions). |
| 19 | B2-10 | kill the process using the most cpu | only offer: pkill -- sleep | `pid=$(ps -eo pid --sort=-%cpu --no-headers \| head -n 1 \| tr -d ' '); ps -o pid,comm,%cpu -p "$pid"; kill "$pid"` | The only offer kills an unrelated program. |
| 20 | B1-12 | show the last commit | #1 offer: git reset --soft HEAD~1 | `git show --stat HEAD` | The top offer for a read-only question un-commits (rewrites history). |
| 21 | B2-16 | nginx status | only offer: systemctl restart nginx | `systemctl status nginx --no-pager` | The only offer restarts a live service for a read-only question. |
| 22 | B2-18 | remove nginx completely | only offer: systemctl restart nginx | `sudo apt purge nginx && sudo apt autoremove` | The only offer restarts the service. 'uninstall nginx completely' offers apt remove htop (wrong package). |
| 23 | B2-06 | clean up docker | only offer: delete *.tmp/*.temp/*.swp here | `docker system prune` | Deletes files in the current folder (.swp = editor recovery data) instead of docker data. |
| 24 | B2-05 | remove untracked files | #1 delete all *.pyc, #2 delete empty folders | `git clean -fd` | Both offers are unrelated -delete commands (low-value data, but destructive and off-target). |

Cross-cutting fixes these point to: (1) confirm any bash line that matches RISKY_RE and route `reboot|shutdown <words>` to the rules; (2) never rank a destructive or power command first in the "closest things" menu unless the request has the same verb **and** object (this would also defuse A1-30/A2-05/A2-08 `sort -u -o`, B1-12/13/14 `git reset --soft`, B1-03/04/39 reboot and poweroff, B2-16/18 restart); (3) "except / but not / all but / keep" must become an exclusion, never the target (A1-01, A1-02, A1-11, A1-17, A2-10, B1-09, B2-08).

## Accepted findings by area

Safety items are marked **S**. "Paraphrases" are extra test-corpus phrases that should give the same command.

### files (20)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| A1-01 **S** | delete everything except report.pdf | rm -- report.pdf (deletes the one file to keep; 'ignored: except') | `find . -mindepth 1 -maxdepth 1 ! -name report.pdf ! -name .git -exec rm -rI -- {} +` | yes | Judge fix (B2-C3 upheld): A's -type f left the folders; "everything" includes folders. Same bug: 'remove all .tmp files except old.tmp' best guess = delete old.tmp (want find . -type f -name '*.tmp' ! -name old.tmp -delete). | remove everything except report.pdf / get rid of everything but report.pdf |
| A1-02 | copy everything except backup.zip to /tmp/x | exclusion becomes -not -iname '*qlit0*' (placeholder leak); backup.zip is copied too | `mkdir -p -- /tmp/x && find . -path ./.git -prune -o -type f ! -name backup.zip -exec cp -i -t /tmp/x -- {} +` | no | Root cause: the qlitN placeholder for a quoted/path token is never mapped back. Also 'list everything except backup.zip'. The same leak shows in the rationale of B1-08 ('ignored: qlit0') and A2-19. | copy all files but backup.zip to /tmp/x / copy everything apart from backup.zip into /tmp/x |
| A1-03 **S** | move the oldest log to archive | moves EVERY .log into archive/ ('oldest' top-1 dropped) | `f=$(find . -path ./.git -prune -o -type f -name '*.log' -printf '%T@\t%p\n' \| sort -n \| head -n 1 \| cut -f2-); [ -n "$f" ] && mkdir -p archive && mv -i -- "$f" archive/` | no | Judge: added the empty-result guard. Superlative + move/copy/delete must keep head -n 1. | move the oldest .log file into archive / put the oldest log file in the archive folder |
| A1-05 | biggest folder | find -type d -printf %s (inode size, always 4096: arbitrary) | `du -sh -- */ 2>/dev/null \| sort -hr \| head -n 1` | no | Judge fix: human-readable du -sh + sort -h. 'largest 3 folders' = head -n 3. | which folder is the largest / what folder takes the most space |
| A1-09 | second newest file | none | `find . -path ./.git -prune -o -type f -printf '%T@\t%p\n' \| sort -nr \| sed -n 2p \| cut -f2-` | no | Ordinals (second/third/2nd) unsupported; 'second biggest file' = same with %s. | 2nd newest file / second most recently modified file |
| A1-10 | files I edited yesterday afternoon | none | `d=$(date -d yesterday +%F); find . -path ./.git -prune -o -type f -newermt "$d 12:00" ! -newermt "$d 18:00" -print` | no | Part of day: morning 00-12, afternoon 12-18, evening 18-24. 'files modified this morning' also fails. | files modified yesterday afternoon / what did I change yesterday afternoon |
| A1-11 | delete all but the newest 3 files | only offer: list files older than 30 days (harmless, unrelated) | `find . -maxdepth 1 -mindepth 1 -type f -printf '%T@\t%p\n' \| sort -nr \| tail -n +4 \| cut -f2- \| xargs -r -d '\n' rm -v --` | yes | Judge fix (B2-C1 upheld): xargs gives rm /dev/null as stdin, so A's rm -i deletes nothing; rely on aisha's y/N with the file list shown. Not safety: today's offer is read-only. | keep only the 3 newest files / delete everything except the 3 most recent files |
| A1-13 | empty the log file | finds empty .log files (read-only) | `truncate -s 0 -- var/log/app.log` | yes | 'empty' is a verb here. The only *.log is var/log/app.log; with several, ask which. 'truncate var/log/app.log' goes to bash and fails (missing -s). Not safety: today read-only. | clear the contents of var/log/app.log / truncate app.log to zero |
| A1-14 | move everything from run1 to here | best guess mv -i -- 'everything from run1' . | `find run1 -mindepth 1 -maxdepth 1 -exec mv -i -t . -- {} +` | no |  | move all files out of run1 into this folder / move run1's contents up here |
| A1-15 | what folder am i in | lists every subfolder | `pwd` | no |  | where am i / which directory am i in |
| A1-16 | list files in run1 and src | ls -lh -- src (run1 silently dropped) | `ls -lh -- run1 src` | no |  | show what's in run1 and src / list run1 and src |
| A1-17 | list all files but not the hidden ones | name filter *hidden* and 'including hidden' (opposite) | `find . -maxdepth 1 -mindepth 1 -type f ! -name '.*'` | no |  | list files without the hidden files / show files excluding hidden ones |
| A1-18 | find files with spaces in the name | searches folder 'name' for content 'spac' | `find . -path ./.git -prune -o -type f -name '* *' -print` | no |  | which files have a space in their name / find filenames containing spaces |
| A1-22 | files newer than report.pdf | offer: files older than a year | `find . -path ./.git -prune -o -type f -newer report.pdf -print` | no | 'files older than data.json' even offers mkdir data.json + mv; want find . -type f ! -newer data.json. | files modified after report.pdf / which files changed since report.pdf |
| A1-31 | size of report.pdf in bytes | du -sh report.pdf (4.0K disk usage; 'ignored: bytes') | `stat -c %s -- report.pdf` | no |  | how many bytes is report.pdf / exact size of report.pdf |
| A1-32 | files modified before 2024 | offer: modified in the last 2024 minutes | `find . -path ./.git -prune -o -type f ! -newermt 2024-01-01 -print` | no | Absolute years/months unsupported: 'files modified in march' = find . -type f -newermt 2026-03-01 ! -newermt 2026-04-01. | files older than 2024 / files last changed before january 2024 |
| A1-34 | full path of report.pdf | offers echo $PATH / df | `realpath -- report.pdf` | no | Also extension / name-without-extension questions only get 'count files by extension'. | absolute path of report.pdf / where exactly is report.pdf |
| A2-04 | move all pdfs older than a week to the trash | mkdir ./trash and mv into it | `find . -path ./.git -prune -o -type f -iname '*.pdf' -mtime +7 -exec gio trash -- {} +` | yes | 'move report.pdf to the trash' already uses gio trash (libglib2.0-bin). | trash pdfs older than 7 days / put week-old pdf files in the trash |
| A2-10 | remove all files in run1 but keep the folder | #2 offer: rm -r -- run1 (the excluded outcome) | `find run1 -mindepth 1 -delete` | yes | Not scored as safety: the rm -r offer is #2, #1 is ls. 'delete everything in run1' gives the same offer. | empty the run1 folder / delete everything inside run1 |
| A2-14 | how many files of each type in run1 | counts the whole tree ('ignored: run1') | `find run1 -type f -name '*.*' \| sed 's/.*\.//' \| sort \| uniq -c \| sort -rn` | no |  | count files by extension in run1 / file types in run1 and how many of each |

### text (20)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| A1-06 | how many lines does each txt file have | one grand total (xargs cat \| wc -l) | `find . -path ./.git -prune -o -type f -name '*.txt' -exec wc -l {} +` | no | 'each'/'per file' dropped (rationale says 'ignored: per'). | line count per txt file / count the lines in every txt file separately |
| A1-07 | encode report.pdf in base64 | base64 of the string 'report.pdf' | `base64 -- report.pdf` | no | Merged A2-09 ('convert logs.txt to lowercase' → tr '[:upper:]' '[:lower:]' < logs.txt). Root cause: an existing file argument is treated as literal text. | base64 encode report.pdf / convert report.pdf to base64 |
| A1-08 | lines in logs.txt that don't contain error | only offer: grep -niF error (the opposite) | `grep -viF -- error logs.txt` | no | Negation lost. Related: 'grep error but not warning in logs.txt' = grep -i error logs.txt \| grep -vi warning. | show lines in logs.txt without error / lines of logs.txt not containing error |
| A1-12 | top 10 lines in logs.txt by frequency | head -n 10 logs.txt ('ignored: frequency') | `sort logs.txt \| uniq -c \| sort -rn \| head -n 10` | no | Related: 'most common words in README.md' = tr -cs '[:alnum:]' '\n' < README.md \| tr A-Z a-z \| sort \| uniq -c \| sort -rn \| head. | most common lines in logs.txt / which lines repeat most in logs.txt |
| A1-21 | find files containing both error and warning | 'both' required as a third word | `grep -rlIi --exclude-dir=.git -- error . \| xargs -r -d '\n' grep -lIi -- warning` | no |  | files that contain error and warning / which files mention both error and warning |
| A1-23 | show the 3rd column of people.csv | offer: cat people.csv | `cut -d, -f3 people.csv` | no | Naive split (no quoted commas). Related: column count (head -n 1 people.csv \| tr ',' '\n' \| wc -l), column sum (awk -F, 'NR>1{s+=$2} END{print s}'). | print column 3 of people.csv / third field of people.csv |
| A1-24 | sort people.csv by the second column | offer: sort -- people.csv (column ignored, header moved) | `(head -n 1 people.csv; tail -n +2 people.csv \| sort -t, -k2,2)` | no | Use -k2,2n when the column is numeric. 'sort logs.txt in reverse order' also only suggests. | sort people.csv by column 2 / order people.csv by the second field |
| A1-25 | show the keys in data.json | cat data.json ('ignored: keys') | `python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(*(d.keys() if isinstance(d,dict) else range(len(d))), sep="\n")' data.json` | no | jq keys data.json when jq is installed. Related: 'show the header of people.csv' = head -n 1 people.csv. | list the top-level keys of data.json / what keys does data.json have |
| A1-26 | convert people.csv to json | here: bash `convert people.csv to json` (ImageMagick, errors out); stock Debian: offers uppercasing the string 'people.csv' | `python3 -c 'import csv,json,sys; print(json.dumps(list(csv.DictReader(open(sys.argv[1]))), indent=2))' people.csv` | no | B2-C2 upheld on the facts: without ImageMagick the only offer is 'convert "people.csv" to uppercase' (judge re-ran with convert removed from PATH); ImageMagick writes no 'json' file. Finding stands. | turn people.csv into json / people.csv as json |
| A1-28 | replace all occurrences of error with ERROR in every txt file | offer: which txt files contain error (read-only) | `find . -path ./.git -prune -o -type f -name '*.txt' -exec sed -i 's/error/ERROR/g' -- {} +` | yes | In-place edit: must confirm. Single-file replace already works. | change error to ERROR in all txt files / replace error with ERROR in all .txt files |
| A1-33 | check if data.json is valid json | offers apt upgradable / internet check / cat | `python3 -m json.tool data.json > /dev/null && echo valid` | no | json.tool prints the parse error itself when invalid. | is data.json valid json / validate data.json |
| A2-02 **S** | change all tabs to spaces in run.sh | sed -i s/tabs/spaces/g -- run.sh | `sed -i 's/\t/    /g' -- run.sh` | yes | Map tabs→\t (or expand -t 4 into a temp file). | convert tabs to spaces in run.sh / replace tabs with spaces in run.sh |
| A2-06 | delete line 3 from logs.txt | sed -n '3p' (prints it; 'ignored: delete') | `sed -i '3d' -- logs.txt` | yes | Not safety: today read-only. | remove line 3 of logs.txt / delete the third line in logs.txt |
| A2-07 | delete the first line of people.csv | grep -r for the text 'people.csv' | `sed -i '1d' -- people.csv` | yes |  | remove the header line from people.csv / drop the first line of people.csv |
| A2-08 **S** | remove blank lines from logs.txt | only offer: sort -u -o logs.txt -- logs.txt | `sed -i '/^[[:space:]]*$/d' -- logs.txt` | yes |  | delete empty lines in logs.txt / strip blank lines from logs.txt |
| A2-11 | show lines containing error in logs.txt with 2 lines of context | name/content search for 'logs.txt', '2', 'context' | `grep -niF -C 2 -- error logs.txt` | no | -A/-B for 'after'/'before'. | grep error in logs.txt with 2 lines before and after / show error lines in logs.txt plus 2 lines around them |
| A2-12 | count lines matching error in each file | grep -rn: every matching line | `grep -rcIi --exclude-dir=.git -- error . \| grep -v ':0$'` | no |  | how many lines mention error in each file / count error lines per file |
| A2-13 | which file has the most lines | name/content search for 'most', 'line' | `find . -path ./.git -prune -o -type f -exec wc -l {} + \| grep -v ' total$' \| sort -nr \| head -n 1` | no | Related: 'longest line in logs.txt' = awk '{ if (length > m) { m = length; l = $0 } } END { print m": "l }' logs.txt. | longest file by line count / which file here has the most lines in it |
| A2-19 | search for error case sensitive in logs.txt | best guess: name/content search; file leaks as 'qlit0' | `grep -nF -- error logs.txt` | no | aisha always adds -i. Related: 'find the exact word error in logs.txt' = grep -nw -- error logs.txt. The qlit0 leak is A1-02's root cause. | case-sensitive search for error in logs.txt / grep error in logs.txt matching case |
| A2-20 | write hello to logs.txt | offer: overwrite logs.txt with 'hello world' | `printf '%s\n' hello > logs.txt` | yes | Not safety: the user asked to write to the file; only the text is wrong. Unquoted text for write/append/insert: 'add hello to the end of logs.txt' (>>), 'insert hello at line 3 of logs.txt' (sed -i '3i hello'). | overwrite logs.txt with hello / write the word hello into logs.txt |

### archives (7)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| A1-04 | zip all the pdfs | lists .zip and .pdf files ('zip' read as a type) | `zip pdfs.zip -- *.pdf` | no | Package zip; base fallback tar -czf pdfs.tar.gz -- *.pdf. | make a zip of all the pdf files / put all the pdfs in a zip |
| A1-27 | compress each file in run1 | one tarball of run1 | `gzip -k -- run1/*` | no | 'zip every csv file separately' = for f in *.csv; do gzip -k -- "$f"; done. | gzip every file in run1 separately / compress the files in run1 one by one |
| A2-01 **S** | add notes.txt to backup.zip | printf '%s\n' notes.txt >> backup.zip (unconfirmed) | `zip -j backup.zip run1/notes.txt` | yes | Base fallback: python3 -c 'import zipfile,sys; zipfile.ZipFile(sys.argv[1],"a").write(sys.argv[2],"notes.txt")' backup.zip run1/notes.txt. | put notes.txt into backup.zip / add run1/notes.txt to the zip backup.zip |
| A2-03 **S** | create a password protected zip of report.pdf | zip -r report.pdf.zip report.pdf (no encryption) | `zip -e report.zip report.pdf` | no | Alternative: gpg -c report.pdf (gnupg). | zip report.pdf with a password / make an encrypted zip of report.pdf |
| A2-05 **S** | extract only README.md from data.tar.gz | only offer: sort -u -o README.md -- README.md | `tar --keep-old-files -xzf data.tar.gz README.md` | no |  | get README.md out of data.tar.gz / unpack just README.md from data.tar.gz |
| A2-17 | test if backup.zip is corrupted | none | `python3 -m zipfile -t backup.zip` | no | unzip -t backup.zip if unzip is installed. Related: 'decompress logs.txt.gz' (gunzip -k --), 'how big is data.tar.gz uncompressed' (gzip -l). | check backup.zip for errors / is backup.zip ok |
| A2-18 | extract data.tar.gz and delete it | tar --keep-old-files -xf (second step dropped silently) | `tar --keep-old-files -xf data.tar.gz && rm -i -- data.tar.gz` | yes | 'X and Y' chains cut without an 'ignored' note. Not safety: today does less, not more. | unpack data.tar.gz then remove the archive / extract data.tar.gz and remove it afterwards |

### permissions (5)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| A1-19 | find world writable files | name/content search for 'world', 'writabl' | `find . -path ./.git -prune -o -type f -perm -0002 -print` | no | Merged A2-16 ('find files with 777 permissions' → find . -path ./.git -prune -o -type f -perm 0777 -print). Root cause: permission criteria parsed as name/content words. | find files anyone can write to / files writable by everyone |
| A1-20 | find files i can't read | text search for 'cannot', 'read' | `find . -path ./.git -prune -o ! -readable -print` | no |  | which files am i not allowed to read / find unreadable files |
| A1-29 | make run.sh readable only by me | offers touch / chmod +x / create+open | `chmod go-rwx -- run.sh` | no | Related: 'give everyone write access to logs.txt' = chmod a+w -- logs.txt (dangerous: widens access). | make run.sh private / only i should be able to read run.sh |
| A1-30 **S** | remove execute permission from run.sh | #1 offer: sort -u -o run.sh -- run.sh | `chmod -x -- run.sh` | no | Systemic: 'remove duplicate lines from X' (sort -u -o) over-ranks for any 'remove ... from FILE' (also A2-05, A2-08). | make run.sh not executable / take away the execute bit on run.sh |
| A2-15 | find .sh files that are not executable | offers the opposite (executable files) | `find . -path ./.git -prune -o -type f -name '*.sh' ! -executable -print` | no | Merged A2-21 ('find files not owned by me' → find . -path ./.git -prune -o ! -user "$USER" -print). Root cause: a negation before a known find predicate is dropped. | which shell scripts are missing the execute bit / find non-executable .sh files |

### processes (9)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| B1-02 | kill the app on port 3000 | only lists what listens on 3000 | `pids=$(ss -ltnpH 'sport = :3000' \| grep -o 'pid=[0-9]*' \| cut -d= -f2 \| sort -u); [ -n "$pids" ] && kill $pids \|\| echo 'nothing is using port 3000'` | yes | Not safety: today read-only. ss -p shows other users' processes only with sudo. | kill the thing on port 3000 / free up port 3000 |
| B1-23 | show the process tree | file search | `ps -ef --forest` | no | 'show zombie processes' also a file search (ps -eo pid,ppid,stat,cmd \| awk '$3 ~ /^Z/'). | process tree / show processes as a tree |
| B1-24 | kill -9 firefox | bash `kill -9 firefox` (fails: needs PIDs) | `pkill -9 -- firefox` | yes | Not safety: fails harmlessly. 'force kill chrome' gives pkill (TERM, 'force' ignored; want -KILL). | force kill firefox / kill firefox with signal 9 |
| B1-25 | how many threads does firefox have | nproc ('ignored: firefox') | `ps -o pid,nlwp,cmd -C firefox-esr,firefox` | no | Judge fix (A2-C02 upheld): the Debian browser process is firefox-esr. Aisha's own 'how much memory is firefox using' (ps -C firefox) has the same flaw. | thread count of firefox / how many threads is firefox running |
| B1-37 | how much ram does chrome use in total | per-process list in KiB ('ignored: total') | `ps -C chrome,chromium -o rss= \| awk '{s+=$1} END {printf "%.0f MiB\n", s/1024}'` | no | Judge fix: the Debian package is chromium (process chromium); Google Chrome is chrome. | total memory used by chrome / how much memory is chrome using altogether |
| B2-08 **S** | kill all python processes except 1234 | #1 pkill -- python (kills 1234 too), #2 kill 1234 | `pgrep python \| grep -vxF 1234 \| xargs -r kill` | yes | Judge fix: pipeline instead of a loop. Merged B2-09 ('kill python but not jupyter': bash, fails; want pgrep -a python \| grep -v jupyter \| cut -d' ' -f1 \| xargs -r kill). Root cause: no exclusion for process kills. | kill every python process but 1234 / stop all python processes except pid 1234 |
| B2-10 **S** | kill the process using the most cpu | only offer: pkill -- sleep | `pid=$(ps -eo pid --sort=-%cpu --no-headers \| head -n 1 \| tr -d ' '); ps -o pid,comm,%cpu -p "$pid"; kill "$pid"` | yes | Most memory: --sort=-%mem; 'kill the oldest python process' = pkill -o python. | kill the top cpu process / kill whatever is eating my cpu |
| B2-11 | pause firefox | offer: firefox memory | `pkill -STOP -- firefox` | no | 'resume firefox' = pkill -CONT -- firefox. | freeze firefox / pause the firefox process |
| B2-14 | what's using my swap | swap totals only ('ignored: using') | `for f in /proc/[0-9]*/status; do awk '/^Name:/{n=$2} /^VmSwap:/{if($2>0) print $2" kB", n}' "$f" 2>/dev/null; done \| sort -nr \| head` | no | Judge: 2>/dev/null for processes that exit mid-loop. | which processes use swap / swap usage per process |

### services (10)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| B1-01 **S** | reboot nginx | bash `reboot nginx`, unconfirmed: reboots the computer | `sudo systemctl restart nginx` | yes | Merged B2-01 ('reboot tonight', also 'reboot later' → immediate reboot; want sudo shutdown -r 23:00). Fix: send 'reboot <words>' to the rules and confirm bash lines that match RISKY_RE. | reboot the nginx server / bounce nginx |
| B1-04 **S** | restart the network | #1 offer: systemctl reboot | `systemctl is-active --quiet NetworkManager && sudo systemctl restart NetworkManager \|\| sudo systemctl restart networking` | yes | Judge fix: one line that picks the active network manager. Merged B1-39 ('shut down nginx': #1 offer systemctl poweroff; want sudo systemctl stop nginx; 'shut down apache' same). Root cause: power verb + non-computer object ranks the computer power action first. | restart networking / restart my wifi |
| B1-19 | show logs since yesterday 3pm | offers cat logs.txt / find *.log *3pm* | `journalctl --since 'yesterday 15:00' --no-pager` | no | Also 'system logs from the last 30 minutes' (--since '30 min ago'), 'logs from the previous boot' (journalctl -b -1). | system logs since 3pm yesterday / show the journal since yesterday 15:00 |
| B1-20 | show sshd logs | find *.log named *sshd* here | `journalctl -u ssh -n 50 --no-pager` | no | Merged B1-21 ('follow nginx logs' → tail -f logs.txt; want journalctl -u nginx -f). Root cause: '<service> logs' is not routed to journalctl -u; map sshd→ssh. | ssh logs / show logs for sshd |
| B1-26 | uptime of nginx | uptime (the computer's) | `systemctl show nginx -p ActiveEnterTimestamp --value` | no |  | how long has nginx been running / since when is nginx up |
| B1-31 | is ssh enabled at boot | offer: pgrep -a ssh | `systemctl is-enabled ssh` | no | 'enable ssh on startup' = sudo systemctl enable --now ssh (dangerous). | does ssh start at boot / is ssh enabled on startup |
| B2-06 **S** | clean up docker | only offer: delete *.tmp/*.temp/*.swp here | `docker system prune` | yes | Add -a --volumes only if asked. | prune docker / free up docker space |
| B2-07 **S** | stop all docker containers | only offer: sudo usermod -aG docker "$USER" | `docker ps -q \| xargs -r docker stop` | yes | Judge fix: xargs -r so nothing fails when no container runs. | stop every running container / docker stop all |
| B2-12 | list services that start at boot | file search in a non-existent folder 'boot' | `systemctl list-unit-files --type=service --state=enabled` | no |  | which services are enabled / what starts at boot |
| B2-16 **S** | nginx status | only offer: systemctl restart nginx | `systemctl status nginx --no-pager` | no | Also 'why did nginx fail' (status + journalctl -u nginx -b -n 50 --no-pager). | is nginx ok / nginx service status |

### packages (6)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| B1-09 **S** | update everything except the kernel | apt update && apt upgrade (kernel included; no confirm) | `k=$(dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' 'linux-image-*' \| awk '$1=="ii"{print $2}'); sudo apt-mark hold $k && sudo apt update && sudo apt upgrade; sudo apt-mark unhold $k` | yes | Judge fix: hold only installed (ii) packages and unhold in the same line. Note aisha's own line also lacks sudo. | upgrade all packages but not the kernel / update the system without the kernel |
| B1-10 | install vlc and gimp | bash coreutils `install vlc and gimp` (fails: cannot stat 'vlc') | `sudo apt install vlc gimp` | yes | Not safety: the coreutils call fails harmlessly. Also 'install vlc, gimp and htop'. | install both vlc and gimp / get vlc and gimp |
| B1-35 | which packages take the most space | du of the current folder ('ignored: packages') | `dpkg-query -W -f='${Installed-Size}\t${Package}\n' \| sort -nr \| head -n 15` | no | Sizes in KiB. | biggest installed packages / what packages use the most disk space |
| B1-36 | fix broken packages | offer: find broken symlinks | `sudo dpkg --configure -a && sudo apt --fix-broken install` | yes | Related gaps: reinstall (apt install --reinstall), only-upgrade, apt-mark showmanual. | repair broken apt packages / apt is broken, fix it |
| B2-17 | purge nginx | apt remove nginx (config kept; no sudo) | `sudo apt purge nginx` | yes | The UNINSTALL table maps purge to remove. | purge the nginx package / uninstall nginx and delete its config |
| B2-18 **S** | remove nginx completely | only offer: systemctl restart nginx | `sudo apt purge nginx && sudo apt autoremove` | yes | 'remove vlc' offers only file deletions. | uninstall nginx completely / get rid of nginx entirely |

### network (4)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| B1-11 | block port 22 | lists the listener on 22 | `sudo ufw deny 22/tcp` | yes | ufw package (nft fallback). The confirm must warn: blocking 22 over SSH locks you out. Also 'open port 8080 in the firewall' (ufw allow 8080/tcp). | close port 22 in the firewall / deny port 22 |
| B1-34 | who is using my wifi | offers whoami / ps | `ip neigh show` | no | Label honestly: devices this computer has seen; only the router's client list is authoritative. nmap -sn <subnet> if nmap is installed. | who is connected to my network / what devices are on my network |
| B1-40 | show active connections | file search | `ss -tunp state established` | no | -p needs sudo for other users' processes. | list open network connections / what connections are active |
| B2-13 | renew my ip | hostname -I ('ignored: renew') | `dev=$(ip route show default \| awk '{print $5; exit}'); sudo nmcli device disconnect "$dev" && sudo nmcli device connect "$dev"` | yes | Judge fix: NetworkManager form (Debian desktop default). ifupdown servers: sudo ifdown "$dev" && sudo ifup "$dev" (DHCP client varies by release). Drops the link briefly; dangerous over SSH. | get a new ip address / renew my dhcp lease |

### users (6)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| B1-05 | who has sudo | bash `who has sudo` prints your own login line | `getent group sudo` | no |  | which users are admins / who can use sudo |
| B1-06 | what groups is bob in | groups (yours; 'ignored: bob') | `id -nG bob` | no |  | show bob's groups / which groups does bob belong to |
| B1-22 | failed login attempts | none | `journalctl -u ssh --no-pager \| grep -iE 'failed\|invalid' \| tail -n 30` | no | Judge fix (A2-C01 upheld): Debian 13's OpenSSH 10 logs auth failures from sshd-session, so _COMM=sshd misses them; -u ssh catches both. Needs sudo or the adm group. | show failed ssh logins / who tried to log in and failed |
| B1-27 | make bob an admin | bash `make bob an admin` (No rule to make target, harmless) | `sudo usermod -aG sudo bob` | yes | Not safety: make stops at the first unknown target. 'give bob sudo rights' only offers adduser. | give bob sudo rights / add bob to the sudo group |
| B1-28 **S** | delete user bob | #1 offer: sudo adduser bob | `sudo deluser bob` | yes | Also 'remove bob from the docker group' offers adding ME (want sudo gpasswd -d bob docker). | remove the user bob / delete bob's account |
| B1-29 | which users can log in | cut -d: -f1 /etc/passwd (every system account) | `getent passwd \| awk -F: '$7 !~ /(nologin\|false\|sync)$/ {print $1}'` | no | Judge fix (A2-C03 upheld): exclude /bin/sync; getent also covers LDAP/SSSD. 'list all human users' = uid 1000..65533. | list users that can log in / which accounts have a login shell |

### git (10)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| B1-12 **S** | show the last commit | #1 offer: git reset --soft HEAD~1 | `git show --stat HEAD` | no | 'show the last commit diff' = git show HEAD. | what changed in the last commit / show me the latest commit |
| B1-13 **S** | revert the last commit | only offer: git reset --soft HEAD~1 | `git revert --no-edit HEAD` | yes |  | git revert the last commit / make a commit that undoes the last one |
| B1-14 **S** | undo my last git pull | only offer: git reset --soft HEAD~1 | `git reset --keep ORIG_HEAD` | yes | ORIG_HEAD is only right immediately after the pull. | undo git pull / go back to before the last pull |
| B1-15 | squash the last 3 commits | git log -n 3 ('ignored: squash') | `git reset --soft HEAD~3 && git commit` | yes |  | squash my last 3 commits into one / combine the last three commits |
| B1-16 | who wrote line 10 of README.md | sed -n '10p' ('ignored: wrote') | `git blame -L 10,10 -- README.md` | no |  | who changed line 10 in README.md / blame line 10 of README.md |
| B1-17 | last 3 commits please | bash `last 3 commits` (login history) | `git log --oneline -n 3` | no |  | last 3 commits / my last three commits |
| B1-18 | delete the branch feature-x | only offer: git switch -c feature-x (opposite, harmless) | `git branch -d feature-x` | yes | Not safety: the offer creates, it does not destroy. 'rename branch dev to develop' best guess is mv (want git branch -m dev develop). | remove branch feature-x / delete the local branch feature-x |
| B2-04 **S** | remove README.md from git | rm -- README.md ('ignored: git') | `git rm --cached -- README.md` | yes | 'stop tracking README.md' = none. | stop tracking README.md / untrack README.md in git |
| B2-05 **S** | remove untracked files | #1 delete all *.pyc, #2 delete empty folders | `git clean -fd` | yes | aisha's confirm should show git clean -nd output first. 'clean the repo' offers temp-file deletion. | clean the repo / delete untracked files in git |
| B2-19 | undo git add | offer: command -v git | `git restore --staged -- .` | no | Index only; working files untouched (aisha still confirms git restore). | unstage everything / unstage all files |

### dates/time (3)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| B1-33 | time in tokyo | bash `time in tokyo` | `TZ=Asia/Tokyo date` | no |  | tokyo time / current time in tokyo |
| B1-38 | what's the date next friday | offers ls -lht / date | `date -d 'next friday' '+%A %d %B %Y'` | no | Also 'date in 3 weeks' (offers +3 days), weekday of a date, days until christmas. | what date is next friday / when is next friday |
| B2-15 | convert 1700000000000 to a date | here bash `convert ...`; stock Debian: uppercase-the-string offer | `date -d @$((1700000000000/1000))` | no | 13-digit millisecond epochs; 10 digits already work. | what date is 1700000000000 / 1700000000000 milliseconds to a date |

### system info (7)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| B1-03 **S** | why is my computer slow | #1 offer: systemctl reboot (#3 poweroff) | `uptime; free -h; ps aux --sort=-%cpu \| head -n 6; ps aux --sort=-%mem \| head -n 6` | no |  | what's slowing down my computer / my pc is really slow, why |
| B1-07 | how much space does docker use | du -sh . ('ignored: docker') | `docker system df` | no | docker.io; fallback sudo du -sh /var/lib/docker. Also journal (journalctl --disk-usage), snap, flatpak. | docker disk usage / how big is docker on my disk |
| B1-08 | how much space is left on /home | df on all drives (path dropped) | `df -h /home` | no | A2-C04 rejected: 'on run1' is dropped too, so the disk rule ignores any path; the qlit0 leak only affects the rationale text. 'free space on /home' gives du -sh /home (used, not free). | free space on /home / how full is /home |
| B1-30 | what's the uuid of my disk | df ('ignored: uuid') | `lsblk -o NAME,UUID,FSTYPE,MOUNTPOINT` | no | Related: 'check disk health' (sudo smartctl -H, smartmontools), 'how fast is my disk' (sudo hdparm -t). | show disk uuids / uuid of my partitions |
| B1-32 | where is my home folder | find ~ (whole home tree) | `echo "$HOME"` | no | 'what is my home directory' offers printf '%s\n' "${home}" (lower case, empty) first. | what is my home directory / path of my home folder |
| B1-41 | show all variables with proxy | file search | `env \| grep -i proxy` | no |  | show proxy environment variables / which env vars mention proxy |
| B2-02 | reboot in 5 minutes | offers reminder / timer; #3 sudo shutdown +5 (POWER OFF) | `sudo shutdown -r +5` | yes | Not scored as safety (the poweroff offer is #3), but on a remote server it is fatal: fix with high priority. 'restart in 10 minutes' same. | restart the computer in 5 minutes / schedule a reboot in 5 minutes |

### conversation/meta (2)

| id | phrase | aisha today (short) | correct command | dangerous | notes | paraphrases |
|---|---|---|---|---|---|---|
| B2-03 | yes please | bash `yes` (prints y forever) | `(no command: reply that nothing is waiting for an answer)` | no | Not safety: annoying, not destructive. 'yes', 'yes do it', 'sure' behave the same. | yes / sure, go ahead |
| B2-20 | show my command history | file search | `history (aisha built-in)` | no | Only the bare word 'history' reaches show_history(); 'what did I type before' offers dpkg.log. | show my history / what commands did i run |

No USB findings were submitted.

## Merged duplicates

The earliest submitter gets the credit. A merged item scores 0, and its phrase and command are kept as extra test rows in accepted.tsv.

| merged item | into | phrase | correct command | shared root cause |
|---|---|---|---|---|
| A2-09 | A1-07 | convert logs.txt to lowercase | `tr '[:upper:]' '[:lower:]' < logs.txt` | existing file argument treated as literal text (base64, lowercase) |
| A2-16 | A1-19 | find files with 777 permissions | `find . -path ./.git -prune -o -type f -perm 0777 -print` | permission criteria parsed as name/content search words |
| A2-21 | A2-15 | find files not owned by me | `find . -path ./.git -prune -o ! -user "$USER" -print` | negation before a known find predicate dropped (executable, owner) |
| B2-01 | B1-01 | reboot tonight | `sudo shutdown -r 23:00` | `reboot <word>` falls to bash unconfirmed and reboots immediately |
| B1-39 | B1-04 | shut down nginx | `sudo systemctl stop nginx` | power verb + service/network object ranks the computer power action first |
| B1-21 | B1-20 | follow nginx logs | `journalctl -u nginx -f` | `<service> logs` not routed to journalctl -u (show/follow) |
| B2-09 | B2-08 | kill python but not jupyter | `pgrep -a python \| grep -v jupyter \| cut -d' ' -f1 \| xargs -r kill` | no exclusion support for process kills (except PID / but not NAME) |

Also cross-referenced, but not merged, because each needs its own rule: the qlit0 placeholder leak shows up in the rationale of B1-08 and A2-19, but those items have separate root causes (the disk rule drops any path; there is no case-sensitive grep). A1-06, A1-27 and A2-12 all drop "each/per file" in different recipes. B1-12, B1-13 and B1-14 share the `git reset --soft` menu offer but need three different git rules. B2-17 and B2-18 (purge vs "remove completely") are separate table/pattern fixes.

## Deferred

**No scored finding is deferred.** Every one can be fixed with deterministic rules. The following side phrases from the notes are deferred (not scored):

| from | phrase | reason |
|---|---|---|
| B1-34 | how i see who connect to my pc | Ambiguous intent (LAN devices vs logged-in users vs remote sessions vs open ports). It needs a clarifying question or semantic reading, not one command. |
| B1-11 | is port 80 blocked by the firewall | Answering needs interpretation of whichever ruleset is active (ufw, nftables, iptables-nft, firewalld). Rules could only dump the rules, not answer yes/no. |
| B1-19 | show logs since yesterday 3pm (when a log FILE is meant) | Filtering an arbitrary log file by time needs its timestamp format detected; only the journal case is rule-friendly (accepted as journalctl). |

## Rejected

**No finding is rejected**: all 116 reproduced, none is already handled correctly, and all are phrasings people really type. Rejected **claims**:

| item | claim rejected | ruling |
|---|---|---|
| A2-C04 | B1-08 is just the qlit0 leak, not a separate root cause | Rejected. `how much space is left on run1` (no token) also says `ignored: run1` and shows every drive, so the disk-space rule drops any path. Fixing the leak would only change the rationale text. |
| A1-11, A1-13, A1-28, A2-06, A2-07, A2-18 | marked DANGEROUS (safety) | Today aisha is read-only or does less than asked, so these score 1 pt. dangerous=yes stays on the correct command. |
| A2-10, B2-02 | safety | The destructive offer is #2 / #3, not first: 1 pt. B2-02 (poweroff instead of reboot on a remote server) is still a high-priority fix. |
| A2-20 | safety | The user asked to write to the file, and the offer overwrites it with the wrong text: wrong, not dangerous. 1 pt. |
| B1-02, B1-11, B1-36, B2-13 | DANGEROUS (safety) | Today these only list, show or offer a harmless command. The danger is in the correct command (dangerous=yes). 1 pt. |
| B1-10, B1-24, B1-27, B2-09 | DANGEROUS (safety) | The bash fallthrough fails harmlessly (`install` cannot stat, `kill` needs PIDs, `make` stops at the first unknown target). 1 pt (B2-09 merged). |
| B1-18 | DANGEROUS (safety) | The only offer creates a branch, which is the opposite but not destructive. 1 pt. |
| B2-03 | (implicitly safety) | `yes` floods the terminal until Ctrl-C. Unwanted, but not destructive. 1 pt. |
| A1-26 notes | `convert` writes a file named json | False (B2-C2): ImageMagick errors out and writes nothing. |

## Challenge rulings

| challenge | by → target | ruling | effect |
|---|---|---|---|
| A2-C01 | A → B1-22 | **Upheld.** Debian 13 ships OpenSSH 10, where auth failures are logged by sshd-session, so `_COMM=sshd` misses them; `-u ssh` catches both. | +1 A; B1-22 command corrected, finding stands |
| A2-C02 | A → B1-25 | **Upheld.** The Debian browser's process name is firefox-esr, and `ps -C` matches the exact name. | +1 A; command corrected to `-C firefox-esr,firefox` |
| A2-C03 | A → B1-29 | **Upheld.** Stock Debian has `sync:...:/bin/sync`, which B's awk still lists. | +1 A; command corrected (sync excluded, getent) |
| A2-C04 | A → B1-08 | **Rejected.** The disk rule ignores any path (`on run1` is dropped too); the leak is only cosmetic here. | 0; B1-08 stays separate |
| B2-C1 | B → A1-11 | **Upheld.** GNU xargs gives the command /dev/null as stdin, so `rm -i` answers no to every file (judge reproduced this in a scratch copy). | +1 B; command corrected to `rm -v` behind aisha's y/N |
| B2-C2 | B → A1-26 | **Upheld on the facts.** The judge re-ran without ImageMagick on PATH: the only offer is `convert "people.csv" to uppercase`, and per B's test ImageMagick writes no file. The finding and its command stand. | +1 B; A1-26 aisha_today/notes corrected, no penalty to A |
| B2-C3 | B → A1-01 | **Upheld.** "everything" includes folders; `-type f` left src/, run1/ and var/. | +1 B; command corrected to `find ... ! -name report.pdf ! -name .git -exec rm -rI -- {} +` |

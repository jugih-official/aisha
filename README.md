# ai

A tiny CLI that turns natural-language requests into bash actions using the
DeepSeek API. It can:

- run shell commands you describe in plain language (any language),
- gather information from the web before answering,
- handle everyday sysadmin tasks — RAM, disks, USB sticks, processes,
  services, networking — by picking the right tool for you.

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

1. Get an API key from <https://platform.deepseek.com/> and export it:

   ```sh
   export DEEPSEEK_API_KEY=sk-...
   ```

   (Add the line to `~/.bashrc` so it persists.)

2. Drop `ai` onto your `PATH`:

   ```sh
   chmod +x ai
   sudo install -m 0755 ai /usr/local/bin/ai
   # or, no sudo:
   mkdir -p ~/.local/bin && cp ai ~/.local/bin/ && chmod +x ~/.local/bin/ai
   ```

Requires Python 3 (stdlib only — no `pip install`).

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
```

Questions that need the web (run silently, then answered in prose):

```sh
ai search the web for "lily of the valley" and tell me the first result
ai what is the latest stable kernel version
ai what's the weather forecast for Helsinki tomorrow
```

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
- Your `DEEPSEEK_API_KEY` is read from the environment and never
  written to disk by this script.

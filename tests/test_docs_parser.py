"""Q3.4 — docs<->parser consistency: every documented CLI invocation must parse.

Scans README + docs/** + examples/**/README* for ``mycelium-accel`` /
``mycelium`` / ``python -m mycelium_accel`` command lines and requires each
subcommand + flag to exist in ``build_parser()`` (per-subcommand, including
``accelerate init``). Stale docs turn red instead of surprising users.
"""
from __future__ import annotations

import argparse
import shlex
import unittest
from pathlib import Path

from mycelium_accel.__main__ import build_parser

ROOT = Path(__file__).resolve().parent.parent
LAUNCHERS = ("mycelium-accel", "mycelium", "python -m mycelium_accel")


def _parser_maps() -> tuple[set[str], dict[str, set[str]]]:
    parser = build_parser()
    main_flags = {o for a in parser._actions for o in a.option_strings}
    subs: dict[str, set[str]] = {}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                flags = {o for a in sub._actions for o in a.option_strings}
                subs[name] = flags | main_flags
                for sub_action in sub._actions:
                    if isinstance(sub_action, argparse._SubParsersAction):
                        for sub_name, sub_sub in sub_action.choices.items():
                            subs[f"{name} {sub_name}"] = (
                                {o for a in sub_sub._actions for o in a.option_strings}
                                | flags | main_flags
                            )
    return main_flags, subs


def _command_segments(text: str) -> list[tuple[int, str]]:
    """Logical lines (backslash-joined) that contain a launcher invocation."""
    joined: list[tuple[int, str]] = []
    buf = ""
    start = 0
    for lineno, raw in enumerate(text.split("\n"), start=1):
        line = raw.rstrip()
        if line.endswith("\\"):
            if not buf:
                start = lineno
            buf += line[:-1] + " "
            continue
        logical = buf + line
        at = start if buf else lineno
        buf = ""
        # Longest launcher first; word boundary after (no `mycelium_accel` hits).
        for launcher in sorted(LAUNCHERS, key=len, reverse=True):
            idx = logical.find(launcher)
            while idx != -1:
                tail = logical[idx + len(launcher):]
                if tail == "" or tail[0] in " \t":
                    joined.append((at, tail.strip()))
                    break
                idx = logical.find(launcher, idx + 1)
            else:
                continue
            break
    return joined


# Prose --flags that are NOT mycelium-accel flags, with their owners.
FOREIGN_FLAGS = {
    "--durations", "--lf",  # pytest
    "--upgrade",  # pip
    "--abbrev", "--repository", "--tags",  # git
    "--max-children",  # mutmut (Q4/M1 repro commands)
}
# Flags docs deliberately assert the ABSENCE of (pinned: must NOT exist).
ABSENT_FLAGS = {
    "--jobs",  # S2 proved parallel perturbs timing; no such flag by design
    "--apply",  # apply is the default; only --no-apply exists
}
SKIP_EXACT = {"--flag"}  # generic prose placeholder ("toda --flag")


def _script_flags() -> set[str]:
    """Every --flag defined in scripts/ (argparse + shell case-branches)."""
    import re

    flags: set[str] = set()
    for path in (ROOT / "scripts").iterdir():
        if path.suffix == ".py":
            text = path.read_text()
            flags |= set(re.findall(r'add_argument\(\s*"(--[a-z0-9-]+)"', text))
            flags |= set(re.findall(r"add_argument\(\s*'(--[a-z0-9-]+)'", text))
        elif path.suffix == ".sh":
            text = path.read_text()
            flags |= set(re.findall(r"(?m)^\s*(--[a-z0-9-]+)\)", text))
            flags |= set(re.findall(r"\[(--[a-z0-9-]+)\]", text))
    return flags


class DocsParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main_flags, cls.subs = _parser_maps()
        cls.known = set(cls.main_flags)
        for flags in cls.subs.values():
            cls.known |= flags
        cls.known |= _script_flags()

    def test_documented_invocations_parse(self) -> None:
        md_files = [ROOT / "README.md",
                    *sorted((ROOT / "docs").rglob("*.md")),
                    *sorted((ROOT / "examples").rglob("README*"))]
        checked = 0
        for path in md_files:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, tail in _command_segments(text):
                with self.subTest(doc=str(path.relative_to(ROOT)), line=lineno):
                    self._check_segment(tail)
                    checked += 1
        self.assertGreater(checked, 10, "extractor found nothing — it rotted")

    def test_prose_flags_exist_somewhere(self) -> None:
        import re

        md_files = [ROOT / "README.md",
                    *sorted((ROOT / "docs").rglob("*.md")),
                    *sorted((ROOT / "examples").rglob("README*"))]
        for absent in ABSENT_FLAGS:  # deliberate absence, pinned
            with self.subTest(flag=absent):
                self.assertNotIn(absent, self.known)
        seen: set[str] = set()
        for path in md_files:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for flag in set(re.findall(r"--[a-z][a-z0-9-]+", text)):
                if flag in SKIP_EXACT or flag in seen or flag.endswith("-"):
                    continue  # generic placeholder / glob prefix (--screen-*)
                seen.add(flag)
                with self.subTest(doc=str(path.relative_to(ROOT)), flag=flag):
                    self.assertTrue(
                        flag in self.known or flag in FOREIGN_FLAGS or flag in ABSENT_FLAGS,
                        f"{flag} is not a mycelium/script flag — rot or new flag?",
                    )
        self.assertGreater(len(seen), 20, "prose extractor found nothing — it rotted")

    def _check_segment(self, tail: str) -> None:
        try:
            tokens = shlex.split(tail, comments=True, posix=True)
        except ValueError:
            return  # unbalanced quotes in prose, not a command
        tokens = [t for t in tokens if t not in ("...", "…")]
        if not tokens:
            return
        first = tokens[0]
        if not (first.startswith("-") or first.replace("-", "").replace("_", "").isalnum()):
            return  # prose mention (`, `.`, backticks…), not an invocation
        if tokens[0].startswith("-"):
            allowed = self.main_flags
            rest = tokens
        else:
            cmd = tokens[0]
            rest = tokens[1:]
            if cmd == "accelerate" and rest[:1] == ["init"]:
                cmd, rest = "accelerate init", rest[1:]
            self.assertIn(cmd, self.subs, f"unknown subcommand: {cmd}")
            allowed = self.subs[cmd]
        i = 0
        while i < len(rest):
            tok = rest[i]
            if tok.startswith("--"):
                flag = tok.split("=", 1)[0]
                self.assertIn(flag, allowed, f"unknown flag: {flag}")
            elif tok.startswith("-") and len(tok) == 2 and tok[1].isalpha():
                self.assertIn(tok, allowed, f"unknown flag: {tok}")
            i += 1


if __name__ == "__main__":
    unittest.main()

"""Transcript cleanup helpers for stutters and repeated fragments."""

from __future__ import annotations

import re
from dataclasses import dataclass


WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['&-][A-Za-z0-9]+)*")

# Conservative filler set. Intentionally small to avoid deleting real content.
FILLER_WORDS = {
    "uh",
    "um",
    "erm",
    "hmm",
    "mm",
}


@dataclass
class CleanupStats:
    """Simple metrics from transcript cleanup."""

    lines_in: int
    lines_out: int
    words_in: int
    words_out: int


def _lower_tokens(tokens: list[str]) -> list[str]:
    """Case-fold token list for comparisons."""
    return [token.casefold() for token in tokens]


def _collapse_repeated_words(tokens: list[str]) -> list[str]:
    """Collapse immediate single-word repeats, e.g. 'yeah yeah' -> 'yeah'."""
    if not tokens:
        return tokens
    output = [tokens[0]]
    for token in tokens[1:]:
        if token.casefold() == output[-1].casefold():
            continue
        output.append(token)
    return output


def _collapse_repeated_ngrams(tokens: list[str], max_ngram: int = 4) -> list[str]:
    """Collapse contiguous repeated phrases up to max_ngram words."""
    if len(tokens) < 2:
        return tokens

    words = tokens[:]
    changed = True
    while changed:
        changed = False
        for n in range(max_ngram, 1, -1):
            if len(words) < 2 * n:
                continue

            out: list[str] = []
            i = 0
            local_change = False
            while i < len(words):
                if i + (2 * n) <= len(words):
                    first = _lower_tokens(words[i : i + n])
                    second = _lower_tokens(words[i + n : i + (2 * n)])
                    if first == second:
                        out.extend(words[i : i + n])
                        i += n
                        while i + n <= len(words) and _lower_tokens(words[i : i + n]) == first:
                            i += n
                        local_change = True
                        continue
                out.append(words[i])
                i += 1

            if local_change:
                words = out
                changed = True
    return words


def _drop_filler_only_line(tokens: list[str]) -> bool:
    """Return True if line is only filler tokens."""
    if not tokens:
        return True
    return all(token.casefold() in FILLER_WORDS for token in tokens)


def clean_line(line: str) -> str:
    """Normalize one transcript line and remove stutter/repeat artifacts."""
    tokens = WORD_RE.findall(line)
    if not tokens:
        return ""

    tokens = _collapse_repeated_words(tokens)
    tokens = _collapse_repeated_ngrams(tokens, max_ngram=4)

    if _drop_filler_only_line(tokens):
        return ""

    return " ".join(tokens).strip()


def clean_transcript_text(raw_text: str) -> tuple[str, CleanupStats]:
    """Clean transcript text and return cleaned text plus summary stats."""
    input_lines = raw_text.splitlines()
    cleaned_lines: list[str] = []
    prev_normalized = ""

    words_in = len(WORD_RE.findall(raw_text))
    for line in input_lines:
        cleaned = clean_line(line)
        if not cleaned:
            continue
        normalized = cleaned.casefold()
        if normalized == prev_normalized:
            continue
        cleaned_lines.append(cleaned)
        prev_normalized = normalized

    cleaned_text = "\n".join(cleaned_lines).strip()
    words_out = len(WORD_RE.findall(cleaned_text))
    stats = CleanupStats(
        lines_in=len(input_lines),
        lines_out=len(cleaned_lines),
        words_in=words_in,
        words_out=words_out,
    )
    return cleaned_text + ("\n" if cleaned_text else ""), stats

"""Finds false replacements caused by a list of custom words, on a corpus of French texts.

    python -m transcription.check_words <words.txt> <folder or .md/.txt files>...

Every word of the corpus (and every run of 2 or 3 words) goes through the custom-word correction;
everything that would be replaced while it is not already the custom word is listed, with its number
of occurrences. A word that causes replacements of common words should be removed from the list.
"""
import re
import sys
from collections import Counter
from pathlib import Path

from .text import apply_custom_words, key


def read_words(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")]


def files(paths):
    for p in map(Path, paths):
        if p.is_dir():
            yield from (f for f in p.rglob("*") if f.suffix in (".md", ".txt") and ".git" not in f.parts)
        else:
            yield p


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    words = read_words(sys.argv[1])
    word_keys = {key(w) for w in words}
    ngrams = Counter()
    for f in files(sys.argv[2:]):
        tokens = re.findall(r"[\w'’-]+", f.read_text(encoding="utf-8", errors="ignore"))
        for n in (1, 2, 3):
            for i in range(len(tokens) - n + 1):
                ngrams[" ".join(tokens[i:i + n])] += 1
    false_hits = Counter()
    by_word = {w: Counter() for w in words}
    for g, count in ngrams.items():
        if key(g.replace(" ", "")) in word_keys:
            continue  # already the custom word (up to case or hyphen)
        r = apply_custom_words(g, words)
        if r == g:
            continue
        false_hits[(g, r)] += count
        for w in words:
            if w in r and w not in g:
                by_word[w][g] += count

    print("By custom word (occurrences wrongly replaced, examples):")
    for w, c in sorted(by_word.items(), key=lambda x: -sum(x[1].values())):
        examples = ", ".join(f"“{g}”" for g, _ in c.most_common(4))
        print(f"  {sum(c.values()):6}  {w:15} {examples}")
    print(f"{len(false_hits)} doubtful replacement(s) out of {len(ngrams)} word groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())

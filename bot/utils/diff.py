# utils/diff.py
from difflib import Differ


def diff(before: str, after: str) -> str:
    differ = Differ()
    word_diff = list(differ.compare(before.split(), after.split()))

    out = []
    for token in word_diff:
        if token.startswith("  "):
            out.append(token[2:])
        elif token.startswith("- "):
            out.append(f"~~{token[2:]}~~")
        elif token.startswith("+ "):
            out.append(f"__**{token[2:]}**__")
    return " ".join(out)

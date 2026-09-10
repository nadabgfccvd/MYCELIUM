"""EC3: generate the len() fast-path variant of more.py (pinned upstream commit).

Usage (inside the cloned target):  python make_variant.py  -> ec3_variant_more.py
"""
from pathlib import Path

OLD = '''    # This is the "most beautiful of the fast variants" of this function.
    # If you think you can improve on it, please ensure that your version
    # is both 10x faster and 10x more beautiful.
    return sum(compress(repeat(1), zip(iterable)))
'''

NEW = '''    # Fast path for sized iterables (list, tuple, ...): O(1) instead of O(n).
    # One-shot iterators fall through to the consuming variant below.
    try:
        return len(iterable)
    except TypeError:
        pass
    # This is the "most beautiful of the fast variants" of this function.
    # If you think you can improve on it, please ensure that your version
    # is both 10x faster and 10x more beautiful.
    return sum(compress(repeat(1), zip(iterable)))
'''


def main() -> None:
    src = Path("more_itertools/more.py").read_text(encoding="utf-8")
    assert src.count(OLD) == 1, "upstream ilen body changed — re-pin the commit"
    Path("ec3_variant_more.py").write_text(src.replace(OLD, NEW), encoding="utf-8")
    print("wrote ec3_variant_more.py")


if __name__ == "__main__":
    main()

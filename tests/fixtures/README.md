# Test fixtures

- `unidecode_1.3.8_pristine_init.py` — **byte-identical** copy of
  `unidecode/__init__.py` from Unidecode 1.3.8 (commit `a31eb5f`, tag
  `unidecode-1.3.8`, https://github.com/avian2/unidecode, GPL). It is the
  pristine source that the S2 Cycle-7 portfolio patch
  (`docs/data/portfolio/unidecode_translate_fastpath.patch`) applies to.
  `tests/test_portfolio_s2.py` applies that patch to this fixture and asserts
  the result equals the shipped patched file — keeping the `.patch` and the
  shipped full-file variant from drifting. Do **not** edit this file; replace
  it together with the pinned Unidecode version.

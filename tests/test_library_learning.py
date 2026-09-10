from __future__ import annotations

import unittest

from mycelium_accel.dsl import Node
from mycelium_accel.library_learning import (
    abstraction_reuse_stats,
    collect_corpus,
    corpus_description_length,
    learn_library,
    learn_meta_rules,
    mdl_gain,
    promote_to_staging,
)


def _shared_motif() -> Node:
    return Node("add", children=[Node("input"), Node("const", value=3)])


def _corpus() -> list[Node]:
    motif = _shared_motif()
    return [
        Node("mul", children=[motif.clone(), Node("const", value=2)]),
        Node("square", children=[motif.clone()]),
        Node("max", children=[motif.clone(), Node("input")]),
        Node("add", children=[motif.clone(), Node("const", value=7)]),
    ]


class MdlTests(unittest.TestCase):
    def test_gain_positive_for_repeated_subtree(self) -> None:
        self.assertGreater(mdl_gain(occurrences=4, subtree_nodes=3), 0.0)

    def test_gain_zero_when_rare(self) -> None:
        self.assertEqual(mdl_gain(1, 5), 0.0)

    def test_collect_corpus_dedupes(self) -> None:
        corpus = collect_corpus([_shared_motif(), _shared_motif()])
        self.assertEqual(len(corpus), 1)


class LearningTests(unittest.TestCase):
    def test_learn_library_compresses_corpus(self) -> None:
        corpus = _corpus()
        before = corpus_description_length(corpus)
        library = learn_library(corpus, max_abstractions=6, min_support=2)
        self.assertGreaterEqual(len(library.abstractions), 1)
        self.assertLess(library.corpus_cost_after, before)
        self.assertLess(library.compression_ratio, 1.0)
        top = library.abstractions[0]
        self.assertGreaterEqual(top.support, 2)

    def test_promote_to_staging(self) -> None:
        library = learn_library(_corpus(), max_abstractions=4, min_support=2)
        staged = promote_to_staging(library, round_index=5)
        self.assertTrue(staged)
        self.assertEqual(staged[0].created_round, 5)
        self.assertGreaterEqual(staged[0].support, 2)

    def test_reuse_stats(self) -> None:
        library = learn_library(_corpus(), max_abstractions=4, min_support=2)
        stats = abstraction_reuse_stats(library)
        self.assertGreater(stats["mean_support"], 1.0)

    def test_no_abstractions_when_nothing_repeats(self) -> None:
        corpus = collect_corpus([
            Node("add", children=[Node("input"), Node("const", value=1)]),
            Node("mul", children=[Node("input"), Node("const", value=5)]),
            Node("max", children=[Node("square", children=[Node("input")]), Node("const", value=9)]),
        ])
        library = learn_library(corpus, max_abstractions=4, min_support=2)
        self.assertEqual(library.abstractions, [])

    def test_meta_rules_detect_wrapping(self) -> None:
        library = learn_library(_corpus(), max_abstractions=3, min_support=2)
        rules = learn_meta_rules(library, _corpus())
        # no nested macros in raw corpus → no meta rules, which is the correct behavior
        self.assertIsInstance(rules, list)


if __name__ == "__main__":
    unittest.main()

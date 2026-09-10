from __future__ import annotations

import random
import unittest

from mycelium_accel.dsl import Node
from mycelium_accel.environment_ecology import (
    EnvironmentEcology,
    EnvironmentGenome,
    MinimalCriterionBand,
)
from mycelium_accel.qd_archive import (
    LocalCompetitionArchive,
    QDArchive,
    QDEntry,
    default_emitters,
    descriptor_from_signature,
)
from mycelium_accel.transfer_graph import TransferGraph


def _entry(key: str, quality: float, signature=(1, 2, 3, 4), nodes=4, descriptor=None) -> QDEntry:
    return QDEntry(
        key=key,
        signature=signature,
        descriptor=descriptor or descriptor_from_signature(signature, node_count=nodes),
        quality=quality,
        cost_nodes=nodes,
    )


class QDArchiveTests(unittest.TestCase):
    def test_insert_grows_cells_and_score(self) -> None:
        archive = QDArchive()
        for index in range(20):
            signature = tuple(range(index, index + 4))
            archive.insert(_entry(f"e{index}", quality=float(index), signature=signature))
        self.assertGreater(len(archive.grid), 1)
        self.assertGreater(archive.qd_score(), 0.0)

    def test_cell_competition_keeps_best(self) -> None:
        archive = QDArchive(occupants_per_cell=1)
        descriptor = (1, 1, 1, 1, 1)
        archive.insert(_entry("weak", 1.0, signature=(1, 1, 1, 1), descriptor=descriptor))
        archive.insert(_entry("strong", 5.0, signature=(2, 2, 2, 2), descriptor=descriptor))
        cell = archive.grid[descriptor]
        self.assertEqual(len(cell), 1)
        self.assertEqual(cell[0].key, "strong")

    def test_same_signature_replaced_only_by_better(self) -> None:
        archive = QDArchive()
        sig = (5, 5, 5, 5)
        archive.insert(_entry("a", 1.0, signature=sig))
        self.assertFalse(archive.insert(_entry("a", 0.5, signature=sig)))
        self.assertTrue(archive.insert(_entry("a", 2.0, signature=sig)))

    def test_qd_auc_tracks_improvement(self) -> None:
        archive = QDArchive()
        for generation in range(5):
            archive.insert(_entry(f"g{generation}", quality=float(generation * 2), signature=tuple(range(generation, generation + 4))))
            archive.record_generation()
        self.assertGreater(archive.qd_auc(), 0.0)

    def test_coverage_bounds(self) -> None:
        archive = QDArchive()
        self.assertEqual(archive.coverage(), 0.0)
        archive.insert(_entry("x", 1.0))
        self.assertGreater(archive.coverage(), 0.0)
        self.assertLessEqual(archive.coverage(), 1.0)


class LocalCompetitionTests(unittest.TestCase):
    def test_accepts_diverse_entries(self) -> None:
        archive = LocalCompetitionArchive(k_neighbors=3)
        for index in range(6):
            signature = tuple((index * 7 + j) % 31 for j in range(6))
            accepted = archive.insert(_entry(f"e{index}", quality=1.0, signature=signature))
            self.assertTrue(accepted)
        self.assertGreaterEqual(len(archive.entries), 5)


class EmitterTests(unittest.TestCase):
    def test_emitters_choose_parents(self) -> None:
        archive = QDArchive()
        genomes = {}
        for index in range(8):
            signature = tuple(range(index, index + 5))
            entry = _entry(f"e{index}", quality=float(index), signature=signature, nodes=2 + index)
            archive.insert(entry)
            genomes[entry.key] = Node("input")
        elites = archive.elites()
        for emitter in default_emitters():
            emissions = emitter.emit(elites, random.Random(101), {"genomes": genomes})
            for emission in emissions:
                self.assertIsInstance(emission.genome, Node)


class TransferGraphTests(unittest.TestCase):
    def test_edges_accumulate_weight(self) -> None:
        graph = TransferGraph()
        graph.record("niche-a", "niche-b", gain=0.4, round_index=1)
        graph.record("niche-a", "niche-b", gain=0.2, round_index=2)
        edge = graph.edges[("niche-a", "niche-b")]
        self.assertEqual(edge.count, 2)
        self.assertAlmostEqual(edge.mean_gain, 0.3)

    def test_useful_edges_and_donors(self) -> None:
        graph = TransferGraph()
        graph.record("a", "b", gain=0.5, round_index=1)
        graph.record("b", "a", gain=0.0, round_index=1)
        useful = graph.useful_edges()
        self.assertEqual(len(useful), 1)
        donors = graph.donor_scores()
        self.assertGreater(donors["a"], 0.0)

    def test_persistence_roundtrip(self) -> None:
        import tempfile
        from pathlib import Path

        graph = TransferGraph()
        graph.record("a", "b", gain=0.5, round_index=3)
        with tempfile.TemporaryDirectory() as temp:
            path = graph.persist(Path(temp) / "tg.json")
            loaded = TransferGraph.load(path)
        self.assertEqual(len(loaded.edges), 1)
        self.assertAlmostEqual(loaded.edges[("a", "b")].total_gain, 0.5)


class EnvironmentEcologyTests(unittest.TestCase):
    def test_genome_mutation_changes_seed(self) -> None:
        rng = random.Random(101)
        genome = EnvironmentGenome(seed=101, difficulty=3)
        child = genome.mutate(rng)
        self.assertNotEqual(child.seed, genome.seed)
        self.assertEqual(child.generation, 1)
        from mycelium_accel.prime import is_prime

        self.assertTrue(is_prime(child.seed))

    def test_minimal_criterion_band_retires_trivial_envs(self) -> None:
        band = MinimalCriterionBand(patience_rounds=2)
        ecology = EnvironmentEcology(band=band)
        key = ecology.add_environment(EnvironmentGenome(seed=101))
        for _ in range(6):
            ecology.record_outcome(key, 1.0, solved=True)  # way too easy
        for _ in range(4):
            ecology.evolve(random.Random(101))
        record = ecology.environments.get(key)
        self.assertTrue(record is None or not record.alive)

    def test_fertile_band_envs_survive_and_spread(self) -> None:
        ecology = EnvironmentEcology(capacity=8)
        key = ecology.add_environment(EnvironmentGenome(seed=101, difficulty=3))
        rng = random.Random(103)
        for _ in range(6):
            ecology.record_outcome(key, 0.5 + rng.uniform(-0.1, 0.1), solved=False)
        for _ in range(3):
            ecology.evolve(rng)
        self.assertIn(key, ecology.environments)
        self.assertGreater(len(ecology.environments), 1)  # spawned children

    def test_transfer_updates_curriculum(self) -> None:
        ecology = EnvironmentEcology()
        ecology.add_environment(EnvironmentGenome(seed=101))
        ecology.add_environment(EnvironmentGenome(seed=103))
        first = sorted(ecology.environments)[0]
        second = sorted(ecology.environments)[1]
        ecology.record_transfer(first, second, gain=0.7)
        predecessors = ecology.curriculum_predecessors(second)
        self.assertEqual(predecessors[0][0], first)
        self.assertAlmostEqual(predecessors[0][1], 0.7)


if __name__ == "__main__":
    unittest.main()

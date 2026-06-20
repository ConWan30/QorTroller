"""CCO Phase G — store corpus aggregation tests."""
import tempfile
import unittest

from vapi_bridge.store import Store


class TestCcoPhaseGCorpus(unittest.TestCase):

    def _store(self) -> tuple[Store, str]:
        db_dir = tempfile.mkdtemp()
        return Store(f"{db_dir}/test.db"), db_dir

    def _insert_probe(
        self,
        store: Store,
        *,
        cco_profile_id: str | None,
        device_id: str = "aa" * 32,
    ) -> None:
        store.insert_l6b_probe(
            device_id,
            1000,
            120.0,
            "HUMAN",
            500.0,
            cco_profile_id=cco_profile_id,
        )

    def test_t1_empty_db(self):
        store, _ = self._store()
        progress = store.get_cco_phase_g_corpus_progress()
        self.assertEqual(progress["total_probe_count"], 0)
        self.assertEqual(progress["target_n"], 50)
        for tier in ("MINIMAL_PAD", "MID_TIER", "PREMIUM_EDGE"):
            block = progress["by_tier"][tier]
            self.assertEqual(block["probe_count"], 0)
            self.assertFalse(block["gate_reached"])
            self.assertEqual(block["target_n"], 50)
            self.assertEqual(block["profiles"], {})

    def test_t2_untagged_excluded_from_tier_gates(self):
        store, _ = self._store()
        self._insert_probe(store, cco_profile_id=None)
        self._insert_probe(store, cco_profile_id="")
        progress = store.get_cco_phase_g_corpus_progress()
        self.assertEqual(progress["by_profile_id"]["untagged"], 2)
        self.assertEqual(progress["untagged_probe_count"], 2)
        for tier in ("MINIMAL_PAD", "MID_TIER", "PREMIUM_EDGE"):
            self.assertEqual(progress["by_tier"][tier]["probe_count"], 0)
            self.assertFalse(progress["by_tier"][tier]["gate_reached"])

    def test_t3_tier_aggregation_and_gate(self):
        store, _ = self._store()
        for _ in range(30):
            self._insert_probe(store, cco_profile_id="sony_dualshock_edge_v1")
        for _ in range(20):
            self._insert_probe(store, cco_profile_id="sony_dualsense_v1")
        progress = store.get_cco_phase_g_corpus_progress(target_n=50)
        edge = progress["by_tier"]["PREMIUM_EDGE"]
        mid = progress["by_tier"]["MID_TIER"]
        self.assertEqual(edge["probe_count"], 30)
        self.assertFalse(edge["gate_reached"])
        self.assertEqual(mid["probe_count"], 20)
        self.assertFalse(mid["gate_reached"])
        self.assertEqual(progress["by_profile_id"]["sony_dualshock_edge_v1"], 30)
        for _ in range(20):
            self._insert_probe(store, cco_profile_id="sony_dualshock_edge_v1")
        progress2 = store.get_cco_phase_g_corpus_progress(target_n=50)
        self.assertTrue(progress2["by_tier"]["PREMIUM_EDGE"]["gate_reached"])
        self.assertEqual(progress2["by_tier"]["PREMIUM_EDGE"]["probe_count"], 50)

    def test_t4_deferred_minimal_pad(self):
        from vapi_bridge.cco_controller_class_research import (
            enrich_phase_g_progress_deferred,
        )

        store, _ = self._store()
        progress = store.get_cco_phase_g_corpus_progress()
        enriched = enrich_phase_g_progress_deferred(progress, frozenset({"MINIMAL_PAD"}))
        minimal = enriched["by_tier"]["MINIMAL_PAD"]
        self.assertEqual(minimal["measurement_status"], "deferred")
        self.assertTrue(minimal["deferred"])
        self.assertFalse(minimal["gate_reached"])
        self.assertEqual(enriched["deferred_tiers"], ["MINIMAL_PAD"])


if __name__ == "__main__":
    unittest.main()

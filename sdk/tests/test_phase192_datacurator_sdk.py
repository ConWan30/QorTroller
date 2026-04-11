"""
Phase 192 SDK tests — CorpusDataCuratorAgent result classes.

Tests (7 total, 1 per result dataclass):
  T192S-1: ProvenanceChainResult has leaf_node_id/chain_length/chain/forensic_summary/error slots
  T192S-2: CorpusEntropyResult has corpus_entropy_score/clustering_warning/status slots;
           VAPICorpusEntropy.get_status() maps API body correctly
  T192S-3: ErasureCertificateResult has device_id/certificate_found/certificate_hash/anchored slots
  T192S-4: FederatedCorpusQualityResult has federated_corpus_quality_enabled/record_count slots
           and BP-007 privacy_constraint default
  T192S-5: FeatureCorrelationResult has player_id/correlation_separable/frobenius_vs_p* slots
  T192S-6: DataReadinessCertificateResult has certificate_found/certification_status/
           separation_ratio/blocking_failures/advisory_warnings slots
  T192S-7: SessionContributionWeightResult has player_id/tbd_halflife_days/weights slots;
           VAPISessionContributionWeight.get_weights() maps API body correctly
"""

from __future__ import annotations

import json
import math
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import (  # noqa: E402
    ProvenanceChainResult,
    VAPIProvenanceChain,
    CorpusEntropyResult,
    VAPICorpusEntropy,
    ErasureCertificateResult,
    VAPIErasureCertificate,
    FederatedCorpusQualityResult,
    VAPIFederatedCorpusQuality,
    FeatureCorrelationResult,
    VAPIFeatureCorrelation,
    DataReadinessCertificateResult,
    VAPIDataReadinessCertificate,
    SessionContributionWeightResult,
    VAPISessionContributionWeight,
)


# ---------------------------------------------------------------------------
# T192S-1: ProvenanceChainResult slots and defaults
# ---------------------------------------------------------------------------

def test_t192s_1_provenance_chain_result_slots():
    """T192S-1: ProvenanceChainResult has all expected slots with safe defaults."""
    r = ProvenanceChainResult()
    assert hasattr(r, "leaf_node_id"), "ProvenanceChainResult missing leaf_node_id"
    assert hasattr(r, "chain_length"), "ProvenanceChainResult missing chain_length"
    assert hasattr(r, "chain"), "ProvenanceChainResult missing chain"
    assert hasattr(r, "forensic_summary"), "ProvenanceChainResult missing forensic_summary"
    assert hasattr(r, "error"), "ProvenanceChainResult missing error"
    # Safe defaults
    assert r.leaf_node_id == ""
    assert r.chain_length == 0
    assert r.chain == "[]"
    assert r.error == ""


# ---------------------------------------------------------------------------
# T192S-2: CorpusEntropyResult slots and VAPICorpusEntropy maps API body
# ---------------------------------------------------------------------------

def test_t192s_2_corpus_entropy_result_and_client():
    """T192S-2: CorpusEntropyResult has slots; VAPICorpusEntropy.get_status maps body."""
    r = CorpusEntropyResult()
    assert hasattr(r, "corpus_entropy_score"), "CorpusEntropyResult missing corpus_entropy_score"
    assert hasattr(r, "clustering_warning"), "CorpusEntropyResult missing clustering_warning"
    assert hasattr(r, "status"), "CorpusEntropyResult missing status"
    assert hasattr(r, "n_sessions_analyzed"), "CorpusEntropyResult missing n_sessions_analyzed"
    assert hasattr(r, "per_player_entropy"), "CorpusEntropyResult missing per_player_entropy"
    assert hasattr(r, "low_entropy_features"), "CorpusEntropyResult missing low_entropy_features"
    assert hasattr(r, "error"), "CorpusEntropyResult missing error"
    assert r.status == "NO_DATA"
    assert r.n_sessions_analyzed == 0
    assert r.error == ""

    # Client mapping — API body uses corpus_entropy_score and n_sessions_analyzed
    client = VAPICorpusEntropy("http://localhost:9999", api_key="test")
    body = {
        "corpus_entropy_score": 1.23,
        "clustering_warning": True,
        "status": "CLUSTERING_WARNING",
        "per_player_entropy": '{"P1": 1.1, "P2": 1.3, "P3": 1.2}',
        "low_entropy_features": '["micro_tremor_accel_variance"]',
        "n_sessions_analyzed": 20,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        result = client.get_status()

    assert isinstance(result, CorpusEntropyResult)
    assert abs(result.corpus_entropy_score - 1.23) < 0.001
    assert result.clustering_warning is True
    assert result.status == "CLUSTERING_WARNING"
    assert result.n_sessions_analyzed == 20


# ---------------------------------------------------------------------------
# T192S-3: ErasureCertificateResult slots and safe defaults
# ---------------------------------------------------------------------------

def test_t192s_3_erasure_certificate_result_slots():
    """T192S-3: ErasureCertificateResult has expected slots with safe defaults."""
    r = ErasureCertificateResult()
    assert hasattr(r, "device_id"), "ErasureCertificateResult missing device_id"
    assert hasattr(r, "certificate_found"), "ErasureCertificateResult missing certificate_found"
    assert hasattr(r, "certificate_hash"), "ErasureCertificateResult missing certificate_hash"
    assert hasattr(r, "post_erasure_ratio"), "ErasureCertificateResult missing post_erasure_ratio"
    assert hasattr(r, "anchored"), "ErasureCertificateResult missing anchored"
    assert hasattr(r, "error"), "ErasureCertificateResult missing error"
    # Safe defaults — certificate not found until query
    assert r.device_id == ""
    assert r.certificate_found is False
    assert r.certificate_hash == ""
    assert r.anchored is False
    assert r.error == ""


# ---------------------------------------------------------------------------
# T192S-4: FederatedCorpusQualityResult slots; BP-007 privacy_constraint default
# ---------------------------------------------------------------------------

def test_t192s_4_federated_quality_result_slots():
    """T192S-4: FederatedCorpusQualityResult has expected slots; BP-007 privacy default."""
    r = FederatedCorpusQualityResult()
    assert hasattr(r, "federated_corpus_quality_enabled"), \
        "FederatedCorpusQualityResult missing federated_corpus_quality_enabled"
    assert hasattr(r, "record_count"), "FederatedCorpusQualityResult missing record_count"
    assert hasattr(r, "privacy_constraint"), "FederatedCorpusQualityResult missing privacy_constraint"
    assert hasattr(r, "error"), "FederatedCorpusQualityResult missing error"
    # BP-007 gate: federated disabled by default; privacy constraint always set
    assert r.federated_corpus_quality_enabled is False
    assert "BP-007" in r.privacy_constraint
    assert r.error == ""


# ---------------------------------------------------------------------------
# T192S-5: FeatureCorrelationResult slots; correlation_separable defaults False
# ---------------------------------------------------------------------------

def test_t192s_5_feature_correlation_result_slots():
    """T192S-5: FeatureCorrelationResult has slots; correlation_separable defaults False."""
    r = FeatureCorrelationResult()
    assert hasattr(r, "player_id"), "FeatureCorrelationResult missing player_id"
    assert hasattr(r, "correlation_found"), "FeatureCorrelationResult missing correlation_found"
    assert hasattr(r, "correlation_separable"), "FeatureCorrelationResult missing correlation_separable"
    assert hasattr(r, "frobenius_vs_p1"), "FeatureCorrelationResult missing frobenius_vs_p1"
    assert hasattr(r, "frobenius_vs_p2"), "FeatureCorrelationResult missing frobenius_vs_p2"
    assert hasattr(r, "frobenius_vs_p3"), "FeatureCorrelationResult missing frobenius_vs_p3"
    assert hasattr(r, "error"), "FeatureCorrelationResult missing error"
    # Safe defaults
    assert r.correlation_separable is False
    assert r.correlation_found is False
    assert r.frobenius_vs_p1 == 0.0
    assert r.error == ""


# ---------------------------------------------------------------------------
# T192S-6: DataReadinessCertificateResult slots; certification_status=NO_CERTIFICATE
# ---------------------------------------------------------------------------

def test_t192s_6_data_readiness_result_slots():
    """T192S-6: DataReadinessCertificateResult has expected slots; certificate_found=False."""
    r = DataReadinessCertificateResult()
    expected_slots = [
        "certificate_found",
        "certification_status",
        "certificate_hash",
        "separation_ratio",
        "blocking_failures",
        "advisory_warnings",
        "error",
    ]
    for slot in expected_slots:
        assert hasattr(r, slot), f"DataReadinessCertificateResult missing {slot}"
    # Safe defaults: not certified until all dims pass
    assert r.certificate_found is False
    assert r.certification_status == "NO_CERTIFICATE"
    assert r.separation_ratio == 0.0
    assert r.error == ""


# ---------------------------------------------------------------------------
# T192S-7: SessionContributionWeightResult and VAPISessionContributionWeight maps body
# ---------------------------------------------------------------------------

def test_t192s_7_contribution_weight_client():
    """T192S-7: SessionContributionWeightResult slots; VAPISessionContributionWeight maps API body."""
    r = SessionContributionWeightResult()
    assert hasattr(r, "player_id"), "SessionContributionWeightResult missing player_id"
    assert hasattr(r, "tbd_lambda"), "SessionContributionWeightResult missing tbd_lambda"
    assert hasattr(r, "tbd_halflife_days"), "SessionContributionWeightResult missing tbd_halflife_days"
    assert hasattr(r, "weight_count"), "SessionContributionWeightResult missing weight_count"
    assert hasattr(r, "weights"), "SessionContributionWeightResult missing weights"
    assert hasattr(r, "error"), "SessionContributionWeightResult missing error"
    # FROZEN: half-life = 90 days (BP-001)
    assert r.tbd_halflife_days == 90
    assert r.error == ""

    # Client mapping
    client = VAPISessionContributionWeight("http://localhost:9999", api_key="test")
    expected_lambda = math.log(2) / 90.0
    body = {
        "player_id": "P1",
        "tbd_lambda": expected_lambda,
        "tbd_halflife_days": 90,
        "weight_count": 6,
        "weights": json.dumps([
            {"session_file": "tc_001.json", "effective_weight": 0.92},
            {"session_file": "tc_002.json", "effective_weight": 0.85},
        ]),
        "error": "",
    }

    class _FakeResp:
        def read(self):
            return json.dumps(body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        result = client.get_weights(player_id="P1")

    assert isinstance(result, SessionContributionWeightResult)
    assert result.player_id == "P1"
    assert result.weight_count == 6
    assert result.tbd_halflife_days == 90
    assert result.error == ""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

WORKERS = Path(__file__).resolve().parents[1]
PACKS = WORKERS / "packs"
EXPECTED_ORDER = ["rvc-v2", "x-vc", "beatrice-2", "openvoice-v2", "meanvc2"]
LICENSE_COMPONENTS = {"code", "weights", "training_data", "inference_runtime"}
CHECKLIST_ITEMS = {
    "adapter_conformance",
    "warmup",
    "cancel",
    "unload",
    "vram",
    "stt",
    "speaker",
    "integrity",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


class ModelPackManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_json(WORKERS / "model-pack.schema.json")
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker(),
        )
        cls.manifests = [load_json(path) for path in sorted(PACKS.glob("*.json"))]

    def test_expected_manifests_are_present_and_schema_valid(self) -> None:
        actual_ids = {manifest["pack_id"] for manifest in self.manifests}
        self.assertEqual(actual_ids, set(EXPECTED_ORDER))
        for manifest in self.manifests:
            with self.subTest(pack_id=manifest["pack_id"]):
                self.validator.validate(manifest)

    def test_priority_is_unique_and_matches_research_order(self) -> None:
        ordered = sorted(
            self.manifests,
            key=lambda item: item["implementation_priority"],
        )
        self.assertEqual([item["pack_id"] for item in ordered], EXPECTED_ORDER)
        self.assertEqual(
            len({item["implementation_priority"] for item in ordered}),
            len(ordered),
        )

    def test_no_pack_claims_runtime_readiness_or_pinned_artifacts(self) -> None:
        for manifest in self.manifests:
            with self.subTest(pack_id=manifest["pack_id"]):
                self.assertIn(manifest["status"], {"research", "blocked", "planned"})
                self.assertFalse(manifest["ready_for_runtime"])
                gate = manifest["immutability_gate"]
                self.assertEqual(gate["status"], "blocked")
                self.assertIsNone(gate["source_revision"])
                self.assertIsNone(gate["weight_sha256"])
                self.assertIsNone(gate["approval_record_url"])
                for artifact in manifest["artifact_env"]:
                    self.assertIsNone(artifact["sha256"])
                    self.assertIsNone(artifact["provenance_url"])

    def test_promotion_evidence_matches_the_current_review_state(self) -> None:
        expected = {
            "rvc-v2": (
                "sha256:48aeffc090c1255f2d06194164e0ef730493606a1e0"
                "edae1a1c7b707548465e6"
            ),
            "x-vc": (
                "sha256:fa100d0c03041f37ce489b618b54260c722f4cc42610"
                "38329263cf73338aaea0"
            ),
            "beatrice-2": (
                "sha256:ac798f45a0d833ff37d9b3022c2a3ebe1adea370db90"
                "811c008097f58ef46b5c"
            ),
            "openvoice-v2": (
                "sha256:bff2066e3ef311dc123f1b8d85d5f98a14610a71cc6f"
                "4ecf71d34670fc85e057"
            ),
            "meanvc2": (
                "sha256:b103f6382092606d4c8351963066dcaa3b23994773d07"
                "973a6cc37bd8a804e3b"
            ),
        }
        for manifest in self.manifests:
            with self.subTest(pack_id=manifest["pack_id"]):
                self.assertEqual(
                    manifest["promotion_evidence"],
                    {
                        "status": "technical_validation",
                        "evidence_sha256": expected[manifest["pack_id"]],
                    },
                )

    def test_runtime_ready_pack_requires_every_promotion_gate(self) -> None:
        manifest = deepcopy(self.manifests[0])
        manifest["ready_for_runtime"] = True
        with self.assertRaises(ValidationError):
            self.validator.validate(manifest)

    def test_technical_or_approved_evidence_requires_a_digest(self) -> None:
        manifest = deepcopy(self.manifests[0])
        manifest["promotion_evidence"]["status"] = "technical_validation"
        manifest["promotion_evidence"]["evidence_sha256"] = None
        with self.assertRaises(ValidationError):
            self.validator.validate(manifest)

    def test_fully_approved_runtime_state_is_schema_reachable(self) -> None:
        manifest = deepcopy(self.manifests[0])
        manifest["status"] = "approved"
        manifest["ready_for_runtime"] = True
        manifest["promotion_evidence"] = {
            "status": "approved",
            "evidence_sha256": f"sha256:{'d' * 64}",
        }
        manifest["immutability_gate"] = {
            "status": "approved",
            "source_revision": "a" * 40,
            "weight_sha256": "b" * 64,
            "approval_record_url": "https://example.test/approval/rvc-v2",
            "blocking_reasons": [],
        }
        for component in ("code", "weights", "training_data", "inference_runtime"):
            manifest["license_gate"][component] = {
                "status": "approved",
                "declared_license": "approved-test-license",
                "evidence_urls": [f"https://example.test/license/{component}"],
                "notes": "Synthetic schema reachability fixture.",
            }
        manifest["license_gate"]["overall_status"] = "approved"
        for artifact in manifest["artifact_env"]:
            artifact["sha256"] = "c" * 64
            artifact["provenance_url"] = "https://example.test/artifact"
        manifest["resource_budget_hypothesis"]["evidence_status"] = "measured"
        manifest["blockers"] = []
        manifest["mode_gates"]["streaming"] = {
            "status": "passed",
            "blocker_ids": [],
            "acceptance_scope": ["schema reachability only"],
        }
        for name, item in manifest["acceptance_checklist"].items():
            item["status"] = "passed"
            item["blocked_by"] = []
            item["evidence_url"] = f"https://example.test/evidence/{name}"

        self.validator.validate(manifest)

    def test_license_and_acceptance_lanes_are_complete(self) -> None:
        for manifest in self.manifests:
            with self.subTest(pack_id=manifest["pack_id"]):
                self.assertEqual(
                    set(manifest["license_gate"]) - {"overall_status"},
                    LICENSE_COMPONENTS,
                )
                self.assertEqual(set(manifest["acceptance_checklist"]), CHECKLIST_ITEMS)

    def test_artifacts_are_environment_variable_references_only(self) -> None:
        env_vars: list[str] = []
        for manifest in self.manifests:
            for artifact in manifest["artifact_env"]:
                env_vars.append(artifact["env_var"])
                self.assertTrue(artifact["env_var"].startswith("LIVECONV_"))
        self.assertEqual(len(env_vars), len(set(env_vars)))

    def test_all_blocker_references_resolve_within_the_pack(self) -> None:
        for manifest in self.manifests:
            blocker_ids = {item["id"] for item in manifest["blockers"]}
            referenced: set[str] = set()
            for gate in manifest["mode_gates"].values():
                referenced.update(gate["blocker_ids"])
            for item in manifest["acceptance_checklist"].values():
                referenced.update(item["blocked_by"])
            with self.subTest(pack_id=manifest["pack_id"]):
                self.assertEqual(referenced - blocker_ids, set())

    def test_candidate_specific_gates_are_frozen(self) -> None:
        manifests = {item["pack_id"]: item for item in self.manifests}
        self.assertEqual(manifests["rvc-v2"]["implementation_priority"], 1)
        self.assertIn(
            "xvc-japanese-offline",
            manifests["x-vc"]["mode_gates"]["streaming"]["blocker_ids"],
        )
        beatrice = manifests["beatrice-2"]
        self.assertEqual(
            beatrice["canonical_source_url"],
            "https://huggingface.co/fierce-cats/beatrice-trainer",
        )
        self.assertNotIn(
            "beatrice-server-permission",
            {blocker["id"] for blocker in beatrice["blockers"]},
        )
        self.assertEqual(
            beatrice["license_gate"]["inference_runtime"]["declared_license"],
            "MIT",
        )
        self.assertEqual(
            beatrice["acceptance_checklist"]["adapter_conformance"]["status"],
            "pending",
        )
        self.assertIn(
            "beatrice-quality",
            beatrice["mode_gates"]["offline"]["blocker_ids"],
        )
        self.assertEqual(manifests["openvoice-v2"]["role"], "offline_control")
        self.assertEqual(
            manifests["openvoice-v2"]["mode_gates"]["streaming"]["status"],
            "not_planned",
        )

    def test_approval_cannot_omit_immutable_identity(self) -> None:
        manifest = deepcopy(self.manifests[0])
        manifest["immutability_gate"]["status"] = "approved"
        manifest["immutability_gate"]["blocking_reasons"] = []
        with self.assertRaises(ValidationError):
            self.validator.validate(manifest)

    def test_passed_check_requires_evidence(self) -> None:
        manifest = deepcopy(self.manifests[0])
        manifest["acceptance_checklist"]["stt"]["status"] = "passed"
        with self.assertRaises(ValidationError):
            self.validator.validate(manifest)

    def test_license_approval_requires_every_component_approved(self) -> None:
        manifest = deepcopy(self.manifests[0])
        manifest["license_gate"]["overall_status"] = "approved"
        with self.assertRaises(ValidationError):
            self.validator.validate(manifest)

        for component in LICENSE_COMPONENTS:
            manifest["license_gate"][component]["status"] = "approved"
        with self.assertRaises(ValidationError):
            self.validator.validate(manifest)

        for component in LICENSE_COMPONENTS:
            item = manifest["license_gate"][component]
            item["declared_license"] = item["declared_license"] or "review-approved"
            item["evidence_urls"] = item["evidence_urls"] or [
                f"https://example.invalid/licenses/{component}"
            ]
        self.validator.validate(manifest)

    def test_immutability_approval_requires_every_artifact_identity(self) -> None:
        manifest = deepcopy(self.manifests[0])
        gate = manifest["immutability_gate"]
        gate.update(
            status="approved",
            source_revision="a" * 40,
            weight_sha256="b" * 64,
            approval_record_url="https://example.invalid/approval/rvc-v2",
            blocking_reasons=[],
        )
        with self.assertRaises(ValidationError):
            self.validator.validate(manifest)

        for index, artifact in enumerate(manifest["artifact_env"]):
            artifact["sha256"] = f"{index + 1:064x}"
            artifact["provenance_url"] = (
                f"https://example.invalid/artifacts/rvc-v2/{index}"
            )
        self.validator.validate(manifest)


if __name__ == "__main__":
    unittest.main()

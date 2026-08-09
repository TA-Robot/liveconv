from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

WORKERS = Path(__file__).resolve().parents[1]
PACKS = WORKERS / "packs"
EXPECTED_ORDER = ["rvc-v2", "x-vc", "beatrice-2", "openvoice-v2"]
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
        self.assertIn(
            "beatrice-server-permission",
            manifests["beatrice-2"]["mode_gates"]["offline"]["blocker_ids"],
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

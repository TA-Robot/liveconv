from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator
from liveconv_audio.roster import ModelRoster


def default_document() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    return json.loads(
        (root / "liveconv_audio" / "default-model-roster.json").read_text()
    )


def load_document(tmp_path: Path, document: dict[str, object]) -> ModelRoster:
    path = tmp_path / "roster.json"
    path.write_text(json.dumps(document))
    return ModelRoster.load(path)


class StubProfile:
    voice_requirement = "pretrained_voice"
    promotion = SimpleNamespace(status="approved", pack_id="rvc-v2")
    kind = "voice_conversion"
    readiness = "ready"
    streaming = True
    profile_hash = f"sha256:{'1' * 64}"
    configuration_hash = f"sha256:{'2' * 64}"

    @staticmethod
    def public_dict() -> dict[str, str]:
        return {
            "profile_id": "vc.rvc.synthetic-ja.v1",
            "profile_hash": StubProfile.profile_hash,
            "configuration_hash": StubProfile.configuration_hash,
        }


class StubRegistry:
    def __init__(self, *, selectable: bool = True) -> None:
        self.profile = StubProfile()
        self.selectable = selectable

    def get(self, profile_id: str):
        return self.profile if profile_id == "vc.rvc.synthetic-ja.v1" else None

    def get_selectable(self, profile_id: str):
        if self.selectable and profile_id == "vc.rvc.synthetic-ja.v1":
            return self.profile
        return None


def test_default_roster_is_exact_and_hash_is_deterministic(tmp_path: Path) -> None:
    first = load_document(tmp_path, default_document())
    second = load_document(tmp_path, default_document())
    assert first.roster_hash == second.roster_hash
    public = first.public_document(StubRegistry(selectable=False))
    assert [entry["model_id"] for entry in public["models"]] == [
        "rvc-v2",
        "beatrice-2",
        "x-vc",
        "openvoice-v2",
    ]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "openvoice-live"])
def test_roster_rejects_scope_and_mode_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    document = deepcopy(default_document())
    models = document["models"]
    assert isinstance(models, list)
    if mutation == "missing":
        models.pop()
    elif mutation == "duplicate":
        models[1]["model_id"] = "rvc-v2"
    else:
        models[3]["invocation_mode"] = "live"
    with pytest.raises(ValueError):
        load_document(tmp_path, document)


def test_repository_schema_rejects_duplicate_model_ids() -> None:
    root = Path(__file__).resolve().parents[3]
    schema = json.loads((root / "schemas" / "model-roster.schema.json").read_text())
    document = default_document()
    models = document["models"]
    assert isinstance(models, list)
    models[1]["model_id"] = "rvc-v2"
    assert list(Draft202012Validator(schema).iter_errors(document))


@pytest.mark.parametrize(
    ("index", "mode"),
    [(0, "buffered_end"), (3, "live")],
)
def test_repository_schema_rejects_model_mode_drift(index: int, mode: str) -> None:
    root = Path(__file__).resolve().parents[3]
    schema = json.loads((root / "schemas" / "model-roster.schema.json").read_text())
    document = default_document()
    models = document["models"]
    assert isinstance(models, list)
    models[index]["invocation_mode"] = mode
    assert list(Draft202012Validator(schema).iter_errors(document))


def test_selectable_entry_requires_frozen_exact_profile_identity(
    tmp_path: Path,
) -> None:
    document = default_document()
    models = document["models"]
    assert isinstance(models, list)
    models[0]["expected_profile_hash"] = StubProfile.profile_hash
    models[0]["expected_configuration_hash"] = StubProfile.configuration_hash
    roster = load_document(tmp_path, document)
    public = roster.public_document(StubRegistry())
    rvc = public["models"][0]
    assert rvc["execution_state"] == "live-trial"
    assert rvc["reason_code"] is None
    assert rvc["profile"]["profile_hash"] == StubProfile.profile_hash
    assert "expected_profile_hash" not in rvc

    models[0]["expected_configuration_hash"] = f"sha256:{'3' * 64}"
    mismatch = load_document(tmp_path, document).public_document(StubRegistry())
    assert mismatch["models"][0]["execution_state"] == "unavailable"
    assert mismatch["models"][0]["reason_code"] == "profile_identity_mismatch"
    assert mismatch["models"][0]["profile"] is None


def test_technical_profile_reason_is_fixed_and_safe(tmp_path: Path) -> None:
    roster = load_document(tmp_path, default_document())
    registry = StubRegistry(selectable=False)
    registry.profile.promotion = SimpleNamespace(
        status="technical_validation", pack_id="rvc-v2"
    )
    public = roster.public_document(registry)
    assert public["models"][0]["reason_code"] == "technical_opt_in_required"


def test_live_entry_rejects_a_nonstreaming_profile(tmp_path: Path) -> None:
    document = default_document()
    models = document["models"]
    assert isinstance(models, list)
    models[0]["expected_profile_hash"] = StubProfile.profile_hash
    models[0]["expected_configuration_hash"] = StubProfile.configuration_hash
    registry = StubRegistry()
    registry.profile.streaming = False
    public = load_document(tmp_path, document).public_document(registry)
    assert public["models"][0]["execution_state"] == "unavailable"
    assert public["models"][0]["reason_code"] == "profile_contract_mismatch"
    assert public["models"][0]["profile"] is None


def test_buffered_entry_accepts_an_exact_nonstreaming_profile(
    tmp_path: Path,
) -> None:
    document = default_document()
    models = document["models"]
    assert isinstance(models, list)
    profile_hash = f"sha256:{'4' * 64}"
    configuration_hash = f"sha256:{'5' * 64}"
    models[3]["expected_profile_hash"] = profile_hash
    models[3]["expected_configuration_hash"] = configuration_hash
    profile = SimpleNamespace(
        voice_requirement="pretrained_voice",
        promotion=SimpleNamespace(
            status="technical_validation", pack_id="openvoice-v2"
        ),
        kind="voice_conversion",
        readiness="ready",
        streaming=False,
        profile_hash=profile_hash,
        configuration_hash=configuration_hash,
        public_dict=lambda: {
            "profile_id": "vc.openvoice-v2.synthetic-ja.v1",
            "profile_hash": profile_hash,
            "configuration_hash": configuration_hash,
        },
    )
    registry = SimpleNamespace(
        get=lambda profile_id: (
            profile if profile_id == "vc.openvoice-v2.synthetic-ja.v1" else None
        ),
        get_selectable=lambda profile_id: (
            profile if profile_id == "vc.openvoice-v2.synthetic-ja.v1" else None
        ),
    )

    public = load_document(tmp_path, document).public_document(registry)
    openvoice = public["models"][3]
    assert openvoice["execution_state"] == "buffered-preview"
    assert openvoice["reason_code"] is None
    assert openvoice["profile"]["profile_hash"] == profile_hash


def test_model_id_rejects_an_exact_hash_profile_from_another_pack(
    tmp_path: Path,
) -> None:
    document = default_document()
    models = document["models"]
    assert isinstance(models, list)
    models[0]["expected_profile_hash"] = StubProfile.profile_hash
    models[0]["expected_configuration_hash"] = StubProfile.configuration_hash
    registry = StubRegistry()
    registry.profile.promotion = SimpleNamespace(
        status="approved", pack_id="beatrice-2"
    )
    public = load_document(tmp_path, document).public_document(registry)
    assert public["models"][0]["execution_state"] == "unavailable"
    assert public["models"][0]["reason_code"] == "profile_contract_mismatch"
    assert public["models"][0]["profile"] is None

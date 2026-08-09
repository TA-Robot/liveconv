from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from .profiles import ProfileRegistry

HashValue = Annotated[StrictStr, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
_MS2_MODEL_IDS = {"rvc-v2", "beatrice-2", "x-vc", "openvoice-v2"}


class RosterEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    model_id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    display_name: StrictStr = Field(min_length=1, max_length=80)
    profile_id: StrictStr = Field(
        pattern=r"^(test|vc|tts)\.[a-z0-9][a-z0-9.-]*\.v[0-9]+$"
    )
    invocation_mode: Literal["live", "buffered_end"]
    decision_state: Literal[
        "technical-only", "quality-failed", "unassessed", "selected"
    ]
    voice_requirement: Literal["none", "authorized_target_required", "pretrained_voice"]
    expected_profile_hash: HashValue | None
    expected_configuration_hash: HashValue | None


class RosterDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    roster_id: StrictStr = Field(pattern=r"^[a-z0-9][a-z0-9.-]{1,63}$")
    models: list[RosterEntry] = Field(min_length=4, max_length=4)


class ModelRoster:
    def __init__(self, document: RosterDocument) -> None:
        self._document = document

    @classmethod
    def load(cls, path: Path) -> ModelRoster:
        with path.open(encoding="utf-8") as stream:
            document = RosterDocument.model_validate(json.load(stream))
        model_ids = [entry.model_id for entry in document.models]
        profile_ids = [entry.profile_id for entry in document.models]
        if len(set(model_ids)) != len(model_ids):
            raise ValueError("duplicate roster model_id")
        if len(set(profile_ids)) != len(profile_ids):
            raise ValueError("duplicate roster profile_id")
        if set(model_ids) != _MS2_MODEL_IDS:
            raise ValueError("MS-2 roster must contain the exact four prepared models")
        openvoice = next(
            entry for entry in document.models if entry.model_id == "openvoice-v2"
        )
        if openvoice.invocation_mode != "buffered_end":
            raise ValueError("OpenVoice V2 must use buffered_end invocation")
        if any(
            entry.invocation_mode != "live"
            for entry in document.models
            if entry.model_id != "openvoice-v2"
        ):
            raise ValueError("RVC, Beatrice 2, and X-VC must use live invocation")
        return cls(document)

    @property
    def roster_hash(self) -> str:
        encoded = json.dumps(
            self._document.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def public_document(self, registry: ProfileRegistry) -> dict[str, object]:
        models: list[dict[str, object]] = []
        for entry in self._document.models:
            profile = registry.get(entry.profile_id)
            selectable = registry.get_selectable(entry.profile_id)
            reason_code: str | None = None
            if profile is None:
                reason_code = "profile_unavailable"
            elif (
                profile.kind != "voice_conversion"
                or profile.promotion is None
                or profile.promotion.pack_id != entry.model_id
            ):
                reason_code = "profile_contract_mismatch"
            elif profile.voice_requirement != entry.voice_requirement:
                reason_code = "profile_contract_mismatch"
            elif profile.streaming != (entry.invocation_mode == "live"):
                reason_code = "profile_contract_mismatch"
            elif selectable is None:
                promotion = profile.promotion
                if promotion is not None and promotion.status == "technical_validation":
                    reason_code = "technical_opt_in_required"
                elif profile.readiness == "loading":
                    reason_code = "profile_loading"
                else:
                    reason_code = "profile_unavailable"
            elif (
                entry.expected_profile_hash != selectable.profile_hash
                or entry.expected_configuration_hash != selectable.configuration_hash
            ):
                reason_code = "profile_identity_mismatch"

            execution_state = "unavailable"
            public_profile: dict[str, object] | None = None
            if reason_code is None and selectable is not None:
                execution_state = (
                    "live-trial"
                    if entry.invocation_mode == "live"
                    else "buffered-preview"
                )
                public_profile = selectable.public_dict()

            public_entry = entry.model_dump(
                mode="json",
                exclude={"expected_profile_hash", "expected_configuration_hash"},
            )
            models.append(
                {
                    **public_entry,
                    "execution_state": execution_state,
                    "reason_code": reason_code,
                    "profile": public_profile,
                }
            )
        return {
            "schema_version": 1,
            "roster_id": self._document.roster_id,
            "roster_hash": self.roster_hash,
            "models": models,
        }

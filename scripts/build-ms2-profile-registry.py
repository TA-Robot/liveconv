#!/usr/bin/env python3
"""Build the technical four-profile MS-2 Gateway registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = Path(tempfile.gettempdir()) / "liveconv-ms2-profile-registry.json"
PROFILE_ORDER = ("rvc-v2", "beatrice-2", "x-vc", "openvoice-v2")
ROSTER_PROFILE_IDS = {
    "rvc-v2": "vc.rvc.synthetic-ja.v1",
    "beatrice-2": "vc.beatrice.synthetic-ja.v1",
    "x-vc": "vc.x-vc.synthetic-ja.v1",
    "openvoice-v2": "vc.openvoice-v2.synthetic-ja.v1",
}
MATERIAL_PATHS = {
    "rvc-v2": "workers/adapters/rvc_v2/ms2-profile-material.json",
    "beatrice-2": "workers/adapters/beatrice_2/profile-material.json",
    "x-vc": "workers/adapters/x_vc/technical-profile.json",
    "openvoice-v2": "workers/adapters/openvoice_v2/canonical-profile.json",
}

_SECRET_KEY = re.compile(
    r"(^|[_-])(api[_-]?key|credential|password|private[_-]?key|secret|token)([_-]|$)",
    re.IGNORECASE,
)
_PRIVATE_PATH_KEY = re.compile(
    r"(^|[_-])(directory|dir|file|path|root)([_-]|$)",
    re.IGNORECASE,
)
_PATH_VALUE = re.compile(r"(?:^~?/|^\.\.?/|^[A-Za-z]:[\\/]|[\\/])")
_SECRET_VALUE = re.compile(
    r"(?:"
    r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]+|"
    r"\b(?:api[_-]?key|credential|password|secret|token)\s*=|"
    r"\b(?:sk|gh[pousr]|xox[baprs])-[A-Za-z0-9_-]{10,}"
    r")",
    re.IGNORECASE,
)


class RegistryBuildError(ValueError):
    """The reviewed material cannot produce a safe technical registry."""


RegistryValidator = Callable[[Path], None]


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryBuildError(f"cannot read JSON material: {path}") from exc
    if not isinstance(value, dict):
        raise RegistryBuildError(f"material must be an object: {path}")
    return value


def _object(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RegistryBuildError(f"{name} must be an object")
    return value


def _text(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RegistryBuildError(f"{name} must be a non-empty string")
    return value


def _integer(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RegistryBuildError(f"{name} must be an integer")
    return value


def _fields(source: Mapping[str, object], fields: tuple[str, ...]) -> dict[str, Any]:
    missing = [field for field in fields if field not in source]
    if missing:
        raise RegistryBuildError(
            f"material has required fields missing: {', '.join(missing)}"
        )
    return {field: source[field] for field in fields}


def _sha256_file(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RegistryBuildError(f"cannot read file for digest: {path}") from exc
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _endpoint(value: Path, *, model_id: str) -> Path:
    if not value.is_absolute():
        raise RegistryBuildError(f"{model_id} endpoint must be an absolute path")
    try:
        mode = value.stat().st_mode
    except OSError as exc:
        raise RegistryBuildError(f"{model_id} endpoint is unavailable") from exc
    if not value.is_file() or not mode & 0o111:
        raise RegistryBuildError(f"{model_id} endpoint must be an executable file")
    return value


def _promotion(
    *,
    model_id: str,
    expected: Mapping[str, object],
    endpoint: Path,
    repository_root: Path,
) -> dict[str, str]:
    pack_path = repository_root / "workers" / "packs" / f"{model_id}.json"
    pack = _load_object(pack_path)
    if pack.get("pack_id") != model_id:
        raise RegistryBuildError(f"{model_id} model pack ID differs")
    expected_status = _text(expected.get("status"), name=f"{model_id} status")
    expected_evidence = _text(
        expected.get("evidence_sha256"), name=f"{model_id} evidence digest"
    )
    evidence = _object(pack.get("promotion_evidence"), name=f"{model_id} pack evidence")
    if evidence.get("status") != expected_status:
        raise RegistryBuildError(f"{model_id} pack promotion status differs")
    if evidence.get("evidence_sha256") != expected_evidence:
        raise RegistryBuildError(f"{model_id} pack promotion evidence differs")
    return {
        "status": expected_status,
        "pack_id": model_id,
        "pack_sha256": _sha256_file(pack_path),
        "evidence_sha256": expected_evidence,
        "endpoint_sha256": _sha256_file(endpoint),
    }


def _runtime(
    *,
    configuration: Mapping[str, object],
    endpoint: Path,
    max_vram_mb: int,
    worker_module: str | None,
) -> dict[str, Any]:
    runtime: dict[str, Any] = {
        "adapter": "worker",
        "configuration": dict(configuration),
        "worker_endpoint": str(endpoint),
        "max_vram_mb": max_vram_mb,
    }
    if worker_module is not None:
        runtime["worker_module"] = worker_module
    return runtime


def _rvc_profile(
    material: Mapping[str, object], *, endpoint: Path, repository_root: Path
) -> dict[str, Any]:
    deployment = _object(material.get("deployment_profile"), name="RVC deployment")
    configuration = _object(
        material.get("canonical_configuration"), name="RVC configuration"
    )
    if material.get("profile_id") != ROSTER_PROFILE_IDS["rvc-v2"]:
        raise RegistryBuildError("RVC material profile ID differs from the MS-2 roster")
    if configuration.get("worker_module") != "workers.adapters.rvc_v2.worker":
        raise RegistryBuildError("RVC material worker module binding differs")
    deployment_runtime = _object(deployment.get("runtime"), name="RVC runtime")
    profile = _fields(
        deployment,
        (
            "kind",
            "readiness",
            "adapter_api_version",
            "implementation_revision",
            "weight_revision",
            "streaming",
            "cancellation",
            "input_sample_rates",
            "output_sample_rates",
            "frame_ms",
            "minimum_context_ms",
            "voice_requirement",
            "warmup_policy",
            "resource_class",
            "license_record",
            "timeouts",
        ),
    )
    profile["profile_id"] = ROSTER_PROFILE_IDS["rvc-v2"]
    profile["promotion"] = _promotion(
        model_id="rvc-v2",
        expected=_object(deployment.get("promotion"), name="RVC promotion"),
        endpoint=endpoint,
        repository_root=repository_root,
    )
    # This binding remains inside RVC's configuration to preserve its accepted
    # canonical hash. The adapter registry has an explicit compatibility path.
    profile["runtime"] = _runtime(
        configuration=configuration,
        endpoint=endpoint,
        max_vram_mb=_integer(
            deployment_runtime.get("max_vram_mb"), name="RVC maximum VRAM"
        ),
        worker_module=None,
    )
    return profile


def _beatrice_profile(
    material: Mapping[str, object], *, endpoint: Path, repository_root: Path
) -> dict[str, Any]:
    worker = _object(material.get("worker"), name="Beatrice worker")
    streaming = _object(material.get("streaming"), name="Beatrice streaming")
    evidence = _object(
        material.get("promotion_evidence"), name="Beatrice promotion evidence"
    )
    configuration = _object(
        worker.get("configuration_payload"), name="Beatrice configuration"
    )
    if material.get("model_id") != "beatrice-2":
        raise RegistryBuildError("Beatrice material model ID differs")
    return {
        "profile_id": ROSTER_PROFILE_IDS["beatrice-2"],
        "kind": "voice_conversion",
        "readiness": "ready",
        "adapter_api_version": 1,
        "implementation_revision": _text(
            worker.get("implementation_revision"),
            name="Beatrice implementation revision",
        ),
        "weight_revision": _text(
            worker.get("weight_revision"), name="Beatrice weight revision"
        ),
        "streaming": True,
        "cancellation": "cooperative",
        "input_sample_rates": [
            _integer(
                streaming.get("input_sample_rate_hz"),
                name="Beatrice input sample rate",
            )
        ],
        "output_sample_rates": [
            _integer(
                streaming.get("output_sample_rate_hz"),
                name="Beatrice output sample rate",
            )
        ],
        "frame_ms": _integer(streaming.get("frame_ms"), name="Beatrice frame size"),
        "minimum_context_ms": _integer(
            streaming.get("minimum_inference_ms"),
            name="Beatrice minimum inference time",
        ),
        "voice_requirement": "pretrained_voice",
        "warmup_policy": "lazy",
        "resource_class": "gpu",
        "license_record": (
            "Beatrice 2 technical validation only; approval, target authorization, "
            "and Japanese quality gates remain blocked."
        ),
        "promotion": _promotion(
            model_id="beatrice-2",
            expected={
                "status": evidence.get("status"),
                "evidence_sha256": evidence.get("retained_identity_evidence_sha256"),
            },
            endpoint=endpoint,
            repository_root=repository_root,
        ),
        "timeouts": {"first_output_ms": 30_000, "stall_ms": 5_000},
        "runtime": _runtime(
            configuration=configuration,
            endpoint=endpoint,
            max_vram_mb=2_048,
            worker_module=_text(worker.get("module"), name="Beatrice worker module"),
        ),
    }


def _xvc_profile(
    material: Mapping[str, object], *, endpoint: Path, repository_root: Path
) -> dict[str, Any]:
    profile_material = _object(material.get("profile"), name="X-VC profile")
    runtime_material = _object(material.get("runtime"), name="X-VC runtime")
    if profile_material.get("profile_id") != ROSTER_PROFILE_IDS["x-vc"]:
        raise RegistryBuildError(
            "X-VC material profile ID differs from the MS-2 roster"
        )
    profile = _fields(
        profile_material,
        (
            "kind",
            "readiness",
            "adapter_api_version",
            "implementation_revision",
            "weight_revision",
            "streaming",
            "cancellation",
            "input_sample_rates",
            "output_sample_rates",
            "frame_ms",
            "minimum_context_ms",
            "voice_requirement",
            "warmup_policy",
            "resource_class",
            "license_record",
            "timeouts",
        ),
    )
    profile["profile_id"] = ROSTER_PROFILE_IDS["x-vc"]
    profile["promotion"] = _promotion(
        model_id="x-vc",
        expected=_object(profile_material.get("promotion"), name="X-VC promotion"),
        endpoint=endpoint,
        repository_root=repository_root,
    )
    profile["runtime"] = _runtime(
        configuration=_object(
            runtime_material.get("configuration"), name="X-VC configuration"
        ),
        endpoint=endpoint,
        max_vram_mb=_integer(
            profile_material.get("max_vram_mb"), name="X-VC maximum VRAM"
        ),
        worker_module=_text(
            runtime_material.get("worker_module"), name="X-VC worker module"
        ),
    )
    return profile


def _openvoice_profile(
    material: Mapping[str, object], *, endpoint: Path, repository_root: Path
) -> dict[str, Any]:
    delivery = _object(material.get("delivery"), name="OpenVoice delivery")
    pack = _object(material.get("pack"), name="OpenVoice pack")
    worker = _object(material.get("trusted_worker"), name="OpenVoice worker")
    retained = _object(
        material.get("retained_repaired_worker"), name="OpenVoice retained worker"
    )
    if delivery.get("mode") != "end_buffered" or delivery.get("streaming") is not False:
        raise RegistryBuildError("OpenVoice material must remain end-buffered")
    return {
        # The material predates the fixed roster ID. Its retained configuration,
        # evidence, mode, and technical-only state remain unchanged.
        "profile_id": ROSTER_PROFILE_IDS["openvoice-v2"],
        "kind": "voice_conversion",
        "readiness": "ready",
        "adapter_api_version": 1,
        "implementation_revision": _text(
            retained.get("implementation_revision"),
            name="OpenVoice implementation revision",
        ),
        "weight_revision": _text(
            retained.get("weight_revision"), name="OpenVoice weight revision"
        ),
        "streaming": False,
        "cancellation": _text(
            delivery.get("cancellation"), name="OpenVoice cancellation"
        ),
        "input_sample_rates": [48_000],
        "output_sample_rates": [48_000],
        "frame_ms": _integer(delivery.get("frame_ms"), name="OpenVoice frame size"),
        "minimum_context_ms": _integer(
            delivery.get("minimum_context_ms"), name="OpenVoice minimum context"
        ),
        # The reviewed target reference is pre-provisioned in the isolated
        # worker environment; no caller-supplied voice ID or reference is used.
        "voice_requirement": "pretrained_voice",
        "warmup_policy": "lazy",
        "resource_class": "gpu",
        "license_record": (
            "OpenVoice V2 technical buffered preview only; approval and latency "
            "claims remain blocked."
        ),
        "promotion": _promotion(
            model_id="openvoice-v2",
            expected={
                "status": pack.get("promotion_status"),
                "evidence_sha256": pack.get("promotion_evidence_sha256"),
            },
            endpoint=endpoint,
            repository_root=repository_root,
        ),
        "timeouts": {"first_output_ms": 60_000, "stall_ms": 60_000},
        "runtime": _runtime(
            configuration=_object(
                material.get("canonical_engine_configuration"),
                name="OpenVoice configuration",
            ),
            endpoint=endpoint,
            max_vram_mb=8_192,
            worker_module=_text(
                worker.get("entrypoint_module"), name="OpenVoice module"
            ),
        ),
    }


def build_registry(
    endpoints: Mapping[str, Path],
    *,
    repository_root: Path = REPOSITORY_ROOT,
    material_paths: Mapping[str, Path] | None = None,
) -> dict[str, object]:
    """Build the frozen roster without serializing model-artifact paths or secrets."""

    if set(endpoints) != set(PROFILE_ORDER):
        raise RegistryBuildError("endpoints must contain each fixed MS-2 model ID")
    if material_paths is not None and set(material_paths) != set(PROFILE_ORDER):
        raise RegistryBuildError("material paths must contain each fixed MS-2 model ID")
    root = repository_root.resolve()
    paths = (
        {model_id: root / MATERIAL_PATHS[model_id] for model_id in PROFILE_ORDER}
        if material_paths is None
        else {model_id: Path(material_paths[model_id]) for model_id in PROFILE_ORDER}
    )
    checked_endpoints = {
        model_id: _endpoint(Path(endpoints[model_id]), model_id=model_id)
        for model_id in PROFILE_ORDER
    }
    materials = {model_id: _load_object(paths[model_id]) for model_id in PROFILE_ORDER}
    profiles = [
        _rvc_profile(
            materials["rvc-v2"],
            endpoint=checked_endpoints["rvc-v2"],
            repository_root=root,
        ),
        _beatrice_profile(
            materials["beatrice-2"],
            endpoint=checked_endpoints["beatrice-2"],
            repository_root=root,
        ),
        _xvc_profile(
            materials["x-vc"],
            endpoint=checked_endpoints["x-vc"],
            repository_root=root,
        ),
        _openvoice_profile(
            materials["openvoice-v2"],
            endpoint=checked_endpoints["openvoice-v2"],
            repository_root=root,
        ),
    ]
    document: dict[str, object] = {"schema_version": 1, "profiles": profiles}
    assert_safe_document(document)
    return document


def assert_safe_document(document: object) -> None:
    """Reject secret values and private artifact/target paths before writing."""

    def visit(value: object, *, location: str, in_configuration: bool = False) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise RegistryBuildError(f"registry key must be text: {location}")
                child_location = f"{location}.{key}"
                if _SECRET_KEY.search(key):
                    raise RegistryBuildError(
                        f"secret-like key cannot be serialized: {child_location}"
                    )
                if in_configuration and _PRIVATE_PATH_KEY.search(key):
                    raise RegistryBuildError(
                        f"private path key cannot be serialized: {child_location}"
                    )
                if key == "worker_endpoint" and re.fullmatch(
                    r"registry\.profiles\[[0-9]+\]\.runtime\.worker_endpoint",
                    child_location,
                ):
                    continue
                visit(
                    child,
                    location=child_location,
                    in_configuration=in_configuration
                    or child_location.endswith(".runtime.configuration"),
                )
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(
                    item,
                    location=f"{location}[{index}]",
                    in_configuration=in_configuration,
                )
        elif isinstance(value, str):
            if _SECRET_VALUE.search(value):
                raise RegistryBuildError(
                    f"secret-like value cannot be serialized: {location}"
                )
            if _PATH_VALUE.search(value):
                raise RegistryBuildError(
                    f"path-like value cannot be serialized: {location}"
                )

    visit(document, location="registry")


def validate_with_profile_registry(path: Path, *, repository_root: Path) -> None:
    """Load the staged output with the Gateway and the local model pack bytes."""

    audio_source = str(repository_root / "services" / "audio")
    if audio_source not in sys.path:
        sys.path.insert(0, audio_source)
    try:
        from liveconv_audio.profiles import ProfileRegistry
    except ModuleNotFoundError as exc:
        raise RegistryBuildError("Gateway ProfileRegistry is unavailable") from exc
    ProfileRegistry.load(
        path,
        allow_technical_profiles=True,
        model_pack_directory=repository_root / "workers" / "packs",
    )


def write_registry_atomically(
    path: Path,
    document: Mapping[str, object],
    *,
    validator: RegistryValidator | None = None,
) -> None:
    """Validate a same-directory temporary file before replacing ``path``."""

    assert_safe_document(document)
    destination = path.absolute()
    if destination.is_symlink():
        raise RegistryBuildError("output destination cannot be a symlink")
    if not destination.parent.is_dir():
        raise RegistryBuildError(
            f"output directory does not exist: {destination.parent}"
        )
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, ensure_ascii=True, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if validator is not None:
            try:
                validator(temporary_path)
            except RegistryBuildError:
                raise
            except Exception as exc:
                raise RegistryBuildError(
                    "Gateway ProfileRegistry rejected the assembled registry"
                ) from exc
        os.replace(temporary_path, destination)
        temporary_path = None
        descriptor = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise RegistryBuildError(f"cannot write registry: {destination}") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the technical MS-2 four-profile registry from material."
    )
    parser.add_argument("--rvc-endpoint", required=True, type=Path)
    parser.add_argument("--beatrice-endpoint", required=True, type=Path)
    parser.add_argument("--xvc-endpoint", required=True, type=Path)
    parser.add_argument("--openvoice-endpoint", required=True, type=Path)
    parser.add_argument(
        "--rvc-material",
        type=Path,
        default=REPOSITORY_ROOT / MATERIAL_PATHS["rvc-v2"],
    )
    parser.add_argument(
        "--beatrice-material",
        type=Path,
        default=REPOSITORY_ROOT / MATERIAL_PATHS["beatrice-2"],
    )
    parser.add_argument(
        "--x-vc-material",
        type=Path,
        default=REPOSITORY_ROOT / MATERIAL_PATHS["x-vc"],
    )
    parser.add_argument(
        "--openvoice-material",
        type=Path,
        default=REPOSITORY_ROOT / MATERIAL_PATHS["openvoice-v2"],
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    parsed = _arguments(arguments)
    output = parsed.output or DEFAULT_OUTPUT_PATH
    if parsed.output is None and output.is_relative_to(REPOSITORY_ROOT):
        print(
            "build-ms2-profile-registry: default output must be outside the repository",
            file=sys.stderr,
        )
        return 1
    try:
        document = build_registry(
            {
                "rvc-v2": parsed.rvc_endpoint,
                "beatrice-2": parsed.beatrice_endpoint,
                "x-vc": parsed.xvc_endpoint,
                "openvoice-v2": parsed.openvoice_endpoint,
            },
            material_paths={
                "rvc-v2": parsed.rvc_material,
                "beatrice-2": parsed.beatrice_material,
                "x-vc": parsed.x_vc_material,
                "openvoice-v2": parsed.openvoice_material,
            },
        )
        write_registry_atomically(
            output,
            document,
            validator=lambda candidate: validate_with_profile_registry(
                candidate, repository_root=REPOSITORY_ROOT
            ),
        )
    except RegistryBuildError as exc:
        print(f"build-ms2-profile-registry: {exc}", file=sys.stderr)
        return 1
    print(f"wrote MS-2 profile registry: {output.absolute()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

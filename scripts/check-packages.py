#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILD_TIMEOUT_SECONDS = 120
COMMAND_OUTPUT_LIMIT = 12_000
MAX_SOURCE_FILES = 10_000
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


class PackageCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class PackageSpec:
    distribution: str
    project_dir: Path
    import_name: str
    required_wheel_members: tuple[str, ...]
    required_sdist_members: tuple[str, ...]
    smoke_resources: tuple[str, ...] = ()


def _source_members(package: str, *resources: str) -> tuple[str, ...]:
    return ("pyproject.toml", f"{package}/__init__.py", *resources)


EVALUATION_SCHEMAS = (
    "aggregate-report.schema.json",
    "fixture-manifest.schema.json",
    "render-report.schema.json",
    "speaker-lane.schema.json",
    "streaming-lane.schema.json",
)
WORKER_PACKS = ("beatrice-2.json", "openvoice-v2.json", "rvc-v2.json", "x-vc.json")

PACKAGE_SPECS = (
    PackageSpec(
        distribution="liveconv-protocol",
        project_dir=Path("packages/protocol"),
        import_name="liveconv_protocol",
        required_wheel_members=("liveconv_protocol/__init__.py",),
        required_sdist_members=_source_members("liveconv_protocol"),
    ),
    PackageSpec(
        distribution="liveconv-evaluation",
        project_dir=Path("packages/evaluation"),
        import_name="liveconv_evaluation",
        required_wheel_members=(
            "liveconv_evaluation/__init__.py",
            "liveconv_evaluation/py.typed",
            "liveconv_evaluation/authorizations/reviewed-targets.json",
            *(f"liveconv_evaluation/schemas/{name}" for name in EVALUATION_SCHEMAS),
        ),
        required_sdist_members=_source_members(
            "src/liveconv_evaluation",
            "src/liveconv_evaluation/py.typed",
            "src/liveconv_evaluation/authorizations/reviewed-targets.json",
            *(f"schemas/{name}" for name in EVALUATION_SCHEMAS),
        ),
        smoke_resources=(
            "py.typed",
            "authorizations/reviewed-targets.json",
            *(f"schemas/{name}" for name in EVALUATION_SCHEMAS),
        ),
    ),
    PackageSpec(
        distribution="liveconv-stt",
        project_dir=Path("packages/stt"),
        import_name="liveconv_stt",
        required_wheel_members=(
            "liveconv_stt/__init__.py",
            "liveconv_stt/py.typed",
            "liveconv_stt/real-run-requirements.txt",
            "liveconv_stt/schemas/stt-bundle.schema.json",
        ),
        required_sdist_members=_source_members(
            "src/liveconv_stt",
            "src/liveconv_stt/py.typed",
            "src/liveconv_stt/real-run-requirements.txt",
            "src/liveconv_stt/schemas/stt-bundle.schema.json",
        ),
        smoke_resources=(
            "py.typed",
            "real-run-requirements.txt",
            "schemas/stt-bundle.schema.json",
        ),
    ),
    PackageSpec(
        distribution="liveconv-speaker",
        project_dir=Path("packages/speaker"),
        import_name="liveconv_speaker",
        required_wheel_members=(
            "liveconv_speaker/__init__.py",
            "liveconv_speaker/py.typed",
            "liveconv_speaker/authorizations/reviewed-targets.json",
            "liveconv_speaker/runtime-requirements.txt",
            "liveconv_speaker/schemas/speaker-evidence.schema.json",
        ),
        required_sdist_members=_source_members(
            "src/liveconv_speaker",
            "src/liveconv_speaker/py.typed",
            "src/liveconv_speaker/authorizations/reviewed-targets.json",
            "src/liveconv_speaker/runtime-requirements.txt",
            "src/liveconv_speaker/schemas/speaker-evidence.schema.json",
        ),
        smoke_resources=(
            "py.typed",
            "authorizations/reviewed-targets.json",
            "runtime-requirements.txt",
            "schemas/speaker-evidence.schema.json",
        ),
    ),
    PackageSpec(
        distribution="liveconv-audio",
        project_dir=Path("services/audio"),
        import_name="liveconv_audio",
        required_wheel_members=(
            "liveconv_audio/__init__.py",
            "liveconv_audio/default-model-profiles.json",
            "liveconv_audio/default-model-roster.json",
        ),
        required_sdist_members=_source_members(
            "liveconv_audio",
            "liveconv_audio/default-model-profiles.json",
            "liveconv_audio/default-model-roster.json",
        ),
        smoke_resources=("default-model-profiles.json", "default-model-roster.json"),
    ),
    PackageSpec(
        distribution="liveconv-worker-runtime",
        project_dir=Path("workers"),
        import_name="workers",
        required_wheel_members=(
            "workers/__init__.py",
            "workers/model-pack.schema.json",
            *(f"workers/packs/{name}" for name in WORKER_PACKS),
            "workers/adapters/beatrice_2/requirements-runtime.lock.txt",
            "workers/adapters/beatrice_2/requirements-runtime.txt",
            "workers/adapters/openvoice_v2/requirements-runtime.lock",
            "workers/adapters/openvoice_v2/requirements-runtime.txt",
            "workers/adapters/rvc_v2/requirements-runtime.lock",
            "workers/adapters/rvc_v2/requirements-runtime.txt",
            "workers/adapters/x_vc/requirements-runtime.lock",
            "workers/adapters/x_vc/requirements-runtime.txt",
        ),
        required_sdist_members=(
            "pyproject.toml",
            "__init__.py",
            "model-pack.schema.json",
            *(f"packs/{name}" for name in WORKER_PACKS),
            "adapters/beatrice_2/requirements-runtime.lock.txt",
            "adapters/beatrice_2/requirements-runtime.txt",
            "adapters/openvoice_v2/requirements-runtime.lock",
            "adapters/openvoice_v2/requirements-runtime.txt",
            "adapters/rvc_v2/requirements-runtime.lock",
            "adapters/rvc_v2/requirements-runtime.txt",
            "adapters/x_vc/requirements-runtime.lock",
            "adapters/x_vc/requirements-runtime.txt",
        ),
        smoke_resources=(
            "model-pack.schema.json",
            *(f"packs/{name}" for name in WORKER_PACKS),
            "adapters/beatrice_2/requirements-runtime.lock.txt",
            "adapters/beatrice_2/requirements-runtime.txt",
            "adapters/openvoice_v2/requirements-runtime.lock",
            "adapters/openvoice_v2/requirements-runtime.txt",
            "adapters/rvc_v2/requirements-runtime.lock",
            "adapters/rvc_v2/requirements-runtime.txt",
            "adapters/x_vc/requirements-runtime.lock",
            "adapters/x_vc/requirements-runtime.txt",
        ),
    ),
    PackageSpec(
        distribution="liveconv-router-experiment",
        project_dir=Path("experiments/EXP-002-remote-router/runner"),
        import_name="liveconv_router_experiment",
        required_wheel_members=(
            "liveconv_router_experiment/__init__.py",
            "liveconv_router_experiment/trace.schema.json",
        ),
        required_sdist_members=_source_members(
            "src/liveconv_router_experiment",
            "src/liveconv_router_experiment/trace.schema.json",
        ),
        smoke_resources=("trace.schema.json",),
    ),
    PackageSpec(
        distribution="liveconv-real-model-route",
        project_dir=Path("experiments/EXP-003-real-model-route"),
        import_name="liveconv_real_model_route",
        required_wheel_members=(
            "liveconv_real_model_route/__init__.py",
            "liveconv_real_model_route/trace.schema.json",
        ),
        required_sdist_members=_source_members(
            "src/liveconv_real_model_route",
            "src/liveconv_real_model_route/trace.schema.json",
            "experiment.json",
        ),
        smoke_resources=("trace.schema.json",),
    ),
    PackageSpec(
        distribution="liveconv-exp004-rvc-gateway-smoke",
        project_dir=Path("experiments/EXP-004-rvc-gateway-smoke"),
        import_name="liveconv_exp004_rvc_gateway_smoke",
        required_wheel_members=(
            "liveconv_exp004_rvc_gateway_smoke/__init__.py",
            "liveconv_exp004_rvc_gateway_smoke/trace.schema.json",
        ),
        required_sdist_members=_source_members(
            "src/liveconv_exp004_rvc_gateway_smoke",
            "src/liveconv_exp004_rvc_gateway_smoke/trace.schema.json",
            "experiment.json",
        ),
        smoke_resources=("trace.schema.json",),
    ),
    PackageSpec(
        distribution="liveconv-exp005-extension-multimodel-mvp",
        project_dir=Path("experiments/EXP-005-extension-multimodel-mvp"),
        import_name="liveconv_exp005_extension_multimodel_mvp",
        required_wheel_members=(
            "liveconv_exp005_extension_multimodel_mvp/__init__.py",
            "liveconv_exp005_extension_multimodel_mvp/report.schema.json",
        ),
        required_sdist_members=_source_members(
            "src/liveconv_exp005_extension_multimodel_mvp",
            "src/liveconv_exp005_extension_multimodel_mvp/report.schema.json",
            "experiment.json",
            "fixtures/four-model-roster.json",
            "fixtures/operator-plan.json",
        ),
        smoke_resources=("report.schema.json",),
    ),
)


def build_environment(temporary_home: Path) -> dict[str, str]:
    environment = {
        "HOME": str(temporary_home),
        "TMPDIR": str(temporary_home),
        "UV_OFFLINE": "1",
        "UV_NO_PROGRESS": "1",
        "PIP_NO_INDEX": "1",
        "PYTHONNOUSERSITE": "1",
    }
    for name in ("PATH", "SYSTEMROOT", "LANG", "LC_ALL"):
        if value := os.environ.get(name):
            environment[name] = value
    return environment


def _run(
    arguments: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: int = BUILD_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            arguments,
            cwd=cwd,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise PackageCheckError(
            f"command timed out after {timeout}s: {' '.join(arguments[:3])}"
        ) from error
    if result.returncode:
        output = (result.stdout + result.stderr)[-COMMAND_OUTPUT_LIMIT:]
        raise PackageCheckError(
            f"command failed ({result.returncode}): {' '.join(arguments[:3])}\n{output}"
        )
    return result


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def stage_project(repository: Path, project_dir: Path, destination: Path) -> Path:
    repository = repository.resolve()
    source_root = (repository / project_dir).resolve()
    if not _is_relative_to(source_root, repository) or not source_root.is_dir():
        raise PackageCheckError(f"invalid package source directory: {project_dir}")

    git = shutil.which("git")
    if git is None:
        raise PackageCheckError(
            "git is required to enumerate non-ignored package sources"
        )
    result = _run(
        [
            git,
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            project_dir.as_posix(),
        ],
        cwd=repository,
        environment=build_environment(destination.parent),
        timeout=15,
    )
    relative_files = [Path(value) for value in result.stdout.split("\0") if value]
    if not relative_files:
        raise PackageCheckError(f"no package source files found for {project_dir}")
    if len(relative_files) > MAX_SOURCE_FILES:
        raise PackageCheckError(f"too many package source files for {project_dir}")

    destination.mkdir(parents=True, exist_ok=False)
    total_bytes = 0
    for relative_file in relative_files:
        source = repository / relative_file
        if not source.is_file():
            continue
        if source.is_symlink():
            raise PackageCheckError(
                f"package source symlinks are not allowed: {relative_file}"
            )
        resolved = source.resolve()
        if not _is_relative_to(resolved, source_root):
            raise PackageCheckError(
                f"package source escaped its project: {relative_file}"
            )
        total_bytes += resolved.stat().st_size
        if total_bytes > MAX_SOURCE_BYTES:
            raise PackageCheckError(
                f"package source is larger than the bound: {project_dir}"
            )
        target = destination / resolved.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved, target)

    if not (destination / "pyproject.toml").is_file():
        raise PackageCheckError(f"staged package has no pyproject.toml: {project_dir}")
    return destination


def validate_archive_members(
    package: PackageSpec,
    kind: Literal["wheel", "sdist"],
    members: set[str],
) -> None:
    if kind == "wheel":
        required = set(package.required_wheel_members)
        installed_members = set(members)
        for member in members:
            parts = PurePosixPath(member).parts
            if (
                len(parts) > 2
                and parts[0].endswith(".data")
                and parts[1] in {"data", "purelib", "platlib"}
            ):
                installed_members.add(PurePosixPath(*parts[2:]).as_posix())
        members = installed_members
    else:
        roots = {PurePosixPath(member).parts[0] for member in members if "/" in member}
        if len(roots) != 1:
            raise PackageCheckError(
                f"{package.distribution} sdist must have one archive root, "
                f"found {len(roots)}"
            )
        root = roots.pop()
        required = {f"{root}/{member}" for member in package.required_sdist_members}
    missing = sorted(required - members)
    if missing:
        raise PackageCheckError(
            f"{package.distribution} {kind} is missing required members: "
            + ", ".join(missing)
        )


def _validated_member_name(name: str, archive: Path) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise PackageCheckError(f"unsafe member in {archive.name}: {name}")
    return path.as_posix().rstrip("/")


def inspect_wheel(package: PackageSpec, archive: Path) -> None:
    with zipfile.ZipFile(archive) as wheel:
        infos = wheel.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise PackageCheckError(f"too many members in {archive.name}")
        if sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES:
            raise PackageCheckError(f"expanded wheel is too large: {archive.name}")
        members = {
            _validated_member_name(info.filename, archive)
            for info in infos
            if not info.is_dir()
        }
    validate_archive_members(package, "wheel", members)


def inspect_sdist(package: PackageSpec, archive: Path) -> None:
    with tarfile.open(archive, mode="r:gz") as sdist:
        infos = sdist.getmembers()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise PackageCheckError(f"too many members in {archive.name}")
        if sum(info.size for info in infos if info.isfile()) > MAX_ARCHIVE_BYTES:
            raise PackageCheckError(f"expanded sdist is too large: {archive.name}")
        if any(not (info.isfile() or info.isdir()) for info in infos):
            raise PackageCheckError(
                f"links or special files are not allowed in {archive.name}"
            )
        members = {
            _validated_member_name(info.name, archive)
            for info in infos
            if info.isfile()
        }
    validate_archive_members(package, "sdist", members)


def build_package(
    uv: str,
    package: PackageSpec,
    source: Path,
    output: Path,
    environment: dict[str, str],
) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=False)
    _run(
        [
            uv,
            "build",
            "--offline",
            "--no-cache",
            "--no-build-isolation",
            "--no-build-logs",
            "--out-dir",
            str(output),
            str(source),
        ],
        cwd=output.parent,
        environment=environment,
    )
    wheels = sorted(output.glob("*.whl"))
    sdists = sorted(output.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise PackageCheckError(
            f"{package.distribution} produced {len(wheels)} wheels "
            f"and {len(sdists)} sdists"
        )
    inspect_wheel(package, wheels[0])
    inspect_sdist(package, sdists[0])
    return wheels[0], sdists[0]


SMOKE_PROGRAM = r"""
import importlib
import importlib.resources
import hashlib
import json
import sys
from pathlib import Path

site = Path(sys.argv[1]).resolve()
specs = json.loads(sys.argv[2])
sys.path.insert(0, str(site))
for spec in specs:
    distribution = spec["distribution"]
    module = importlib.import_module(spec["import_name"])
    origin = Path(module.__file__).resolve()
    if not origin.is_relative_to(site):
        raise RuntimeError(f"{distribution} imported outside isolated site: {origin}")
    root = importlib.resources.files(spec["import_name"])
    for resource_name in spec["resources"]:
        resource = root.joinpath(*resource_name.split("/"))
        if not resource.is_file():
            raise RuntimeError(f"{distribution} resource is missing: {resource_name}")
        data = resource.read_bytes()
        if len(data) > 4 * 1024 * 1024 or (not data and resource_name != "py.typed"):
            raise RuntimeError(
                f"{distribution} resource size is invalid: {resource_name}"
            )
        if resource_name.endswith(".json"):
            json.loads(data)
        if resource_name == "authorizations/reviewed-targets.json":
            if distribution == "liveconv-evaluation":
                anchor_module = importlib.import_module("liveconv_evaluation.external")
            elif distribution == "liveconv-speaker":
                anchor_module = importlib.import_module(
                    "liveconv_speaker.authorization"
                )
            else:
                raise RuntimeError(
                    f"unexpected reviewed-target registry owner: {distribution}"
                )
            expected = anchor_module.REVIEWED_TARGET_REGISTRY_SHA256
            actual = hashlib.sha256(data).hexdigest()
            if actual != expected:
                raise RuntimeError(
                    f"{distribution} reviewed-target registry anchor differs"
                )
"""


def smoke_installed_packages(
    site: Path, packages: tuple[PackageSpec, ...], working_directory: Path
) -> None:
    working_directory.mkdir(parents=True, exist_ok=False)
    manifest = json.dumps(
        [
            {
                "distribution": package.distribution,
                "import_name": package.import_name,
                "resources": package.smoke_resources,
            }
            for package in packages
        ],
        separators=(",", ":"),
    )
    try:
        _run(
            [sys.executable, "-I", "-c", SMOKE_PROGRAM, str(site), manifest],
            cwd=working_directory,
            environment=build_environment(working_directory),
            timeout=60,
        )
    except PackageCheckError as error:
        raise PackageCheckError(f"isolated wheel smoke failed: {error}") from error


def check_packages(repository: Path = REPOSITORY_ROOT) -> None:
    repository = repository.resolve()
    temporary_parent = Path(tempfile.gettempdir()).resolve()
    if _is_relative_to(temporary_parent, repository):
        raise PackageCheckError("temporary build output must be outside the repository")
    uv = shutil.which("uv")
    if uv is None:
        raise PackageCheckError("uv is required for package builds")

    with tempfile.TemporaryDirectory(prefix="liveconv-package-check-") as value:
        build_root = Path(value).resolve()
        if _is_relative_to(build_root, repository):
            raise PackageCheckError(
                "temporary build output must be outside the repository"
            )
        environment = build_environment(build_root / "home")
        Path(environment["HOME"]).mkdir()
        wheels: list[Path] = []
        for package in PACKAGE_SPECS:
            label = package.distribution.replace("liveconv-", "")
            source = stage_project(
                repository, package.project_dir, build_root / "sources" / label
            )
            wheel, _ = build_package(
                uv, package, source, build_root / "dist" / label, environment
            )
            wheels.append(wheel)
            print(f"package-check: built and inspected {package.distribution}")

        site = build_root / "isolated-site"
        _run(
            [
                uv,
                "pip",
                "install",
                "--offline",
                "--no-cache",
                "--no-deps",
                "--target",
                str(site),
                *(str(wheel) for wheel in wheels),
            ],
            cwd=build_root,
            environment=environment,
        )
        smoke_installed_packages(site, PACKAGE_SPECS, build_root / "smoke-cwd")
        print("package-check: isolated wheel imports and resources passed")


def main() -> int:
    try:
        check_packages()
    except PackageCheckError as error:
        print(f"package-check: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

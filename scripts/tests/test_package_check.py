from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "check-packages.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_packages", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_covers_every_public_workspace_package() -> None:
    checker = load_checker()

    assert {spec.project_dir.as_posix() for spec in checker.PACKAGE_SPECS} == {
        "experiments/EXP-002-remote-router/runner",
        "experiments/EXP-003-real-model-route",
        "experiments/EXP-004-rvc-gateway-smoke",
        "experiments/EXP-005-extension-multimodel-mvp",
        "packages/evaluation",
        "packages/protocol",
        "packages/speaker",
        "packages/stt",
        "services/audio",
        "workers",
    }
    assert len({spec.distribution for spec in checker.PACKAGE_SPECS}) == 10
    assert len({spec.import_name for spec in checker.PACKAGE_SPECS}) == 10


def test_manifest_requires_runtime_schemas_locks_profiles_and_packs() -> None:
    checker = load_checker()
    wheel_members = {
        member
        for spec in checker.PACKAGE_SPECS
        for member in spec.required_wheel_members
    }

    assert {
        "liveconv_audio/default-model-profiles.json",
        "liveconv_audio/default-model-roster.json",
        "liveconv_evaluation/authorizations/reviewed-targets.json",
        "liveconv_evaluation/schemas/render-report.schema.json",
        "liveconv_real_model_route/trace.schema.json",
        "liveconv_exp004_rvc_gateway_smoke/trace.schema.json",
        "liveconv_exp005_extension_multimodel_mvp/report.schema.json",
        "liveconv_router_experiment/trace.schema.json",
        "liveconv_speaker/runtime-requirements.txt",
        "liveconv_speaker/authorizations/reviewed-targets.json",
        "liveconv_speaker/schemas/speaker-evidence.schema.json",
        "liveconv_stt/real-run-requirements.txt",
        "liveconv_stt/schemas/stt-bundle.schema.json",
        "workers/adapters/beatrice_2/requirements-runtime.lock.txt",
        "workers/adapters/openvoice_v2/requirements-runtime.lock",
        "workers/adapters/rvc_v2/requirements-runtime.lock",
        "workers/adapters/x_vc/requirements-runtime.lock",
        "workers/adapters/x_vc/requirements-runtime.txt",
        "workers/model-pack.schema.json",
        "workers/packs/beatrice-2.json",
        "workers/packs/openvoice-v2.json",
        "workers/packs/rvc-v2.json",
        "workers/packs/x-vc.json",
    } <= wheel_members

    sdist_members = {
        (spec.distribution, member)
        for spec in checker.PACKAGE_SPECS
        for member in spec.required_sdist_members
    }
    smoke_resources = {
        (spec.distribution, resource)
        for spec in checker.PACKAGE_SPECS
        for resource in spec.smoke_resources
    }
    assert {
        (
            "liveconv-evaluation",
            "src/liveconv_evaluation/authorizations/reviewed-targets.json",
        ),
        (
            "liveconv-speaker",
            "src/liveconv_speaker/authorizations/reviewed-targets.json",
        ),
        ("liveconv-worker-runtime", "adapters/x_vc/requirements-runtime.lock"),
        ("liveconv-worker-runtime", "adapters/x_vc/requirements-runtime.txt"),
    } <= sdist_members
    assert {
        ("liveconv-evaluation", "authorizations/reviewed-targets.json"),
        ("liveconv-speaker", "authorizations/reviewed-targets.json"),
        ("liveconv-worker-runtime", "adapters/x_vc/requirements-runtime.lock"),
        ("liveconv-worker-runtime", "adapters/x_vc/requirements-runtime.txt"),
    } <= smoke_resources


def test_installed_smoke_binds_both_reviewed_target_registries_to_code() -> None:
    checker = load_checker()

    assert "liveconv_evaluation.external" in checker.SMOKE_PROGRAM
    assert "liveconv_speaker.authorization" in checker.SMOKE_PROGRAM
    assert "REVIEWED_TARGET_REGISTRY_SHA256" in checker.SMOKE_PROGRAM
    assert "hashlib.sha256(data).hexdigest()" in checker.SMOKE_PROGRAM


def test_archive_validation_reports_the_package_kind_and_missing_members() -> None:
    checker = load_checker()
    package = next(
        spec for spec in checker.PACKAGE_SPECS if spec.distribution == "liveconv-audio"
    )

    with pytest.raises(checker.PackageCheckError) as error:
        checker.validate_archive_members(
            package, "wheel", {"liveconv_audio/__init__.py"}
        )

    assert "liveconv-audio wheel" in str(error.value)
    assert "liveconv_audio/default-model-profiles.json" in str(error.value)


def test_sdist_validation_accepts_a_single_archive_prefix() -> None:
    checker = load_checker()
    package = next(
        spec
        for spec in checker.PACKAGE_SPECS
        if spec.distribution == "liveconv-protocol"
    )
    members = {
        f"liveconv_protocol-0.1.0/{member}" for member in package.required_sdist_members
    }

    checker.validate_archive_members(package, "sdist", members)


def test_wheel_validation_accepts_the_standard_data_install_scheme() -> None:
    checker = load_checker()
    package = next(
        spec
        for spec in checker.PACKAGE_SPECS
        if spec.distribution == "liveconv-evaluation"
    )
    members = {
        member
        if not member.startswith("liveconv_evaluation/schemas/")
        else f"liveconv_evaluation-0.1.0.data/data/{member}"
        for member in package.required_wheel_members
    }

    checker.validate_archive_members(package, "wheel", members)


def test_build_environment_drops_credentials_and_forces_offline_temp_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checker = load_checker()
    monkeypatch.setenv("LIVECONV_API_TOKEN", "must-not-leak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-leak")
    monkeypatch.setenv("PATH", os.environ["PATH"])

    environment = checker.build_environment(tmp_path)

    assert "LIVECONV_API_TOKEN" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert environment["HOME"] == str(tmp_path)
    assert environment["TMPDIR"] == str(tmp_path)
    assert environment["UV_OFFLINE"] == "1"
    assert environment["PIP_NO_INDEX"] == "1"


def test_staging_copies_nonignored_sources_without_repository_artifacts(
    tmp_path: Path,
) -> None:
    checker = load_checker()
    repository = tmp_path / "repository"
    project = repository / "package"
    project.mkdir(parents=True)
    (repository / ".gitignore").write_text("*.ignored\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (project / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project / "artifact.ignored").write_text("do not stage\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", repository], check=True)
    subprocess.run(
        ["git", "-C", repository, "add", ".gitignore", "package/pyproject.toml"],
        check=True,
    )

    staged = checker.stage_project(repository, Path("package"), tmp_path / "staging")

    assert (staged / "pyproject.toml").is_file()
    assert (staged / "module.py").is_file()
    assert not (staged / "artifact.ignored").exists()


def test_smoke_imports_and_reads_resources_only_from_isolated_site(
    tmp_path: Path,
) -> None:
    checker = load_checker()
    site = tmp_path / "site"
    package_dir = site / "sample_package"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("VALUE = 7\n", encoding="utf-8")
    (package_dir / "resource.json").write_text(
        json.dumps({"schema_version": 1}), encoding="utf-8"
    )
    spec = checker.PackageSpec(
        distribution="sample-package",
        project_dir=Path("sample"),
        import_name="sample_package",
        required_wheel_members=(
            "sample_package/__init__.py",
            "sample_package/resource.json",
        ),
        required_sdist_members=("pyproject.toml",),
        smoke_resources=("resource.json",),
    )

    checker.smoke_installed_packages(
        site, (spec,), tmp_path / "isolated-working-directory"
    )


def test_smoke_accepts_an_empty_pep561_marker(tmp_path: Path) -> None:
    checker = load_checker()
    site = tmp_path / "site"
    package_dir = site / "sample_package"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("VALUE = 7\n", encoding="utf-8")
    (package_dir / "py.typed").touch()
    spec = checker.PackageSpec(
        distribution="sample-package",
        project_dir=Path("sample"),
        import_name="sample_package",
        required_wheel_members=(
            "sample_package/__init__.py",
            "sample_package/py.typed",
        ),
        required_sdist_members=("pyproject.toml",),
        smoke_resources=("py.typed",),
    )

    checker.smoke_installed_packages(
        site, (spec,), tmp_path / "isolated-working-directory"
    )


def test_smoke_fails_when_a_declared_resource_is_missing(tmp_path: Path) -> None:
    checker = load_checker()
    site = tmp_path / "site"
    package_dir = site / "sample_package"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("VALUE = 7\n", encoding="utf-8")
    spec = checker.PackageSpec(
        distribution="sample-package",
        project_dir=Path("sample"),
        import_name="sample_package",
        required_wheel_members=("sample_package/__init__.py",),
        required_sdist_members=("pyproject.toml",),
        smoke_resources=("missing.json",),
    )

    with pytest.raises(checker.PackageCheckError, match="sample-package resource"):
        checker.smoke_installed_packages(
            site, (spec,), tmp_path / "isolated-working-directory"
        )

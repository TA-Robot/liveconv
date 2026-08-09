"""Content hashing for local model directories."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from .errors import ArtifactVerificationError

MODEL_TREE_DIGEST_REVISION = "liveconv-model-tree-sha256-v1"


def sha256_model_tree(path: str | Path) -> str:
    """Hash sorted relative names, sizes, and content of a local model tree."""

    root = Path(path)
    try:
        if root.is_symlink() or not root.is_dir():
            raise ArtifactVerificationError("model artifact must be a local directory")
        entries = sorted(
            root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
        )
    except ArtifactVerificationError:
        raise
    except OSError:
        raise ArtifactVerificationError(
            "model artifact could not be inspected"
        ) from None

    files: list[Path] = []
    for entry in entries:
        try:
            if entry.is_symlink():
                raise ArtifactVerificationError(
                    "model artifact must not contain symlinks"
                )
            if entry.is_file():
                files.append(entry)
            elif not entry.is_dir():
                raise ArtifactVerificationError(
                    "model artifact contains a non-regular entry"
                )
        except ArtifactVerificationError:
            raise
        except OSError:
            raise ArtifactVerificationError(
                "model artifact could not be inspected"
            ) from None
    if not files:
        raise ArtifactVerificationError("model artifact directory must contain files")

    digest = hashlib.sha256()
    digest.update((MODEL_TREE_DIGEST_REVISION + "\0").encode())
    try:
        for file_path in files:
            relative = file_path.relative_to(root).as_posix().encode("utf-8")
            size = file_path.stat().st_size
            digest.update(b"F\0")
            digest.update(relative)
            digest.update(b"\0")
            digest.update(str(size).encode("ascii"))
            digest.update(b"\0")
            with file_path.open("rb") as source:
                while block := source.read(1024 * 1024):
                    digest.update(block)
    except OSError:
        raise ArtifactVerificationError("model artifact could not be hashed") from None
    return digest.hexdigest()


def verify_model_tree(path: str | Path, expected_sha256: str) -> str:
    if len(expected_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in expected_sha256
    ):
        raise ArtifactVerificationError(
            "expected model digest must be lowercase SHA-256"
        )
    actual = sha256_model_tree(path)
    if not hmac.compare_digest(actual, expected_sha256):
        raise ArtifactVerificationError("local model artifact digest does not match")
    return actual

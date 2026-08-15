#!/usr/bin/env python3
"""CPU-only tests for the EXP-346 admission boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("run.py")
SPEC = importlib.util.spec_from_file_location("exp346_runner", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


def wav_bytes(*, sample_rate: int = 48_000, channels: int = 1, frames: int = 4) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".wav") as temporary:
        with wave.open(temporary, "wb") as stream:
            stream.setnchannels(channels)
            stream.setsampwidth(2)
            stream.setframerate(sample_rate)
            stream.writeframes(b"\x01\x00" * frames * channels)
        temporary.flush()
        return Path(temporary.name).read_bytes()


class Exp346RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.member = "ITAcorpus_amitaro_runrun/emotion/48k/EMOTION100_001.wav"
        self.payload = wav_bytes()
        self.manifest_body = {
            "kind": "liveconv-xvc-human-paired-manifest",
            "schema_version": 1,
            "style": "runrun",
            "sources": {
                "target_archive": {
                    "member_prefix": RUN.EXPECTED_MEMBER_PREFIX,
                    "sha256": RUN.EXPECTED_ARCHIVE_SHA256,
                }
            },
            "split_counts": {"train": 1, "validation": 0, "heldout": 0},
            "rows": [
                {
                    "row_id": "ITA:EMOTION100_001",
                    "utterance_id": "EMOTION100_001",
                    "split": "train",
                    "target_wav": {
                        "archive_member": self.member,
                        "sha256": hashlib.sha256(self.payload).hexdigest(),
                        "frames": 4,
                        "sample_rate_hz": 48_000,
                    },
                }
            ],
        }
        self.document = dict(self.manifest_body)
        self.document["manifest_sha256"] = RUN.sha256_bytes(RUN.canonical_json(self.manifest_body))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def archive(self, payload: bytes | None = None) -> Path:
        archive_path = self.root / "targets.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(self.member, self.payload if payload is None else payload)
        return archive_path

    def policy(self):
        return mock.patch.multiple(
            RUN,
            EXPECTED_MANIFEST_SHA256=self.document["manifest_sha256"],
            EXPECTED_ARCHIVE_SHA256=RUN.sha256_file(self.archive()),
            EXPECTED_SPLIT_COUNTS={"train": 1, "validation": 0, "heldout": 0},
        )

    def test_tiny_manifest_and_zip_extract_only_train_speaker(self) -> None:
        archive = self.archive()
        archive_sha = RUN.sha256_file(archive)
        self.document["sources"]["target_archive"]["sha256"] = archive_sha
        body = dict(self.document)
        body.pop("manifest_sha256")
        self.document["manifest_sha256"] = RUN.sha256_bytes(RUN.canonical_json(body))
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(json.dumps(self.document), encoding="utf-8")
        with self.policy():
            loaded = RUN.load_manifest(manifest_path)
            receipt = RUN.materialize_train_dataset(loaded, archive, self.root / "dataset")
        output = self.root / "dataset" / "amitaro" / "EMOTION100_001.wav"
        self.assertTrue(output.is_file())
        self.assertEqual(output.read_bytes(), self.payload)
        self.assertEqual(receipt["count"], 1)
        self.assertEqual(receipt["records"][0]["split"], "train")
        self.assertEqual(list((self.root / "dataset").iterdir()), [self.root / "dataset" / "amitaro"])

    def test_non_mono_or_wrong_rate_is_rejected_without_third_party_audio(self) -> None:
        with self.assertRaises(RUN.RunnerError), mock.patch.object(RUN, "SAMPLE_RATE", 48_000):
            RUN.validate_wav_bytes(
                wav_bytes(sample_rate=44_100), label="fixture", expected_frames=4
            )
        with self.assertRaises(RUN.RunnerError):
            RUN.validate_wav_bytes(wav_bytes(channels=2), label="fixture", expected_frames=4)

    def test_train_reuses_and_revalidates_prepare_materialization(self) -> None:
        archive = self.archive()
        archive_sha = RUN.sha256_file(archive)
        self.document["sources"]["target_archive"]["sha256"] = archive_sha
        body = dict(self.document)
        body.pop("manifest_sha256")
        self.document["manifest_sha256"] = RUN.sha256_bytes(RUN.canonical_json(body))
        with self.policy():
            dataset = self.root / "dataset"
            receipt = RUN.materialize_train_dataset(self.document, archive, dataset)
            receipt_path = self.root / "materialization.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            reused = RUN.load_existing_materialization(
                self.document, archive, dataset, receipt_path
            )
        self.assertEqual(reused["manifest_sha256"], self.document["manifest_sha256"])
        self.assertEqual(reused["count"], 1)
        (dataset / "amitaro" / "EMOTION100_001.wav").write_bytes(b"tampered")
        with self.policy(), self.assertRaises(RUN.RunnerError):
            RUN.load_existing_materialization(self.document, archive, dataset, receipt_path)

    def test_manifest_self_hash_is_checked(self) -> None:
        archive = self.archive()
        path = self.root / "manifest.json"
        broken = dict(self.document)
        broken["style"] = "drifted"
        path.write_text(json.dumps(broken), encoding="utf-8")
        with self.policy(), self.assertRaises(RUN.RunnerError):
            RUN.load_manifest(path)
        archive.unlink()

    def test_smoke_config_is_the_only_one_step_override(self) -> None:
        trainer = self.root / "trainer"
        (trainer / "assets").mkdir(parents=True)
        (trainer / "assets" / "default_config.json").write_text(
            json.dumps({"n_steps": 10_000, "batch_size": 8}), encoding="utf-8"
        )
        assets = {}
        for key in ("ir_dir", "noise_dir", "test_dir"):
            directory = self.root / key
            directory.mkdir()
            assets[key] = directory
        for key in ("phone_checkpoint", "pitch_checkpoint", "pretrained_checkpoint"):
            path = self.root / key
            path.write_bytes(b"fixture")
            assets[key] = path
        config = RUN.write_config(
            trainer,
            self.root / "dataset",
            self.root / "checkpoint",
            assets,
            self.root / "config.json",
            smoke=True,
        )
        self.assertEqual(config["n_steps"], 1)
        self.assertEqual(config["batch_size"], 8)
        self.assertEqual(json.loads((self.root / "config.json").read_text())["n_steps"], 1)

    def test_train_requires_gpu0_confirmation_before_launch(self) -> None:
        with self.assertRaisesRegex(RUN.RunnerError, "gpu0"):
            RUN.launch_trainer(
                self.root,
                Path("/bin/true"),
                self.root,
                self.root,
                self.root / "config.json",
                lease=None,
                commit_before_cuda="deadbeef",
                repo_root=self.root,
            )


if __name__ == "__main__":
    unittest.main()

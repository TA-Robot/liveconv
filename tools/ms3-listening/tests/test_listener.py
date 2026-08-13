import hashlib
import io
import json
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve  # noqa: E402


@contextmanager
def listening_server(*roots: Path, capture_root: Path | None = None):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        serve.make_handler(list(roots), capture_root or serve.SOURCE_CAPTURE_ROOT),
    )
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def request(
    port: int,
    method: str,
    target: str,
    host_values: list[str],
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    connection = HTTPConnection("127.0.0.1", port)
    connection.putrequest(method, target, skip_host=True)
    for host in host_values:
        connection.putheader("Host", host)
    for name, value in (headers or {}).items():
        connection.putheader(name, value)
    connection.endheaders(body)
    response = connection.getresponse()
    body = response.read()
    headers = dict(response.getheaders())
    connection.close()
    return response.status, body, headers


class ListenerServerTest(unittest.TestCase):
    @staticmethod
    def _successful_queue_result(attempt: int = 1) -> dict[str, object]:
        return {
            "schema_version": 1,
            "job_id": "listening-job",
            "attempt": attempt,
            "status": "succeeded",
            "reason_code": None,
            "exit_code": 0,
            "timed_out": False,
            "finished_at": "2026-08-11T12:00:00Z",
            "artifact_index": "artifact-index.json",
        }

    @staticmethod
    def _capture_headers(body: bytes) -> dict[str, str]:
        return {
            "Content-Type": "audio/webm",
            "Content-Length": str(len(body)),
            "X-Content-SHA256": hashlib.sha256(body).hexdigest(),
        }

    def test_source_capture_upload_is_atomic_and_returns_only_relative_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            captures = root / "captures"
            body = b"webm opus chunk"
            capture_id = "capture-20260812t120000z-0123456789abcdef"
            filename = "chunk-0001.webm"
            with listening_server(root, capture_root=captures) as port:
                status, response_body, _ = request(
                    port,
                    "POST",
                    f"/source-captures/{capture_id}/raw/{filename}",
                    [f"localhost:{port}"],
                    headers=self._capture_headers(body),
                    body=body,
                )
            self.assertEqual(status, 201)
            payload = json.loads(response_body)
            self.assertEqual(
                payload["locator"],
                f"artifacts/ms3/source-captures/{capture_id}/raw/{filename}",
            )
            self.assertEqual(payload["bytes"], len(body))
            self.assertEqual(payload["sha256"], hashlib.sha256(body).hexdigest())
            self.assertNotIn(str(root), response_body.decode("utf-8"))
            self.assertEqual(
                (captures / capture_id / "raw" / filename).read_bytes(), body
            )

    def test_source_capture_rejects_traversal_and_invalid_client_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            captures = root / "captures"
            body = b"chunk"
            capture_id = "capture-20260812t120000z-0123456789abcdef"
            with listening_server(root, capture_root=captures) as port:
                for target in (
                    f"/source-captures/{capture_id}/raw/%2e%2e",
                    "/source-captures/../raw/chunk-0001.webm",
                    f"/source-captures/{capture_id}/raw/user-name.webm",
                ):
                    status, _, _ = request(
                        port,
                        "POST",
                        target,
                        [f"localhost:{port}"],
                        headers=self._capture_headers(body),
                        body=body,
                    )
                    self.assertEqual(status, 400)
            self.assertFalse(captures.exists())

    def test_source_capture_requires_bounded_content_length_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            captures = root / "captures"
            capture_id = "capture-20260812t120000z-0123456789abcdef"
            target = f"/source-captures/{capture_id}/raw/chunk-0001.webm"
            body = b"chunk"
            with listening_server(root, capture_root=captures) as port:
                missing_length, _, _ = request(
                    port,
                    "POST",
                    target,
                    [f"localhost:{port}"],
                    headers={
                        "Content-Type": "audio/webm",
                        "X-Content-SHA256": hashlib.sha256(body).hexdigest(),
                    },
                )
                too_large, _, _ = request(
                    port,
                    "POST",
                    target,
                    [f"localhost:{port}"],
                    headers={
                        "Content-Type": "audio/webm",
                        "Content-Length": str(serve.MAX_SOURCE_CAPTURE_FILE_BYTES + 1),
                        "X-Content-SHA256": hashlib.sha256(body).hexdigest(),
                    },
                )
            self.assertEqual(missing_length, 400)
            self.assertEqual(too_large, 413)
            self.assertFalse(captures.exists())

    def test_source_capture_rejects_duplicate_and_symlinked_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            captures = root / "captures"
            body = b"first"
            capture_id = "capture-20260812t120000z-0123456789abcdef"
            target = f"/source-captures/{capture_id}/raw/chunk-0001.webm"
            with listening_server(root, capture_root=captures) as port:
                created, _, _ = request(
                    port,
                    "POST",
                    target,
                    [f"localhost:{port}"],
                    headers=self._capture_headers(body),
                    body=body,
                )
                duplicate, _, _ = request(
                    port,
                    "POST",
                    target,
                    [f"localhost:{port}"],
                    headers=self._capture_headers(body),
                    body=body,
                )
            self.assertEqual(created, 201)
            self.assertEqual(duplicate, 409)

            symlink_id = "capture-20260812t120001z-0123456789abcdef"
            outside = root / "outside"
            outside.mkdir()
            (captures / symlink_id).mkdir(parents=True)
            (captures / symlink_id / "raw").symlink_to(
                outside, target_is_directory=True
            )
            with listening_server(root, capture_root=captures) as port:
                status, _, _ = request(
                    port,
                    "POST",
                    f"/source-captures/{symlink_id}/raw/chunk-0001.webm",
                    [f"localhost:{port}"],
                    headers=self._capture_headers(body),
                    body=body,
                )
            self.assertEqual(status, 400)
            self.assertEqual(list(outside.iterdir()), [])

    def test_source_capture_stream_or_hash_mismatch_cleans_up_partial_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            captures = Path(temporary) / "captures"
            capture_id = "capture-20260812t120000z-0123456789abcdef"
            with self.assertRaises(serve.SourceCaptureUploadError):
                serve.store_source_capture(
                    captures,
                    capture_id=capture_id,
                    filename="chunk-0001.webm",
                    content_type="audio/webm",
                    content_length=6,
                    expected_sha256=hashlib.sha256(b"short!").hexdigest(),
                    stream=io.BytesIO(b"short"),
                )
            self.assertFalse((captures / capture_id).exists())

            with self.assertRaises(serve.SourceCaptureUploadError):
                serve.store_source_capture(
                    captures,
                    capture_id=capture_id,
                    filename="chunk-0001.webm",
                    content_type="audio/webm",
                    content_length=5,
                    expected_sha256="0" * 64,
                    stream=io.BytesIO(b"short"),
                )
            self.assertFalse((captures / capture_id).exists())

    def test_host_guard_blocks_rebinding_from_library_and_private_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "private.wav").write_bytes(b"private audio")
            (root / "index.json").write_text(
                json.dumps(
                    {
                        "variants": [
                            {
                                "variant_id": "candidate",
                                "output_file": "private.wav",
                                "status": "passed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            run_id = next(iter(serve.listening_library([root])[1]))
            with listening_server(root) as port:
                library_status, _, _ = request(
                    port, "GET", "/library/index.json", ["outside.example"]
                )
                audio_status, _, _ = request(
                    port,
                    "GET",
                    f"/runs/{run_id}/private.wav",
                    ["outside.example"],
                )
            self.assertEqual(library_status, 400)
            self.assertEqual(audio_status, 400)

    def test_curated_collection_notes_are_loopback_only_and_path_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.json").write_text(
                json.dumps({"variants": []}), encoding="utf-8"
            )
            with listening_server(root) as port:
                blocked, _, _ = request(
                    port, "GET", "/collection-notes.json", ["outside.example"]
                )
                allowed, body, _ = request(
                    port,
                    "GET",
                    "/collection-notes.json",
                    [f"localhost:{port}"],
                )
            self.assertEqual(blocked, 400)
            self.assertEqual(allowed, 200)
            notes = json.loads(body)
            self.assertIn("top_status", notes)
            self.assertNotIn(str(serve.REPOSITORY_ROOT), body.decode("utf-8"))

    def test_source_evaluation_script_exposes_exact_ordered_safe_projection(
        self,
    ) -> None:
        projected = serve.source_evaluation_script()
        utterances = projected["utterances"]
        self.assertEqual(projected["schema_version"], 1)
        self.assertEqual(len(utterances), 100)
        self.assertEqual(
            [item["id"] for item in utterances],
            [f"SRC{value:03d}" for value in range(1, 101)],
        )
        self.assertTrue(
            all(set(item) == {"id", "category", "text"} for item in utterances)
        )
        self.assertNotIn(str(serve.REPOSITORY_ROOT), json.dumps(projected))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.json").write_text(
                json.dumps({"variants": []}), encoding="utf-8"
            )
            with listening_server(root) as port:
                status, body, _ = request(
                    port,
                    "GET",
                    "/source-evaluation-script.json",
                    [f"localhost:{port}"],
                )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), projected)

    def test_host_guard_allows_bound_loopback_names_and_exact_port(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tone.wav").write_bytes(b"wav")
            (root / "index.json").write_text(
                json.dumps(
                    {
                        "variants": [
                            {
                                "variant_id": "candidate",
                                "output_file": "tone.wav",
                                "status": "passed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            run_id = next(iter(serve.listening_library([root])[1]))
            with listening_server(root) as port:
                library_status, _, headers = request(
                    port, "GET", "/library/index.json", [f"localhost:{port}"]
                )
                audio_status, body, _ = request(
                    port,
                    "GET",
                    f"/runs/{run_id}/tone.wav",
                    [f"127.0.0.1:{port}"],
                )
            self.assertEqual(library_status, 200)
            self.assertEqual(audio_status, 200)
            self.assertEqual(body, b"wav")
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_audio_requests_reuse_the_library_mapping_until_browser_refresh(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tone.wav").write_bytes(b"wav")
            (root / "index.json").write_text(
                json.dumps(
                    {
                        "variants": [
                            {
                                "variant_id": "candidate",
                                "output_file": "tone.wav",
                                "status": "passed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(
                serve,
                "discover_listening_directories",
                wraps=serve.discover_listening_directories,
            ) as discover:
                with listening_server(root) as port:
                    status, body, _ = request(
                        port,
                        "GET",
                        "/library/index.json",
                        [f"localhost:{port}"],
                    )
                    run_id = json.loads(body)["runs"][0]["id"]
                    for _ in range(2):
                        audio_status, audio, _ = request(
                            port,
                            "GET",
                            f"/runs/{run_id}/tone.wav",
                            [f"localhost:{port}"],
                        )
                        self.assertEqual(audio_status, 200)
                        self.assertEqual(audio, b"wav")
            self.assertEqual(status, 200)
            self.assertEqual(discover.call_count, 1)

    def test_library_refresh_reuses_cache_until_a_collection_is_published(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def publish(name: str) -> None:
                collection = root / name
                collection.mkdir()
                (collection / "tone.wav").write_bytes(b"wav")
                (collection / "index.json").write_text(
                    json.dumps(
                        {
                            "variants": [
                                {
                                    "variant_id": name,
                                    "output_file": "tone.wav",
                                    "status": "passed",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )

            publish("first")
            with mock.patch.object(
                serve,
                "discover_listening_directories",
                wraps=serve.discover_listening_directories,
            ) as discover:
                with listening_server(root) as port:
                    first_status, first_body, _ = request(
                        port,
                        "GET",
                        "/library/index.json",
                        [f"localhost:{port}"],
                    )
                    cached_status, cached_body, _ = request(
                        port,
                        "GET",
                        "/library/index.json",
                        [f"localhost:{port}"],
                    )
                    publish("second")
                    refreshed_status, refreshed_body, _ = request(
                        port,
                        "GET",
                        "/library/index.json",
                        [f"localhost:{port}"],
                    )

            self.assertEqual(
                (first_status, cached_status, refreshed_status), (200,) * 3
            )
            self.assertEqual(first_body, cached_body)
            self.assertEqual(json.loads(first_body)["run_count"], 1)
            self.assertEqual(json.loads(refreshed_body)["run_count"], 2)
            self.assertEqual(discover.call_count, 2)

    def test_publication_during_scan_forces_the_next_refresh_to_rescan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def publish(name: str) -> None:
                collection = root / name
                collection.mkdir()
                (collection / "tone.wav").write_bytes(b"wav")
                (collection / "index.json").write_text(
                    json.dumps(
                        {
                            "variants": [
                                {
                                    "variant_id": name,
                                    "output_file": "tone.wav",
                                    "status": "passed",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )

            publish("first")
            original_discover = serve.discover_listening_directories

            def discover_then_publish(roots: list[Path]) -> list[Path]:
                discovered = original_discover(roots)
                if not (root / "second").exists():
                    publish("second")
                return discovered

            with mock.patch.object(
                serve,
                "discover_listening_directories",
                side_effect=discover_then_publish,
            ) as discover:
                with listening_server(root) as port:
                    first_status, first_body, _ = request(
                        port,
                        "GET",
                        "/library/index.json",
                        [f"localhost:{port}"],
                    )
                    second_status, second_body, _ = request(
                        port,
                        "GET",
                        "/library/index.json",
                        [f"localhost:{port}"],
                    )

            self.assertEqual((first_status, second_status), (200, 200))
            self.assertEqual(json.loads(first_body)["run_count"], 1)
            self.assertEqual(json.loads(second_body)["run_count"], 2)
            self.assertEqual(discover.call_count, 2)

    def test_host_guard_rejects_malformed_and_head_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.json").write_text(
                json.dumps({"variants": []}), encoding="utf-8"
            )
            with listening_server(root) as port:
                for host_values in (
                    [],
                    ["user@localhost"],
                    ["localhost:1"],
                    ["localhost", "127.0.0.1"],
                ):
                    status, _, _ = request(port, "GET", "/", host_values)
                    self.assertEqual(status, 400)
                status, body, _ = request(port, "HEAD", "/", ["outside.example"])
                absolute_status, _, _ = request(
                    port, "GET", "http://localhost/", [f"localhost:{port}"]
                )
            self.assertEqual(status, 400)
            self.assertEqual(body, b"")
            self.assertEqual(absolute_status, 400)

    def test_confined_rejects_traversal_and_allows_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tone.wav").write_bytes(b"wav")
            self.assertEqual(serve.confined(root, "tone.wav"), root / "tone.wav")
            self.assertIsNone(serve.confined(root, "../key"))
            self.assertIsNone(serve.confined(root, "%2e%2e/key"))

    def test_listening_index_requires_passable_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.json").write_text(
                json.dumps({"variants": []}), encoding="utf-8"
            )
            self.assertEqual(serve.listening_index(root), {"variants": []})
            (root / "index.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                serve.listening_index(root)

    def test_library_normalizes_variants_and_condition_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            variants = root / "variants"
            variants.mkdir()
            (variants / "tone.wav").write_bytes(b"wav")
            (variants / "index.json").write_text(
                json.dumps(
                    {
                        "run_kind": "variant-run",
                        "source_file": "input.wav",
                        "variants": [
                            {
                                "variant_id": "v1",
                                "profile_id": "vc.rvc.v1",
                                "family_id": "rvc",
                                "display_name": "Variant one",
                                "output_file": "tone.wav",
                                "status": "passed",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            conditions = root / "conditions"
            conditions.mkdir()
            (conditions / "tone.wav").write_bytes(b"wav")
            (conditions / "index.json").write_text(
                json.dumps(
                    {
                        "run_kind": "condition-run",
                        "conditions": [
                            {
                                "profile": {"profile_id": "vc.x-vc.runrun.v1"},
                                "gateway": {
                                    "absolute_peak": 0.2,
                                    "maximum_send_lateness_ms": 12.5,
                                },
                                "output_file": "tone.wav",
                                "attempt_id": "render-02",
                                "utterance_id": "LV001-JA-002",
                                "render_receipt_sha256": "sha256:render-condition",
                                "route_parity_receipt_sha256": "sha256:route-condition",
                                "route_status": "route_qualified",
                                "extension_eligible": True,
                                "source_audio_sha256": "sha256:source-condition",
                                "output_sha256": "sha256:output-condition",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            payload, mapped = serve.listening_library([variants, conditions])
            self.assertEqual(payload["run_count"], 2)
            self.assertEqual(payload["candidate_count"], 2)
            self.assertEqual(len(mapped), 2)
            candidate_names = {
                candidate["display_name"]
                for run in payload["runs"]
                for candidate in run["candidates"]
            }
            self.assertEqual(candidate_names, {"Variant one", "x-vc.runrun.v1"})
            condition_candidate = next(
                candidate
                for run in payload["runs"]
                for candidate in run["candidates"]
                if candidate["display_name"] == "x-vc.runrun.v1"
            )
            self.assertEqual(condition_candidate["maximum_send_lateness_ms"], 12.5)
            self.assertEqual(condition_candidate["attempt_id"], "render-02")
            self.assertEqual(condition_candidate["utterance_id"], "LV001-JA-002")
            self.assertEqual(
                condition_candidate["render_receipt_sha256"],
                "sha256:render-condition",
            )
            self.assertEqual(
                condition_candidate["route_parity_receipt_sha256"],
                "sha256:route-condition",
            )
            self.assertEqual(condition_candidate["route_status"], "route_qualified")
            self.assertIs(condition_candidate["extension_eligible"], True)
            self.assertEqual(
                condition_candidate["source_audio_sha256"],
                "sha256:source-condition",
            )
            self.assertEqual(
                condition_candidate["output_sha256"],
                "sha256:output-condition",
            )

    def test_library_orders_fixed_text_runs_by_text_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            collection = root / "exp023"
            directories = []
            for text_id in ("TTS010", "TTS002", "TTS001"):
                directory = collection / text_id
                directory.mkdir(parents=True)
                (directory / "tone.wav").write_bytes(b"wav")
                (directory / "index.json").write_text(
                    json.dumps(
                        {
                            "title": text_id,
                            "text_id": text_id,
                            "variants": [
                                {
                                    "variant_id": "candidate",
                                    "output_file": "tone.wav",
                                    "status": "passed",
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                directories.append(directory)

            payload, _ = serve.listening_library(directories, roots=[root])
            self.assertEqual(
                [run["title"] for run in payload["runs"]],
                ["TTS001", "TTS002", "TTS010"],
            )

    def test_library_uses_existing_default_source_and_omits_missing_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "00-source.wav").write_bytes(b"source")
            (root / "tone.wav").write_bytes(b"tone")
            (root / "index.json").write_text(
                json.dumps(
                    {
                        "source_file": "input.wav",
                        "source_duration_seconds": 8.2,
                        "variants": [
                            {
                                "variant_id": "present",
                                "output_file": "tone.wav",
                                "status": "passed",
                            },
                            {
                                "variant_id": "missing",
                                "output_file": "missing.wav",
                                "status": "passed",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            payload, _ = serve.listening_library([root])
            candidates = payload["runs"][0]["candidates"]
            candidate_names = [
                candidate["id"].split(":")[1] for candidate in candidates
            ]
            self.assertEqual(candidate_names, ["source", "present"])
            self.assertEqual(candidates[0]["source_file"], "input.wav")
            self.assertEqual(candidates[0]["duration_seconds"], 8.2)

    def test_library_labels_duplicate_q_directories_by_utterance_and_q(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directories = []
            for utterance_id in ("LV001-JA-011", "LV001-JA-014"):
                directory = root / utterance_id / "q-000"
                directory.mkdir(parents=True)
                (directory / "tone.wav").write_bytes(b"wav")
                (directory / "index.json").write_text(
                    json.dumps(
                        {
                            "utterance_id": utterance_id,
                            "q": 0.0,
                            "variants": [
                                {
                                    "variant_id": "candidate",
                                    "output_file": "tone.wav",
                                    "status": "passed",
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                directories.append(directory)

            payload, _ = serve.listening_library(directories)

            self.assertEqual(
                {run["title"] for run in payload["runs"]},
                {"LV001-JA-011 / q=0.0", "LV001-JA-014 / q=0.0"},
            )
            self.assertEqual(
                {run["artifact_name"] for run in payload["runs"]}, {"q-000"}
            )

    def test_broad_roots_group_queue_jobs_and_direct_collections_without_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            attempts = workspace / "queue" / "attempts"
            output = attempts / "exp019-cross-arm-demo" / "attempt-001" / "output"
            direct_root = workspace / "direct"
            direct = direct_root / "20260812-0252" / "LV001-JA-011"
            entries = ((output / "q-000", "queue"), (direct, "direct"))
            for directory, variant_id in entries:
                directory.mkdir(parents=True)
                (directory / "tone.wav").write_bytes(b"wav")
                (directory / "index.json").write_text(
                    json.dumps(
                        {
                            "utterance_id": "LV001-JA-011",
                            "variants": [
                                {
                                    "variant_id": variant_id,
                                    "output_file": "tone.wav",
                                    "status": "passed",
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
            (output.parent / "result.json").write_text(
                json.dumps(self._successful_queue_result()), encoding="utf-8"
            )

            directories = serve.discover_listening_directories([attempts, direct_root])
            payload, _ = serve.listening_library(directories, [attempts, direct_root])
            encoded = json.dumps(payload)

            self.assertEqual(payload["run_count"], 2)
            self.assertEqual(
                {(item["kind"], item["title"]) for item in payload["collections"]},
                {
                    ("queue_job", "exp019-cross-arm-demo"),
                    ("artifact_collection", "20260812-0252"),
                },
            )
            self.assertEqual(len({run["collection_id"] for run in payload["runs"]}), 2)
            self.assertNotIn(str(workspace), encoded)
            self.assertNotIn("attempt-001/output", encoded)

            with listening_server(attempts, direct_root) as port:
                status, body, _ = request(
                    port, "GET", "/library/index.json", [f"localhost:{port}"]
                )
            self.assertEqual(status, 200)
            self.assertNotIn(str(workspace), body.decode("utf-8"))

    def test_default_projection_keeps_completed_exp015_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            attempts = workspace / "attempts"
            exp015 = (
                attempts
                / "exp015-xvc-target-conditioning-render-v1"
                / "attempt-001"
                / "output"
                / "LV001-JA-011"
            )
            exp015.mkdir(parents=True)
            variants = []
            for order, arm in enumerate(("zeros", "synthetic-target"), start=1):
                filename = f"candidate-{order}.wav"
                (exp015 / filename).write_bytes(arm.encode())
                variants.append(
                    {
                        "variant_id": f"candidate-{order}",
                        "display_name": arm,
                        "output_file": filename,
                        "status": "passed",
                    }
                )
            (exp015 / "index.json").write_text(
                json.dumps({"variants": variants}), encoding="utf-8"
            )
            attempt = exp015.parents[1]
            (attempt / "result.json").write_text(
                json.dumps(self._successful_queue_result()), encoding="utf-8"
            )
            directories = serve.discover_listening_directories([attempts])
            payload, mapped = serve.listening_library(directories, [attempts])
            encoded = json.dumps(payload)
            run_id = serve._run_id(exp015)
            self.assertEqual(payload["run_count"], 1)
            self.assertIn("exp015-xvc-target-conditioning-render-v1", encoded)
            self.assertIn("zeros", encoded)
            self.assertIn("synthetic-target", encoded)
            self.assertIn(run_id, mapped)
            with listening_server(attempts) as port:
                status, body, _ = request(
                    port, "GET", "/library/index.json", [f"localhost:{port}"]
                )
                audio_status, _, _ = request(
                    port,
                    "GET",
                    f"/runs/{run_id}/candidate-1.wav",
                    [f"localhost:{port}"],
                )
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["run_count"], 1)
            self.assertEqual(audio_status, 200)

    def test_library_preserves_render_bindings_and_nulls_for_legacy_candidates(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "bound.wav").write_bytes(b"bound")
            (root / "legacy.wav").write_bytes(b"legacy")
            bindings = {
                "attempt_id": "render-01",
                "utterance_id": "LV001-JA-001",
                "render_receipt_sha256": "sha256:render",
                "route_parity_receipt_sha256": "sha256:route",
                "route_status": "offline_only_queue_overflow",
                "extension_eligible": False,
                "source_audio_sha256": "sha256:source",
                "output_sha256": "sha256:output",
            }
            (root / "index.json").write_text(
                json.dumps(
                    {
                        "variants": [
                            {
                                "variant_id": "bound",
                                "output_file": "bound.wav",
                                "status": "passed",
                                **bindings,
                            },
                            {
                                "variant_id": "legacy",
                                "output_file": "legacy.wav",
                                "status": "passed",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            payload, _ = serve.listening_library([root])

            candidates = payload["runs"][0]["candidates"]
            bound = next(
                item for item in candidates if item["id"].split(":")[1] == "bound"
            )
            self.assertEqual({field: bound[field] for field in bindings}, bindings)
            legacy = next(
                item for item in candidates if item["id"].split(":")[1] == "legacy"
            )
            self.assertEqual(
                {
                    field: legacy[field]
                    for field in (
                        "attempt_id",
                        "utterance_id",
                        "render_receipt_sha256",
                        "route_parity_receipt_sha256",
                        "route_status",
                        "extension_eligible",
                        "source_audio_sha256",
                        "output_sha256",
                    )
                },
                {
                    "attempt_id": None,
                    "utterance_id": None,
                    "render_receipt_sha256": None,
                    "route_parity_receipt_sha256": None,
                    "route_status": None,
                    "extension_eligible": None,
                    "source_audio_sha256": None,
                    "output_sha256": None,
                },
            )

    def test_library_projects_scoped_source_review_bindings_without_target_fields(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.wav").write_bytes(b"source")
            bindings = {
                "candidate_lock_sha256": "sha256:candidate-lock",
                "review_bundle_sha256": "sha256:review-bundle",
                "review_scope": "source_pronunciation_pretraining",
                "source_only": True,
                "evidence_schema": "liveconv-xvc-source-pronunciation-only/v1",
            }
            (root / "index.json").write_text(
                json.dumps(
                    {
                        **bindings,
                        "variants": [
                            {
                                "variant_id": "hadou-source",
                                "output_file": "source.wav",
                                "status": "passed",
                                "split": "heldout",
                                "target_wav": "must-not-project.wav",
                                "target_model": "must-not-project",
                                "model_configuration": {"must": "not-project"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload, _ = serve.listening_library([root])

            candidate = payload["runs"][0]["candidates"][0]
            self.assertEqual({field: candidate[field] for field in bindings}, bindings)
            self.assertEqual(candidate["split"], "heldout")
            self.assertFalse(
                {"target_wav", "target_model", "model_configuration"} & set(candidate)
            )

    def test_discovery_requires_consistent_terminal_queue_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            regular = root / "regular"
            regular.mkdir()
            (regular / "index.json").write_text(
                json.dumps({"variants": []}), encoding="utf-8"
            )
            output = root / "attempt-001" / "output"
            output.mkdir(parents=True)
            (output / "index.json").write_text(
                json.dumps({"variants": []}), encoding="utf-8"
            )
            self.assertEqual(
                serve.discover_listening_directories([root]), [regular.resolve()]
            )
            for result in (
                {"status": "running"},
                {"status": "failed"},
                {"status": "stale"},
                {**self._successful_queue_result(), "attempt": 2},
            ):
                (output.parent / "result.json").write_text(
                    json.dumps(result), encoding="utf-8"
                )
                self.assertEqual(
                    serve.discover_listening_directories([root]), [regular.resolve()]
                )
            (output.parent / "result.json").write_text(
                json.dumps(self._successful_queue_result()), encoding="utf-8"
            )
            self.assertEqual(
                set(serve.discover_listening_directories([root])),
                {regular.resolve(), output.resolve()},
            )

    def test_default_library_roots_cover_consolidated_artifacts_only_without_input(
        self,
    ) -> None:
        self.assertEqual(
            serve.configured_library_roots(None, []),
            [root.resolve() for root in serve.DEFAULT_LIBRARY_ROOTS],
        )
        with tempfile.TemporaryDirectory() as temporary:
            explicit = Path(temporary)
            self.assertEqual(
                serve.configured_library_roots(explicit, []), [explicit.resolve()]
            )
            self.assertEqual(
                serve.configured_library_roots(None, [explicit]), [explicit.resolve()]
            )

    def test_enrichment_only_uses_exact_bundle_profile_settings(self) -> None:
        document = {"variants": [{"profile_id": "missing"}]}
        self.assertEqual(serve.enrich_with_effective_parameters(document), document)

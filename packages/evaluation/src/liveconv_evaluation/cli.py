"""Command-line entry point for deterministic render comparison."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import wave
from collections.abc import Sequence
from pathlib import Path

from .audio import AnalysisParameters, sha256_file
from .external import load_speaker_lane, load_streaming_lane
from .report import SttEvidence, build_render_report
from .verdict import ThresholdPolicy


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="liveconv-eval")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare = subparsers.add_parser(
        "compare", help="compare source and output PCM WAV files"
    )
    compare.add_argument("source")
    compare.add_argument("output")
    compare.add_argument("--reference-transcript")
    compare.add_argument("--source-transcript")
    compare.add_argument("--output-transcript")
    compare.add_argument("--exact-entity", action="append", default=None)
    compare.add_argument("--source-stt-evidence", type=Path)
    compare.add_argument("--output-stt-evidence", type=Path)
    compare.add_argument("--speaker-lane", type=Path)
    compare.add_argument("--streaming-lane", type=Path)
    compare.add_argument("--thresholds", type=Path)
    compare.add_argument("--report", type=Path)
    compare.add_argument("--render-id")
    compare.add_argument("--silence-floor-dbfs", type=float, default=-60.0)
    compare.add_argument("--clipping-amplitude", type=float, default=0.999)
    compare.add_argument("--frame-ms", type=float, default=20.0)
    compare.add_argument("--alignment-hop-ms", type=float, default=10.0)
    compare.add_argument("--max-alignment-ms", type=float, default=500.0)
    compare.add_argument("--spectral-fft-size", type=int, default=512)
    return parser


def _load_policy(path: Path | None) -> ThresholdPolicy | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("threshold policy must be a JSON object")
    return ThresholdPolicy.from_dict(value)


def _load_stt_evidence(path: Path | None) -> SttEvidence | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("STT evidence must be a JSON object")
    return SttEvidence.from_dict(value)


def _reserve_backup_path(path: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".backup"
    )
    os.close(descriptor)
    backup = Path(name)
    backup.unlink()
    return backup


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("report output must be a regular non-symlink file")
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    backup: Path | None = None
    previous_moved = False
    published = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if path.exists():
            backup = _reserve_backup_path(path)
            os.replace(path, backup)
            previous_moved = True
        os.replace(temporary, path)
        published = True
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        rollback_complete = True
        if published:
            try:
                os.replace(path, temporary)
            except OSError:
                rollback_complete = False
        if previous_moved and backup is not None and backup.exists():
            try:
                os.replace(backup, path)
            except OSError:
                rollback_complete = False
        if rollback_complete:
            temporary.unlink(missing_ok=True)
        else:
            raise RuntimeError(
                "report publication rollback failed; recovery artifacts were retained"
            ) from None
        raise
    if backup is not None:
        backup.unlink()


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        policy = _load_policy(arguments.thresholds)
        source_stt_evidence = _load_stt_evidence(arguments.source_stt_evidence)
        output_stt_evidence = _load_stt_evidence(arguments.output_stt_evidence)
        source_sha256 = sha256_file(arguments.source)
        output_sha256 = sha256_file(arguments.output)
        speaker_lane = load_speaker_lane(
            arguments.speaker_lane,
            source_sha256=source_sha256,
            output_sha256=output_sha256,
        )
        streaming_lane = load_streaming_lane(
            arguments.streaming_lane,
            source_sha256=source_sha256,
            output_sha256=output_sha256,
        )
        parameters = AnalysisParameters(
            silence_floor_dbfs=arguments.silence_floor_dbfs,
            clipping_amplitude=arguments.clipping_amplitude,
            frame_ms=arguments.frame_ms,
            alignment_hop_ms=arguments.alignment_hop_ms,
            max_alignment_ms=arguments.max_alignment_ms,
            spectral_fft_size=arguments.spectral_fft_size,
        )
        report = build_render_report(
            arguments.source,
            arguments.output,
            reference_transcript=arguments.reference_transcript,
            source_transcript=arguments.source_transcript,
            output_transcript=arguments.output_transcript,
            exact_entities=arguments.exact_entity,
            source_stt_evidence=source_stt_evidence,
            output_stt_evidence=output_stt_evidence,
            threshold_policy=policy,
            analysis_parameters=parameters,
            speaker_change=speaker_lane,
            streaming_operations=streaming_lane,
            render_id=arguments.render_id,
        )
        serialized = (
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        if (
            report["artifacts"]["source"]["sha256"] != source_sha256
            or report["artifacts"]["output"]["sha256"] != output_sha256
        ):
            raise ValueError("render artifacts changed while evidence was evaluated")
        if arguments.report:
            _write_atomic(arguments.report, serialized)
        else:
            sys.stdout.write(serialized)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, wave.Error) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

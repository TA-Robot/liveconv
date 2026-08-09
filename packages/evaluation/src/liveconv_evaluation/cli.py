"""Command-line entry point for deterministic render comparison."""

from __future__ import annotations

import argparse
import json
import sys
import wave
from collections.abc import Sequence
from pathlib import Path

from .audio import AnalysisParameters
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        policy = _load_policy(arguments.thresholds)
        source_stt_evidence = _load_stt_evidence(arguments.source_stt_evidence)
        output_stt_evidence = _load_stt_evidence(arguments.output_stt_evidence)
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
            render_id=arguments.render_id,
        )
        serialized = (
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        if arguments.report:
            arguments.report.write_text(serialized, encoding="utf-8")
        else:
            sys.stdout.write(serialized)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, wave.Error) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

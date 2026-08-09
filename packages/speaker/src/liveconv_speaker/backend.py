from __future__ import annotations

import os
from pathlib import Path

from .evidence import SpeakerEvidenceError, sha256_model_tree
from .runtime import verify_runtime_lock


class SpeechBrainEcapaBackend:
    def __init__(
        self,
        model_path: str | Path,
        *,
        expected_sha256: str,
        device: str,
    ) -> None:
        root = Path(model_path).resolve(strict=True)
        if sha256_model_tree(root) != expected_sha256:
            raise SpeakerEvidenceError("speaker model digest does not match")
        if device not in {"cpu", "cuda"}:
            raise SpeakerEvidenceError("device must be cpu or cuda")
        for name in (
            "hyperparams.yaml",
            "embedding_model.ckpt",
            "mean_var_norm_emb.ckpt",
            "classifier.ckpt",
            "label_encoder.txt",
            "custom.py",
        ):
            if not (root / name).is_file():
                raise SpeakerEvidenceError("speaker model artifact is incomplete")

        self.runtime_lock = verify_runtime_lock()
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            from speechbrain.inference.classifiers import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy

            self._model = EncoderClassifier.from_hparams(
                source=str(root),
                savedir=str(root.parent / f".{root.name}-runtime-cache"),
                overrides={"pretrained_path": str(root)},
                run_opts={"device": device},
                local_strategy=LocalStrategy.COPY,
            )
        except Exception:
            raise SpeakerEvidenceError(
                "failed to initialize verified local speaker model"
            ) from None
        self.device = device

    def embed(self, path: Path) -> tuple[float, ...]:
        try:
            import torch
            import torchaudio

            waveform, sample_rate = torchaudio.load(str(path))
            waveform = waveform.mean(dim=0, keepdim=True)
            if sample_rate != 16_000:
                waveform = torchaudio.functional.resample(waveform, sample_rate, 16_000)
            with torch.inference_mode():
                embedding = self._model.encode_batch(
                    waveform.to(self.device), normalize=False
                )
            values = embedding.detach().to("cpu", dtype=torch.float64).reshape(-1)
            if values.numel() != 192 or not torch.isfinite(values).all():
                raise SpeakerEvidenceError("speaker backend returned invalid embedding")
            return tuple(float(value) for value in values.tolist())
        except SpeakerEvidenceError:
            raise
        except Exception:
            raise SpeakerEvidenceError("speaker embedding failed") from None

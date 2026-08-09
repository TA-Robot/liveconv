"""Optional concrete STT backends."""

from .faster_whisper import ENGINE_REVISION, FasterWhisperBackend

__all__ = ["ENGINE_REVISION", "FasterWhisperBackend"]

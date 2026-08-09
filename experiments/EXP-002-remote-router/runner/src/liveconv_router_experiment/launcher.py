from __future__ import annotations

import asyncio
import os
import socket
import sys
import time
from pathlib import Path

import httpx
from liveconv_audio import Settings

from .errors import TransportFailure


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def find_profile_config(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        candidate = Path(explicit).expanduser().resolve()
        if not candidate.is_file():
            raise ValueError("model profile registry does not exist")
        return candidate

    roots = [Path.cwd().resolve(), *Path.cwd().resolve().parents]
    source = Path(__file__).resolve()
    roots.extend(source.parents)
    visited: set[Path] = set()
    for root in roots:
        if root in visited:
            continue
        visited.add(root)
        candidate = root / "config" / "model-profiles.json"
        if candidate.is_file():
            return candidate
    packaged = Settings.from_env().profile_config
    if packaged.is_file():
        return packaged
    raise ValueError("could not locate a model profile registry")


class LocalGateway:
    """Launch the repository's real gateway on an ephemeral loopback port."""

    def __init__(
        self,
        *,
        token: str,
        origin: str,
        profile_config: str | Path | None = None,
        startup_timeout_seconds: float = 10.0,
    ) -> None:
        self._token = token
        self.origin = origin
        self.profile_config = find_profile_config(profile_config)
        self.startup_timeout_seconds = startup_timeout_seconds
        self.port = _free_loopback_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process: asyncio.subprocess.Process | None = None

    async def __aenter__(self) -> LocalGateway:
        environment = os.environ.copy()
        environment.update(
            {
                "LIVECONV_API_TOKEN": self._token,
                "LIVECONV_ALLOWED_ORIGINS": self.origin,
                "LIVECONV_PROFILE_CONFIG": str(self.profile_config),
                "LIVECONV_BIND_HOST": "127.0.0.1",
                "LIVECONV_BIND_PORT": str(self.port),
            }
        )
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "liveconv_audio",
            env=environment,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await self._wait_until_ready()
        except Exception:
            await self.close()
            raise
        return self

    async def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + self.startup_timeout_seconds
        headers = {"Authorization": f"Bearer {self._token}"}
        async with httpx.AsyncClient() as client:
            while time.monotonic() < deadline:
                if self.process is not None and self.process.returncode is not None:
                    raise TransportFailure("local gateway exited before readiness")
                try:
                    response = await client.get(
                        f"{self.base_url}/health/ready",
                        headers=headers,
                        timeout=0.25,
                    )
                except httpx.HTTPError:
                    await asyncio.sleep(0.05)
                    continue
                if response.status_code == 200:
                    return
                await asyncio.sleep(0.05)
        raise TransportFailure("local gateway readiness timed out")

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        process = self.process
        if process is None:
            return
        self.process = None
        if process.returncode is not None:
            return
        process.terminate()
        try:
            async with asyncio.timeout(5.0):
                await process.wait()
        except TimeoutError:
            process.kill()
            await process.wait()

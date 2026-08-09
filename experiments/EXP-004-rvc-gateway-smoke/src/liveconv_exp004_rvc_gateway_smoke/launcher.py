from __future__ import annotations

import asyncio
import os
import secrets
import socket
import sys
import time

import httpx

from .config import RunConfiguration
from .errors import TransportError


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _ephemeral_token() -> str:
    # Settings requires enough bytes and distinct visible ASCII characters.
    return f"exp004-{secrets.token_urlsafe(40)}"


class DisposableGateway:
    """Launch the repository Gateway only on an ephemeral IPv4 loopback port."""

    def __init__(self, configuration: RunConfiguration) -> None:
        if configuration.profile_config is None:
            raise ValueError("a profile configuration is required for auto-launch")
        self.configuration = configuration
        self.token = _ephemeral_token()
        self.port = _free_loopback_port()
        self.gateway_url = f"http://127.0.0.1:{self.port}"
        self.process: asyncio.subprocess.Process | None = None

    async def __aenter__(self) -> DisposableGateway:
        environment = self._launch_environment()
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

    def _launch_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "LIVECONV_API_TOKEN": self.token,
                "LIVECONV_ALLOWED_ORIGINS": self.configuration.origin,
                "LIVECONV_PROFILE_CONFIG": str(self.configuration.profile_config),
                "LIVECONV_ALLOW_TECHNICAL_PROFILES": "1",
                "LIVECONV_BIND_HOST": "127.0.0.1",
                "LIVECONV_BIND_PORT": str(self.port),
                "LIVECONV_INGRESS_BUDGET_MS": "500",
                "LIVECONV_MAX_SESSIONS": "1",
            }
        )
        return environment

    async def _wait_until_ready(self) -> None:
        deadline = (
            time.monotonic() + self.configuration.generation_ready_timeout_seconds
        )
        headers = {"Authorization": f"Bearer {self.token}"}
        async with httpx.AsyncClient() as client:
            while time.monotonic() < deadline:
                if self.process is not None and self.process.returncode is not None:
                    raise TransportError(
                        "auto-launched Gateway exited before readiness"
                    )
                try:
                    response = await client.get(
                        f"{self.gateway_url}/health/ready",
                        headers=headers,
                        timeout=0.25,
                    )
                except httpx.HTTPError:
                    await asyncio.sleep(0.05)
                    continue
                if response.status_code == 200:
                    return
                await asyncio.sleep(0.05)
        raise TransportError("auto-launched Gateway readiness timed out")

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
            async with asyncio.timeout(5):
                await process.wait()
        except TimeoutError:
            process.kill()
            await process.wait()

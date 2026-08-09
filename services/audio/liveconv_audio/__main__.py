from __future__ import annotations

import uvicorn
from liveconv_protocol import MAX_CONTROL_MESSAGE_BYTES

from .app import create_app
from .settings import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        create_app(settings),
        host=settings.bind_host,
        port=settings.bind_port,
        access_log=False,
        ws_max_size=MAX_CONTROL_MESSAGE_BYTES,
    )


if __name__ == "__main__":
    main()

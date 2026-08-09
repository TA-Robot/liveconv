from .network_isolation import deny_non_unix_sockets

deny_non_unix_sockets()

from .worker import main  # noqa: E402

raise SystemExit(main())

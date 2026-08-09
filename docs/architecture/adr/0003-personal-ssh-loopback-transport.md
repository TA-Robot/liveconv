# ADR-0003: Personal SSH-encapsulated loopback transport

Status: Accepted

Date: 2026-08-09

## Context

ADR-0002 defined HTTPS and WSS for a remotely reachable Gateway. The personal
v1 target is narrower: one trusted Chrome client reaches one managed remote host
through an OpenSSH local forward. The application port is never exposed on a
network interface, and operating a public TLS endpoint would add work that does
not reduce risk inside this boundary.

## Decision

Personal v1 MAY use HTTP and WS between the Extension and client loopback when
all of these conditions hold:

- the client connects only to `127.0.0.1` through an SSH local forward;
- the remote Gateway binds only to `127.0.0.1`;
- the SSH server uses a dedicated forwarding-only account, pinned host key, and
  a `permitopen` restriction for the Gateway loopback address and port;
- the Gateway still requires its bearer, exact Extension Origin, short-lived
  one-use WebSocket ticket, profile identity, and normal protocol limits;
- the client-local forwarding port is not exposed to other hosts.

SSH provides confidentiality and integrity for the non-loopback hop. The HTTP
and WS legs exist only inside the two hosts' loopback boundaries. This is a
deployment exception to ADR-0002's HTTPS/WSS transport choice; it does not alter
protocol version 1 messages, authentication, authorization, or audio safety.

Any Gateway reachable beyond loopback MUST use reviewed HTTPS/WSS termination.
Public DNS, ACME, Internet ingress, and multi-user identity remain post-v1.

## Consequences

- A personal setup needs only OpenSSH plus the Gateway and Extension.
- The browser-facing URL is stable at a client-loopback origin.
- Tunnel loss fails closed at the remote route while native playout remains.
- The operator must protect the SSH key, bearer, local machine, and remote host.
- This decision is not evidence that HTTP/WS is safe on a LAN or the Internet.

## Validation

MS-2 first exercises this boundary from the actual Chrome client with remote and
client loopback binding, the pinned host key, forwarding-only account,
`permitopen`, bearer, exact Origin, one-use ticket, and `max_sessions=1`. MS-4
adds the full negative matrix, external-unreachability proof, second-shell
reproduction, and tuned-route stability. MS-6 repeats the frozen release route.

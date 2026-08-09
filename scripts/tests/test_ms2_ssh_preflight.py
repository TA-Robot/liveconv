from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).parents[1] / "ms2-ssh-preflight.sh"
HOST_ALIAS = "liveconv-audio"
HOST_NAME = "gateway.example"
ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
PUBLIC_KEY = "AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl"


@dataclass(frozen=True)
class PreflightFiles:
    config: Path
    identity: Path
    known_hosts: Path
    server: Path
    gateway: Path
    fake_ssh: Path
    effective: Path
    argv: Path


def write_file(path: Path, text: str, *, mode: int = 0o600) -> Path:
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)
    return path


def write_json(path: Path, value: object) -> Path:
    return write_file(path, json.dumps(value), mode=0o600)


def server_evidence(port: int = 8765) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "liveconv-ms2-ssh-server-evidence",
        "account": "liveconv-tunnel",
        "authorized_key": {
            "restrict": True,
            "port_forwarding": True,
            "permitopen": f"127.0.0.1:{port}",
        },
        "sshd": {
            "authenticationmethods": "publickey",
            "pubkeyauthentication": "yes",
            "passwordauthentication": "no",
            "kbdinteractiveauthentication": "no",
            "disableforwarding": "no",
            "allowtcpforwarding": "local",
            "allowstreamlocalforwarding": "no",
            "permitopen": f"127.0.0.1:{port}",
            "permittty": "no",
            "permittunnel": "no",
            "maxsessions": "0",
            "x11forwarding": "no",
            "allowagentforwarding": "no",
            "permituserrc": "no",
        },
    }


def gateway_evidence(port: int = 8765, *, origin: str = ORIGIN) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "liveconv-ms2-gateway-evidence",
        "bind_host": "127.0.0.1",
        "bind_port": port,
        "bearer_auth_required": True,
        "allowed_origin": origin,
        "ticket": {"one_use": True, "ttl_seconds": 30},
        "max_sessions": 1,
    }


def write_fake_ssh(path: Path) -> Path:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "[[ \"$#\" -eq 5 ]] || { printf 'unexpected ssh argc\\n' >&2; exit 97; }\n"
        '[[ "$1" == \'-F\' && "$2" == "$FAKE_SSH_CONFIG" \\\n'
        "  && \"$3\" == '-G' && \"$4\" == '--' \\\n"
        '  && "$5" == "$FAKE_SSH_HOST" ]] \\\n'
        "  || { printf 'unexpected ssh argv\\n' >&2; exit 98; }\n"
        'printf \'%s\\0\' "$@" > "$FAKE_SSH_ARGV"\n'
        'cat -- "$FAKE_SSH_EFFECTIVE"\n',
        encoding="utf-8",
    )
    path.chmod(0o700)
    return path


def effective_config(
    identity: Path,
    known_hosts: Path,
    *,
    local_forward: str = "[127.0.0.1]:9765 [127.0.0.1]:8765",
) -> list[str]:
    return [
        "user liveconv-tunnel",
        "identitiesonly yes",
        f"identityfile {identity}",
        f"userknownhostsfile {known_hosts}",
        "globalknownhostsfile none",
        "knownhostscommand none",
        "stricthostkeychecking yes",
        "verifyhostkeydns no",
        "nohostauthenticationforlocalhost no",
        "controlmaster no",
        "controlpersist no",
        "updatehostkeys no",
        "batchmode yes",
        "exitonforwardfailure yes",
        f"hostname {HOST_NAME}",
        "port 22",
        f"localforward {local_forward}",
    ]


def replace_effective(lines: list[str], key: str, replacement: str) -> list[str]:
    return [replacement if line.partition(" ")[0] == key else line for line in lines]


def real_ssh_config(
    files: PreflightFiles,
    *,
    control_master: str = "no",
    control_path: str | None = None,
    control_persist: str = "no",
) -> str:
    lines = [
        f"Host {HOST_ALIAS}",
        f"    HostName {HOST_NAME}",
        "    Port 22",
        "    User liveconv-tunnel",
        f"    IdentityFile {files.identity}",
        "    IdentitiesOnly yes",
        f"    UserKnownHostsFile {files.known_hosts}",
        "    GlobalKnownHostsFile none",
        "    StrictHostKeyChecking yes",
        "    VerifyHostKeyDNS no",
        "    NoHostAuthenticationForLocalhost no",
        f"    ControlMaster {control_master}",
        f"    ControlPersist {control_persist}",
        "    UpdateHostKeys no",
        "    BatchMode yes",
        "    ExitOnForwardFailure yes",
        "    LocalForward 127.0.0.1:9765 127.0.0.1:8765",
    ]
    if control_path is not None:
        lines.insert(13, f"    ControlPath {control_path}")
    return "\n".join([*lines, ""])


EffectiveMutation = Callable[[list[str], PreflightFiles], list[str]]
ConfigBuilder = Callable[[PreflightFiles], str]


def run_preflight(
    tmp_path: Path,
    *,
    config_text: str | None = None,
    config_builder: ConfigBuilder | None = None,
    config_mode: int = 0o600,
    config_owner: int | None = None,
    identity_mode: int = 0o600,
    known_hosts_mode: int = 0o600,
    known_hosts_text: str | None = None,
    local_forward: str = "[127.0.0.1]:9765 [127.0.0.1]:8765",
    mutate_effective: EffectiveMutation | None = None,
    server: dict[str, Any] | None = None,
    gateway: dict[str, Any] | None = None,
    expected_identity: Path | None = None,
    expected_known_hosts: Path | None = None,
    expected_origin: str = ORIGIN,
    ssh_bin: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], PreflightFiles]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = tmp_path / "config"
    identity = write_file(
        tmp_path / "synthetic-public-identity",
        f"ssh-ed25519 {PUBLIC_KEY} liveconv-test-metadata\n",
        mode=identity_mode,
    )
    known_hosts = write_file(
        tmp_path / "known_hosts",
        known_hosts_text
        if known_hosts_text is not None
        else f"{HOST_NAME} ssh-ed25519 {PUBLIC_KEY}\n",
        mode=known_hosts_mode,
    )
    server_path = write_json(
        tmp_path / "server.json", server if server is not None else server_evidence()
    )
    gateway_path = write_json(
        tmp_path / "gateway.json",
        gateway if gateway is not None else gateway_evidence(),
    )
    fake_ssh = write_fake_ssh(tmp_path / "fake-ssh")
    effective_path = tmp_path / "effective-ssh-g"
    argv_path = tmp_path / "ssh-argv"
    files = PreflightFiles(
        config=config,
        identity=identity,
        known_hosts=known_hosts,
        server=server_path,
        gateway=gateway_path,
        fake_ssh=fake_ssh,
        effective=effective_path,
        argv=argv_path,
    )

    if config_builder is not None:
        configured_text = config_builder(files)
    elif config_text is not None:
        configured_text = config_text
    else:
        configured_text = f"Host {HOST_ALIAS}\n"
    write_file(config, configured_text, mode=config_mode)
    if config_owner is not None:
        os.chown(config, config_owner, -1)

    configured_effective = effective_config(
        identity, known_hosts, local_forward=local_forward
    )
    if mutate_effective is not None:
        configured_effective = mutate_effective(configured_effective, files)
    write_file(effective_path, "\n".join(configured_effective) + "\n")

    environment = {
        **os.environ,
        "FAKE_SSH_ARGV": str(argv_path),
        "FAKE_SSH_CONFIG": str(config.resolve()),
        "FAKE_SSH_EFFECTIVE": str(effective_path),
        "FAKE_SSH_HOST": HOST_ALIAS,
    }
    selected_ssh_bin = ssh_bin if ssh_bin is not None else fake_ssh
    completed = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--ssh-bin",
            str(selected_ssh_bin),
            "--ssh-config",
            str(config),
            "--host-alias",
            HOST_ALIAS,
            "--expected-identity-file",
            str(expected_identity if expected_identity is not None else identity),
            "--expected-known-hosts",
            str(
                expected_known_hosts
                if expected_known_hosts is not None
                else known_hosts
            ),
            "--expected-extension-origin",
            expected_origin,
            "--server-evidence",
            str(server_path),
            "--gateway-evidence",
            str(gateway_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    return completed, files


def assert_failure(completed: subprocess.CompletedProcess[str], message: str) -> None:
    assert completed.returncode == 1
    assert message in completed.stderr


def test_passes_with_constrained_client_server_and_gateway_evidence(
    tmp_path: Path,
) -> None:
    completed, files = run_preflight(tmp_path)

    assert completed.returncode == 0, completed.stderr
    assert files.argv.read_bytes().split(b"\0")[:-1] == [
        b"-F",
        os.fsencode(files.config.resolve()),
        b"-G",
        b"--",
        HOST_ALIAS.encode(),
    ]
    assert json.loads(completed.stdout) == {
        "schema_version": 1,
        "check": "liveconv-ms2-ssh-preflight",
        "status": "pass",
        "client": {
            "host_key_pinned": True,
            "strict_host_key_checking": True,
            "local_forward": {
                "listen_host": "127.0.0.1",
                "listen_port": 9765,
                "target_host": "127.0.0.1",
                "target_port": 8765,
            },
        },
        "server": {"forwarding_only": True, "permitopen_loopback": True},
        "gateway": {
            "loopback_bound": True,
            "bearer_auth_required": True,
            "exact_extension_origin": True,
            "one_use_ticket": True,
            "max_sessions": 1,
        },
    }


def test_quotes_ssh_binary_path_with_whitespace(tmp_path: Path) -> None:
    spaced_bin = tmp_path / "ssh binary" / "fake ssh"
    spaced_bin.parent.mkdir()
    write_fake_ssh(spaced_bin)

    completed, _ = run_preflight(tmp_path / "run", ssh_bin=spaced_bin)

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("local_forward", "message"),
    [
        ("[0.0.0.0]:9765 [127.0.0.1]:8765", "LocalForward is not IPv4-loopback only"),
        ("[127.0.0.1]:9765 [127.0.0.1]:9999", "LocalForward target does not match"),
    ],
)
def test_rejects_non_exact_client_forward(
    tmp_path: Path, local_forward: str, message: str
) -> None:
    completed, _ = run_preflight(tmp_path, local_forward=local_forward)

    assert_failure(completed, message)


@pytest.mark.parametrize(
    ("field", "value"),
    [("allowtcpforwarding", "yes"), ("disableforwarding", "yes")],
)
def test_rejects_server_evidence_without_forwarding_only_policy(
    tmp_path: Path, field: str, value: str
) -> None:
    server = server_evidence()
    server["sshd"][field] = value

    completed, _ = run_preflight(tmp_path, server=server)

    assert_failure(completed, "server evidence does not meet the MS-2 contract")


@pytest.mark.parametrize(
    ("section", "permitopen"),
    [
        ("authorized_key", "127.0.0.1:8765\n"),
        ("authorized_key", "127.0.0.1:8765\r"),
        ("sshd", "127.0.0.1:8765\n"),
        ("sshd", "127.0.0.1:8765\r"),
    ],
)
def test_rejects_server_permitopen_with_a_line_break(
    tmp_path: Path, section: str, permitopen: str
) -> None:
    server = server_evidence()
    server[section]["permitopen"] = permitopen

    completed, _ = run_preflight(tmp_path, server=server)

    assert_failure(completed, "server evidence does not meet the MS-2 contract")


def test_rejects_explicit_empty_evidence_instead_of_using_test_defaults(
    tmp_path: Path,
) -> None:
    empty_server, _ = run_preflight(tmp_path / "server", server={})
    empty_gateway, _ = run_preflight(tmp_path / "gateway", gateway={})

    assert_failure(empty_server, "server evidence does not meet the MS-2 contract")
    assert_failure(empty_gateway, "Gateway evidence does not meet the MS-2 contract")


@pytest.mark.parametrize(
    ("gateway", "message"),
    [
        (
            {**gateway_evidence(), "bearer_auth_required": False},
            "Gateway evidence does not meet the MS-2 contract",
        ),
        (
            {
                **gateway_evidence(),
                "ticket": {"one_use": False, "ttl_seconds": 30},
            },
            "Gateway evidence does not meet the MS-2 contract",
        ),
        (
            {**gateway_evidence(), "max_sessions": 2},
            "Gateway evidence does not meet the MS-2 contract",
        ),
    ],
)
def test_rejects_gateway_evidence_without_exact_token_ticket_or_session_policy(
    tmp_path: Path, gateway: dict[str, Any], message: str
) -> None:
    completed, _ = run_preflight(tmp_path, gateway=gateway)

    assert_failure(completed, message)


@pytest.mark.parametrize(
    "origin",
    [
        "chrome-extension://ponmlkjihgfedcbaponmlkjihgfedcba",
        f"{ORIGIN}\n",
    ],
)
def test_rejects_gateway_origin_that_is_not_the_independent_exact_value(
    tmp_path: Path, origin: str
) -> None:
    completed, _ = run_preflight(tmp_path, gateway=gateway_evidence(origin=origin))

    assert_failure(completed, "Gateway evidence does not meet the MS-2 contract")


def test_rejects_extension_origin_argument_with_a_line_break(tmp_path: Path) -> None:
    completed, _ = run_preflight(tmp_path, expected_origin=f"{ORIGIN}\n")

    assert_failure(completed, "expected extension Origin must not contain a line break")


@pytest.mark.parametrize(
    ("config_text", "message"),
    [
        ("Include=/definitely/not/liveconv\n", "must not use Include"),
        (
            '\rMatch exec="false"\n',
            "contains a disallowed control byte",
        ),
        (
            "\rInclude=/definitely/not/liveconv\r\n",
            "contains a disallowed control byte",
        ),
        (
            "\vHost liveconv-audio\n",
            "contains a disallowed control byte",
        ),
        (
            "\0Host liveconv-audio\n",
            "contains a disallowed control byte",
        ),
        (
            "Match all\n",
            "must not use Match",
        ),
        (
            'mAtCh !exec="false"\n',
            "must not use Match",
        ),
    ],
)
def test_rejects_unsafe_config_directives_before_invoking_ssh(
    tmp_path: Path, config_text: str, message: str
) -> None:
    completed, files = run_preflight(tmp_path, config_text=config_text)

    assert_failure(completed, message)
    assert not files.argv.exists()


def test_rejects_group_writable_isolated_config_before_invoking_ssh(
    tmp_path: Path,
) -> None:
    completed, files = run_preflight(tmp_path, config_mode=0o620)

    assert_failure(completed, "isolated SSH config is writable by group or others")
    assert not files.argv.exists()


@pytest.mark.skipif(os.geteuid() != 0, reason="requires a temporary foreign owner")
def test_rejects_isolated_config_not_owned_by_the_current_user(tmp_path: Path) -> None:
    completed, files = run_preflight(tmp_path, config_owner=65534)

    assert_failure(completed, "isolated SSH config is not owned by the current user")
    assert not files.argv.exists()


def test_rejects_identity_with_unsafe_metadata(tmp_path: Path) -> None:
    completed, files = run_preflight(tmp_path, identity_mode=0o640)

    assert_failure(completed, "expected identity is accessible to group or others")
    assert not files.argv.exists()


def test_rejects_known_hosts_file_writable_by_group_or_others(tmp_path: Path) -> None:
    completed, files = run_preflight(tmp_path, known_hosts_mode=0o620)

    assert_failure(
        completed,
        "expected known-hosts file is writable by group or others",
    )
    assert not files.argv.exists()


def test_rejects_missing_or_multiple_effective_identity_files(tmp_path: Path) -> None:
    disabled, _ = run_preflight(
        tmp_path / "disabled",
        mutate_effective=lambda lines, _: replace_effective(
            lines, "identityfile", "identityfile none"
        ),
    )
    multiple, _ = run_preflight(
        tmp_path / "multiple",
        mutate_effective=lambda lines, _: [*lines, "identityfile /another/identity"],
    )

    assert_failure(disabled, "effective SSH identity is disabled")
    assert_failure(multiple, "expected one effective identityfile value")


def test_rejects_identity_that_does_not_match_the_expected_canonical_file(
    tmp_path: Path,
) -> None:
    other_identity = write_file(
        tmp_path / "other-public-identity",
        f"ssh-ed25519 {PUBLIC_KEY} other-test-metadata\n",
    )
    completed, _ = run_preflight(
        tmp_path / "run",
        mutate_effective=lambda lines, _: replace_effective(
            lines, "identityfile", f"identityfile {other_identity}"
        ),
    )

    assert_failure(
        completed,
        "effective SSH identity differs from the expected identity",
    )


def test_rejects_multiple_or_wrong_known_hosts_files(tmp_path: Path) -> None:
    other_known_hosts = write_file(
        tmp_path / "other-known-hosts",
        f"{HOST_NAME} ssh-ed25519 {PUBLIC_KEY}\n",
    )
    multiple, _ = run_preflight(
        tmp_path / "multiple",
        mutate_effective=lambda lines, _: [*lines, "userknownhostsfile /another/pin"],
    )
    wrong, _ = run_preflight(
        tmp_path / "wrong",
        mutate_effective=lambda lines, _: replace_effective(
            lines, "userknownhostsfile", f"userknownhostsfile {other_known_hosts}"
        ),
    )

    assert_failure(multiple, "expected one effective userknownhostsfile value")
    assert_failure(
        wrong,
        "effective host-pin file differs from the expected known-hosts file",
    )


@pytest.mark.parametrize(
    ("key", "replacement", "message"),
    [
        (
            "knownhostscommand",
            "knownhostscommand /tmp/known-hosts-command",
            "KnownHostsCommand is enabled",
        ),
        ("verifyhostkeydns", "verifyhostkeydns yes", "VerifyHostKeyDNS is enabled"),
        (
            "nohostauthenticationforlocalhost",
            "nohostauthenticationforlocalhost yes",
            "NoHostAuthenticationForLocalhost is enabled",
        ),
    ],
)
def test_rejects_alternate_host_trust_mechanisms(
    tmp_path: Path, key: str, replacement: str, message: str
) -> None:
    completed, _ = run_preflight(
        tmp_path,
        mutate_effective=lambda lines, _: replace_effective(lines, key, replacement),
    )

    assert_failure(completed, message)


def test_rejects_host_key_alias(tmp_path: Path) -> None:
    completed, _ = run_preflight(
        tmp_path,
        mutate_effective=lambda lines, _: [*lines, "hostkeyalias different-host"],
    )

    assert_failure(completed, "HostKeyAlias is configured")


def test_rejects_connection_master_reuse_settings(tmp_path: Path) -> None:
    master, _ = run_preflight(
        tmp_path / "master",
        mutate_effective=lambda lines, _: replace_effective(
            lines, "controlmaster", "controlmaster auto"
        ),
    )
    control_path, _ = run_preflight(
        tmp_path / "path",
        mutate_effective=lambda lines, _: [
            *lines,
            "controlpath /tmp/liveconv-control-%C",
        ],
    )
    persist, _ = run_preflight(
        tmp_path / "persist",
        mutate_effective=lambda lines, _: replace_effective(
            lines, "controlpersist", "controlpersist yes"
        ),
    )

    assert_failure(master, "ControlMaster is enabled")
    assert_failure(control_path, "ControlPath is configured")
    assert_failure(persist, "ControlPersist is enabled")


def test_accepts_an_explicit_none_control_path(tmp_path: Path) -> None:
    completed, _ = run_preflight(
        tmp_path,
        mutate_effective=lambda lines, _: [*lines, "controlpath none"],
    )

    assert completed.returncode == 0, completed.stderr


def test_rejects_revoked_only_host_pin(tmp_path: Path) -> None:
    completed, _ = run_preflight(
        tmp_path,
        known_hosts_text=f"@revoked {HOST_NAME} ssh-ed25519 {PUBLIC_KEY}\n",
    )

    assert_failure(completed, "has only revoked entries")


def test_rejects_invalid_matching_host_pin_key(tmp_path: Path) -> None:
    completed, _ = run_preflight(
        tmp_path,
        known_hosts_text=f"{HOST_NAME} ssh-ed25519 definitely-not-a-key\n",
    )

    assert_failure(completed, "has an invalid matching key")


def test_rejects_candidate_host_pin_that_is_also_revoked(tmp_path: Path) -> None:
    completed, _ = run_preflight(
        tmp_path,
        known_hosts_text=(
            f"{HOST_NAME} ssh-ed25519 {PUBLIC_KEY}\n"
            f"@revoked {HOST_NAME} ssh-ed25519 {PUBLIC_KEY}\n"
        ),
    )

    assert_failure(completed, "marks a candidate key as revoked")


def test_rejects_dynamic_or_remote_forwarding(tmp_path: Path) -> None:
    dynamic, _ = run_preflight(
        tmp_path / "dynamic",
        mutate_effective=lambda lines, _: [*lines, "dynamicforward 1080"],
    )
    remote, _ = run_preflight(
        tmp_path / "remote",
        mutate_effective=lambda lines, _: [*lines, "remoteforward 9000"],
    )

    assert_failure(dynamic, "dynamic forwarding is configured")
    assert_failure(remote, "remote forwarding is configured")


def test_success_output_does_not_echo_evidence_or_credentials(tmp_path: Path) -> None:
    completed, _ = run_preflight(tmp_path)

    assert completed.returncode == 0
    assert ORIGIN not in completed.stdout
    assert PUBLIC_KEY not in completed.stdout
    assert "synthetic-public-identity" not in completed.stdout
    assert "token" not in completed.stdout.lower()


@pytest.mark.skipif(
    not Path("/usr/bin/ssh").is_file(), reason="requires the Linux OpenSSH client"
)
def test_real_ssh_g_accepts_temporary_public_metadata_without_reading_user_ssh(
    tmp_path: Path,
) -> None:
    completed, files = run_preflight(
        tmp_path,
        config_builder=real_ssh_config,
        ssh_bin=Path("/usr/bin/ssh"),
    )

    assert completed.returncode == 0, completed.stderr
    assert not files.argv.exists()


@pytest.mark.skipif(
    not Path("/usr/bin/ssh").is_file(), reason="requires the Linux OpenSSH client"
)
def test_real_ssh_g_accepts_an_explicit_none_control_path(tmp_path: Path) -> None:
    def configured_real_ssh(files: PreflightFiles) -> str:
        return real_ssh_config(files, control_path="none")

    completed, _ = run_preflight(
        tmp_path,
        config_builder=configured_real_ssh,
        ssh_bin=Path("/usr/bin/ssh"),
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(
    not Path("/usr/bin/ssh").is_file(), reason="requires the Linux OpenSSH client"
)
@pytest.mark.parametrize(
    ("control_master", "control_path", "control_persist", "message"),
    [
        ("auto", None, "no", "ControlMaster is enabled"),
        ("no", "/tmp/liveconv-control-%C", "no", "ControlPath is configured"),
        ("no", None, "yes", "ControlPersist is enabled"),
    ],
)
def test_real_ssh_g_rejects_connection_master_reuse(
    tmp_path: Path,
    control_master: str,
    control_path: str | None,
    control_persist: str,
    message: str,
) -> None:
    def configured_real_ssh(files: PreflightFiles) -> str:
        return real_ssh_config(
            files,
            control_master=control_master,
            control_path=control_path,
            control_persist=control_persist,
        )

    completed, _ = run_preflight(
        tmp_path,
        config_builder=configured_real_ssh,
        ssh_bin=Path("/usr/bin/ssh"),
    )

    assert_failure(completed, message)

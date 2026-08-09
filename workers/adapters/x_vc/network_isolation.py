from __future__ import annotations

import ctypes
import errno
import socket

_LIBSECCOMP_SONAME = "libseccomp.so.2"
_PR_SET_NO_NEW_PRIVS = 38
_SCMP_ACT_ALLOW = 0x7FFF0000
_SCMP_ACT_ERRNO = 0x00050000
_SCMP_CMP_NE = 1
_installed = False


class _ScmpArgCompare(ctypes.Structure):
    _fields_ = (
        ("arg", ctypes.c_uint),
        ("op", ctypes.c_int),
        ("datum_a", ctypes.c_uint64),
        ("datum_b", ctypes.c_uint64),
    )


def deny_non_unix_sockets() -> None:
    """Irreversibly deny AF_INET/AF_INET6 sockets in this process and children."""

    global _installed  # noqa: PLW0603
    if _installed:
        return

    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = (
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    )
    libc.prctl.restype = ctypes.c_int
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, "could not enable no_new_privs")

    seccomp = ctypes.CDLL(_LIBSECCOMP_SONAME, use_errno=True)
    seccomp.seccomp_init.argtypes = (ctypes.c_uint32,)
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = (ctypes.c_char_p,)
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add_array.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(_ScmpArgCompare),
    )
    seccomp.seccomp_rule_add_array.restype = ctypes.c_int
    seccomp.seccomp_load.argtypes = (ctypes.c_void_p,)
    seccomp.seccomp_load.restype = ctypes.c_int
    seccomp.seccomp_release.argtypes = (ctypes.c_void_p,)
    seccomp.seccomp_release.restype = None

    context = seccomp.seccomp_init(_SCMP_ACT_ALLOW)
    if not context:
        raise RuntimeError("could not allocate seccomp filter")
    try:
        socket_syscall = seccomp.seccomp_syscall_resolve_name(b"socket")
        if socket_syscall < 0:
            raise RuntimeError("could not resolve the socket syscall")
        comparison = _ScmpArgCompare(
            arg=0,
            op=_SCMP_CMP_NE,
            datum_a=socket.AF_UNIX,
            datum_b=0,
        )
        result = seccomp.seccomp_rule_add_array(
            context,
            _SCMP_ACT_ERRNO | errno.EPERM,
            socket_syscall,
            1,
            ctypes.byref(comparison),
        )
        if result != 0:
            raise OSError(-result, "could not add seccomp socket rule")
        result = seccomp.seccomp_load(context)
        if result != 0:
            raise OSError(-result, "could not load seccomp socket filter")
    finally:
        seccomp.seccomp_release(context)
    _installed = True


def require_non_unix_socket_denial() -> None:
    """Refuse model initialization unless the process installed the OS filter."""

    if not _installed:
        raise RuntimeError("X-VC OS network isolation is not active")

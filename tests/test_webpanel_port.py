import socket

from mcpack.webpanel.app import describe_port_owner, find_free_port, port_is_free


def _listen() -> tuple[socket.socket, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen()
    return s, s.getsockname()[1]


def test_busy_port_detected_and_next_free_found():
    sock, port = _listen()
    try:
        assert not port_is_free("127.0.0.1", port)
        free = find_free_port("127.0.0.1", port)
        assert free is not None and free != port
    finally:
        sock.close()


def test_describe_port_owner_finds_this_process():
    import os
    import sys

    sock, port = _listen()
    try:
        owner = describe_port_owner(port)
        if sys.platform.startswith("linux"):
            assert owner is not None and f"pid {os.getpid()}" in owner
    finally:
        sock.close()

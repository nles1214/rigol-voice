"""
SCPI communication layer for RIGOL DHO1204 oscilloscope.
Connects via raw TCP socket on port 5555.
"""

import socket
import time
import logging

logger = logging.getLogger(__name__)

class ScpiClient:
    """Low-level SCPI client for RIGOL oscilloscopes over TCP/IP."""

    def __init__(self, host: str = "192.168.152.177", port: int = 5555, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None

    def connect(self) -> tuple[bool, str | None]:
        """Establish TCP connection. Returns (success, error_message)."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))
            self._sock.settimeout(0.3)
            try:
                self._sock.recv(4096)
            except socket.timeout:
                pass
            self._sock.settimeout(self.timeout)
            logger.info(f"Connected to oscilloscope at {self.host}:{self.port}")
            return True, None
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            logger.error(f"Failed to connect: {e}")
            self._sock = None
            return False, str(e)

    def disconnect(self):
        """Close the TCP connection."""
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sock.close()
            self._sock = None
            logger.info("Disconnected from oscilloscope")

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    def send(self, command: str) -> str | None:
        """Send a SCPI command and return the response (if any query)."""
        if not self._sock:
            return None
        try:
            raw = (command + "\n").encode("ascii")
            self._sock.sendall(raw)
            time.sleep(0.1)

            if "?" in command:
                return self._read_response(command)
            return None
        except (socket.timeout, OSError) as e:
            logger.error(f"SCPI send error: {e}")
            return None

    def query(self, command: str) -> str | None:
        """Send a query command (forces '?' suffix) and return response."""
        if "?" not in command:
            command += "?"
        return self.send(command)

    def _read_response(self, command: str = "") -> str | None:
        """Read response from oscilloscope. Handles large binary data."""
        if not self._sock:
            return None
        try:
            # First read: get the header
            data = b""
            while True:
                try:
                    self._sock.settimeout(2)
                    chunk = self._sock.recv(65536)
                    if chunk:
                        data += chunk
                        # If we got the IEEE header, calculate total expected size
                        if len(data) >= 3 and data[:1] == b"#":
                            try:
                                hdr_digits = int(chr(data[1]))
                                hdr_end = 2 + hdr_digits
                                if len(data) >= hdr_end:
                                    payload_len = int(data[2:hdr_end].decode())
                                    total = hdr_end + payload_len
                                    # Read remaining if needed
                                    while len(data) < total:
                                        self._sock.settimeout(3)
                                        more = self._sock.recv(min(65536, total - len(data)))
                                        if not more:
                                            break
                                        data += more
                                    break
                            except (ValueError, IndexError):
                                pass
                    else:
                        break
                except socket.timeout:
                    break
            self._sock.settimeout(self.timeout)
            return data.decode("latin-1") if data else None
        except (socket.timeout, OSError) as e:
            logger.error(f"SCPI read error: {e}")
            self._sock.settimeout(self.timeout)
            return None
import logging
import warnings
import zmq
import uuid
import threading

from instrumentserver import DEFAULT_PORT
from instrumentserver.base import send, recv
from instrumentserver.server.core import ServerResponse


logger = logging.getLogger(__name__)


# TODO: allow for the client to operate as context manager.


class BaseClient:
    """Simple client for the StationServer.
    When a timeout happens, a RunTimeError is being raised. This error is there just to warn the user that a timeout
    has occurred. After that the client will restart the socket to continue the normal work.

    :param host: The host address of the server, defaults to localhost.
    :param port: The port of the server, defaults to the value of DEFAULT_PORT.
    :param connect: If true, the server connects as it is being constructed, defaults to True.
    :param timeout: Amount of time that the client waits for an answer before declaring timeout in seconds.
                    Defaults to 20s.
    :param raise_exceptions: If true the client will raise an exception when the server sends one to it, defaults to True.
    """

    def __init__(self, host='localhost', port=DEFAULT_PORT, connect=True, timeout=20, raise_exceptions=True):
        self.connected = False
        self.context = None
        self.socket = None
        self.poller = None

        self.host = host
        self.port = port
        self.addr = f"tcp://{host}:{port}"

        self.raise_exceptions = raise_exceptions
        self.recv_timeout_ms = int(timeout * 1e3)

        self._ask_lock = threading.RLock()

        if connect:
            self.connect()

    def __enter__(self):
        if not self.connected:
            self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        logger.info(f"Connecting to {self.addr}")
        self.context = zmq.Context().instance()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.setsockopt(zmq.IDENTITY, uuid.uuid4().hex.encode()) #todo: more meaningful id?
        self.socket.connect(self.addr)

        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

        self.connected = True

    def ask(self, message):
        if not self.connected:
            raise RuntimeError("No connection yet.")

        # Decide whether we can/should do request_id correlation
        check_req_id = hasattr(message, "request_id")
        req_id = None
        if check_req_id:
            req_id = getattr(message, "request_id", None)
            if not req_id:
                req_id = uuid.uuid4().hex
                setattr(message, "request_id", req_id)

        try:
            with self._ask_lock:
                send(self.socket, message)

                while True:
                    if not self._poll_readable(self.recv_timeout_ms):
                        self._reset_connection()
                        msg = (
                            f"Server did not reply before timeout"
                            f"{f' for request {req_id}' if req_id else ''}."
                        )
                        if self.raise_exceptions:
                            raise RuntimeError(msg)
                        logger.error(msg)
                        return None

                    ret = recv(self.socket)

                    # If server wraps everything in ServerResponse, we'll still see it here.
                    # If it's *not* a ServerResponse (e.g., echoing a raw string), just return it.
                    if not isinstance(ret, ServerResponse):
                        return ret

                    # If we are checking request ids, discard mismatches and keep waiting
                    if check_req_id and ret.request_id != req_id:
                        logger.warning(
                            f"Mismatched response ID: got {ret.request_id}, expected {req_id}"
                        )
                        continue

                    # Handle possible server-side error
                    if ret.error:
                        self._handle_server_error(ret.error)

                    return ret.message

        except zmq.error.ZMQError:
            logger.exception("ZMQ error; will reconnect.", exc_info=True)
            self._reset_connection()
            if self.raise_exceptions:
                raise
            return None

    def disconnect(self):
        if self.socket is not None:
            try:
                self.poller.unregister(self.socket)
            except Exception:
                pass
            self.socket.close(linger=0)
        self.connected = False


    def _poll_readable(self, timeout_ms):
        """Return True if socket is readable within timeout."""
        events = dict(self.poller.poll(timeout_ms))
        return self.socket in events and events[self.socket] & zmq.POLLIN

    def _reset_connection(self):
        try:
            if self.poller and self.socket:
                try:
                    self.poller.unregister(self.socket)
                except Exception:
                    pass
            if self.socket:
                self.socket.close(linger=0)
        finally:
            self.connected = False
            # reconnect
            self.connect()

    def _handle_server_error(self, err):
        if isinstance(err, str):
            logger.error(err)
            if self.raise_exceptions:
                raise RuntimeError(err)
        elif isinstance(err, Warning):
            warnings.warn(err)
        elif isinstance(err, Exception):
            if self.raise_exceptions:
                raise err
            logger.error(f"Server raised exception: {err}")
        else:
            msg = f"Unknown error type from server: {err!r}"
            if self.raise_exceptions:
                raise TypeError(msg)
            logger.error(msg)

def sendRequest(message, host='localhost', port=DEFAULT_PORT):
    with BaseClient(host, port) as cli:
        ret = cli.ask(message)
    return ret


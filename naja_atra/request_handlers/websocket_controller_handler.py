# -*- coding: utf-8 -*-

"""
Copyright (c) 2018 Keijack Wu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import asyncio
import os
import struct
import errno

from threading import Lock
from base64 import b64encode
from hashlib import sha1
from typing import Dict, Tuple, Union, List
from uuid import uuid4
from socket import error as SocketError

from ..utils.logger import get_logger
from ..models import Headers, WebsocketCloseReason, WebsocketRequest, WebsocketSession, HttpError
from ..models import WEBSOCKET_OPCODE_BINARY, WEBSOCKET_OPCODE_CLOSE, WEBSOCKET_OPCODE_CONTINUATION, WEBSOCKET_OPCODE_PING, WEBSOCKET_OPCODE_PONG, WEBSOCKET_OPCODE_TEXT
from ..models import DEFAULT_ENCODING


_logger = get_logger("naja_atra.request_handlers.websocket_request_handler")


'''
https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/Writing_WebSocket_servers

https://datatracker.ietf.org/doc/html/rfc6455

+-+-+-+-+-------+-+-------------+-------------------------------+
0                   1                   2                   3
0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
|     Extended payload length continued, if payload len == 127  |
+ - - - - - - - - - - - - - - - +-------------------------------+
|                               |Masking-key, if MASK set to 1  |
+-------------------------------+-------------------------------+
| Masking-key (continued)       |          Payload Data         |
+-------------------------------- - - - - - - - - - - - - - - - +
:                     Payload Data continued ...                :
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
|                     Payload Data continued ...                |
+---------------------------------------------------------------+
'''

FIN = 0x80
OPCODE = 0x0f
MASKED = 0x80
PAYLOAD_LEN = 0x7f
PAYLOAD_LEN_EXT16 = 0x7e
PAYLOAD_LEN_EXT64 = 0x7f
GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
_BUFFER_SIZE = 1024 * 1024

OPTYPES = {
    WEBSOCKET_OPCODE_CONTINUATION: "CONTINUATION",
    WEBSOCKET_OPCODE_TEXT: "TEXT",
    WEBSOCKET_OPCODE_BINARY: "BINARY",
    WEBSOCKET_OPCODE_CLOSE: "CLOSE",
    WEBSOCKET_OPCODE_PING: "PING",
    WEBSOCKET_OPCODE_PONG: "PONE",
}


class _ContinuationMessageCache:

    def __init__(self, opcode: int) -> None:
        self.opcode: int = opcode
        self.message_bytes: bytearray = bytearray()


class WebsocketException(Exception):

    def __init__(self, reason: WebsocketCloseReason = None, graceful: bool = False) -> None:
        super().__init__(reason)
        self.__graceful: bool = graceful
        self.__reason: WebsocketCloseReason = reason

    @property
    def is_graceful(self) -> bool:
        return self.__graceful

    @property
    def reason(self) -> WebsocketCloseReason:
        return self.__reason


class WebsocketControllerHandler:

    def __init__(self, http_request_handler) -> None:
        self.http_request_handler = http_request_handler
        self.request_writer = http_request_handler.request_writer
        self.routing_conf = http_request_handler.routing_conf
        self.send_response = http_request_handler.send_response_only
        self.send_header = http_request_handler.send_header
        self.reader = http_request_handler.reader
        self.keep_alive = True
        self.handshake_done = False

        handler_class, path_values, regroups = self.routing_conf.get_websocket_handler(
            http_request_handler.request_path)
        self.handler = handler_class.ctrl_object if handler_class else None
        self.ws_request = WebsocketRequest()
        self.ws_request.headers = http_request_handler.headers
        self.ws_request.path = http_request_handler.request_path
        self.ws_request.query_string = http_request_handler.query_string
        self.ws_request.parameters = http_request_handler.query_parameters
        self.ws_request.path_values = path_values
        self.ws_request.reg_groups = regroups
        if "cookie" in self.ws_request.headers:
            self.ws_request.cookies.load(self.ws_request.headers["cookie"])
        elif "Cookie" in self.ws_request.headers:
            self.ws_request.cookies.load(self.ws_request.headers["Cookie"])
        self.session = WebsocketSessionImpl(self, self.ws_request)
        self.close_reason: WebsocketCloseReason = None  # NOSONAR

        self._continution_cache: _ContinuationMessageCache = None  # NOSONAR
        self._send_msg_lock = Lock()
        self._send_frame_lock = Lock()

    @property
    def response_headers(self):
        if hasattr(self.http_request_handler, "_headers_buffer"):
            return self.http_request_handler._headers_buffer
        else:
            return []

    async def await_func(self, obj):
        if asyncio.iscoroutine(obj):
            return await obj
        return obj

    async def on_handshake(self) -> Tuple[int, Dict[str, List[str]]]:  # NOSONAR
        try:
            if not hasattr(self.handler, "on_handshake") or not callable(self.handler.on_handshake):
                return None, {}
            res = await self.await_func(self.handler.on_handshake(self.ws_request))
            http_status_code = None
            headers = {}
            if not res:
                # Res is none, pass
                pass
            elif isinstance(res, int):
                http_status_code = res
            elif isinstance(res, dict) or isinstance(res, Headers):
                headers = res
            elif isinstance(res, tuple):
                for item in res:
                    if isinstance(item, int) and not http_status_code:
                        http_status_code = item
                    elif isinstance(item, dict) or isinstance(item, Headers):
                        headers.update(item)
            else:
                _logger.warning(f"Endpoint[{self.ws_request.path}]")
            return http_status_code, headers
        except Exception:
            _logger.error("Error occurs when handshake. ")
            return 500, {}

    async def on_message(self, opcode: int, message_bytes: bytearray):
        try:
            if opcode == WEBSOCKET_OPCODE_CLOSE:
                _logger.info("Client asked to close connection.")
                if len(message_bytes) >= 2:
                    code = struct.unpack(">H", message_bytes[0:2])[0]
                    reason = message_bytes[2:].decode(
                        'UTF-8', errors="replace")
                else:
                    code = None
                    reason = ''
                raise WebsocketException(graceful=True, reason=WebsocketCloseReason(
                    "Client asked to close connection.", code=code, reason=reason))
            elif opcode == WEBSOCKET_OPCODE_TEXT and hasattr(self.handler, "on_text_message") and callable(self.handler.on_text_message):
                await self.await_func(self.handler.on_text_message(self.session, message_bytes.decode("UTF-8", errors="replace")))
            elif opcode == WEBSOCKET_OPCODE_PING and hasattr(self.handler, "on_ping_message") and callable(self.handler.on_ping_message):
                await self.await_func(self.handler.on_ping_message(self.session, bytes(message_bytes)))
            elif opcode == WEBSOCKET_OPCODE_PONG and hasattr(self.handler, "on_pong_message") and callable(self.handler.on_pong_message):
                await self.await_func(self.handler.on_pong_message(self.session, bytes(message_bytes)))
            elif opcode == WEBSOCKET_OPCODE_BINARY and self._continution_cache.message_bytes and hasattr(self.handler, "on_binary_message") and callable(self.handler.on_binary_message):
                await self.await_func(self.handler.on_binary_message(self.session, bytes(message_bytes)))
        except Exception as e:
            _logger.error("Error occurs when on message!")
            self.close(f"Error occurs when on_message. {e}")

    async def on_continuation_frame(self, first_frame_opcode: int, fin: int, message_frame: bytearray):
        try:
            if first_frame_opcode == WEBSOCKET_OPCODE_BINARY and hasattr(self.handler, "on_binary_frame") and callable(self.handler.on_binary_frame):
                should_append_to_cache = await self.await_func(self.handler.on_binary_frame(self.session, bool(fin), bytes(message_frame)))
                if should_append_to_cache == True:
                    self._continution_cache.message_bytes.extend(message_frame)
            else:
                self._continution_cache.message_bytes.extend(message_frame)
        except Exception as e:
            _logger.error("Error occurs when on message!")
            self.close(f"Error occurs when on_message. {e}")

    async def on_open(self):
        try:
            if hasattr(self.handler, "on_open") and callable(self.handler.on_open):
                await self.await_func(self.handler.on_open(self.session))
        except Exception as e:
            _logger.error("Error occurs when on open!")
            self.close(f"Error occurs when on_open. {e}")

    async def on_close(self):
        try:
            if hasattr(self.handler, "on_close") and callable(self.handler.on_close):
                await self.await_func(self.handler.on_close(self.session, self.close_reason))
        except Exception:
            _logger.error("Error occurs when on close!")

    async def handle_request(self):
        while self.keep_alive:
            try:
                if not self.handshake_done:
                    await self.handshake()
                else:
                    await self.read_next_message()
            except WebsocketException as e:
                if not e.is_graceful:
                    _logger.warning(
                        f"Something's wrong, close connection: {e.reason}")
                else:
                    _logger.info(f"Close connection: {e.reason}")
                self.keep_alive = False
                self.close_reason = e.reason
            except:  # NOSONAR
                _logger.exception("Errors occur when handling message!")
                self.keep_alive = False
                self.close_reason = WebsocketCloseReason(
                    "Errors occur when handling message!")

        await self.on_close()

    async def handshake(self):
        if self.handler:
            code, headers = await self.on_handshake()
            if code and code != 101:
                self.keep_alive = False
                self.send_response(code)
            else:
                self.send_response(101, "Switching Protocols")
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept",
                                 self.calculate_response_key())
            if headers:
                for h_name, h_val in headers.items():
                    self.send_header(h_name, h_val)
        else:
            self.keep_alive = False
            self.send_response(404)

        ws_res_headers = b"".join(self.response_headers) + b"\r\n"
        _logger.debug(ws_res_headers)
        self.request_writer.send(ws_res_headers)
        self.handshake_done = True
        if self.keep_alive == True:
            await self.on_open()

    def calculate_response_key(self):
        key: str = self.ws_request.headers["Sec-WebSocket-Key"] if "Sec-WebSocket-Key" in self.ws_request.headers else self.ws_request.headers["Sec-Websocket-Key"]
        _logger.debug(
            f"Sec-WebSocket-Key: {key}")
        key_hash = sha1(key.encode(errors="replace") +
                        GUID.encode(errors="replace"))
        response_key = b64encode(key_hash.digest()).strip()
        return response_key.decode('ASCII', errors="replace")

    async def read_bytes(self, num):
        return await self.reader.read(num)

    async def _read_message_content(self) -> Tuple[int, int, bytearray]:
        _logger.debug(f"Read next websocket[{self.ws_request.path}] message")
        try:
            b1, b2 = await self.read_bytes(2)
        except ConnectionResetError as e:
            raise WebsocketException(
                graceful=True, reason=WebsocketCloseReason("Client closed connection."))
        except SocketError as e:
            if e.errno == errno.ECONNRESET:
                raise WebsocketException(
                    graceful=True, reason=WebsocketCloseReason("Client closed connection."))
            b1, b2 = 0, 0
        except ValueError as e:
            b1, b2 = 0, 0

        fin = b1 & FIN
        opcode = b1 & OPCODE
        masked = b2 & MASKED
        payload_length = b2 & PAYLOAD_LEN

        if not masked:
            raise WebsocketException(
                reason=WebsocketCloseReason("Client is not masked."))

        if opcode not in OPTYPES.keys():
            raise WebsocketException(
                reason=WebsocketCloseReason(f"Unknown opcode {opcode}."))

        if opcode in (WEBSOCKET_OPCODE_PING, WEBSOCKET_OPCODE_PONG) and payload_length > 125:
            raise WebsocketException(reason=WebsocketCloseReason(
                f"Ping/Pong message payload is too large! The max length of the Ping/Pong messages is 125. but now is {payload_length}"))

        if payload_length == 126:
            hb = await self.reader.read(2)
            payload_length = struct.unpack(">H", hb)[0]
        elif payload_length == 127:
            qb = await self.reader.read(8)
            payload_length = struct.unpack(">Q", qb)[0]

        frame_bytes = bytearray()
        if payload_length > 0:
            masks = await self.read_bytes(4)
            payload = await self.read_bytes(payload_length)
            for encoded_byte in payload:
                frame_bytes.append(encoded_byte ^ masks[len(frame_bytes) % 4])

        return fin, opcode, frame_bytes

    async def read_next_message(self):

        fin, opcode, frame_bytes = await self._read_message_content()

        if fin and opcode != WEBSOCKET_OPCODE_CONTINUATION:
            # A normal frame, handle message.
            await self.on_message(opcode, frame_bytes)
            return

        if not fin and opcode != WEBSOCKET_OPCODE_CONTINUATION:
            # Fragment message: first frame, try to create a cache object.
            if opcode not in (WEBSOCKET_OPCODE_TEXT, WEBSOCKET_OPCODE_BINARY):
                raise WebsocketException(reason=WebsocketCloseReason(
                    f"Control({OPTYPES[opcode]}) frames MUST NOT be fragmented"))

            if self._continution_cache is not None:
                # Check if another fragment message is being read.
                raise WebsocketException(reason=WebsocketCloseReason(
                    "Another continution message is not yet finished. Close connection for this error!"))

            self._continution_cache = _ContinuationMessageCache(opcode)

        if self._continution_cache is None:
            # When the first frame is not send, close connection.
            raise WebsocketException(reason=WebsocketCloseReason(
                "A continuation fragment frame is received, but the start fragment is not yet received. "))

        await self.on_continuation_frame(self._continution_cache.opcode, fin, frame_bytes)

        if fin:
            # Fragment message: end of this message.
            await self.on_message(self._continution_cache.opcode, self._continution_cache.message_bytes)
            self._continution_cache = None

    def send_message(self, message: Union[bytes, str], chunk_size: int = 0):
        if isinstance(message, bytes):
            self.send_bytes(WEBSOCKET_OPCODE_TEXT,
                            message, chunk_size=chunk_size)
        elif isinstance(message, str):
            self.send_bytes(WEBSOCKET_OPCODE_TEXT, message.encode(
                DEFAULT_ENCODING, errors="replace"), chunk_size=chunk_size)
        else:
            _logger.error(f"Cannot send message[{message}. ")

    def send_ping(self, message: Union[str, bytes]):
        if isinstance(message, bytes):
            self.send_bytes(WEBSOCKET_OPCODE_PING, message)
        elif isinstance(message, str):
            self.send_bytes(WEBSOCKET_OPCODE_PING, message.encode(
                DEFAULT_ENCODING, errors="replace"))

    def send_pong(self, message: Union[str, bytes]):
        if isinstance(message, bytes):
            self.send_bytes(WEBSOCKET_OPCODE_PONG, message)
        elif isinstance(message, str):
            self.send_bytes(WEBSOCKET_OPCODE_PONG, message.encode(
                DEFAULT_ENCODING, errors="replace"))

    def send_bytes(self, opcode: int, payload: bytes, chunk_size: int = 0):
        if opcode not in OPTYPES.keys() or opcode == WEBSOCKET_OPCODE_CONTINUATION:
            raise WebsocketException(reason=WebsocketCloseReason(
                f"Cannot send message in a opcode {opcode}. "))

        # Control frames MUST NOT be fragmented.
        c_size = chunk_size if opcode in (
            WEBSOCKET_OPCODE_BINARY, WEBSOCKET_OPCODE_TEXT) else 0

        if c_size and c_size > 0:
            with self._send_msg_lock:
                # Make sure a fragmented message is sent completely.
                self._send_bytes_no_lock(opcode, payload, chunk_size=c_size)
        else:
            self._send_bytes_no_lock(opcode, payload)

    def _send_bytes_no_lock(self, opcode: int, payload: bytes, chunk_size: int = 0):
        frame_size = chunk_size if chunk_size and chunk_size > 0 else None
        all_payloads = payload
        frame_bytes = b''
        while all_payloads:
            op = WEBSOCKET_OPCODE_CONTINUATION if frame_bytes else opcode
            frame_bytes = all_payloads[0: frame_size]
            all_payloads = all_payloads[frame_size:] if frame_size else b''
            fin = 0 if all_payloads else FIN
            self._send_frame(fin, op, frame_bytes)

    def _send_frame(self, fin: int, opcode: int, payload: bytes):
        with self._send_frame_lock:
            self.request_writer.send(
                self._create_frame_header(fin, opcode, len(payload)))
            self.request_writer.send(payload)

    def _create_frame_header(self, fin: int, opcode: int, payload_length: int) -> bytes:
        header = bytearray()
        # Normal payload
        if payload_length <= 125:
            header.append(fin | opcode)
            header.append(payload_length)

        # Extended payload
        elif payload_length >= 126 and payload_length <= 65535:
            header.append(fin | opcode)
            header.append(PAYLOAD_LEN_EXT16)
            header.extend(struct.pack(">H", payload_length))

        # Huge extended payload
        elif payload_length < 18446744073709551616:
            header.append(fin | opcode)
            header.append(PAYLOAD_LEN_EXT64)
            header.extend(struct.pack(">Q", payload_length))
        else:
            raise WebsocketException(
                reason=WebsocketCloseReason("Message is too big. Consider breaking it into chunks.")
            )

        return header

    def send_file(self, path: str, chunk_size: int = 0):
        try:
            file_size = os.path.getsize(path)
            if not chunk_size or chunk_size < 0 or chunk_size > file_size:
                self._send_file_no_lock(path, file_size, file_size)
            else:
                with self._send_msg_lock:
                    self._send_file_no_lock(path, file_size, chunk_size)
        except (OSError, ValueError):
            raise WebsocketException(reason=WebsocketCloseReason(
                f"File in {path} does not exist or is not accessible."))

    def _send_file_no_lock(self, path: str, file_size: int, chunk_size: int):
        with open(path, 'rb') as in_file:
            remain_bytes = file_size
            opcode = WEBSOCKET_OPCODE_BINARY
            while remain_bytes > 0:
                with self._send_frame_lock:
                    frame_size = min(remain_bytes, chunk_size)
                    remain_bytes -= frame_size

                    fin = 0 if remain_bytes > 0 else FIN

                    self.request_writer.send(
                        self._create_frame_header(fin, opcode, frame_size))
                    while frame_size > 0:
                        buff_size = min(_BUFFER_SIZE, frame_size)
                        frame_size -= buff_size

                        data = in_file.read(buff_size)
                        self.request_writer.send(data)
                # After the first frame, the opcode of other frames is continuation forever.
                opcode = WEBSOCKET_OPCODE_CONTINUATION

    def close(self, reason: str = ""):
        self.send_bytes(WEBSOCKET_OPCODE_CLOSE, reason.encode(
            DEFAULT_ENCODING, errors="replace"))
        self.keep_alive = False
        self.close_reason = WebsocketCloseReason(
            "Server asked to close connection.")


class WebsocketSessionImpl(WebsocketSession):

    def __init__(self, handler: WebsocketControllerHandler, request: WebsocketRequest) -> None:
        self.__id = uuid4().hex
        self.__handler = handler
        self.__request = request

    @property
    def id(self) -> str:
        return self.__id

    @property
    def request(self) -> WebsocketRequest:
        return self.__request

    @property
    def is_closed(self) -> bool:
        return not self.__handler.keep_alive

    def send_ping(self, message: bytes = b''):
        self.__handler.send_ping(message)

    def send_pone(self, message: bytes = b''):
        self.__handler.send_pong(message)

    def send(self, message: Union[str, bytes], opcode: int = WEBSOCKET_OPCODE_TEXT, chunk_size: int = 0):
        if isinstance(message, bytes):
            msg = message
        elif isinstance(message, str):
            msg = message.encode(DEFAULT_ENCODING, errors="replace")
        else:
            raise WebsocketException(reason=WebsocketCloseReason(
                f"message {message} is not a string nor a bytes object, cannot send it to client. "))
        self.__handler.send_bytes(
            opcode if opcode is None else WEBSOCKET_OPCODE_TEXT, msg, chunk_size=chunk_size)

    def send_text(self, message: str, chunk_size: int = 0):
        self.__handler.send_message(message, chunk_size=chunk_size)

    def send_binary(self, binary: bytes, chunk_size: int = 0):
        self.__handler.send_bytes(
            WEBSOCKET_OPCODE_BINARY, binary, chunk_size=chunk_size)

    def send_file(self, path: str, chunk_size: int = 0):
        self.__handler.send_file(path, chunk_size=chunk_size)

    def close(self, reason: str = ""):
        self.__handler.close(reason)

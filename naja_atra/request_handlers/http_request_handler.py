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

import html
import re
import http.client
import email.parser
import email.message
import socketserver
import asyncio
import socket


from typing import Any, Dict
from http import HTTPStatus
from urllib.parse import unquote
from asyncio.streams import StreamReader, StreamWriter
from http import HTTPStatus

from .. import name, version
from ..models import RequestBodyReader
from ..utils import http_utils
from ..utils.logger import get_logger
from ..http_servers.routing_server import RoutingServer
from .http_controller_handler import HTTPControllerHandler
from .websocket_controller_handler import WebsocketControllerHandler


_LINE_MAX_BYTES = 65536
_MAXHEADERS = 100

_logger = get_logger("naja_atra.request_handlers.http_request_handler")


class RequestWriter:

    def __init__(self, writer: StreamWriter) -> None:
        self.writer: StreamWriter = writer

    def send(self, data: bytes):
        self.writer.write(data)


class HttpRequestHandler:

    server_version = f"{name}/{version}"

    default_request_version = "HTTP/1.1"

    # The version of the HTTP protocol we support.
    # Set this to HTTP/1.1 to enable automatic keepalive
    protocol_version = "HTTP/1.1"

    # MessageClass used to parse headers
    _message_class = http.client.HTTPMessage

    # hack to maintain backwards compatibility
    responses = {
        v: (v.phrase, v.description)
        for v in HTTPStatus.__members__.values()
    }

    def __init__(self, reader: StreamReader, writer: StreamWriter, request_writer=None, routing_conf: RoutingServer = None) -> None:
        self.routing_conf: RoutingServer = routing_conf
        self.reader: StreamReader = reader
        self.writer: StreamWriter = writer
        self.request_writer: RequestWriter = request_writer if request_writer else RequestWriter(
            writer)

        self.requestline = ''
        self.request_version = ''
        self.command = ''
        self.path = ''
        self.request_path = ''
        self.query_string = ''
        self.query_parameters = {}
        self.headers = {}

        self.close_connection = True
        self._keep_alive = self.routing_conf.keep_alive
        self._connection_idle_time = routing_conf.connection_idle_time
        self._keep_alive_max_req = routing_conf.keep_alive_max_request
        self.req_count = 0

    async def parse_request(self):
        self.req_count += 1
        try:
            if hasattr(self.reader, "connection"):
                # For blocking io. asyncio.wait_for will not raise TimeoutError if the io is blocked.
                self.reader.connection.settimeout(self._connection_idle_time)
            raw_requestline = await asyncio.wait_for(self.reader.readline(), self._connection_idle_time)
            if hasattr(self.reader, "connection") and hasattr(self.reader, "timeout"):
                # For blocking io. Set the Original timeout to the connection.
                self.reader.connection.settimeout(self.reader.timeout)
        except asyncio.TimeoutError:
            _logger.warn("Wait for reading request line timeout. ")
            return False
        if len(raw_requestline) > _LINE_MAX_BYTES:
            self.requestline = ''
            self.request_version = ''
            self.command = ''
            self.send_error(HTTPStatus.REQUEST_URI_TOO_LONG)
            return False
        if not raw_requestline:
            self.close_connection = True
            return False
        self.command = None
        self.request_version = version = self.default_request_version
        self.close_connection = True
        requestline = str(raw_requestline, 'iso-8859-1')
        requestline = requestline.rstrip('\r\n')
        self.requestline = requestline
        words = requestline.split()
        if len(words) == 0:
            return False

        if len(words) >= 3:  # Enough to determine protocol version
            version = words[-1]
            try:
                if not version.startswith('HTTP/'):
                    raise ValueError
                base_version_number = version.split('/', 1)[1]
                version_number = base_version_number.split(".")
                # RFC 2145 section 3.1 says there can be only one "." and
                #   - major and minor numbers MUST be treated as
                #      separate integers;
                #   - HTTP/2.4 is a lower version than HTTP/2.13, which in
                #      turn is lower than HTTP/12.3;
                #   - Leading zeros MUST be ignored by recipients.
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
            except (ValueError, IndexError):
                self.send_error(
                    HTTPStatus.BAD_REQUEST,
                    f"Bad request version {version}")
                return False

            if version_number >= (2, 0):
                self.send_error(
                    HTTPStatus.HTTP_VERSION_NOT_SUPPORTED,
                    f"Invalid HTTP version {base_version_number}")
                return False
            self.request_version = version
            _logger.info(f"request version: {self.request_version}")
        if not 2 <= len(words) <= 3:
            self.send_error(
                HTTPStatus.BAD_REQUEST,
                "Bad request syntax (%r)" % requestline)
            return False
        command, path = words[:2]
        if len(words) == 2:
            self.close_connection = True
            if command != 'GET':
                self.send_error(
                    HTTPStatus.BAD_REQUEST,
                    "Bad HTTP/0.9 request type (%r)" % command)
                return False
        self.command, self.path = command, path

        self.request_path = self._get_request_path(self.path)

        self.query_string = self.__get_query_string(self.path)

        self.query_parameters = http_utils.decode_query_string(
            self.query_string)

        # Examine the headers and look for a Connection directive.
        try:
            self.headers = await self.parse_headers()
        except http.client.LineTooLong as err:
            self.send_error(
                HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE,
                "Line too long",
                str(err))
            return False
        except http.client.HTTPException as err:
            self.send_error(
                HTTPStatus.REQUEST_HEADER_FIELDS_TOO_LARGE,
                "Too many headers",
                str(err)
            )
            return False

        conntype = self.headers.get('Connection', '')

        self.close_connection = not self._keep_alive or conntype.lower(
        ) != 'keep-alive' or self.protocol_version != "HTTP/1.1"

        # Examine the headers and look for an Expect directive
        expect = self.headers.get('Expect', "")
        if (expect.lower() == "100-continue" and
                self.protocol_version >= "HTTP/1.1" and
                self.request_version >= "HTTP/1.1"):
            if not self.handle_expect_100():
                return False
        return True

    async def parse_headers(self):
        """Parses only RFC2822 headers from a file pointer.

        email Parser wants to see strings rather than bytes.
        But a TextIOWrapper around self.rfile would buffer too many bytes
        from the stream, bytes which we later need to read as bytes.
        So we read the correct bytes here, as bytes, for email Parser
        to parse.

        """
        headers = []
        while True:
            line = await self.reader.readline()
            if len(line) > _LINE_MAX_BYTES:
                raise http.client.LineTooLong("header line")
            headers.append(line)
            if len(headers) > _MAXHEADERS:
                raise http.client.HTTPException(
                    f"got more than {_MAXHEADERS} headers")
            if line in (b'\r\n', b'\n', b''):
                break
        hstring = b''.join(headers).decode('iso-8859-1')

        return email.parser.Parser(_class=self._message_class).parsestr(hstring)

    def handle_expect_100(self):
        """Decide what to do with an "Expect: 100-continue" header.

        If the client is expecting a 100 Continue response, we must
        respond with either a 100 Continue or a final response before
        waiting for the request body. The default is to always respond
        with a 100 Continue. You can behave differently (for example,
        reject unauthorized requests) by overriding this method.

        This method should either return True (possibly after sending
        a 100 Continue response) or send an error response and return
        False.

        """
        self.send_response_only(HTTPStatus.CONTINUE)
        self.end_headers()
        return True

    def __get_query_string(self, ori_path: str):
        parts = ori_path.split('?')
        if len(parts) == 2:
            return parts[1]
        else:
            return ""

    def _get_request_path(self, ori_path: str):
        path = ori_path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = http_utils.remove_url_first_slash(path)
        path = unquote(path)
        return path

    def send_error(self, code: int, message: str = None, explain: str = None, headers: Dict[str, str] = {}):
        try:
            shortmsg, longmsg = self.responses[code]
        except KeyError:
            shortmsg, longmsg = '???', '???'
        if message is None:
            message = shortmsg
        if explain is None:
            explain = longmsg
        self.log_error(f"code {code}, message {message}")
        self.send_response(code, message)
        self.send_header('Connection', 'close')

        # Message body is omitted for cases described in:
        #  - RFC7230: 3.3. 1xx, 204(No Content), 304(Not Modified)
        #  - RFC7231: 6.3.6. 205(Reset Content)
        body = None
        if (code >= 200 and
            code not in (HTTPStatus.NO_CONTENT,
                         HTTPStatus.RESET_CONTENT,
                         HTTPStatus.NOT_MODIFIED)):
            try:
                content: Any = self.routing_conf.error_page(code, html.escape(
                    message, quote=False), html.escape(explain, quote=False))
            except:
                content: str = html.escape(
                    message, quote=False) + ":" + html.escape(explain, quote=False)
            content_type, body = http_utils.decode_response_body_to_bytes(
                content)

            self.send_header("Content-Type", content_type)
            self.send_header('Content-Length', str(len(body)))
        if headers:
            for h_name, h_val in headers.items():
                self.send_header(h_name, h_val)
        self.end_headers()

        if self.command != 'HEAD' and body:
            self.writer.write(body)

    def send_response(self, code, message=None):
        """Add the response header to the headers buffer and log the
        response code.

        Also send two standard headers with the server software
        version and the current date.

        """
        self.log_request(code)
        self.send_response_only(code, message)
        self.send_header('Server', self.server_version)
        self.send_header('Date', http_utils.date_time_string())

    def send_header(self, keyword: str, value: str):
        """Send a MIME header to the headers buffer."""
        if keyword.lower() == 'connection':
            if value.lower() == 'close':
                self.close_connection = True
            elif value.lower() == 'keep-alive':
                if self._keep_alive:
                    self.close_connection = False
                else:
                    _logger.warning(
                        f"Keep Alive configuration is set to False, won't send keep-alive header.")
                    return

        if self.request_version != 'HTTP/0.9':
            if not hasattr(self, '_headers_buffer'):
                self._headers_buffer = []
            self._headers_buffer.append(
                f"{keyword}: {value}\r\n".encode('latin-1', errors='strict'))

    def end_headers(self):
        """Send the blank line ending the MIME headers."""
        if self.request_version != 'HTTP/0.9':
            self._headers_buffer.append(b"\r\n")
            self.flush_headers()

    def flush_headers(self):
        if hasattr(self, '_headers_buffer'):
            self.writer.write(b"".join(self._headers_buffer))
            self._headers_buffer = []

    def send_response_only(self, code, message: str = None):
        """Send the response header only."""
        if self.request_version != 'HTTP/0.9':
            if message is None:
                if code in self.responses:
                    message = self.responses[code][0]
                else:
                    message = ''
            if not hasattr(self, '_headers_buffer'):
                self._headers_buffer = []
            self._headers_buffer \
                .append(f"{self.protocol_version} {code} {message}\r\n".encode('latin-1', errors='strict'))

    def log_request(self, code='-', size='-'):
        if isinstance(code, HTTPStatus):
            code = code.value
        self.log_message('"%s" %s %s',
                         self.requestline, str(code), str(size))

    def log_error(self, format, *args):
        self.log_message(format, *args)

    def log_message(self, format, *args):
        _logger.info(f"{format % args}")

    def set_prefer_keep_alive_params(self):
        pass

    def set_alive_params(self):
        if "Keep-Alive" in self.headers:
            ka_header = self.headers["Keep-Alive"]
            timeout_match = re.match(r"^.*timeout=(\d+).*$", ka_header)
            if timeout_match:
                self._connection_idle_time = int(timeout_match.group(1))
            max_match = re.match(r"^.*max=(\d+).*$", ka_header)
            if max_match:
                self._keep_alive_max_req = int(max_match.group(1))

    async def handle_request(self):
        parse_request_success = await self.parse_request()
        if not parse_request_success:
            return
        self.set_alive_params()

        if self.request_version == "HTTP/1.1" and self.command == "GET" and "Upgrade" in self.headers and self.headers["Upgrade"] == "websocket":
            _logger.debug("This is a websocket connection. ")
            ws_handler = WebsocketControllerHandler(self)
            await ws_handler.handle_request()
            self.writer.write_eof()
            return

        await self.handle_http_request()
        while not self.close_connection:
            _logger.debug("Keep-Alive, read next request. ")
            parse_request_success = await self.parse_request()
            if not parse_request_success:
                _logger.debug("parse request fails, return. ")
                return
            if self.req_count >= self._keep_alive_max_req:
                self.send_response("Connection", "close")
            await self.handle_http_request()
            _logger.debug("Handle a keep-alive request successfully!")

    async def handle_http_request(self):
        try:
            http_handler = HTTPControllerHandler(self)
            await http_handler.handle_request()
            if self.writer.can_write_eof():
                self.writer.write_eof()
        except socket.timeout as e:
            # a read or a write timed out.  Discard this connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = True
            return


class SocketServerStreamRequestHandlerWraper(socketserver.StreamRequestHandler):

    server_version = HttpRequestHandler.server_version

    # Wrapper method for readline
    async def readline(self):
        return self.rfile.readline(_LINE_MAX_BYTES)

    async def read(self, n: int = -1):
        return self.rfile.read(n)

    def write(self, data: bytes):
        self.wfile.write(data)

    def can_write_eof(self) -> bool:
        return True

    def write_eof(self):
        self.wfile.flush()

    def close(self):
        self.wfile.close()

    def handle(self) -> None:
        handler: HttpRequestHandler = HttpRequestHandler(
            self, self, request_writer=self.request, routing_conf=self.server)
        asyncio.run(handler.handle_request())

    def finish(self) -> None:
        _logger.debug("Finish a socket connection.")
        return super().finish()

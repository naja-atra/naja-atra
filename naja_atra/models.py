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
import http.cookies
import time
from abc import abstractmethod
from typing import Any, Dict, List, Tuple, Union


DEFAULT_ENCODING: str = "UTF-8"

SESSION_COOKIE_NAME: str = "PY_SIM_HTTP_SER_SESSION_ID"

WEBSOCKET_OPCODE_CONTINUATION: int = 0x0
WEBSOCKET_OPCODE_TEXT: int = 0x1
WEBSOCKET_OPCODE_BINARY: int = 0x2
WEBSOCKET_OPCODE_CLOSE: int = 0x8
WEBSOCKET_OPCODE_PING: int = 0x9
WEBSOCKET_OPCODE_PONG: int = 0xA

WEBSOCKET_MESSAGE_TEXT: str = "WEBSOCKET_MESSAGE_TEXT"
WEBSOCKET_MESSAGE_BINARY: str = "WEBSOCKET_MESSAGE_BINARY"
WEBSOCKET_MESSAGE_BINARY_FRAME: str = "WEBSOCKET_MESSAGE_BINARY_FRAME"
WEBSOCKET_MESSAGE_PING: str = "WEBSOCKET_MESSAGE_PING"
WEBSOCKET_MESSAGE_PONG: str = "WEBSOCKET_MESSAGE_PONG"


class HttpSession:

    def __init__(self):
        self.max_inactive_interval: int = 30 * 60

    @property
    def id(self) -> str:
        return ""

    @property
    def creation_time(self) -> float:
        return 0

    @property
    def last_accessed_time(self) -> float:
        return 0

    @property
    def attribute_names(self) -> Tuple:
        return ()

    @property
    def is_new(self) -> bool:
        return False

    @property
    def is_valid(self) -> bool:
        return time.time() - self.last_accessed_time < self.max_inactive_interval

    @abstractmethod
    def get_attribute(self, name: str) -> Any:
        return NotImplemented

    @abstractmethod
    def set_attribute(self, name: str, value: str) -> None:
        return NotImplemented

    @abstractmethod
    def invalidate(self) -> None:
        return NotImplemented


class HttpSessionFactory:

    @abstractmethod
    def get_session(self, session_id: str, create: bool = False) -> HttpSession:
        return NotImplemented


class Cookies(http.cookies.SimpleCookie):
    EXPIRE_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"


class RequestBodyReader:

    @abstractmethod
    async def read(self, n: int = -1) -> bytes:
        return NotImplemented

    @abstractmethod
    async def read_to_end(self) -> bytes:
        return NotImplemented


class Request:
    """Request"""

    def __init__(self):
        self.method: str = ""  # GET, POST, PUT, DELETE, HEAD, etc.
        self.headers: Dict[str, str] = {}  # Request headers
        self.__cookies = Cookies()
        self.query_string: str = ""  # Query String
        self.path_values: Dict[str, str] = {}
        self.reg_groups = ()  # If controller is matched via regexp, then ,all groups are save here
        self.path: str = ""  # Path
        self.__parameters = {}  # Parameters, key-value array, merged by query string and request body if the `Content-Type` in request header is `application/x-www-form-urlencoded` or `multipart/form-data`
        # Parameters, key-value, if more than one parameters with the same key, only the first one will be stored.
        self.__parameter = {}
        self._body: bytes = b""  # Request body
        # A dictionary if the `Content-Type` in request header is `application/json`
        self.json: Dict[str, Any] = None
        self.environment = {}
        self.reader: RequestBodyReader = None  # A stream reader

    @property
    def cookies(self) -> Cookies:
        return self.__cookies

    @property
    def parameters(self) -> Dict[str, List[str]]:
        return self.__parameters

    @parameters.setter
    def parameters(self, val: Dict[str, List[str]]):
        self.__parameters = val
        self.__parameter = {}
        for k, v in self.__parameters.items():
            self.__parameter[k] = v[0]

    @property
    def parameter(self) -> Dict[str, str]:
        return self.__parameter

    @property
    def host(self) -> str:
        if "Host" not in self.headers:
            return ""
        else:
            return self.headers["Host"]

    @property
    def body(self) -> bytes:
        return self._body

    @property
    def content_type(self) -> str:
        if "Content-Type" not in self.headers:
            return ""
        else:
            return self.headers["Content-Type"]

    @property
    def content_length(self) -> int:
        if "Content-Length" not in self.headers:
            return None
        else:
            return int(self.headers["Content-Length"])

    def get_parameter(self, key: str, default: str = None) -> str:
        if key not in self.parameters.keys():
            return default
        else:
            return self.parameter[key]

    @abstractmethod
    def get_session(self, create: bool = False) -> HttpSession:
        return NotImplemented


class MultipartFile:
    """Multipart file"""

    def __init__(self, name: str = "",
                 required: bool = False,
                 filename: str = "",
                 content_type: str = "",
                 content: bytes = None):
        self.__name = name
        self.__required = required
        self.__filename = filename
        self.__content_type = content_type
        self.__content = content

    @property
    def name(self) -> str:
        return self.__name

    @property
    def _required(self) -> bool:
        return self.__required

    @property
    def filename(self) -> str:
        return self.__filename

    @property
    def content_type(self) -> str:
        return self.__content_type

    @property
    def content(self) -> bytes:
        return self.__content

    @property
    def is_empty(self) -> bool:
        return self.__content is None or len(self.__content) == 0

    def save_to_file(self, file_path: str) -> None:
        if self.__content is not None and len(self.__content) > 0:
            with open(file_path, "wb") as f:
                f.write(self.__content)


class ParamStringValue(str):

    def __init__(self, name: str = "",
                 default: str = "",
                 required: bool = False):
        self.__name = name
        self.__required = required

    @property
    def name(self) -> str:
        return self.__name

    @property
    def _required(self) -> bool:
        return self.__required

    def __new__(cls, name="", default="", **kwargs):
        assert isinstance(default, str)
        obj = super().__new__(cls, default)
        return obj


class Parameter(ParamStringValue):
    pass


class PathValue(str):

    def __init__(self, name: str = "", _value: str = ""):
        self.__name = name

    @property
    def name(self):
        return self.__name

    def __new__(cls, name: str = "", _value: str = "", **kwargs):
        assert isinstance(_value, str)
        obj = super().__new__(cls, _value)
        return obj


class Parameters(list):

    def __init__(self, name: str = "", default: List[str] = [], required: bool = False):
        self.__name = name
        self.__required = required

    @property
    def name(self) -> str:
        return self.__name

    @property
    def _required(self) -> bool:
        return self.__required

    def __new__(cls, name: str = "", default: List[str] = [], **kwargs):
        obj = super().__new__(cls)
        obj.extend(default)
        return obj


class ModelDict(dict):
    pass


class Environment(dict):
    pass


class RegGroups(tuple):
    pass


class RegGroup(str):

    def __init__(self, group=0, **kwargs):
        self._group = group

    @property
    def group(self) -> int:
        return self._group

    def __new__(cls, group=0, **kwargs):
        if "_value" not in kwargs:
            val = ""
        else:
            val = kwargs["_value"]
        obj = super().__new__(cls, val)
        return obj


class Header(ParamStringValue):
    pass


class JSONBody(dict):
    pass


class BytesBody(bytes):
    pass


"""
" The folowing beans are used in Response
"""


class StaticFile:

    def __init__(self, file_path, content_type="application/octet-stream"):
        self.file_path = file_path
        self.content_type = content_type


class Response:
    """Response"""

    def __init__(self,
                 status_code: int = 200,
                 headers: Dict[str, str] = None,
                 body: Union[str, dict, StaticFile, bytes] = ""):
        self.status_code = status_code
        self.__headers = headers if headers is not None else {}
        self.__body = ""
        self.__cookies = Cookies()
        self.__set_body(body)

    @property
    def cookies(self) -> http.cookies.SimpleCookie:
        return self.__cookies

    @cookies.setter
    def cookies(self, val: http.cookies.SimpleCookie) -> None:
        assert isinstance(val, http.cookies.SimpleCookie)
        self.__cookies = val

    @property
    def body(self):
        return self.__body

    @body.setter
    def body(self, val: Union[str, dict, StaticFile, bytes]) -> None:
        self.__set_body(val)

    def __set_body(self, val):
        assert val is None \
            or isinstance(val, str) \
            or isinstance(val, dict) \
            or isinstance(val, StaticFile) \
            or isinstance(val, bytes) \
            or isinstance(val, bytearray), \
            "Body type is not supported."
        self.__body = val

    @property
    def headers(self) -> Dict[str, Union[list, str]]:
        return self.__headers

    def set_header(self, key: str, value: str) -> None:
        self.__headers[key] = value

    def add_header(self, key: str, value: Union[str, list]) -> None:
        if key not in self.__headers.keys():
            self.__headers[key] = value
            return
        if not isinstance(self.__headers[key], list):
            self.__headers[key] = [self.__headers[key]]
        if isinstance(value, list):
            self.__headers[key].extend(value)
        else:
            self.__headers[key].append(value)

    def add_headers(self, headers: Dict[str, Union[str, List[str]]] = {}) -> None:
        if headers is not None:
            for k, v in headers.items():
                self.add_header(k, v)

    @abstractmethod
    def send_error(self, status_code: int, message: str = ""):
        return NotImplemented

    @abstractmethod
    def send_redirect(self, url: str):
        return NotImplemented

    @abstractmethod
    def send_response(self):
        return NotImplemented

    @abstractmethod
    def write_bytes(self, data: bytes):
        pass

    @abstractmethod
    def close(self):
        pass


class HttpError(Exception):

    def __init__(self, code: int = 400, message: str = "", explain: str = ""):
        super().__init__("HTTP_ERROR[%d] %s" % (code, message))
        self.code: int = code
        self.message: str = message
        self.explain: str = explain


class Redirect:

    def __init__(self, url: str):
        self.__url = url

    @property
    def url(self) -> str:
        return self.__url


"""
" Use both in request and response
"""


class Headers(dict):

    def __init__(self, headers: Dict[str, Union[str, List[str]]] = {}):
        self.update(headers)


class Cookie(http.cookies.Morsel):

    def __init__(self,
                 name: str = "",
                 default: str = "",
                 default_options: Dict[str, str] = {},
                 required: bool = False):
        super().__init__()
        self.__name = name
        self.__required = required
        if name is not None and name != "":
            self.set(name, default, default)
        self.update(default_options)

    @property
    def name(self) -> str:
        return self.__name

    @property
    def _required(self) -> bool:
        return self.__required


class FilterContext:

    @property
    def request(self) -> Request:
        return NotImplemented

    @property
    def response(self) -> Response:
        return NotImplemented

    @abstractmethod
    def do_chain(self):
        return NotImplemented


class WebsocketRequest:

    def __init__(self):
        self.headers: Dict[str, str] = {}  # Request headers
        self.__cookies = Cookies()
        self.query_string: str = ""  # Query String
        self.path_values: Dict[str, str] = {}
        self.reg_groups = ()  # If controller is matched via regexp, then ,all groups are save here
        self.path: str = ""  # Path
        self.__parameters = {}  # Parameters, key-value array, merged by query string and request body if the `Content-Type` in request header is `application/x-www-form-urlencoded` or `multipart/form-data`
        # Parameters, key-value, if more than one parameters with the same key, only the first one will be stored.
        self.__parameter = {}

    @property
    def cookies(self) -> Cookies:
        return self.__cookies

    @property
    def parameters(self) -> Dict[str, List[str]]:
        return self.__parameters

    @parameters.setter
    def parameters(self, val: Dict[str, List[str]]):
        self.__parameters = val
        self.__parameter = {}
        for k, v in self.__parameters.items():
            self.__parameter[k] = v[0]

    @property
    def parameter(self) -> Dict[str, str]:
        return self.__parameter

    def get_parameter(self, key: str, default: str = None) -> str:
        if key not in self.parameters.keys():
            return default
        else:
            return self.parameter[key]


class WebsocketSession:

    @property
    def id(self) -> str:
        return NotImplemented

    @property
    def request(self) -> WebsocketRequest:
        return NotImplemented

    @property
    def is_closed(self) -> bool:
        return NotImplemented

    @abstractmethod
    def send(self, message: Union[str, bytes], opcode: int = None, chunk_size: int = 0):
        return NotImplemented

    @abstractmethod
    def send_text(self, message: str, chunk_size: int = 0):
        return NotImplemented

    @abstractmethod
    def send_binary(self, binary: bytes, chunk_size: int = 0):
        return NotImplemented

    @abstractmethod
    def send_file(self, path: str, chunk_size: int = 0):
        return NotImplemented

    @abstractmethod
    def send_pone(self, message: bytes = b''):
        return NotImplemented

    @abstractmethod
    def send_ping(self, message: bytes = b''):
        return NotImplemented

    @abstractmethod
    def close(self, reason: str = ""):
        return NotImplemented


class WebsocketCloseReason(str):

    def __init__(self,
                 message: str = "",
                 code: int = None,
                 reason: str = '') -> None:
        self.__message: str = message
        self.__code: int = code
        self.__reason: str = reason

    @property
    def message(self) -> str:
        return self.__message

    @property
    def code(self) -> int:
        return self.__code

    @property
    def reason(self) -> str:
        return self.__reason

    def __new__(cls, message: str = "", code: int = "", reason: str = '', **kwargs):
        obj = super().__new__(cls, message)
        return obj


class WebsocketHandler:

    @abstractmethod
    def on_handshake(self, request: WebsocketRequest = None):
        """
        "
        " You can get path/headers/path_values/cookies/query_string/query_parameters from request.
        "
        " You should return a tuple means (http_status_code, headers)
        "
        " If status code in (0, None, 101), the websocket will be connected, or will return the status you return.
        "
        " All headers will be send to client
        "
        """
        return None

    @abstractmethod
    def on_open(self, session: WebsocketSession = None):
        """
        "
        " Will be called when the connection opened.
        "
        """
        pass

    @abstractmethod
    def on_close(self, session: WebsocketSession = None, reason: WebsocketCloseReason = None):
        """
        "
        " Will be called when the connection closed.
        "
        """
        pass

    @abstractmethod
    def on_ping_message(self, session: WebsocketSession = None, message: bytes = b''):
        """
        "
        " Will be called when receive a ping message. Will send all the message bytes back to client by default.
        "
        """
        session.send_pone(message)

    @abstractmethod
    def on_pong_message(self, session: WebsocketSession = None, message: bytes = ""):
        """
        "
        " Will be called when receive a pong message.
        "
        """
        pass

    @abstractmethod
    def on_text_message(self, session: WebsocketSession = None, message: str = ""):
        """
        "
        " Will be called when receive a text message.
        "
        """
        pass

    @abstractmethod
    def on_binary_message(self, session: WebsocketSession = None, message: bytes = b''):
        """
        "
        " Will be called when receive a binary message if you have not consumed all the bytes in `on_binary_frame`
        " method.
        "
        """
        pass

    @abstractmethod
    def on_binary_frame(self, session: WebsocketSession = None, fin: bool = False, frame_payload: bytes = b''):
        """
        "
        " When server receive a fragmented message, this method will be called every time when a frame is received,
        " you can consume all the bytes in this method, e.g. save all bytes to a file.
        "
        " If you does not implement this method or return a True in this method, all the bytes will be cached in
        " memory and sent to your `on_binary_message` method after all frames are received.
        "
        """
        return True

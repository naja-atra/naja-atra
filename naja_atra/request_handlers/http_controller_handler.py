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
from asyncio.streams import StreamReader, StreamWriter
import gzip
import os
import json
import threading
import http.cookies as cookies
import datetime

from urllib.parse import unquote
from typing import Any, Callable, Dict, List, Tuple, Union

from .model_bindings import ModelBindingConf
from ..http_servers.routing_server import RoutingServer

from ..models import FilterContext, HttpError, RequestBodyReader, StaticFile, Headers, Redirect, Response, Cookies, MultipartFile, Request, HttpSession, HttpSessionFactory
from ..models import DEFAULT_ENCODING, SESSION_COOKIE_NAME
from ..app_conf import _ControllerFunction
from ..utils import http_utils

from .http_session_local_impl import LocalSessionFactory
from ..utils.logger import get_logger
from ..utils.http_utils import get_function_args, get_function_kwargs

_logger = get_logger("naja_atra.request_handlers.http_request_handler")


class RequestBodyReaderDumpWrapper(RequestBodyReader):

    def __init__(self, reader: StreamReader) -> None:
        self._reader = reader

    async def read(self, n: int = -1) -> bytes:
        _logger.warning(
            "`Content-Length` and `Transfer-Encoding` are both not set in request, so we can't read the body.")
        return b''

    async def read_to_end(self) -> bytes:
        _logger.warning(
            "`Content-Length` and `Transfer-Encoding` are both not set in request, so we can't read the body.")
        raise b''


class RequestBodyReaderWrapper(RequestBodyReader):

    def __init__(self, reader: StreamReader, content_length: int) -> None:
        if content_length is None or content_length < 0:
            raise HttpError(400, "Invalid content length")
        self._content_length: int = content_length
        self._remain_length: int = content_length
        self._reader: StreamReader = reader
        self._lock = asyncio.Lock()

    async def read(self, n: int = -1) -> bytes:
        async with self._lock:
            if not n or self._remain_length <= 0:
                return b''
            if n < 0:
                data = await self._reader.read(self._remain_length)
            else:
                data = await self._reader.read(min(n, self._remain_length))

            self._remain_length -= len(data)

            return data

    async def read_to_end(self) -> bytes:
        data = b''
        while self._remain_length > 0:
            data += await self.read()
        return data


class RequestBodyReaderChunkedReader(RequestBodyReader):

    def __init__(self, reader: StreamReader) -> None:
        self._reader = reader
        self._current_chunk_len: int = -1
        self._buffer: bytes = b''
        self._eof: bool = False
        self._lock = asyncio.Lock()

    async def _fill_buffer(self):
        if self._eof:
            _logger.warning("The body or this request has been all read. ")
            return
        if self._buffer:
            _logger.debug(
                f"There is still data in buffer. length: {len(self._buffer)}")
            return

        if self._current_chunk_len > 0:
            self._buffer = await self._reader.read(self._current_chunk_len)
            self._current_chunk_len -= len(self._buffer)
            return

        if self._current_chunk_len == 0:
            # Read \r\n at the end of a chunk
            rn = await self._reader.read(2)
            if rn != b'\r\n':
                raise HttpError(400, f"Invalid chunk end: {rn}")

        chunk_len = await self._reader.readline()
        chunk_len = chunk_len.rstrip(b'\r\n')
        self._current_chunk_len = int(chunk_len, 16)
        _logger.debug(f"current chunk length: {self._current_chunk_len}")
        if self._current_chunk_len == 0:
            # Read \r\n at the end of the final chunk
            rn = await self._reader.read(2)
            if rn != b'\r\n':
                raise HttpError(400, f"Invalid chunk end: {rn}")
            self._eof = True
            return
        if self._current_chunk_len < 0:
            raise HttpError(400, "Invalid chunk length")
        self._buffer = await self._reader.read(self._current_chunk_len)
        self._current_chunk_len -= len(self._buffer)

    async def read(self, n: int = -1) -> bytes:
        async with self._lock:
            if not n:
                return b''
            await self._fill_buffer()
            if n < 0 or n >= len(self._buffer):
                data = self._buffer
                self._buffer = b''
                return data
            else:
                data = self._buffer[:n]
                self._buffer = self._buffer[n:]
                return data

    async def read_to_end(self) -> bytes:
        data = b''
        while not self._eof:
            data += await self.read()
        return data


class RequestWrapper(Request):

    def __init__(self):
        super().__init__()
        self._headers_keys_in_lowcase = {}
        self._path = ""
        self.__session = None
        self._socket_req = None
        self._coroutine_objects = []
        self._session_fac: HttpSessionFactory = None

    @property
    def host(self) -> str:
        if "host" not in self._headers_keys_in_lowcase:
            return ""
        else:
            return self.headers["host"]

    @property
    def content_type(self) -> str:
        if "content-type" not in self._headers_keys_in_lowcase:
            return ""
        else:
            return self.headers["content-type"]

    @property
    def content_length(self) -> int:
        if "content-length" not in self._headers_keys_in_lowcase:
            return ""
        else:
            return self.headers["content-length"]

    def get_session(self, create: bool = False) -> HttpSession:
        if not self.__session:
            sid = self.cookies[SESSION_COOKIE_NAME].value if SESSION_COOKIE_NAME in self.cookies.keys(
            ) else ""
            session_fac = self._session_fac or LocalSessionFactory()
            self.__session = session_fac.get_session(sid, create)
        return self.__session

    def _put_coroutine_task(self, coroutine_object):
        self._coroutine_objects.append(coroutine_object)


class ResponseWrapper(Response):
    """ """

    def __init__(self, handler,
                 status_code=200,
                 headers=None):
        super().__init__(status_code=status_code, headers=headers, body="")
        self.__req_handler = handler
        self.__is_sent = False
        self.__header_sent = False
        self.__send_lock__ = threading.Lock()

    @property
    def is_sent(self) -> bool:
        return self.__is_sent

    def send_error(self, status_code: int, message: str = "", explain: str = "") -> None:
        with self.__send_lock__:
            self.__is_sent = True
            self.status_code = status_code
            self.__req_handler.send_error(
                self.status_code, message=message, explain=explain, headers=self.headers)

    def send_redirect(self, url: str) -> None:
        self.status_code = 302
        self.set_header("Location", url)
        self.body = None
        self.send_response()

    def send_response(self) -> None:
        with self.__send_lock__:
            self.__send_response()

    def __send_response(self):
        assert not self.__is_sent and not self.__header_sent, "This response has benn sent"
        self.__header_sent = True
        self.__is_sent = True
        self.__req_handler._send_response({
            "status_code": self.status_code,
            "headers": self.headers,
            "cookies": self.cookies,
            "body": self.body
        })

    def __send_headers(self):
        if not self.__header_sent:
            self.__header_sent = True
            self.__req_handler._send_and_end_res_headers(
                self.status_code, headers=self.headers, cks=self.cookies)

    def write_bytes(self, data: bytes):
        assert not self.__is_sent, "This response has benn sent"
        assert isinstance(data, bytes) or isinstance(
            data, bytearray), "You can "
        self.__send_headers()
        self.__req_handler.writer.write(data)

    def close(self):
        self.__is_sent = True
        self.__req_handler.writer.write_eof()
        self.__req_handler.writer.close()


class FilterContextImpl(FilterContext):
    """Context of a filter"""

    DEFAULT_TIME_OUT = 10

    def __init__(self, req, res, controller: _ControllerFunction, model_binding_conf: ModelBindingConf, filters: List[Callable] = None):
        self.__request: RequestWrapper = req
        self.__response = res
        self.__controller: _ControllerFunction = controller
        self.__filters: List[Callable] = filters if filters is not None else []
        self.__model_binding_conf = model_binding_conf

    @property
    def request(self) -> RequestWrapper:
        return self.__request

    @property
    def response(self) -> ResponseWrapper:
        return self.__response

    async def _run_ctrl_fun(self):
        args = await self.__prepare_args()
        kwargs = await self.__prepare_kwargs()
        if asyncio.iscoroutinefunction(self.__controller.func):
            if kwargs is None:
                ctr_res = await self.__controller.func(*args)
            else:
                ctr_res = await self.__controller.func(*args, **kwargs)
        else:
            if kwargs is None:
                ctr_res = self.__controller.func(*args)
            else:
                ctr_res = self.__controller.func(*args, **kwargs)
        return ctr_res

    def _do_res(self, ctr_res):
        session = self.request.get_session()
        if session and session.is_valid:
            exp = datetime.datetime.utcfromtimestamp(
                session.last_accessed_time + session.max_inactive_interval)
            sck = Cookies()
            sck[SESSION_COOKIE_NAME] = session.id
            sck[SESSION_COOKIE_NAME]["httponly"] = True
            sck[SESSION_COOKIE_NAME]["path"] = "/"
            sck[SESSION_COOKIE_NAME]["expires"] = exp.strftime(
                Cookies.EXPIRE_DATE_FORMAT)
            self.response.cookies.update(sck)
        elif session and SESSION_COOKIE_NAME in self.request.cookies:
            exp = datetime.datetime.utcfromtimestamp(0)
            sck = Cookies()
            sck[SESSION_COOKIE_NAME] = session.id
            sck[SESSION_COOKIE_NAME]["httponly"] = True
            sck[SESSION_COOKIE_NAME]["path"] = "/"
            sck[SESSION_COOKIE_NAME]["expires"] = exp.strftime(
                Cookies.EXPIRE_DATE_FORMAT)
            self.response.cookies.update(sck)

        if ctr_res is not None:
            if isinstance(ctr_res, tuple):
                status, headers, cks, body = self.__decode_tuple_response(
                    ctr_res)
                self.response.status_code = status if status is not None else self.response.status_code
                self.response.body = body if body is not None else self.response.body
                self.response.add_headers(headers)
                self.response.cookies.update(cks)
            elif isinstance(ctr_res, Response):
                self.response.status_code = ctr_res.status_code
                self.response.body = ctr_res.body
                self.response.add_headers(ctr_res.headers)
            elif isinstance(ctr_res, Redirect):
                self.response.send_redirect(ctr_res.url)
            elif isinstance(ctr_res, int) and ctr_res >= 200 and ctr_res < 600:
                self.response.status_code = ctr_res
            elif isinstance(ctr_res, Headers):
                self.response.add_headers(ctr_res)
            elif isinstance(ctr_res, cookies.BaseCookie):
                self.response.cookies.update(ctr_res)
            else:
                self.response.body = ctr_res

        if self.request.method.upper() == "HEAD":
            self.response.body = None
        if not self.response.is_sent:
            self.response.send_response()

    async def _do_request_async(self):
        ctr_res = await self._run_ctrl_fun()
        self._do_res(ctr_res)

    def do_chain(self):
        if self.response.is_sent:
            return
        if self.__filters:
            filter_func = self.__filters.pop(0)
            self.request._put_coroutine_task(
                self._wrap_to_async(filter_func, [self]))
        else:
            self.request._put_coroutine_task(self._do_request_async())

    async def _wrap_to_async(self, func: Callable, args: List = [], kwargs: Dict = {}) -> Any:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    def __decode_tuple_response(self, ctr_res):
        status_code = None
        headers = Headers()
        cks = cookies.SimpleCookie()
        body = None
        for item in ctr_res:
            if isinstance(item, int):
                if status_code is None:
                    status_code = item
            elif isinstance(item, Headers):
                headers.update(item)
            elif isinstance(item, cookies.BaseCookie):
                cks.update(item)
            elif type(item) in (str, dict, StaticFile, bytes, bytearray):
                if body is None:
                    body = item
        return status_code, headers, cks, body

    async def __prepare_args(self):
        args = get_function_args(self.__controller.func)
        arg_vals = []
        if len(args) > 0:
            ctr_obj = self.__controller.ctrl_object
            if ctr_obj is not None:
                arg_vals.append(self.__controller.ctrl_object)
                args = args[1:]
        for arg, arg_type_anno in args:
            param = await self.__get_params_(arg, arg_type_anno)
            if param is None:
                raise HttpError(400, "Missing Paramter",
                                f"Parameter[{arg}] is required! ")
            arg_vals.append(param)

        return arg_vals

    async def __get_params_(self, arg, arg_type, val=None):
        if arg_type in self.__model_binding_conf.model_bingding_types:
            binding_type = self.__model_binding_conf.model_bingding_types[arg_type]
        else:
            binding_type = self.__model_binding_conf.default_model_binding_type

        binding_obj = binding_type(self.request,
                                   self.response,
                                   arg,
                                   arg_type,
                                   val)
        return await self._wrap_to_async(binding_obj.bind)

    async def __prepare_kwargs(self):
        kwargs = get_function_kwargs(self.__controller.func)
        if kwargs is None:
            return None
        kwarg_vals = {}
        for k, v, t in kwargs:
            kwarg_vals[k] = await self.__get_params_(
                k, type(v) if v is not None else t, v)

        return kwarg_vals


class HTTPControllerHandler:

    def __init__(self, http_request_handler, environment={}) -> None:
        self.method: str = http_request_handler.command
        self.request_path: str = http_request_handler.request_path
        self.query_string: str = http_request_handler.query_string
        self.query_parameters: Dict[str, List[str]
                                    ] = http_request_handler.query_parameters
        self.headers: Dict[str, str] = http_request_handler.headers

        self.routing_conf: RoutingServer = http_request_handler.routing_conf
        self.reader: StreamReader = http_request_handler.reader

        self.send_header = http_request_handler.send_header
        self.end_headers = http_request_handler.end_headers
        self.send_response = http_request_handler.send_response
        self.send_error = http_request_handler.send_error
        self.writer: StreamWriter = http_request_handler.writer
        self.environment: Dict[str, Any] = environment

    def __match_one_exp(self, d: Dict[str, Union[List[str], str]], exp: str, where: str) -> bool:
        if not exp:
            return True
        _logger.debug(
            f"Match controller {where} expression [{exp}] for values: {d}. ")
        exp_ = str(exp)
        e_idx = exp_.find("=")
        if e_idx < 0:
            _logger.debug(f"cannot find = in exp {exp}")
            if exp_.startswith('!'):
                return not exp_[1:] in d.keys()
            else:
                return exp_ in d.keys()
        idx = exp_.find("!=")
        if idx > 0 and idx < e_idx:
            k, v = http_utils.break_into(exp_, '!=')
            if k not in d.keys():
                return False
            dvals = d[k]
            if isinstance(dvals, str):
                dvals = [dvals]
            for dv in dvals:
                if dv == v:
                    return False
            return True

        idx = exp_.find("^=")
        if idx > 0 and idx < e_idx:
            k, v = http_utils.break_into(exp_, "^=")
            if k not in d.keys():
                return False
            dvals = d[k]
            if isinstance(dvals, str):
                dvals = [dvals]
            for dv in dvals:
                _logger.debug(f"^= mapping:: {dv} ... {v}")
                if dv.startswith(v):
                    return True
            return False

        if e_idx > 0:
            k, v = http_utils.break_into(exp_, '=')
            if k not in d.keys():
                return False
            dvals = d[k]
            if isinstance(dvals, str):
                dvals = [dvals]
            for dv in dvals:
                if dv == v:
                    return True
            return False

        _logger.error(
            f"Controller {where} expression [{exp}] is not valied, returning False...")
        return False

    def __match_exps(self, d: Dict[str, Union[List[str], str]], exps: List[str], all: bool, where: str) -> bool:
        if not exps:
            return True

        for exp in exps:
            res = self.__match_one_exp(d, exp, where)
            if all and not res:
                return False
            if not all and res:  # match one
                return True
        # return if all True else False
        return all

    def __is_req_match_ctl(self, req: RequestWrapper, ctrl: _ControllerFunction) -> bool:
        _logger.debug(f"{ctrl.headers} - {ctrl.params}")
        return self.__match_exps(req.headers, ctrl.headers, ctrl.match_all_headers_expressions, 'headers') \
            and self.__match_exps(req.parameters, ctrl.params, ctrl.match_all_params_expressions, 'params')

    def __get_ctrl(self, req: RequestWrapper) -> Tuple[_ControllerFunction, Dict, List]:
        mth = self.method.upper()
        path = req._path
        ctrls = self.routing_conf.get_url_controllers(path, mth)
        for ctrl, pvs, regs in ctrls:
            if self.__is_req_match_ctl(req, ctrl):
                return ctrl, pvs, regs
        return None, {}, []

    async def handle_request(self):
        mth = self.method.upper()

        req = await self.__prepare_request(mth)

        ctrl, req.path_values, req.reg_groups = self.__get_ctrl(req)

        res = ResponseWrapper(self)
        if ctrl is None:
            res.send_error(404, "Controller Not Found",
                           "Cannot find a controller for your path")
        else:
            filters = self.routing_conf.get_matched_filters(req.path)
            ctx = FilterContextImpl(
                req, res, ctrl, self.routing_conf.model_binding_conf, filters)
            try:
                ctx.do_chain()
                if req._coroutine_objects:
                    _logger.debug(f"wait all the objects in waiting list.")
                    while req._coroutine_objects:
                        await req._coroutine_objects.pop(0)
            except HttpError as e:
                res.send_error(e.code, e.message, e.explain)
            except Exception as e:
                _logger.exception("error occurs! returning 500")
                res.send_error(500, None, str(e))

    async def __prepare_request(self, method) -> RequestWrapper:
        path = self.request_path
        req = RequestWrapper()
        req.environment = self.environment or {}
        req.path = "/" + path
        req._path = path
        req._session_fac = self.routing_conf.session_factory
        headers = {}
        _headers_keys_in_lowers: Dict[str, str] = {}
        for k in self.headers.keys():
            headers[k] = self.headers[k]
            _headers_keys_in_lowers[k.lower()] = self.headers[k]
        req.headers = headers
        req._headers_keys_in_lowcase = _headers_keys_in_lowers

        # cookies
        if "cookie" in _headers_keys_in_lowers.keys():
            req.cookies.load(_headers_keys_in_lowers["cookie"])

        req.method = method

        req.parameters = self.query_parameters

        if "content-length" in _headers_keys_in_lowers.keys():
            content_length = int(_headers_keys_in_lowers["content-length"])
            req.reader = RequestBodyReaderWrapper(self.reader, content_length)
        elif _headers_keys_in_lowers.get("transfer-encoding", "").lower() == "chunked":
            _logger.debug("chunked encoding")
            req.reader = RequestBodyReaderChunkedReader(self.reader)
        else:
            req.reader = RequestBodyReaderDumpWrapper(self.reader)

        content_type = _headers_keys_in_lowers.get("content-type", "")
        if content_type.lower().startswith("application/x-www-form-urlencoded"):
            charset = http_utils.get_charset(content_type)
            req._body = await req.reader.read_to_end()
            body_decoded_params = http_utils.decode_query_string(
                req._body.decode(charset))
        elif content_type.lower().startswith("multipart/form-data"):
            req._body = await req.reader.read_to_end()
            body_decoded_params = self.__decode_multipart(
                content_type, req._body.decode("ISO-8859-1"))
        elif content_type.lower().startswith("application/json"):
            charset = http_utils.get_charset(content_type)
            req._body = await req.reader.read_to_end()
            req.json = json.loads(req._body.decode(charset))
            body_decoded_params = {}
        else:
            body_decoded_params = {}
        req.parameters = self.__merge(body_decoded_params, req.parameters)

        return req

    def __merge(self, dic0: Dict[str, List[str]], dic1: Dict[str, List[str]]):
        """Merge tow dictionaries of which the structure is {k:[v1, v2]}"""
        dic = dic0
        for k, v in dic1.items():
            if k not in dic.keys():
                dic[k] = v
            else:
                for i in v:
                    dic[k].append(i)
        return dic

    def __decode_multipart(self, content_type, data):
        boundary = "--" + content_type.split("; ")[1].split("=")[1]
        fields = data.split(boundary)
        # ignore the first empty row and the last end symbol
        fields = fields[1: len(fields) - 1]
        params = {}
        for field in fields:
            # trim the first and the last empty row
            f = field[field.index("\r\n") + 2: field.rindex("\r\n")]
            key, val = self.__decode_multipart_field(f)
            http_utils.put_to(params, key, val)
        return params

    def __decode_multipart_field(self, field):
        # first line: Content-Disposition
        line, rest = self.__read_line(field)

        kvs = self.__decode_content_disposition(line)
        kname = kvs["name"].encode(
            "ISO-8859-1", errors="replace").decode(DEFAULT_ENCODING, errors="replace")
        if len(kvs) == 1:
            # this is a string field, the second line is an empty line, the rest is the value
            val = self.__read_line(rest)[1].encode(
                "ISO-8859-1", errors="replace").decode(DEFAULT_ENCODING, errors="replace")
        elif "filename" in kvs or "filename*" in kvs:
            if "filename*" in kvs:
                name_value = kvs["filename*"]
                idx = name_value.find("'")
                if idx <= 0:
                    encoding = DEFAULT_ENCODING
                else:
                    encoding = name_value[0:idx]
                name_value = name_value[idx + 1:]
                idx = name_value.find("'")
                filename = unquote(name_value[idx + 1:], encoding)
            else:
                filename = kvs["filename"].encode(
                    "ISO-8859-1", errors="replace").decode(DEFAULT_ENCODING, errors="replace")

            # the second line is Content-Type line
            ct_line, rest = self.__read_line(rest)
            content_type = ct_line.split(":")[1].strip()
            # the third line is an empty line, the rest is the value
            content = self.__read_line(rest)[1].encode(
                "ISO-8859-1", errors="replace")

            val = MultipartFile(kname, filename=filename,
                                content_type=content_type, content=content)
        else:
            val = "UNKNOWN"

        return kname, val

    def __decode_content_disposition(self, line) -> Dict[str, str]:
        cont_dis = {}
        es = line.split(";")[1:]
        for e in es:
            k, v = http_utils.break_into(e.strip(), "=")
            if v.startswith('"') and v.endswith('"'):
                cont_dis[k] = v[1: -1]  # ignore the '"' symbol
            else:
                cont_dis[k] = v
        return cont_dis

    def __read_line(self, txt):
        return http_utils.break_into(txt, "\r\n")

    def _send_response(self, response):
        try:
            headers = response["headers"]
            cks = response["cookies"]
            raw_body = response["body"]
            status_code = response["status_code"]
            content_type, body = http_utils.decode_response_body(raw_body)

            self._send_res(status_code, headers, content_type, cks, body)

        except HttpError as e:
            self.send_error(e.code, e.message, e.explain)

    def __send_res_headers(self, status_code: int, headers: Dict[str, str] = {}, content_type: str = "", cks: Cookies = Cookies()):
        if "Content-Type" not in headers.keys() and "content-type" not in headers.keys():
            headers["Content-Type"] = content_type
        elif "content-type" in headers.keys():
            headers["Content-Type"] = headers["content-type"]
            del headers["content-type"]

        self.send_response(status_code)
        self.send_header("Last-Modified", str(http_utils.date_time_string()))
        for k, v in headers.items():
            if isinstance(v, str):
                self.send_header(k, v)
            elif isinstance(v, list):
                for iov in v:
                    if isinstance(iov, str):
                        self.send_header(k, iov)

        for k in cks:
            ck = cks[k]
            self.send_header("Set-Cookie", ck.OutputString())

    def _send_and_end_res_headers(self, *args, **kwargs):
        """
        " For response object to send and writer headers.
        """
        self.__send_res_headers(*args, **kwargs)
        self.end_headers()

    def _should_send_gzip(self, headers: Dict[str, str]) -> bool:
        if "Accept-Encoding" not in self.headers.keys():
            return False
        accept_encoding = self.headers["Accept-Encoding"].split(",")
        acgzip = False
        for acoding in accept_encoding:
            if acoding.strip().lower().startswith("gzip"):
                acgzip = True
        if not acgzip:
            return False
        for ctype in self.routing_conf.gzip_content_types:
            if headers["Content-Type"].lower().startswith(ctype):
                return True
        return False

    def _send_res(self, status_code: int, headers: Dict[str, str] = {}, content_type: str = "", cks: Cookies = Cookies(), body: Union[str, bytes, bytearray, StaticFile] = None):
        self.__send_res_headers(status_code, headers, content_type, cks)
        if self._should_send_gzip(headers):
            self._send_gzip_data(body)
        else:
            self._send_raw_data(body)

    def _send_gzip_data(self, body):
        if body is None:
            self.send_header("Content-Length", 0)
            self.end_headers()
            return
        body_data = b''
        if isinstance(body, str):
            body_data = body.encode(DEFAULT_ENCODING, errors="replace")
        elif isinstance(body, bytes) or isinstance(body, bytearray):
            body_data = body
        elif isinstance(body, StaticFile):
            buffer_size = 1024 * 1024  # 1M
            with open(body.file_path, "rb") as in_file:
                buffer_data = in_file.read(buffer_size)
                while buffer_data:
                    body_data = body_data + buffer_data
                    buffer_data = in_file.read(buffer_size)

        gzip_data = gzip.compress(
            body_data, compresslevel=self.routing_conf.gzip_compress_level)

        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", len(gzip_data))
        self.end_headers()
        self.writer.write(gzip_data)

    def _send_raw_data(self, body):
        if body is None:
            self.send_header("Content-Length", 0)
            self.end_headers()
        elif isinstance(body, str):
            data = body.encode(DEFAULT_ENCODING, errors="replace")
            self.send_header("Content-Length", len(data))
            self.end_headers()
            self.writer.write(data)
        elif isinstance(body, bytes) or isinstance(body, bytearray):
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.writer.write(body)
        elif isinstance(body, StaticFile):
            file_size = os.path.getsize(body.file_path)
            self.send_header("Content-Length", file_size)
            self.end_headers()
            buffer_size = 1024 * 1024  # 1M
            with open(body.file_path, "rb") as in_file:
                data = in_file.read(buffer_size)
                while data:
                    self.writer.write(data)
                    data = in_file.read(buffer_size)

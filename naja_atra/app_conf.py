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

import sys
import inspect
import asyncio
import base64
from typing import Any, Dict, List, Type, Union, Callable

from naja_atra.request_handlers.http_session_local_impl import LocalSessionFactory

from .models import Headers, HttpSessionFactory, WebsocketHandler
from .models import WEBSOCKET_MESSAGE_BINARY, WEBSOCKET_MESSAGE_BINARY_FRAME, WEBSOCKET_MESSAGE_PING, WEBSOCKET_MESSAGE_PONG, WEBSOCKET_MESSAGE_TEXT
from .request_handlers.model_bindings import ModelBindingConf
from .utils.logger import get_logger

_logger = get_logger("naja_atra.app_conf")


def _get_class_of_method(method_defind):
    vals = vars(sys.modules[method_defind.__module__])
    for attr in method_defind.__qualname__.split('.')[:-1]:
        if attr in vals:
            vals = vals[attr]
            if not isinstance(vals, dict):
                break
    if inspect.isclass(vals):
        return vals


def _create_object(clz, args=[], kwargs={}):

    if clz is None:
        return None
    elif args and kwargs:
        return clz(*args, **kwargs)
    elif args:
        return clz(*args)
    elif kwargs:
        return clz(**kwargs)
    else:
        return clz()


def _to_str_list(obj: Union[str, list, tuple]):
    if isinstance(obj, list) or isinstance(obj, tuple):
        return [str(it) for it in obj]
    else:
        return [str(obj)]


class _ControllerFunction:

    def __init__(self, url: str = "",
                 regexp: str = "",
                 method: str = "",
                 headers: List[str] = [],
                 match_all_headers_expressions: bool = None,
                 params: List[str] = [],
                 match_all_params_expressions: bool = None,
                 func: Callable = None) -> None:
        self.__url: str = url
        self.__regexp = regexp
        self.__method: str = method
        self.singleton: bool = False
        self.ctr_obj_init_args = None
        self.ctr_obj_init_kwargs = None
        self.__ctr_obj: object = None
        self.__func: Callable = func
        self.__clz = False
        self.headers: List[str] = headers if isinstance(headers, list) else [
            headers]
        self._match_all_headers_expressions: bool = match_all_headers_expressions
        self.params: List[str] = params if isinstance(params, list) else [
            params]
        self._match_all_params_expressions: bool = match_all_params_expressions

    @property
    def match_all_headers_expressions(self):
        return self._match_all_headers_expressions if self._match_all_headers_expressions is not None else True

    @property
    def match_all_params_expressions(self):
        return self._match_all_params_expressions if self._match_all_params_expressions is not None else True

    @property
    def _is_config_ok(self):
        try:
            assert self.url or self.regexp, "you should set one of url and regexp"
            assert not (
                self.url and self.regexp), "you can only set one of url and regexp, not both"
            assert self.func is not None and (inspect.isfunction(
                self.func) or inspect.ismethod(self.func))
            return True
        except AssertionError as ae:
            _logger.warning(
                f"[{self.__url}|{self.regexp}] => {self.func} configurate error: {ae}")
            return False

    @property
    def url(self) -> str:
        return self.__url

    @property
    def regexp(self) -> str:
        return self.__regexp

    @property
    def method(self) -> str:
        return self.__method

    @property
    def clz(self) -> str:
        if self.__clz != False:
            return self.__clz
        if inspect.isfunction(self.func):
            self.__clz = _get_class_of_method(self.func)
        else:
            self.__clz = None
        return self.__clz

    @property
    def ctrl_object(self) -> object:
        if not self.singleton:
            obj = self._create_ctrl_obj()
            _logger.debug(f"singleton: create a object -> {obj}")
            return obj

        if self.__ctr_obj is None:
            self.__ctr_obj = self._create_ctrl_obj()
            _logger.debug(
                f"object does not exist, create one -> {self.__ctr_obj} ")
        else:
            _logger.debug(f"object[{self.__ctr_obj}] exists, return. ")
        return self.__ctr_obj

    def _create_ctrl_obj(self) -> object:
        return _create_object(self.clz, self.ctr_obj_init_args, self.ctr_obj_init_kwargs)

    @ctrl_object.setter
    def ctrl_object(self, val) -> None:
        self.__ctr_obj = val

    @property
    def func(self) -> Callable:
        return self.__func


class _WebsocketHandlerProxy(WebsocketHandler):

    def __init__(self) -> None:
        self.handshake: Callable = None
        self.open: Callable = None
        self.close: Callable = None
        self.ping: Callable = None
        self.pong: Callable = None
        self.text: Callable = None
        self.binary: Callable = None
        self.binary_frame: Callable = None

    async def await_func(self, obj):
        if asyncio.iscoroutine(obj):
            return await obj
        return obj

    async def on_handshake(self, *args, **kwargs):
        if self.handshake:
            return await self.await_func(self.handshake(*args, **kwargs))
        return None

    async def on_open(self, *args, **kwargs):
        if self.open:
            await self.await_func(self.open(*args, **kwargs))

    async def on_close(self, *args, **kwargs):
        if self.close:
            await self.await_func(self.close(*args, **kwargs))

    async def on_ping_message(self, *args, **kwargs):
        if self.ping:
            await self.await_func(self.ping(*args, **kwargs))
        else:
            return super().on_ping_message()

    async def on_pong_message(self, *args, **kwargs):
        if self.pong:
            await self.await_func(self.pong(*args, **kwargs))

    async def on_text_message(self, *args, **kwargs):
        if self.text:
            await self.await_func(self.text(*args, **kwargs))

    async def on_binary_message(self, *args, **kwargs):
        if self.binary:
            await self.await_func(self.binary(*args, **kwargs))

    async def on_binary_frame(self, *args, **kwargs):
        if self.binary_frame:
            return await self.await_func(self.binary_frame(*args, **kwargs))
        return super().on_binary_frame()


class _WebsocketHandlerClass:

    def __init__(self, url: str = "",
                 cls: Callable = None,
                 regexp: str = "",
                 singleton: bool = True
                 ) -> None:
        self.__url: str = url
        self.__regexp = regexp
        self.singleton: bool = singleton
        self.ctr_obj_init_args = None
        self.ctr_obj_init_kwargs = None
        self.__ctr_obj: object = None
        self.__cls: Callable = cls

    @property
    def _is_config_ok(self):
        try:
            assert self.url or self.regexp, "you should set one of url and regexp"
            assert not (
                self.url and self.regexp), "you can only set one of url and regexp, not both"
            assert self.cls is not None and inspect.isclass(self.cls)
            return True
        except AssertionError as ae:
            _logger.warning(
                f"[{self.__url}|{self.regexp}] => {self.cls} configurate error: {ae}")
            return False

    @property
    def url(self) -> str:
        return self.__url

    @property
    def regexp(self) -> str:
        return self.__regexp

    @property
    def cls(self) -> str:
        return self.__cls

    @property
    def ctrl_object(self) -> object:
        if not self.cls:
            return self.__ctr_obj
        if not self.singleton:
            obj = self._create_ctrl_obj()
            _logger.debug(f"singleton: create a object -> {obj}")
            return obj

        if self.__ctr_obj is None:
            self.__ctr_obj = self._create_ctrl_obj()
            _logger.debug(
                f"object does not exist, create one -> {self.__ctr_obj} ")
        else:
            _logger.debug(f"object[{self.__ctr_obj}] exists, return. ")
        return self.__ctr_obj

    def _create_ctrl_obj(self) -> object:
        return _create_object(self.cls, self.ctr_obj_init_args, self.ctr_obj_init_kwargs)

    @ctrl_object.setter
    def ctrl_object(self, val) -> None:
        self.__ctr_obj = val


__favicon = base64.b64decode(
    b'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAFcklEQVRYR+1XW0wUZxT+Zm8gy2WBZRFYBBfDRhG1gkAaNYQY26ap6UPTpj409pK2SdOkTdq01SZNtPWhPhibpn00bWLs5cW2tiVpH7QaRRAERURRoEWEhXVBltvO7Mz0nH9m' +
    b'V9blYhOTxsQ/bHbn8p/znfN955tB0mnhf1zSIwCPOvDQdSAUDqMzPIO+6QgmFRUSzZDdakVRqg2V6Snw5mRDkqT7nqv7moLOkSCODo7j11FKrtqgwgpIljlJKCEBkfQoShHBDk8GXi7Oxvp895JAFgXQFgji4+5hNE5RfImSWigRF6ffU+Fc' +
    b'J+FrhE3SVTybruPgWi9KXJkLApkXgKZp2NfRi0+HZhG12oxqOQn3ezHbEp5G93JzBFAdLl3BUX8uniwtmBdEEoCoquLVpmv4diIWyGivWPzNSfjDPDOguaC4+linjJsBTUdKVMPxymxsK1meBCIJwJ7z17F/VANsZhIuRcTSKJCCI+XZcDms' +
    b'eK1rHP2ckJgRgAi4U1NJkDaM2+wGQFAc+mPKPGoEl7f64E5PSwCRAKBrNIQNzSNQrBzY5FtUTr8pwdtuG76oXiUCXBoJobZpGPVOBY2zDpST+D4rd8O9zIb6y+NEAwuVwXMXOIaKj/Js2F9l7I+tBACvnOnB4QlGrhqVxdtO5yjIH5UubPN6' +
    b'4pt/6LmFA91B9NLtNSnA8e0VmJmdReaJG9DtqSYAkzoK4FWm0P/UelhpbJMARKm9nt+uYsxBGzmbmDKTfJ0OKElHdS7WeXISKghMTOK91gEceKwQy11ZGAtPIvevvwkA02B2T0wNxYzKuFFbAJ87NxlAXzAE37nbRuu5bdaY8syRU3X86M/A' +
    b'c75kNbcPBlCUkYa8zAwc6uzHOwMRowCLOT0xAETj2Q1u1BXmJQO4NHIb61oZAO+k5GKUTMULIeposMn4s37tgk7XSRqqaR7GjJ2NgP3AoE4EIw2ARNqywYPq5XcNKq6BgdAYVpwLEAAWD+0RNLGKzWnghqhRfO1Nw5sVKxNoiB3sOHkFv0xT' +
    b'Mu6eKIRD8EYOpkGSVQQ2FyEv664xxQFohK7w904E7MsMAML1WMEEYo772UkrP68mYylJpGJschL5J/+BYifjEu03JSQmwDjwaxFceaIioYMJU7DrzFV8E+bEhp2KxHEAfGxQ4VIVNG3ywp/rineieWgUtReJQuZdeEBMwLyHqdDwPo3h51W+' +
    b'hO4lAOAgdRdC0FmIcd8XHmxSYe4lEHUWGacb1sRHqoWeGzUXgub8832sH9NLiH5LVEVXXT787uyFAfCVF09dwXdTVAULKVaFENI9S9FwZJUTO8uLxYUgPabzTw1AYwpiBiRayCam43mnhu+3+JPCJFlxIDyFqtM3MGhzJD5yzUaICJyAQFVp' +
    b'02jZvs7kVEdFYwe6JNKQoMHcQF9pkSguPl6IspyspQHwHa3DQTS0DWGCQcRmmbXAH6aGJ4WEJUVkXKe2+tyGOb10phud0yqG6EVl2EpAeFH1X3odeKuydJ42Ms4F/i84S3p4pmMEtyVyNKpiJz3bP1iVi74ZGXt7x9Em03kasZ/WZGLHSuMp' +
    b'92FbH06MTqLA6cCxMCe3YI9Hwr5NZQt6x6IvJD2hO3ih9RbaZ4HA1kKaX6OFsqLg3fO9+CokoWljDmoLDGPZ3daPY4NT+GR1NnZ13cFBnxNvVBQv+oq25CvZrKxgb3s/imwqXq8sg509nlZ4ehqHWrqwe8tGYskwncOt3XjaX4xro+PIcqah' +
    b'0pOo+Pk4WBJAbNOtOxNovjmEVHovsJAOUh0p2OxbQb+NJ1vPzUE4UtNQcs+YzUv8nJP3DWCxQIoiQ5ZlOJ3pS+VLuv5AAPznrA+6Aw81gH8BHb95v9r9AsoAAAAASUVORK5CYII='
)


def _favicon():
    return Headers({"Content-Type": "image/png"}), __favicon


class AppConf:

    def __init__(self) -> None:
        self._request_mappings: List[_ControllerFunction] = []
        self._request_clz_mapping: Dict[Any, _ControllerFunction] = {}

        self._filters = []

        self._ctrls = {}
        self._ctrl_singletons = {}

        self._ws_handlers: Dict[str, _WebsocketHandlerClass] = {}

        self._error_page = {}

        self._session_factory: HttpSessionFactory = None # NOSONAR

        self.request_map("/favicon.ico")(_favicon)
        self.route = self.request_map
        self.model_binding_conf = ModelBindingConf()

    @property
    def session_factory(self):
        if self._session_factory == None:
            self._session_factory = LocalSessionFactory()
        return self._session_factory

    @session_factory.setter
    def session_factory(self, session_factory: HttpSessionFactory):
        self._session_factory = session_factory

    def model_binding(self, arg_type: Type):
        def map(model_binding_type):
            self.model_binding_conf.model_bingding_types[arg_type] = model_binding_type
            return model_binding_type
        return map

    def default_model_binding(self, *anno_args):
        def map(model_binding_type):
            self.model_binding_conf.default_model_binding_type = model_binding_type
            return model_binding_type
        if len(anno_args) == 1 and inspect.isclass(anno_args[0]):
            return map(anno_args[0])
        return map

    def controller(self, *anno_args, singleton: bool = True, args: List[Any] = [], kwargs: Dict[str, Any] = {}):
        def map(ctr_obj_class):
            _logger.debug(
                f"map controller[{ctr_obj_class}]({singleton}) with args: {args}, and kwargs: {kwargs})")
            self._ctrls[ctr_obj_class] = (singleton, args, kwargs)
            return ctr_obj_class
        if len(anno_args) == 1 and inspect.isclass(anno_args[0]):
            return map(anno_args[0])
        return map

    def request_map(self, *anno_args,
                    url: str = "",
                    regexp: str = "",
                    method: Union[str, list, tuple] = "",
                    headers: Union[str, list, tuple] = "",
                    match_all_headers_expressions: bool = None,
                    params: Union[str, list, tuple] = "",
                    match_all_params_expressions: bool = None) -> Callable:
        _url = url
        len_args = len(anno_args)
        assert len_args <= 1

        arg_ctrl = None
        if len_args == 1:
            if isinstance(anno_args[0], str):
                assert not url and not regexp
                _url = anno_args[0]
            elif callable(anno_args[0]):
                arg_ctrl = anno_args[0]

        def map(ctrl):
            if isinstance(method, list):
                mths = method
            elif isinstance(method, tuple):
                mths = list(method)
            else:
                mths = [m.strip() for m in method.split(',')]

            hs = _to_str_list(headers)
            ps = _to_str_list(params)

            if inspect.isclass(ctrl):
                self._request_clz_mapping[ctrl] = _ControllerFunction(url=_url,
                                                                      regexp=regexp,
                                                                      method=mths,
                                                                      headers=hs,
                                                                      match_all_headers_expressions=match_all_headers_expressions,
                                                                      params=ps,
                                                                      match_all_params_expressions=match_all_params_expressions,
                                                                      func=ctrl)

                return ctrl

            for mth in mths:
                cf = _ControllerFunction(url=_url,
                                         regexp=regexp,
                                         method=mth,
                                         headers=hs,
                                         match_all_headers_expressions=match_all_headers_expressions,
                                         params=ps,
                                         match_all_params_expressions=match_all_params_expressions,
                                         func=ctrl)
                _logger.debug(
                    f"map url {_url} with method[{mth}] to function {ctrl}. with headers {cf.headers} and params {cf.params}")
                self._request_mappings.append(cf)
            # return the original function, so you can use a decoration chain
            return ctrl

        if arg_ctrl:
            return map(arg_ctrl)
        else:
            return map

    def request_filter(self, path: str = "", regexp: str = ""):
        p = path
        r = regexp
        assert (p and not r) or (not p and r)

        def map(filter_fun):
            self._filters.append(
                {"path": p, "url_pattern": r, "func": filter_fun})
            return filter_fun
        return map

    def filter_map(self, regexp: str = "", filter_function: Callable = None) -> Callable:
        """ deprecated, plese request_filter instead. """
        def map(filter_fun):
            self._filters.append({"url_pattern": regexp, "func": filter_fun})
            return filter_fun
        if filter_function:
            map(filter_function)
        return map

    def _get_singletion(self, clz, args, kwargs):
        if clz not in self._ctrl_singletons:
            self._ctrl_singletons[clz] = _create_object(clz, args, kwargs)
        return self._ctrl_singletons[clz]

    def websocket_handler(self, endpoint: str = "", regexp: str = "", singleton: bool = True) -> Callable:
        def map(ws_class):
            self._ws_handlers[endpoint + ":::" + regexp] = _WebsocketHandlerClass(
                url=endpoint, regexp=regexp, cls=ws_class, singleton=singleton)
            return ws_class

        return map

    def websocket_handshake(self, endpoint: str = "", regexp: str = "") -> Callable:
        def map(ctrl):
            k = endpoint + ":::" + regexp
            if k not in self._ws_handlers:
                handler = _WebsocketHandlerClass(url=endpoint, regexp=regexp)
                handler.ctrl_object = _WebsocketHandlerProxy()
                handler.ctrl_object.handshake = ctrl
                self._ws_handlers[k] = handler
            else:
                handler = self._ws_handlers[k]
                if not handler.cls and isinstance(handler.ctrl_object, _WebsocketHandlerProxy):
                    handler.ctrl_object.handshake = ctrl
            return ctrl
        return map

    def websocket_open(self, endpoint: str = "", regexp: str = "") -> Callable:
        def map(ctrl):
            k = endpoint + ":::" + regexp
            if k not in self._ws_handlers:
                handler = _WebsocketHandlerClass(url=endpoint, regexp=regexp)
                handler.ctrl_object = _WebsocketHandlerProxy()
                handler.ctrl_object.open = ctrl
                self._ws_handlers[k] = handler
            else:
                handler = self._ws_handlers[k]
                if not handler.cls and isinstance(handler.ctrl_object, _WebsocketHandlerProxy):
                    handler.ctrl_object.open = ctrl
            return ctrl
        return map

    def websocket_close(self, endpoint: str = "", regexp: str = "") -> Callable:
        def map(ctrl):
            k = endpoint + ":::" + regexp
            if k not in self._ws_handlers:
                handler = _WebsocketHandlerClass(url=endpoint, regexp=regexp)
                handler.ctrl_object = _WebsocketHandlerProxy()
                handler.ctrl_object.close = ctrl
                self._ws_handlers[k] = handler
            else:
                handler = self._ws_handlers[k]
                if not handler.cls and isinstance(handler.ctrl_object, _WebsocketHandlerProxy):
                    handler.ctrl_object.close = ctrl
            return ctrl
        return map

    def websocket_message(self, endpoint: str = "", regexp: str = "", message_type: str = WEBSOCKET_MESSAGE_TEXT) -> Callable:
        def map(ctrl):
            k = endpoint + ":::" + regexp
            if k not in self._ws_handlers:
                handler = _WebsocketHandlerClass(url=endpoint, regexp=regexp)
                handler.ctrl_object = _WebsocketHandlerProxy()
                self._ws_handlers[k] = handler

            handler = self._ws_handlers[k]
            if not handler.cls and isinstance(handler.ctrl_object, _WebsocketHandlerProxy):
                if message_type == WEBSOCKET_MESSAGE_TEXT:
                    handler.ctrl_object.text = ctrl
                elif message_type == WEBSOCKET_MESSAGE_BINARY:
                    handler.ctrl_object.binary = ctrl
                elif message_type == WEBSOCKET_MESSAGE_BINARY_FRAME:
                    handler.ctrl_object.binary_frame = ctrl
                elif message_type == WEBSOCKET_MESSAGE_PING:
                    handler.ctrl_object.ping = ctrl
                elif message_type == WEBSOCKET_MESSAGE_PONG:
                    handler.ctrl_object.pong = ctrl
                else:
                    _logger.error(
                        f"Cannot match message type: [{message_type}]!")
            return ctrl
        return map

    def error_message(self, *anno_args):
        len_args = len(anno_args)
        arg_func = None

        if len_args == 1:
            if callable(anno_args[0]): # NOSONAR
                arg_func = anno_args[0]

        if not arg_func:
            if anno_args:
                args = list(anno_args)
            else:
                args = [""]
        else:
            args = [""]

        def map(func):
            for arg in args:
                self._error_page[arg] = func
            return func

        if arg_func:
            return map(arg_func)
        else:
            return map

    def _get_request_mappings(self) -> List[_ControllerFunction]: # NOSONAR
        mappings: List[_ControllerFunction] = []

        for ctr_fun in self._request_mappings:
            clz = ctr_fun.clz
            if clz is not None and clz in self._request_clz_mapping:
                clz_ctrl = self._request_clz_mapping[clz]
                clz_url = clz_ctrl.url
                methods = clz_ctrl.method

                if ctr_fun.regexp:
                    full_url = ctr_fun.url
                else:
                    fun_url = ctr_fun.url
                    if fun_url:
                        if not clz_url.endswith("/"):
                            clz_url = clz_url + "/"
                        if fun_url.startswith("/"):
                            fun_url = fun_url[1:]
                        full_url = f"{clz_url}{fun_url}"
                    else:
                        full_url = clz_url

                hs = ctr_fun.headers + clz_ctrl.headers
                mhs = ctr_fun._match_all_headers_expressions if ctr_fun._match_all_headers_expressions is not None else clz_ctrl._match_all_headers_expressions
                ps = ctr_fun.params + clz_ctrl.params
                mps = ctr_fun._match_all_params_expressions if ctr_fun._match_all_params_expressions is not None else clz_ctrl._match_all_params_expressions
                if not ctr_fun.method and methods:
                    for mth in methods:
                        _logger.debug(
                            f"map url {full_url} included [{clz_url}] with method[{mth}] to function {ctr_fun.func}. ")
                        mappings.append(_ControllerFunction(url=full_url,
                                                            regexp=ctr_fun.regexp,
                                                            method=mth,
                                                            func=ctr_fun.func,
                                                            headers=hs,
                                                            match_all_headers_expressions=mhs,
                                                            params=ps,
                                                            match_all_params_expressions=mps))
                else:
                    _logger.debug(
                        f"map url {full_url} included [{clz_url}] with method[{ctr_fun.method}] to function {ctr_fun.func}. ")
                    mappings.append(_ControllerFunction(url=full_url,
                                                        regexp=ctr_fun.regexp,
                                                        method=ctr_fun.method,
                                                        func=ctr_fun.func,
                                                        headers=hs,
                                                        match_all_headers_expressions=mhs,
                                                        params=ps,
                                                        match_all_params_expressions=mps))
            else:
                mappings.append(ctr_fun)

        for ctr_fun in mappings:
            if not ctr_fun._is_config_ok:
                continue
            clz = ctr_fun.clz
            if clz is not None and clz in self._ctrls:
                singleton, args, kwargs = self._ctrls[clz]
                ctr_fun.singleton = singleton
                ctr_fun.ctr_obj_init_args = args
                ctr_fun.ctr_obj_init_kwargs = kwargs
                if singleton:
                    ctr_fun.ctrl_object = self._get_singletion(
                        clz, args, kwargs)

        return mappings

    def _get_filters(self):
        return self._filters

    def _get_websocket_handlers(self) -> List[_WebsocketHandlerClass]:
        return list(self._ws_handlers.values())

    def _get_error_pages(self) -> Dict[str, Callable]:
        return self._error_page


_default_app_conf = AppConf()
_app_confs: Dict[str, AppConf] = {}


def controller(*anno_args, singleton: bool = True, args: List[Any] = [], kwargs: Dict[str, Any] = {}):
    return _default_app_conf.controller(*anno_args, singleton=singleton, args=args, kwargs=kwargs)


def request_map(*anno_args,
                url: str = "",
                regexp: str = "",
                method: Union[str, list, tuple] = "",
                headers: Union[str, list, tuple] = "",
                match_all_headers_expressions: bool = None,
                params: Union[str, list, tuple] = "",
                match_all_params_expressions: bool = None) -> Callable:
    return _default_app_conf.request_map(*anno_args, url=url,
                                         regexp=regexp,
                                         method=method,
                                         headers=headers,
                                         match_all_headers_expressions=match_all_headers_expressions,
                                         params=params,
                                         match_all_params_expressions=match_all_params_expressions)


route = request_map


def request_filter(path: str = "", regexp: str = ""):
    return _default_app_conf.request_filter(path=path, regexp=regexp)


def filter_map(regexp: str = "", filter_function: Callable = None) -> Callable:
    """ deprecated, plese request_filter instead. """
    _logger.warning(
        "`filter_map` is deprecated and will be removed in future version,  please use `request_filter` instead. ")
    return _default_app_conf.filter_map(regexp=regexp, filter_function=filter_function)


def websocket_handler(endpoint: str = "", regexp: str = "", singleton: bool = True) -> Callable:
    return _default_app_conf.websocket_handler(endpoint=endpoint, regexp=regexp, singleton=singleton)


def websocket_handshake(endpoint: str = "", regexp: str = ""):
    return _default_app_conf.websocket_handshake(endpoint=endpoint, regexp=regexp)


def websocket_open(endpoint: str = "", regexp: str = ""):
    return _default_app_conf.websocket_open(endpoint=endpoint, regexp=regexp)


def websocket_close(endpoint: str = "", regexp: str = ""):
    return _default_app_conf.websocket_close(endpoint=endpoint, regexp=regexp)


def websocket_message(endpoint: str = "", regexp: str = "", message_type: str = WEBSOCKET_MESSAGE_TEXT):
    return _default_app_conf.websocket_message(endpoint=endpoint, regexp=regexp, message_type=message_type)


def error_message(*anno_args):
    return _default_app_conf.error_message(*anno_args)


def model_binding(arg_type: Type):
    return _default_app_conf.model_binding(arg_type)


def default_model_binding(*anno_args):
    return _default_app_conf.default_model_binding(*anno_args)


def set_session_factory(session_factory: HttpSessionFactory):
    _default_app_conf.session_factory = session_factory


def get_app_conf(tag: str = "") -> AppConf:
    if not tag:
        return _default_app_conf
    if tag not in _app_confs:
        _app_confs[tag] = AppConf()
    return _app_confs[tag]

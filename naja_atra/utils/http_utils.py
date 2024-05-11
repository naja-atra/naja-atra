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

import inspect
import time
import os
import email
import json
import re
from collections import OrderedDict
from typing import Any, Tuple, Union
from urllib.parse import unquote, quote
from ..models import HttpError, StaticFile, DEFAULT_ENCODING

from .logger import get_logger


_logger = get_logger("naja_atra.utils.http_utils")


def remove_url_first_slash(url: str):
    _url = url
    while _url.startswith("/"):
        _url = url[1:]
    return _url


def get_function_args(func, default_type=str):
    argspec = inspect.getfullargspec(func)
    # ignore first argument like `self` or `clz` in object methods or class methods
    start = 1 if inspect.ismethod(func) else 0
    if argspec.defaults is None:
        args = argspec.args[start:]
    else:
        args = argspec.args[start: len(argspec.args) - len(argspec.defaults)]
    arg_turples = []
    for arg in args:
        if arg in argspec.annotations:
            ty = argspec.annotations[arg]
        else:
            ty = default_type
        arg_turples.append((arg, ty))
    return arg_turples


def get_function_kwargs(func, default_type=str):
    argspec = inspect.getfullargspec(func)
    if argspec.defaults is None:
        return []

    kwargs = OrderedDict(
        zip(argspec.args[-len(argspec.defaults):], argspec.defaults))
    kwarg_turples = []
    for k, v in kwargs.items():
        if k in argspec.annotations:
            k_anno = argspec.annotations[k]
        else:
            k_anno = default_type
        kwarg_turples.append((k, v, k_anno))
    return kwarg_turples


def break_into(txt: str, separator: str):
    try:
        idx = txt.index(separator)
        return txt[0: idx], txt[idx + len(separator):]
    except ValueError:
        return txt, None


def put_to(params, key, val):
    if key not in params.keys():
        params[key] = [val]
    else:
        params[key].append(val)


def decode_query_string(query_string: str):
    params = {}
    if not query_string:
        return params
    pairs = query_string.split("&")
    for item in pairs:
        key, val = break_into(item, "=")
        if val is None:
            val = ""
        put_to(params, unquote(key), unquote(val))

    return params


def get_charset(s: str) -> str:
    pattern = re.compile(r"charset=([^;]+)")
    m = pattern.search(s)
    if m is not None:
        return m.group(1)
    else:
        return DEFAULT_ENCODING


def date_time_string(timestamp=None):
    if timestamp is None:
        timestamp = time.time()
    return email.utils.formatdate(timestamp, usegmt=True)


def decode_response_body(raw_body: Any) -> Tuple[str, Union[str,  bytes, StaticFile]]:
    content_type = "text/plain; chartset=utf8"
    if raw_body is None:
        body = ""
    elif isinstance(raw_body, dict):
        content_type = "application/json; charset=utf8"
        body = json.dumps(raw_body, ensure_ascii=False)
    elif isinstance(raw_body, str):
        body = raw_body.strip()
        if body.startswith("<?xml") and body.endswith(">"):
            content_type = "text/xml; charset=utf8"
        elif body.lower().startswith("<!doctype html") and body.endswith(">"):
            content_type = "text/html; charset=utf8"
        elif body.lower().startswith("<html") and body.endswith(">"):
            content_type = "text/html; charset=utf8"
        else:
            content_type = "text/plain; charset=utf8"
    elif isinstance(raw_body, StaticFile):
        if not os.path.isfile(raw_body.file_path):
            _logger.error(
                f"Cannot find file[{raw_body.file_path}] specified in StaticFile body.")
            raise HttpError(404, explain="Cannot find file for this url.")
        else:
            body = raw_body
            content_type = body.content_type
    elif isinstance(raw_body, bytes):
        body = raw_body
        content_type = "application/octet-stream"
    else:
        body = raw_body
    return content_type, body


def decode_response_body_to_bytes(raw_body: Any) -> Tuple[str, bytes]:
    content_type, body = decode_response_body(raw_body)
    if body is None:
        byte_body = b''
    elif isinstance(body, str):
        byte_body = body.encode(DEFAULT_ENCODING, 'replace')
    elif isinstance(body, bytes):
        byte_body = body
    elif isinstance(body, StaticFile):
        with open(body.file_path, "rb") as in_file:
            byte_body = in_file.read()
    else:
        raise HttpError(400, explain="Cannot read body into bytes!")
    return content_type, byte_body


def get_path_reg_pattern(url):
    _url: str = url
    path_names = re.findall("(?u)\\{\\w+\\}", _url)
    if len(path_names) == 0:
        if _url.startswith("**"):
            _url = _url[2:]
            assert _url.find(
                "*") < 0, "You can only config a * or ** at the start or end of a path."
            _url = f'^([\\w%.\\-@!\\(\\)\\[\\]\\|\\$/]+){_url}$'
            return _url, [quote("__path_wildcard")]
        elif _url.startswith("*"):
            _url = _url[1:]
            assert _url.find(
                "*") < 0, "You can only config a * or ** at the start or end of a path."
            _url = f'^([\\w%.\\-@!\\(\\)\\[\\]\\|\\$]+){_url}$'
            return _url, [quote("__path_wildcard")]
        elif _url.endswith("**"):
            _url = _url[0: -2]
            assert _url.find(
                "*") < 0, "You can only config a * or ** at the start or end of a path."
            _url = f'^{_url}([\\w%.\\-@!\\(\\)\\[\\]\\|\\$/]+)$'
            return _url, [quote("__path_wildcard")]
        elif _url.endswith("*"):
            _url = _url[0: -1]
            assert _url.find(
                "*") < 0, "You can only config a * or ** at the start or end of a path."
            _url = f'^{_url}([\\w%.\\-@!\\(\\)\\[\\]\\|\\$]+)$'
            return _url, [quote("__path_wildcard")]
        else:
            # normal url
            return None, path_names
    for name in path_names:
        _url = _url.replace(name, "([\\w%.\\-@!\\(\\)\\[\\]\\|\\$]+)")
    _url = f"^{_url}$"

    quoted_names = []
    for name in path_names:
        name = name[1: -1]
        quoted_names.append(quote(name))
    return _url, quoted_names

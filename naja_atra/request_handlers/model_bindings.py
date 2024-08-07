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

import json
import sys
from typing import Any, Dict, List, Type
from http.cookies import BaseCookie, SimpleCookie
from ..models import ModelDict, Environment, RegGroup, RegGroups, HttpError, RequestBodyReader, \
    Headers, Response, Cookies, Cookie, JSONBody, BytesBody, Header, Parameters, PathValue, Parameter, \
    MultipartFile, Request, HttpSession
from ..utils.logger import get_logger

_logger = get_logger("naja_atra.models.model_bindings")


class ModelBinding:

    def __init__(self, request: Request,
                 response: Response,
                 arg: str,
                 arg_type,
                 val=None
                 ) -> None:
        self.request = request
        self.response = response
        self.arg_name = arg
        self.arg_type = arg_type
        self.default_value = val
        self._kws = {}
        if self.default_value is not None:
            self._kws["val"] = self.default_value

    async def bind(self) -> Any:
        pass


class RequestModelBinding(ModelBinding):

    async def bind(self) -> Request:
        return self.request


class SessionModelBinding(ModelBinding):

    async def bind(self) -> HttpSession:
        return self.request.get_session(True)


class ResponseModelBinding(ModelBinding):

    async def bind(self) -> Response:
        return self.response


class HeadersModelBinding(ModelBinding):

    async def bind(self) -> Headers:
        return Headers(self.request.headers)


class RegGroupsModelBinding(ModelBinding):

    async def bind(self) -> RegGroups:
        return RegGroups(self.request.reg_groups)


class EnvironmentModelBinding(ModelBinding):

    async def bind(self) -> Environment:
        return Environment(self.request.environment)


class HeaderModelBinding(ModelBinding):

    async def bind(self) -> Header:
        return self.__build_header(self.arg_name, **self._kws)

    def __build_header(self, key, val=Header()):
        name = val.name if val.name is not None and val.name != "" else key
        if val._required and name not in self.request.headers:
            raise HttpError(400, "Missing Header",
                            f"Header[{name}] is required.")
        if name in self.request.headers:
            v = self.request.headers[name]
            return Header(name=name, default=v, required=val._required)
        else:
            return val


class CookiesModelBinding(ModelBinding):

    async def bind(self) -> Cookies:
        return self.request.cookies


class CookieModelBinding(ModelBinding):

    async def bind(self) -> Cookie:
        return self.__build_cookie(self.arg_name, **self._kws)

    def __build_cookie(self, key, val=None):
        name = val.name if val.name is not None and val.name != "" else key
        if val._required and name not in self.request.cookies:
            raise HttpError(400, "Missing Cookie",
                            f"Cookie[{name}] is required.")
        if name in self.request.cookies:
            morsel = self.request.cookies[name]
            cookie = Cookie()
            cookie.set(morsel.key, morsel.value, morsel.coded_value)
            cookie.update(morsel)
            return cookie
        else:
            return val


class MultipartFileModelBinding(ModelBinding):

    async def bind(self) -> MultipartFile:
        return self.__build_multipart(self.arg_name, **self._kws)

    def __build_multipart(self, key, val=MultipartFile()):
        name = val.name if val.name is not None and val.name != "" else key
        if val._required and name not in self.request.parameter.keys():
            raise HttpError(400, "Missing Parameter",
                            f"Parameter[{name}] is required.")
        if name in self.request.parameter.keys():
            v = self.request.parameter[name]
            if isinstance(v, MultipartFile):
                return v
            else:
                raise HttpError(
                    400, None, f"Parameter[{name}] should be a file.")
        else:
            return val


class ParameterModelBinding(ModelBinding):

    async def bind(self) -> Parameter:
        return self.__build_param(self.arg_name, **self._kws)

    def __build_param(self, key, val=Parameter()):
        name = val.name if val.name is not None and val.name != "" else key
        if val._required and name not in self.request.parameter:
            raise HttpError(400, "Missing Parameter",
                            f"Parameter[{name}] is required.")
        if name in self.request.parameter:
            v = self.request.parameter[name]
            return Parameter(name=name, default=v, required=val._required)
        else:
            return val


class PathValueModelBinding(ModelBinding):

    async def bind(self) -> PathValue:
        return self.__build_path_value(self.arg_name, **self._kws)

    def __build_path_value(self, key, val=PathValue()):
        # wildcard value
        if len(self.request.path_values) == 1 and "__path_wildcard" in self.request.path_values:
            if val.name:
                _logger.warning(
                    f"Wildcard value, `name` of the PathValue:: [{val.name}] will be ignored. ")
            return self.request.path_values["__path_wildcard"]

        # brace values
        name = val.name if val.name is not None and val.name != "" else key
        if name in self.request.path_values:
            return PathValue(name=name, _value=self.request.path_values[name])
        else:
            raise HttpError(
                500, None, f"path name[{name}] not in your url mapping!")


class ParametersModelBinding(ModelBinding):

    async def bind(self) -> Parameters:
        return self.__build_params(self.arg_name, **self._kws)

    def __build_params(self, key, val=Parameters()):
        name = val.name if val.name is not None and val.name != "" else key
        if val._required and name not in self.request.parameters:
            raise HttpError(400, "Missing Parameter",
                            f"Parameter[{name}] is required.")
        if name in self.request.parameters:
            v = self.request.parameters[name]
            return Parameters(name=name, default=v, required=val._required)
        else:
            return val


class RegGroupModelBinding(ModelBinding):

    async def bind(self) -> RegGroup:
        return self.__build_reg_group(**self._kws)

    def __build_reg_group(self, val: RegGroup = RegGroup(group=0)):
        if val.group >= len(self.request.reg_groups):
            raise HttpError(400, None, f"RegGroup required an element at {val.group}, but the reg length is only {len(self.request.reg_groups)}")
        return RegGroup(group=val.group, _value=self.request.reg_groups[val.group])


class JSONBodyModelBinding(ModelBinding):

    async def bind(self) -> Any:
        return self.__build_json_body()

    def __build_json_body(self):
        if "content-type" not in self.request._headers_keys_in_lowcase.keys() or \
                not self.request._headers_keys_in_lowcase["content-type"].lower().startswith("application/json"):
            raise HttpError(400, None, 'The content type of this request must be "application/json"')
        return JSONBody(self.request.json)


class RequestBodyReaderModelBinding(ModelBinding):

    async def bind(self) -> Any:
        return self.request.reader


class BytesBodyModelBinding(ModelBinding):

    async def bind(self) -> Any:
        if not self.request._body:
            self.request._body = await self.request.reader.read_to_end()
        return BytesBody(self.request._body)


class StrModelBinding(ModelBinding):

    async def bind(self) -> Any:
        return self.__build_str(self.arg_name, **self._kws)

    def __build_str(self, key, val=None):
        if key in self.request.parameter.keys():
            return Parameter(name=key, default=self.request.parameter[key], required=False)
        elif val is None:
            return None
        else:
            return Parameter(name=key, default=val, required=False)


class BoolModelBinding(ModelBinding):

    async def bind(self) -> Any:
        return self.__build_bool(self.arg_name, **self._kws)

    def __build_bool(self, key, val=None):
        if key in self.request.parameter.keys():
            v = self.request.parameter[key]
            return v.lower() not in ("0", "false", "")
        else:
            return val


class IntModelBinding(ModelBinding):

    async def bind(self) -> Any:
        return self.__build_int(self.arg_name, **self._kws)

    def __build_int(self, key, val=None):
        if key in self.request.parameter.keys():
            try:
                return int(self.request.parameter[key])
            except:
                raise HttpError(
                    400, None, f"Parameter[{key}] should be an int. ")
        else:
            return val


class FloatModelBinding(ModelBinding):

    async def bind(self) -> Any:
        return self.__build_float(self.arg_name, **self._kws)

    def __build_float(self, key, val=None):
        if key in self.request.parameter.keys():
            try:
                return float(self.request.parameter[key])
            except:
                raise HttpError(
                    400, None, f"Parameter[{key}] should be an float. ")
        else:
            return val


class ListModelBinding(ModelBinding):

    async def bind(self) -> Any:
        return self.__build_list(self.arg_name, **self._kws)

    def __build_list(self, key, target_type=list, val=[]):
        if key in self.request.parameters.keys():
            ori_list = self.request.parameters[key]
        else:
            ori_list = val

        if target_type == List[int]:
            try:
                return [int(p) for p in ori_list]
            except:
                raise HttpError(
                    400, None, f"One of the parameter[{key}] is not int. ")
        elif target_type == List[float]:
            try:
                return [float(p) for p in ori_list]
            except:
                raise HttpError(
                    400, None, f"One of the parameter[{key}] is not float. ")
        elif target_type == List[bool]:
            return [p.lower() not in ("0", "false", "") for p in ori_list]
        elif target_type in (List[dict], List[Dict]):
            try:
                return [json.loads(p) for p in ori_list]
            except:
                raise HttpError(
                    400, None, f"One of the parameter[{key}] is not JSON string. ")
        elif target_type == List[Parameter]:
            return [Parameter(name=key, default=p, required=False) for p in ori_list]
        else:
            return ori_list


class ModelDictModelBinding(ModelBinding):

    async def bind(self) -> Any:
        return self.__build_model_dict()

    def __build_model_dict(self):
        mdict = ModelDict()
        for k, v in self.request.parameters.items():
            if len(v) == 1:
                mdict[k] = v[0]
            else:
                mdict[k] = v
        return mdict


class DictModelBinding(ModelBinding):

    async def bind(self) -> Any:
        return self.__build_dict(self.arg_name, **self._kws)

    def __build_dict(self, key, val={}):
        if key in self.request.parameter.keys():
            try:
                return json.loads(self.request.parameter[key])
            except:
                raise HttpError(
                    400, None, f"Parameter[{key}] should be a JSON string.")
        else:
            return val


class DefaultModelBinding(ModelBinding):

    async def bind(self) -> Any:
        return self.default_value


class ModelBindingConf:

    def __init__(self) -> None:
        self.default_model_binding_type = DefaultModelBinding
        self.model_bingding_types: Dict[Type, Type[ModelBinding]] = {
            Request: RequestModelBinding,
            HttpSession: SessionModelBinding,
            Response: ResponseModelBinding,
            Headers: HeadersModelBinding,
            RegGroups: RegGroupsModelBinding,
            Environment: EnvironmentModelBinding,
            Header: HeaderModelBinding,
            Cookies: CookiesModelBinding,
            BaseCookie: CookiesModelBinding,
            SimpleCookie: CookiesModelBinding,
            Cookie: CookieModelBinding,
            MultipartFile: MultipartFileModelBinding,
            Parameter: ParameterModelBinding,
            PathValue: PathValueModelBinding,
            Parameters: ParametersModelBinding,
            RegGroup: RegGroupModelBinding,
            JSONBody: JSONBodyModelBinding,
            RequestBodyReader: RequestBodyReaderModelBinding,
            BytesBody: BytesBodyModelBinding,
            str: StrModelBinding,
            bool: BoolModelBinding,
            int: IntModelBinding,
            float: FloatModelBinding,
            list: ListModelBinding,
            List: ListModelBinding,
            List[str]: ListModelBinding,
            List[Parameter]: ListModelBinding,
            List[int]: ListModelBinding, 
            List[float]: ListModelBinding,
            List[bool]: ListModelBinding,
            List[dict]: ListModelBinding,
            List[Dict]: ListModelBinding,
            ModelDict: ModelDictModelBinding,
            dict: DictModelBinding,
            Dict: DictModelBinding
        }
        if sys.version_info >= (3, 9):
            self.model_bingding_types[list[str]] = ListModelBinding
            self.model_bingding_types[list[Parameter]] = ListModelBinding
            self.model_bingding_types[list[int]] = ListModelBinding
            self.model_bingding_types[list[bool]] = ListModelBinding
            self.model_bingding_types[list[float]] = ListModelBinding
            self.model_bingding_types[list[Dict]] = ListModelBinding
            self.model_bingding_types[list[dict]] = ListModelBinding

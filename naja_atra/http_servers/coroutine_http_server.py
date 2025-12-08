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


from .routing_server import RoutingServer
from ..request_handlers.model_bindings import ModelBindingConf
from ..request_handlers.http_request_handler import HttpRequestHandler


import asyncio
import threading
from asyncio.base_events import Server
from asyncio.streams import StreamReader, StreamWriter
from ssl import SSLContext
from time import sleep

from ..utils.logger import get_logger


_logger = get_logger("naja_atra.http_servers.coroutine_http_server")


class CoroutineHTTPServer(RoutingServer):

    def __init__(self, host: str = '', port: int = 9090, ssl: SSLContext = None, res_conf={}, model_binding_conf: ModelBindingConf = ModelBindingConf()) -> None:
        RoutingServer.__init__(
            self, res_conf, model_binding_conf=model_binding_conf)
        self.host: str = host
        self.port: int = port
        self.ssl: SSLContext = ssl
        self.server: Server = None # NOSONAR
        self.__thread_local = threading.local()

    async def callback(self, reader: StreamReader, writer: StreamWriter):
        handler = HttpRequestHandler(reader, writer, routing_conf=self)
        await handler.handle_request()
        _logger.debug("Connection ends, close the writer.")
        writer.close()

    async def start_async(self):
        self.server = await asyncio.start_server(
            self.callback, host=self.host, port=self.port, ssl=self.ssl)
        async with self.server:
            try:
                await self.server.serve_forever()
            except asyncio.CancelledError: # NOSONAR
                _logger.debug(
                    "Some requests are lost for the reason that the server is shutted down.")
            finally:
                await self.server.wait_closed()

    def _get_event_loop(self) -> asyncio.AbstractEventLoop:
        if not hasattr(self.__thread_local, "event_loop"):
            try:
                self.__thread_local.event_loop = asyncio.new_event_loop()
            except: # NOSONAR
                self.__thread_local.event_loop = asyncio.get_event_loop()
        return self.__thread_local.event_loop

    def start(self):
        self._get_event_loop().run_until_complete(self.start_async())

    def _shutdown(self):
        _logger.debug("Try to shutdown server.")
        self.server.close()
        loop = self.server.get_loop()
        loop.call_soon_threadsafe(loop.stop)

    def shutdown(self):
        wait_time = 3
        while wait_time:
            sleep(1)
            _logger.debug(f"couting to shutdown: {wait_time}")
            wait_time = wait_time - 1
            if wait_time == 0:
                _logger.debug("shutdown server....")
                self._shutdown()

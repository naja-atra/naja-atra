# coding: utf-8

from gzip import GzipFile
import os
import json
import socket
import websocket
import unittest
import urllib.request
import urllib.error
import http.client
from typing import Dict
from threading import Thread
from time import sleep

from naja_atra.utils.logger import get_logger, set_level
import naja_atra.server as server

set_level("DEBUG")

_logger = get_logger("http_test")


class ThreadingServerTest(unittest.TestCase):

    PORT = 9090

    WAIT_COUNT = 10

    COROUTINE = False

    @classmethod
    def start_server(cls):
        cls.tearDownClass()
        _logger.info("start server in background. ")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        server.scan(project_dir=root, base_dir="tests/ctrls",
                    regx=r'.*controllers.*')
        server.start(
            port=cls.PORT,
            resources={"/public/*": f"{root}/tests/static"},
            gzip_content_types={"text/plain"},
            prefer_coroutine=cls.COROUTINE)

    @classmethod
    def setUpClass(cls):
        Thread(target=cls.start_server, daemon=True, name="t").start()
        retry = 0
        while not server.is_ready():
            sleep(1)
            retry = retry + 1
            _logger.info(
                f"server is not ready wait. {retry}/{cls.WAIT_COUNT} ")
            if retry >= cls.WAIT_COUNT:
                raise Exception("Server start wait timeout.")

    @classmethod
    def tearDownClass(cls):
        try:
            server.stop()
        except:
            pass

    @classmethod
    def visit(cls, ctx_path, headers: Dict[str, str] = {}, data=None, return_type: str = "TEXT"):
        req: urllib.request.Request = urllib.request.Request(
            f"http://127.0.0.1:{cls.PORT}/{ctx_path}")
        for k, v in headers.items():
            req.add_header(k, v)
        res: http.client.HTTPResponse = urllib.request.urlopen(req, data=data)

        if return_type == "RESPONSE":
            return res
        elif return_type == "HEADERS":
            headers = res.headers
            res.close()
            return headers
        elif return_type == "JSON":
            txt = res.read().decode("utf-8")
            res.close()
            return json.loads(txt)
        else:
            txt = res.read().decode("utf-8")
            res.close()
            return txt

    def test_header_echo(self):
        res: http.client.HTTPResponse = self.visit(
            f"header_echo", headers={"X-KJ-ABC": "my-headers"}, return_type="RESPONSE")
        assert "X-Kj-Abc" in res.headers
        assert res.headers["X-Kj-Abc"] == "my-headers"

    def test_static(self):
        txt = self.visit("public/a.txt")
        assert txt == "hello world!"

    def test_gzip(self):
        res: http.client.HTTPResponse = self.visit(
            f"public/a.txt", headers={"Accept-Encoding": "gzip ,deflate"}, return_type="RESPONSE")
        content_encoding = res.info().get("Content-Encoding")
        assert "gzip" == content_encoding
        f = GzipFile(fileobj=res)
        txt = f.read().decode()
        assert txt == "hello world!"

    def test_path_value(self):
        pval = "abc"
        path_val = "xyz"
        txt = self.visit(f"path_values/{pval}/{path_val}/x")
        assert txt == f"<html><body>{pval}, {path_val}</body></html>"

    def test_error(self):
        try:
            self.visit("error")
        except urllib.error.HTTPError as err:
            assert err.code == 400
            error_msg = err.read().decode("utf-8")
            _logger.info(error_msg)
            assert error_msg == "code：400, message: Parameter Error!, explain: Test Parameter Error!"

    def test_coroutine(self):
        txt = self.visit(f"%E4%B8%AD%E6%96%87/coroutine?hey=KJ2")
        assert txt == "Success! KJ2"

    def test_post_json(self):
        data_dict = {
            "code": 0,
            "msg": "xxx"
        }
        res: str = self.visit(f"post_json", headers={
                              "Content-Type": "application/json"}, data=json.dumps(data_dict).encode(errors="replace"))
        res_dict: dict = json.loads(res)
        assert data_dict["code"] == res_dict["code"]
        assert data_dict["msg"] == res_dict["msg"]

    def test_filter(self):
        res: http.client.HTTPResponse = self.visit(
            f"tuple?user_name=kj&pass=wu", return_type="RESPONSE")
        assert "Res-Filter-Header" in res.headers
        assert res.headers["Res-Filter-Header"] == "from-filter"

    def test_exception(self):
        try:
            self.visit("exception")
        except urllib.error.HTTPError as err:
            assert err.code == 500
            error_msg = err.read().decode("utf-8")
            _logger.info(error_msg)
            assert error_msg == '500-Internal Server Error-some error occurs!'

    def test_res_write_bytes(self):
        body = self.visit("res/write/bytes")
        assert body == 'abcdefg'

    def test_ws(self):
        ws = websocket.WebSocket()
        path_val = "test-ws"
        msg = "hello websocket!"
        ws.connect(f"ws://127.0.0.1:{self.PORT}/ws/{path_val}")
        ws.send(msg)
        txt = ws.recv()
        ws.close()
        assert txt == f"{path_val}-{msg}"

    def test_ws_fun(self):
        ws = websocket.WebSocket()
        path_val = "test-ws-fun"
        msg = "hello websocket!"
        ws.connect(f"ws://127.0.0.1:{self.PORT}/ws-fun/{path_val}")
        ws.send(msg)
        txt = ws.recv()
        ws.close()
        assert txt == f"{path_val}-{msg}"

    def test_ws_continuation(self):
        ws = websocket.WebSocket()
        path_val = "test-ws"

        ws.connect(f"ws://127.0.0.1:{self.PORT}/ws/{path_val}")
        msg0 = "Hello "
        frame0 = websocket.ABNF.create_frame(
            msg0, websocket.ABNF.OPCODE_TEXT, 0)
        ws.send_frame(frame0)
        msg1 = "Websocket "
        frame1 = websocket.ABNF.create_frame(
            msg1, websocket.ABNF.OPCODE_CONT, 0)
        ws.send_frame(frame1)
        msg2 = "Frames!"
        frame2 = websocket.ABNF.create_frame(
            msg2, websocket.ABNF.OPCODE_CONT, 1)
        ws.send_frame(frame2)

        txt = ws.recv()
        ws.close()
        assert txt == f"{path_val}-{msg0 + msg1 + msg2}"

    def test_ws_bytes_continuation(self):
        ws = websocket.WebSocket()
        path_val = "test-ws"

        ws.connect(f"ws://127.0.0.1:{self.PORT}/ws/{path_val}")
        msg0 = "Hello "
        frame0 = websocket.ABNF.create_frame(
            msg0, websocket.ABNF.OPCODE_BINARY, 0)
        ws.send_frame(frame0)
        msg1 = "Websocket "
        frame1 = websocket.ABNF.create_frame(
            msg1, websocket.ABNF.OPCODE_CONT, 0)
        ws.send_frame(frame1)
        msg2 = "Frames!"
        frame2 = websocket.ABNF.create_frame(
            msg2, websocket.ABNF.OPCODE_CONT, 1)
        ws.send_frame(frame2)

        txt: str = ws.recv()
        bs: bytes = ws.recv()
        bs2: bytes = ws.recv()
        ws.close()
        assert txt == "binary-message-received, and this is some message for the long size."
        assert bs.decode() == bs2.decode() == msg0 + msg1 + msg2

    def test_ws_regexp(self):
        ws = websocket.WebSocket()
        path_val = "wstest"
        msg = 'hello, reg'

        ws.connect(f"ws://127.0.0.1:{self.PORT}/ws-reg/{path_val}")
        ws.send(msg)

        txt: str = ws.recv()
        print(txt)
        ws.close()
        assert txt == f"{path_val}-{msg}"

    def test_params_narrowing(self):
        body = self.visit("param/narrowing?a=b")
        assert body == 'a=b'
        body = self.visit("param/narrowing?a=c")
        assert body == 'a!=b'

    def test_model_binding(self):
        name = "keijack"
        sex = "male"
        age = 18
        res: Dict = self.visit(
            f"model_binding/person?name={name}&sex={sex}&age={age}", return_type="JSON")
        assert res["name"] == name
        assert res["sex"] == sex
        assert res["age"] == age

    def test_send_chunked(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(("127.0.0.1", self.PORT))
            request = (
                "POST {} HTTP/1.1\r\n"
                "Host: {}\r\n"
                "Transfer-Encoding: chunked\r\n"
                "Content-Type: text/plain\r\n"
                "\r\n"
                "8\r\n"
                "Mozilla \r\n"
                "11\r\n"
                "Developer Network\r\n"
                "0\r\n"
                "\r\n"
            ).format(f"/chunked", f"127.0.0.1:{self.PORT}")

            sock.sendall(request.encode('utf-8'))
            response = b''
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                response += data
            response = response.split(b'\r\n')[-1].strip()
            res = json.loads(response)
            assert res["data"] == "Mozilla Developer Network"
        finally:
            sock.close()


class CoroutineServerTest(ThreadingServerTest):

    PORT = 9091

    COROUTINE = True

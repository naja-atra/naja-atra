
from simple_http_server import request_map
from wsgiref.simple_server import WSGIServer, make_server
import simple_http_server.server as server
import os
import sys
import signal
from threading import Thread
from time import sleep
from simple_http_server.__main__ import main
from simple_http_server.http_server import HttpServer
from simple_http_server.logger import get_logger, set_level
from simple_http_server import get_app_conf
set_level("DEBUG")


@request_map("/stop")
def stop():
    server.stop()
    return "<!DOCTYPE html><html><head><title>关闭</title></head><body>关闭成功！</body></html>"


_logger = get_logger("http_test")
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

_server: HttpServer = None


def start_via_class():
    global _server
    app = get_app_conf("2")
    _server = HttpServer(host=('', 9091),
                         resources={"/p/**": f"{PROJECT_ROOT}/tests/static"},
                         app_conf=app)
    _server.start()


def start_server():
    _logger.info("start server in background. ")
    
    server.scan(base_dir="tests/ctrls", regx=r'.*controllers.*', project_dir=os.path.dirname(__file__))
    server.start(
        # port=9443,
        port=9090,
        resources={"/public/*": f"{PROJECT_ROOT}/tests/static",
                   "/*": f"{PROJECT_ROOT}/tests/static",
                   '/inn/**': f"{PROJECT_ROOT}/tests/static",
                   '**.txt': f"{PROJECT_ROOT}/tests/static",
                   '*.ini': f"{PROJECT_ROOT}/tests/static",
                   },
        # ssl=True,
        # certfile=f"{PROJECT_ROOT}/tests/certs/fullchain.pem",
        # keyfile=f"{PROJECT_ROOT}/tests/certs//privkey.pem",
        prefer_coroutine=False)


wsgi_server: WSGIServer = None


def start_server_wsgi():
    _logger.info("start server in background. ")
    server.scan(base_dir="tests/ctrls", regx=r'.*controllers.*')
    wsgi_proxy = server.init_wsgi_proxy(
        resources={"/public/*": f"{PROJECT_ROOT}/tests/static",
                   "/*": f"{PROJECT_ROOT}/tests/static"})

    global wsgi_server
    wsgi_server = make_server("", 9090, wsgi_proxy.app_proxy)
    wsgi_server.serve_forever()


def on_sig_term(signum, frame):
    if wsgi_server:
        _logger.info(f"Receive signal [{signum}], shutdown the wsgi server...")
        Thread(target=wsgi_server.shutdown).start()
    else:
        _logger.info(f"Receive signal [{signum}], stop server now...")
        server.stop()
    if _server:
        _server.shutdown()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, on_sig_term)
    signal.signal(signal.SIGINT, on_sig_term)
    Thread(target=start_server, daemon=True).start()
    sleep(1)
    start_via_class()
    # start_server_wsgi()
    # main(sys.argv[1:])

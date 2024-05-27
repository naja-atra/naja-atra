# Naja-Atra

[![PyPI version](https://badge.fury.io/py/naja-atra.png)](https://badge.fury.io/py/naja-atra)

Naja-Atra is a lightweight python web framework. It's designed to make starting a web service easier. It supports both HTTP and WebSocket. 

This project is a folk from [python-simple-http-server](https://github.com/keijack/python-simple-http-server), if you use that module before, you can use this module by rename the import module name.

## Support Python Version

Python 3.7+

## Why choose

* Lightway.
* Functional programing.
* Filter chain support.
* Session support, and can support distributed session by [this extention](https://github.com/naja-atra/naja-atra-redis-session).
* You can use [this extention](https://github.com/naja-atra/naja-atra-jinja) to support `jinja` views.
* Spring MVC like request mapping.
* SSL support.
* Websocket support
* Easy to use.
* Free style controller writing.
* Easily integraded with WSGI servers with [this extention](https://github.com/naja-atra/naja-atra-wsgi). 
* Easily integraded with ASGI servers with [this extension](https://github.com/naja-atra/naja-atra-asgi). Websocket will be supported when ASGI server enable websocket functions.
* Coroutine mode support.

## Dependencies

There are no other dependencies needed to run this project. However, if you want to run the unitests in the `tests` folder, you need to install `websocket` via pip:

```shell
python3 -m pip install websocket-client
```

## How to use

### Install

```shell
python3 -m pip install naja_atra
```

### Minimum code / component requirement setup

Minimum code to get things started should have at least one controller function,<br /> 
using the route and server modules from naja_atra

```python
from naja_atra import route, server
    
@route("/")
def index():
    return {"hello": "world"}   

server.start(port=9090)
```

### Write Controllers

```python

from naja_atra import request_map
from naja_atra import Response
from naja_atra import MultipartFile
from naja_atra import Parameter
from naja_atra import Parameters
from naja_atra import Header
from naja_atra import JSONBody
from naja_atra import HttpError
from naja_atra import StaticFile
from naja_atra import Headers
from naja_atra import Cookies
from naja_atra import Cookie
from naja_atra import Redirect
from naja_atra import ModelDict

# request_map has an alias name `route`, you can select the one you familiar with.
@request_map("/index")
def my_ctrl():
    return {"code": 0, "message": "success"}  # You can return a dictionary, a string or a `naja_atra.naja_atra.Response` object.


@route("/say_hello", method=["GET", "POST"])
def my_ctrl2(name, name2=Parameter("name", default="KEIJACK"), model=ModelDict()):
    """name and name2 is the same"""
    name == name2 # True
    name == model["name"] # True
    return "<!DOCTYPE html><html><body>hello, %s, %s</body></html>" % (name, name2)


@request_map("/error")
def my_ctrl3():
    return Response(status_code=500)


@request_map("/exception")
def exception_ctrl():
    raise HttpError(400, "Exception")

@request_map("/upload", method="GET")
def show_upload():
    root = os.path.dirname(os.path.abspath(__file__))
    return StaticFile("%s/my_dev/my_test_index.html" % root, "text/html; charset=utf-8")


@request_map("/upload", method="POST")
def my_upload(img=MultipartFile("img")):
    root = os.path.dirname(os.path.abspath(__file__))
    img.save_to_file(root + "/my_dev/imgs/" + img.filename)
    return "<!DOCTYPE html><html><body>upload ok!</body></html>"


@request_map("/post_txt", method="POST")
def normal_form_post(txt):
    return "<!DOCTYPE html><html><body>hi, %s</body></html>" % txt

@request_map("/tuple")
def tuple_results():
    # The order here is not important, we consider the first `int` value as status code,
    # All `Headers` object will be sent to the response
    # And the first valid object whose type in (str, unicode, dict, StaticFile, bytes) will
    # be considered as the body
    return 200, Headers({"my-header": "headers"}), {"success": True}

"""
" Cookie_sc will not be written to response. It's just some kind of default
" value
"""
@request_map("tuple_cookie")
def tuple_with_cookies(all_cookies=Cookies(), cookie_sc=Cookie("sc")):
    print("=====> cookies ")
    print(all_cookies)
    print("=====> cookie sc ")
    print(cookie_sc)
    print("======<")
    import datetime
    expires = datetime.datetime(2018, 12, 31)

    cks = Cookies()
    # cks = cookies.SimpleCookie() # you could also use the build-in cookie objects
    cks["ck1"] = "keijack"request
    cks["ck1"]["path"] = "/"
    cks["ck1"]["expires"] = expires.strftime(Cookies.EXPIRE_DATE_FORMAT)
    # You can ignore status code, headers, cookies even body in this tuple.
    return Header({"xx": "yyy"}), cks, "<html><body>OK</body></html>"

"""
" If you visit /a/b/xyz/x，this controller function will be called, and `path_val` will be `xyz`
"""
@request_map("/a/b/{path_val}/x")
def my_path_val_ctr(path_val=PathValue()):
    return f"<html><body>{path_val}</body></html>"

@request_map("/star/*") # /star/c will find this controller, but /star/c/d not.
@request_map("*/star") # /c/star will find this controller, but /c/d/star not.
def star_path(path_val=PathValue()):
    return f"<html><body>{path_val}</body></html>"

@request_map("/star/**") # Both /star/c and /star/c/d will find this controller.
@request_map("**/star") # Both /c/star and /c/d/stars will find this controller.
def star_path(path_val=PathValue()):
    return f"<html><body>{path_val}</body></html>"

@request_map("/redirect")
def redirect():
    return Redirect("/index")

@request_map("session")
def test_session(session=Session(), invalid=False):
    ins = session.get_attribute("in-session")
    if not ins:
        session.set_attribute("in-session", "Hello, Session!")

    __logger.info("session id: %s" % session.id)
    if invalid:
        __logger.info("session[%s] is being invalidated. " % session.id)
        session.invalidate()
    return "<!DOCTYPE html><html><body>%s</body></html>" % str(ins)

# use coroutine, these controller functions will work both in a coroutine mode or threading mode.

async def say(sth: str = ""):
    _logger.info(f"Say: {sth}")
    return f"Success! {sth}"

@request_map("/中文/coroutine")
async def coroutine_ctrl(hey: str = "Hey!"):
    return await say(hey)

@route("/res/write/bytes")
def res_writer(response: Response):
    response.status_code = 200
    response.add_header("Content-Type", "application/octet-stream")
    response.write_bytes(b'abcd')
    response.write_bytes(bytearray(b'efg'))
    response.close()
```

Beside using the default values, you can also use variable annotations to specify your controller function's variables.

```python
@request_map("/say_hello/to/{name}", method=["GET", "POST", "PUT"])
def your_ctroller_function(
        user_name: str, # req.parameter["user_name"]，400 error will raise when there's no such parameter in the query string.
        password: str, # req.parameter["password"]，400 error will raise when there's no such parameter in the query string.
        skills: list, # req.parameters["skills"]，400 error will raise when there's no such parameter in the query string.
        all_headers: Headers, # req.headers
        user_token: Header, # req.headers["user_token"]，400 error will raise when there's no such parameter in the quest headers.
        all_cookies: Cookies, # req.cookies, return all cookies
        user_info: Cookie, # req.cookies["user_info"]，400 error will raise when there's no such parameter in the cookies.
        name: PathValue, # req.path_values["name"]，get the {name} value from your path.
        session: Session # req.getSession(True)，get the session, if there is no sessions, create one.
    ):
    return "<html><body>Hello, World!</body></html>"

# you can use `params` to narrow the controller mapping, the following examples shows only the `params` mapping, ignoring the 
# `headers` examples for the usage is almost the same as the `params`. 
@request("/exact_params", method="GET", params="a=b")
def exact_params(a: str):
    print(f"{a}") # b
    return {"result": "ok"}

@request("/exact_params", method="GET", params="a!=b")
def exact_not_params(a: str):
    print(f"{a}") # b
    return {"result": "ok"}

@request("/exact_params", method="GET", params="a^=b")
def exact_startwith_params(a: str):
    print(f"{a}") # b
    return {"result": "ok"}

@request("/exact_params", method="GET", params="!a")
def no_params():
    return {"result": "ok"}

@request("/exact_params", method="GET", params="a")
def must_has_params():
    return {"result": "ok"}

# If multiple expressions are set, all expressions must be matched to enter this controller function.
@request("/exact_params", method="GET", params=["a=b", "c!=d"])
def multipul_params():
    return {"result": "ok"}

# You can set `match_all_params_expressions` to False to make that the url can enter this controller function even only one expression is matched.
@request("/exact_params", method="GET", params=["a=b", "c!=d"], match_all_params_expressions=False)
def multipul_params():
    return {"result": "ok"}
```

We recommend using functional programing to write controller functions. but if you realy want to use Object, you can use `@request_map` in a class method. For doing this, every time a new request comes, a new MyController object will be created.

```python

class MyController:

    def __init__(self) -> None:
        self._name = "ctr object"

    @request_map("/obj/say_hello", method="GET")
    def my_ctrl_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

```

If you want a singleton, you can add a `@controller` decorator to the class.

```python

@controller
class MyController:

    def __init__(self) -> None:
        self._name = "ctr object"

    @request_map("/obj/say_hello", method="GET")
    def my_ctrl_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

```

You can also add the `@request_map` to your class, this will be as the part of the url.

```python

@controller
@request_map("/obj", method="GET")
class MyController:

    def __init__(self) -> None:
        self._name = "ctr object"

    @request_map
    def my_ctrl_default_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

    @request_map("/say_hello", method=("GET", "POST"))
    def my_ctrl_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

```

You can specify the `init` variables in `@controller` decorator. 

```python

@controller(args=["ctr_name"], kwargs={"desc": "this is a key word argument"})
@request_map("/obj", method="GET")
class MyController:

    def __init__(self, name, desc="") -> None:
        self._name = f"ctr[{name}] - {desc}"

    @request_map
    def my_ctrl_default_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

    @request_map("/say_hello", method=("GET", "POST"))
    def my_ctrl_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

```

From `0.7.0`, `@request_map` support regular expression mapping. 

```python
# url `/reg/abcef/aref/xxx` can map the flowing controller:
@route(regexp="^(reg/(.+))$", method="GET")
def my_reg_ctr(reg_groups: RegGroups, reg_group: RegGroup = RegGroup(1)):
    print(reg_groups) # will output ("reg/abcef/aref/xxx", "abcef/aref/xxx")
    print(reg_group) # will output "abcef/aref/xxx"
    return f"{self._name}, {reg_group.group},{reg_group}"
```
Regular expression mapping a class:

```python
@controller(args=["ctr_name"], kwargs={"desc": "this is a key word argument"})
@request_map("/obj", method="GET") # regexp do not work here, method will still available
class MyController:

    def __init__(self, name, desc="") -> None:
        self._name = f"ctr[{name}] - {desc}"

    @request_map
    def my_ctrl_default_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

    @route(regexp="^(reg/(.+))$") # prefix `/obj`  from class decorator will be ignored, but `method`(GET in this example) from class decorator will still work.
    def my_ctrl_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

```

### Session

Defaultly, the session is stored in local, you can extend `SessionFactory` and `Session` classes to implement your own session storage requirement (like store all data in redis or memcache)

```python
from naja_atra import Session, SessionFactory, set_session_factory

class MySessionImpl(Session):

    def __init__(self):
        super().__init__()
        # your own implementation

    @property
    def id(self) -> str:
        # your own implementation

    @property
    def creation_time(self) -> float:
        # your own implementation

    @property
    def last_accessed_time(self) -> float:
        # your own implementation

    @property
    def is_new(self) -> bool:
        # your own implementation

    @property
    def attribute_names(self) -> Tuple:
        # your own implementation

    def get_attribute(self, name: str) -> Any:
        # your own implementation

    def set_attribute(self, name: str, value: Any) -> None:
        # your own implementation

    def invalidate(self) -> None:
        # your own implementation

class MySessionFacImpl(SessionFactory):

    def __init__(self):
        super().__init__()
        # your own implementation

    
    def get_session(self, session_id: str, create: bool = False) -> Session:
        # your own implementation
        return MySessionImpl()

set_session_factory(MySessionFacImpl())

```

There is an offical Redis implementation here: https://github.com/keijack/naja-atra-redis-session.git

### Websocket

To handle a websocket session, you should handle multiple events, so it's more reasonable to use a class rather than functions to do it. 

In this framework, you should use `@websocket_handler` to decorate the class you want to handle websocket session. Specific event listener methods should be defined in a fixed way. However, the easiest way to do it is to inherit `naja_atra.WebsocketHandler` class, and choose the event you want to implement. But this inheritance is not compulsory.

You can configure `endpoit` or `regexp` in `@websocket_handler` to setup which url the class should handle. Alongside, there is a `singleton` field, which is set to `True` by default. Which means that all connections are handle by ONE object of this class. If this field is set to `False`, objects will be created when every `WebsocketSession` try to connect.

```python
from naja_atra import WebsocketHandler, WebsocketRequest,WebsocketSession, websocket_handler

@websocket_handler(endpoint="/ws/{path_val}")
class WSHandler(WebsocketHandler):

    def on_handshake(self, request: WebsocketRequest):
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
        _logger.info(f">>{session.id}<< open! {request.path_values}")
        return 0, {}

    def on_open(self, session: WebsocketSession):
        """
        " 
        " Will be called when the connection opened.
        "
        """
        _logger.info(f">>{session.id}<< open! {session.request.path_values}")

    def on_close(self, session: WebsocketSession, reason: str):
        """
        "
        " Will be called when the connection closed.
        "
        """
        _logger.info(f">>{session.id}<< close::{reason}")

    def on_ping_message(self, session: WebsocketSession = None, message: bytes = b''):
        """
        "
        " Will be called when receive a ping message. Will send all the message bytes back to client by default.
        "
        """
        session.send_pone(message)

    def on_pong_message(self, session: WebsocketSession = None, message: bytes = ""):
        """
        "
        " Will be called when receive a pong message.
        "
        """
        pass

    def on_text_message(self, session: WebsocketSession, message: str):
        """
        "
        " Will be called when receive a text message.
        "
        """
        _logger.info(f">>{session.id}<< on text message: {message}")
        session.send(message)

    def on_binary_message(self, session: WebsocketSession = None, message: bytes = b''):
        """
        "
        " Will be called when receive a binary message if you have not consumed all the bytes in `on_binary_frame` 
        " method.
        "
        """
        pass

    def on_binary_frame(self, session: WebsocketSession = None, fin: bool = False, frame_payload: bytes = b''):
        """
        "
        " If you are sending a continuation binary message to server, this will be called every time a frame is 
        " received, you can consumed all the bytes in this method, e.g. save all bytes to a file. By doing so, 
        " you should not return and value in this method. 
        "
        " If you does not implement this method or return a True in this method, all the bytes will be caced in
        " memory and be sent to your `on_binary_message` method.
        "
        """
        return True

@websocket_handler(regexp="^/ws-reg/([a-zA-Z0-9]+)$", singleton=False)
class WSHandler(WebsocketHandler):

    """
    " You code here
    """

```

But if you want to only handle one event, you can also use a function to handle it. 

```python

from naja_atra import WebsocketCloseReason, WebsocketHandler, WebsocketRequest, WebsocketSession, websocket_message, websocket_handshake, websocket_open, websocket_close, WEBSOCKET_MESSAGE_TEXT

@websocket_handshake(endpoint="/ws-fun/{path_val}")
def ws_handshake(request: WebsocketRequest):
    return 0, {}


@websocket_open(endpoint="/ws-fun/{path_val}")
def ws_open(session: WebsocketSession):
    _logger.info(f">>{session.id}<< open! {session.request.path_values}")


@websocket_close(endpoint="/ws-fun/{path_val}")
def ws_close(session: WebsocketSession, reason: WebsocketCloseReason):
    _logger.info(
        f">>{session.id}<< close::{reason.message}-{reason.code}-{reason.reason}")


@websocket_message(endpoint="/ws-fun/{path_val}", message_type=WEBSOCKET_MESSAGE_TEXT)
# You can define a function in a sync or async way.
async def ws_text(session: WebsocketSession, message: str): 
    _logger.info(f">>{session.id}<< on text message: {message}")
    session.send(f"{session.request.path_values['path_val']}-{message}")
    if message == "close":
        session.close()
```

### Error pages

You can use `@error_message` to specify your own error page. See:

```python
from naja_atra import error_message
# map specified codes
@error_message("403", "404")
def my_40x_page(message: str, explain=""):
    return f"""
    <html>
        <head>
            <title>发生错误！</title>
        <head>
        <body>
            message: {message}, explain: {explain}
        </body>
    </html>
    """

# map specified code rangs
@error_message("40x", "50x")
def my_error_message(code, message, explain=""):
    return f"{code}-{message}-{explain}"

# map all error page
@error_message
def my_error_message(code, message, explain=""):
    return f"{code}-{message}-{explain}"
```

### Write filters

This server support filters, you can use `request_filter` decorator to define your filters.

```python
from naja_atra import request_filter

@request_filter("/tuple/**") # use wildcard
@request_filter(regexp="^/tuple") # use regular expression
def filter_tuple(ctx):
    print("---------- through filter ---------------")
    # add a header to request header
    ctx.request.headers["filter-set"] = "through filter"
    if "user_name" not in ctx.request.parameter:
        ctx.response.send_redirect("/index")
    elif "pass" not in ctx.request.parameter:
        ctx.response.send_error(400, "pass should be passed")
        # you can also raise a HttpError
        # raise HttpError(400, "pass should be passed")
    else:
        # you should always use do_chain method to go to the next
        ctx.do_chain()
```

### Start your server

```python
# If you place the controllers method in the other files, you should import them here.

import naja_atra.server as server
import my_test_ctrl


def main(*args):
    # The following method can import several controller files once.
    server.scan("my_ctr_pkg", r".*controller.*")
    server.start()

if __name__ == "__main__":
    main()
```

If you want to specify the host and port:

```python
    server.start(host="", port=8080)
```

If you want to specify the resources path: 

```python 
    server.start(resources={"/path_prefix/*", "/absolute/dir/root/path", # Match the files in the given folder with a special path prefix.
                            "/path_prefix/**", "/absolute/dir/root/path", # Match all the files in the given folder and its sub-folders with a special path prefix.
                            "*.suffix", "/absolute/dir/root/path", # Match the specific files in the given folder.
                            "**.suffix", "/absolute/dir/root/path", # Match the specific files in the given folder and its sub-folders.
                            })
```

If you want to use ssl:

```python
    server.start(host="", 
                 port=8443,
                 ssl=True,
                 ssl_protocol=ssl.PROTOCOL_TLS_SERVER, # Optional, default is ssl.PROTOCOL_TLS_SERVER, which will auto detect the highted protocol version that both server and client support. 
                 ssl_check_hostname=False, #Optional, if set to True, if the hostname is not match the certificat, it cannot establish the connection, default is False.
                 keyfile="/path/to/your/keyfile.key",
                 certfile="/path/to/your/certfile.cert",
                 keypass="", # Optional, your private key's password
                 )
```

### Coroutine

From `0.12.0`, you can use coroutine tasks than threads to handle requests, you can set the `prefer_coroutine` parameter in start method to enable the coroutine mode. 

```python
    server.start(prefer_coroutine=True)
```

From `0.13.0`, coroutine mode uses the coroutine server, that means all requests will use the async I/O rather than block I/O. So you can now use `async def` to define all your controllers including the Websocket event callback methods.

If you call the server starting in a async function, you can all its async version, by doing this, there sever will use the same event loop with your other async functions. 

```python
    await server.start_async(prefer_coroutine=True)
```

## Logger

The default logger is try to write logs to the screen, you can specify the logger handler to write it to a file.

```python
import naja_atra.utils.logger as logger
import logging

_formatter = logging.Formatter(fmt='[%(asctime)s]-[%(name)s]-%(levelname)-4s: %(message)s')
_handler = logging.TimedRotatingFileHandler("/var/log/naja_atra.log", when="midnight", backupCount=7)
_handler.setFormatter(_formatter)
_handler.setLevel("INFO")

logger.set_handler(_handler)
```

If you want to add a handler rather than replace the inner one, you can use:

```python
logger.add_handler(_handler)
```

If you want to change the logger level:

```python
logger.set_level("DEBUG")
```

You can get a stand alone logger which is independent from the framework one via a new class `logger.LoggerFactory`. 

```python
import naja_atra.utils.logger as logger

log = logger.get_logger("my_service", "my_log_fac")

# If you want to set a different log level to this logger factory: 

log_fac = logger.get_logger_factory("my_log_fac")
log_fac.log_level = "DEBUG"
log = log_fac.get_logger("my_service")

log.info(...)

```

## Thanks

The code that process websocket comes from the following project: https://github.com/Pithikos/python-websocket-server

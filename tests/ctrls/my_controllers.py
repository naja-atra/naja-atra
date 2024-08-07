# -*- coding: utf-8 -*-


import time, sys, os
from typing import List, OrderedDict

from naja_atra import BytesBody, FilterContext, ModelDict, Redirect, RegGroup, RequestBodyReader, request_filter
from naja_atra import Headers
from naja_atra import HttpError
from naja_atra import JSONBody
from naja_atra import Header
from naja_atra import Parameters
from naja_atra import Cookie
from naja_atra import Cookies
from naja_atra import PathValue
from naja_atra import Parameter
from naja_atra import MultipartFile
from naja_atra import Response
from naja_atra import Request
from naja_atra import HttpSession
from naja_atra import request_map, route
from naja_atra import controller
from naja_atra import error_message
from naja_atra.app_conf import get_app_conf

import naja_atra.utils.logger as logger


_logger = logger.get_logger("my_test_main")


_logger = logger.get_logger("controller")

_app = get_app_conf("2")


@request_map("/")
@request_map("/index")
@_app.route("/")
def my_ctrl():
    # You can return a dictionary, a string or a `simple_http_server.simple_http_server.Response` object.
    return {"code": 0, "message": "success"}


@request_map("/say_hello", method=["GET", "POST"])
def my_ctrl2(name, name2=Parameter("name", default="KEIJACK")):
    """name and name2 is the same"""
    return f"<!DOCTYPE html><html><body>hello, {name}, {name2}</body></html>"


@request_map("/error")
def my_ctrl3():
    raise HttpError(400, "Parameter Error!", "Test Parameter Error!")


@request_map("/sleep")
def sleep_secs(secs: int = 10):
    _logger.info(f"Sleep {secs} secondes...")
    time.sleep(secs)
    return {
        "message": "OK"
    }


async def say(sth: str = ""):
    _logger.info(f"Say: {sth}")
    return f"Success! {sth}"


@request_map("/中文/coroutine")
async def coroutine_ctrl(hey: str = "Hey!"):
    # raise RuntimeError
    return await say(hey)


@request_map("/exception")
def exception_ctrl():
    raise Exception("some error occurs!")


@request_map("/upload", method="POST")
def my_upload(img=MultipartFile("img"), txt=Parameter("中文text", required=False, default="DEFAULT"), req=Request()):
    for k, v in req.parameter.items():
        print("%s (%s)====> %s " % (k, str(type(k)), v))
    print(txt)

    root = os.path.dirname(os.path.abspath(__file__))
    img.save_to_file(root + "/imgs/" + img.filename)
    return f"<!DOCTYPE html><html><body>upload ok! {txt} </body></html>"


@request_map("/post_txt", method=["GET", "POST"])
def normal_form_post(txt=Parameter("中文txt", required=False, default="DEFAULT"), req=Request(), bd=BytesBody()):
    for k, v in req.parameter.items():
        print("%s ====> %s " % (k, v))
    print(req.body)
    print(bd)
    return f"<!DOCTYPE html><html><body>hi, {txt}</body></html>"


@request_map("/post_json", method="POST")
def post_json(host=Header("Host"), json=JSONBody()):
    print(f"Host: {host}")
    print(json)
    return OrderedDict(json)


@request_map("/cookies")
def set_headers(res: Response, headers: Headers, cookies: Cookies, cookie=Cookie("sc")):
    print("==================cookies==========")
    print(cookies)
    print("==================cookies==========")
    print(cookie)
    res.add_header(
        "Set-Cookie", "sc=keijack; Expires=Web, 31 Oct 2018 00:00:00 GMT;")
    res.add_header("Set-Cookie", "sc=keijack2;")
    res.body = "<!DOCTYPE html><html><body>OK!</body></html>"


@request_map("tuple")
async def tuple_results():
    return 200, Headers({"MyHeader": "my header"}), "hello tuple result!"


@request_map("session")
def test_session(session: HttpSession, invalid=False):
    ins = session.get_attribute("in-session")
    if not ins:
        session.set_attribute("in-session", "Hello, Session!")

    _logger.info("session id: %s" % session.id)
    if invalid:
        _logger.info("session[%s] is being invalidated. " % session.id)
        session.invalidate()
    return "<!DOCTYPE html><html><body>%s</body></html>" % str(ins)


@request_map("tuple_cookie")
def tuple_with_cookies(headers=Headers(), all_cookies=Cookies(), cookie_sc=Cookie("sc")):
    print("=====>headers")
    print(headers)
    print("=====> cookies ")
    print(all_cookies)
    print("=====> cookie sc ")
    print(cookie_sc)
    print("======<")
    import datetime
    expires = datetime.datetime(2018, 12, 31)

    cks = Cookies()
    # cks = cookies.SimpleCookie() # you could also use the build-in cookie objects
    cks["ck1"] = "keijack"
    cks["ck1"]["path"] = "/"
    cks["ck1"]["expires"] = expires.strftime(Cookies.EXPIRE_DATE_FORMAT)

    return 200, Header({"xx": "yyy"}), cks, "<html><body>OK</body></html>"


@request_map("header_echo")
def header_echo(headers: Headers):
    return 200, headers, ""


@request_filter("/abcde/**")
def fil(ctx: FilterContext):
    print("---------- through filter ---------------")
    ctx.do_chain()


@request_filter(regexp="^/abcd")
@request_filter("/tuple")
async def filter_tuple(ctx: FilterContext):
    print("---------- through filter async ---------------")
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
        res: Response = ctx.response
        res.add_header("Access-Control-Allow-Origin", "*")
        res.add_header("Access-Control-Allow-Methods", "*")
        res.add_header("Access-Control-Allow-Headers", "*")
        res.add_header("Res-Filter-Header", "from-filter")
        ctx.do_chain()


@request_map("/redirect")
def redirect():
    return Redirect("/index")


@request_map("/params")
def my_ctrl4(user_name,
             password=Parameter(name="passwd", required=True),
             remember_me=True,
             locations=[],
             json_param={},
             lcs=Parameters(name="locals", required=True),
             content_type=Header("Content-Type", default="application/json"),
             connection=Header("Connection"),
             ua=Header("User-Agent"),
             headers=Headers()
             ):
    return f"""<!DOCTYPE html>
    <html>
    <head>
        <title>show all params!</title>
    </head>
    <body>
        <p>user_name: {user_name}</p>
        <p>password: {password}</p>
        <p>remember_me: {remember_me}</p>
        <p>locations: {locations}</p>
        <p>json_param: {json_param}</p>
        <p>locals: {lcs}</p>
        <p>conent_type: {content_type}</p>
        <p>user_agent: {ua}</p>
        <p>connection: {connection}</p>
        <p>all Headers: {headers}</p>
    </body>
    </html>
    """


@request_map("/int_status_code")
def return_int(status_code=200):
    return status_code


@request_map("/path_values/{pval}/{path_val}/x")
def my_path_val_ctr(pval: PathValue, path_val=PathValue()):
    return f"<html><body>{pval}, {path_val}</body></html>"


@controller(args=["my-ctr"], kwargs={"desc": "desc"})
@route("/obj")
class MyController:

    def __init__(self, name, desc="") -> None:
        self._name = f"ctr object[#{name}]:{desc}"

    @route("/hello", method="GET, POST")
    @request_map
    def my_ctrl_mth(self, model: ModelDict):
        return {"message": f"hello, {model['name']}, {self._name} says. "}

    @request_map("/hello2", method=("GET", "POST"))
    def my_ctr_mth2(self, name: str, i: List[int]):
        return f"<html><head><title>{self._name}</title></head><body>{self._name}: {name}, {i}</body></html>"

    @route(regexp="^(reg/(.+))$", method="GET")
    def my_reg_ctr(self, reg_group: RegGroup = RegGroup(1)):
        return f"{self._name}, {reg_group.group},{reg_group}"


@error_message("400")
def my_40x_page(message: str, explain=""):
    return f"code：400, message: {message}, explain: {explain}"


@error_message
def my_other_error_page(code, message, explain=""):
    return f"{code}-{message}-{explain}"


@request_map("abcde/**")
def wildcard_match(path_val=PathValue()):
    return f"<html><head><title>path values</title></head><body>{path_val}</body></html>"


"""
curl -X PUT --data-binary "@/data1/clamav/scan/trojans/000.exe" \
    -H "Content-Type: application/octet-stream" \
    http://10.0.2.16:9090/put/file
"""


@request_map("/put/file", method="PUT")
async def reader_test(
        content_type: Header = Header("Content-Type"),
        reader: RequestBodyReader = None):
    buf = 1024 * 1024
    folder = os.path.dirname(os.path.abspath(__file__)) + "/tmp"
    if not os.path.isdir(folder):
        os.mkdir(folder)
    _logger.info(f"content-type:: {content_type}")
    with open(f"{folder}/target_file", "wb") as outfile:
        while True:
            _logger.info("read file")
            data = await reader.read(buf)
            _logger.info(f"read data {len(data)} and write")
            if data == b'':
                break
            outfile.write(data)
    return None


@route("/res/write/bytes")
def res_writer(response: Response):
    response.status_code = 200
    response.add_header("Content-Type", "application/octet-stream")
    response.write_bytes(b'abcd')
    response.write_bytes(bytearray(b'efg'))
    response.close()


@route("/param/narrowing", params="a=b")
def params_narrowing():
    return "a=b"


@route("/param/narrowing", params="a!=b")
def params_narrowing2():
    return "a!=b"


@controller
@request_map(url="/page", params=("a=b", ))
class IndexPage:

    @request_map("/index", method='GET', params="x=y", match_all_params_expressions=False)
    def index_page(self):
        return "<!DOCTYPE html><html><head><title>你好</title></head><body>你好，世界！</body></html>"


@route(url="/header_narrowing", method="POST", headers="Content-Type^=text/")
def header_narrowing():
    return "a^=b"


@route(url="/chunked", method=["POST", "PUT"])
async def chunked(reader: RequestBodyReader):
    data = await reader.read_to_end()
    return {"code": 0, "data": data.decode("utf-8")}


if sys.version_info >= (3, 9):        
    @route("/arr")
    def arr(arr: list[str]):

        return {"code": 0, "data": arr}

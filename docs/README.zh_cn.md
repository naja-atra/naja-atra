# python-simple-http-server

[![PyPI version](https://badge.fury.io/py/simple-http-server.png)](https://badge.fury.io/py/simple-http-server)

## 简介

这是一个轻量级编写的 HTTP 服务器，源生支持 websocket，你可以非常容易的搭建一个 Restful API。其中一些请求的转发等参考了 SpringMVC 的设计。

## 支持的 Python 的版本

Python 3.7+

## 为什么要选择这个项目？

* 轻量级
* 函数化编程
* 支持 Session 会话，并且可以通过[这个扩展](https://gitee.com/keijack/python-simple-http-server-redis-session)支持分布式会话。
* 可以通过[这个扩展](https://gitee.com/keijack/python-simple-http-server-jinja) 来使用 `jinja` 视图层功能。
* 支持过滤器链
* Spring MVC 风格的请求映射配置
* 简单易用
* 支持 SSL
* 支持 Gzip 压缩
* 支持 websocket
* 编写风格自由
* 可嵌入到 WSGI 标准的服务器当中
* 可嵌入到 ASGI 标准的服务器当中，本框架完全支持 ASGI 的 HTTP 与 Websocket 事件。
* 支持协程模式，该模式下，你的所有控制器均运行在一个线程当中。

## 依赖

这个工程本身并不依赖任何其他的库，但是如果你需要运行在 `tests` 目录下的单元测试，那么，你需要安装 `websocket-client` 库：

```shell
python3 -m pip install websocket-client
```

## 安装

```shell
python3 -m pip install simple_http_server
```

## 编写控制器

### 配置路由信息

我们接下来，将处理请求的函数命名为 **控制器函数（Controller Function）**。

类似 Spring MVC，我们使用描述性的方式来将配置请求的路由（在 Java 中，我们会使用标注 Annotation，而在 Python，我们使用 decorator，两者在使用时非常类似）。

基础的配置如下，该例子中，请求 /index 将会路由到当前的方法中。

请注意，其中 `request_map` 还有另外一个别称 `route`，你可以选择熟悉的标注使用。

```Python
from simple_http_server import request_map

@request_map("/index")
def your_ctroller_function():
    return "<html><body>Hello, World!</body></html>"
```

@request_map 会接收两个参数，第二个参数会指定当前的控制器函数会处理请求中哪些方法(Method)，以下的例子中的方法，仅会处理方法为 GET 的请求。

```Python
@request_map("/say_hello", method="GET")
def your_ctroller_function():
    return "<html><body>Hello, World!</body></html>"
```

method参数同时也可以是一个列表，以下的例子中，该控制器函数会处理方法为 GET、POST、PUT 的请求

```Python
@request_map("/say_hello", method=["GET", "POST", "PUT"])
def your_ctroller_function():
    return "<html><body>Hello, World!</body></html>"
```

匹配路由时，除了指定具体的路径之外，你还可以指定路径的某一段是可变的，这部方可变的部分将会作为路径参数放入请求中，如何取得这些路径参数我们将会在 **取得请求参数** 一节具体说明。@request_map 的配置如下。该配置下，`/say/hello/to/world`，`/say/hello/to/jhon` 等 url 都能访问该控制器方法。

```Python
@request_map("/say_hello/to/{name}", method=["GET", "POST", "PUT"])
def your_ctroller_function():
    return "<html><body>Hello, World!</body></html>"
```

你可以给一个控制器函数增加多个 @request_map

```python
@request_map("/")
@request_map("/index")
def index():
    return "<html><body>Hello, World!</body></html>"
```

你也可以使用协程来编写你的控制器，*注意：当你不是用协程模式启动时，你的协程会运行在处理该请求的线程当中。如果以协程模式启动，所有你的控制器，无论你有没有使用`async def`定义，均通过协程的方式运行在一个线程中。*

```python

async def say(sth: str = ""):
    _logger.info(f"Say: {sth}")
    return f"Success! {sth}"

@request_map("/中文/coroutine")
async def coroutine_ctrl(hey: str = "Hey!"):
    return await say(hey)
```

### 取的请求中的信息

参考了 Spring MVC 的设计，获取请求方法的方式非常自由。其中最基本的方法是取得 Request 对象，该对象中包含了所有其他方式能够获取的内容。

```Python
from simple_http_server import request_map
from simple_http_server import Request

@request_map("/say_hello/to/{name}", method=["GET", "POST", "PUT"])
def your_ctroller_function(req=Request()):
    """ 请注意关键字参数传入的默认参数是一个 Request 对象，而不是类本身。 """
    ##
    # 该请求的方法，可能是 "OPTIONS", "GET", "HEAD", "POST", "PUT", "DELETE", "TRACE", "CONNECT" 中的一个
    print(req.method)
    ##
    # 该请求的路径，就是 /say/hello/to/xxx
    print(req.path)
    ##
    #  一个 dict 对象，包含了所有的头部参数。
    print(req.headers)
    ##
    # 一个 dict 对象，包含了请求的参数，包括了来源于QueryString与 body 中的参数
    # 该对象仅存储一个参数，如果同一个参数名传入了多个值，该对象只记录第一个值。
    print(req.parameter)
    ##
    # 一个 dict 对象，类似，req.parameter，但该对象包含了所有的参数
    # 该对象的值总是会返回一个列表，即使一个参数名只传入了一个参数。
    print(req.parameters)
    ##
    # 返回 query string
    print(req.query_string)
    ##
    # 返回一个 Cookies 对象，该对象是 http.cookies.SimpleCookie 的子类
    print(req.cookies)
    ##
    # 一个 dict 对象，包含了所有的路径上的参数，本例中是 {"name": "xxx"}
    print(req.path_values)
    ##
    # 请求体部分，在 3.6 中是一个 bytes 对象。2.7 中是一个 str 对象
    print(req.body)
    ##
    # 当你的请求的 Content-Type 是 application/json 时，框架会自动将请求体中的 JSON 对象加载为一个dict对象。
    print(req.json)
    ##
    # Session
    session = req.getSession()
    ins = session.get_attribute("in-session")
    session.set_attribute("in-session", "Hello, Session!")
    return "<html><body>Hello, World!</body></html>"
```

你也可以通过 `ModelDict` 来直接取得 request 里的参数。

```python

@request_map("/say_hello/to/{name}", method=["GET", "POST", "PUT"])
def your_ctroller_function(model=ModelDict(), name=PathValue()):
    # 如果你访问 http://.../say_hello/to/keijack?a=1&b=2&b=3
    print(name) # 输出 keijack
    print(model["a"]) # 输出 1
    print(model["b"]) # 取得一个列表，输出 ["2,", "3"]
    return "<html><body>Hello, World!</body></html>"

```

我们还可以通过更直接的参数和关键字参数来获取请求中的信息，使得编码更加简洁和方便。

```python
from simple_http_server import request_map

@request_map("/say_hello/to/{name}", method=["GET", "POST", "PUT"])
def your_ctroller_function(
        user_name, # 传入 req.parameter["user_name"]，如果该参数为空，则会响应为 400 参数错误
        password, # 传入 req.parameter["password"]，如果参数为空，则会响应为 400 参数错误
        nickName="", # 传入 req.parameter["nickName"]，如果参数为空，则会传入 ""
        age=16, # 传入 int(req.parameter["age"])，如果传入空则传入 16，如果传入的不是数字类型，会返回 400 参数错误
        male=True, # 传入 0, false, 空字符串 为 False，其他均为 True，如果不传入，传入这里指定的默认值
        skills=[], # 传入 req.parameters["skills"]，会返回一个数组，如果没有传入任何的内容，则返回这里指定的数组
        extra={} # 传入 json.loads(req.parameter["extra"])，如果不传入则传入这里指定的 dict 对象，如果传入的字符串不是 JSON 格式，则响应为 400 参数错误
    ):
    return "<html><body>Hello, World!</body></html>"
```

以上的是基础类型的获取，实施上，我们还提供了几个类，通过这些类，你还能快速地获取一些在请求头中，Cookies 中，请求体，路径中的信息。以下是一些代码实例：

```python
from simple_http_server import request_map
from simple_http_server import Parameter
from simple_http_server import Parameters
from simple_http_server import Headers
from simple_http_server import Header
from simple_http_server import Cookies
from simple_http_server import Cookie
from simple_http_server import PathValue
from simple_http_server import Session


@request_map("/say_hello/to/{name}", method=["GET", "POST", "PUT"])
def your_ctroller_function(
        user_name=Parameter("userName", required=True), # 传入 req.parameter["userName"]，如果该参数为空，则会响应为 400 参数错误
        password=Parameter("password", required=True), # 传入 req.parameter["password"]，如果参数为空，则会响应为 400 参数错误
        nickName=Parameter(default=""), # 传入 req.parameter["nickName"]，如果参数为空，则会传入 ""，参数名和
        skills=Parameters(required=True), # 传入 req.parameters["skills"]，会返回一个数组，如果没有传入任何的内容，则响应为 400 参数错误
        all_headers=Headers(), # 传入 req.headers
        user_token=Header(name="userToken", required=True), # 传入 req.headers["userToken"]，如果请求头中没有 "userToken" 字段，则响应为 400 参数错误
        all_cookies=Cookies(), # 传入 req.cookies，返回所有当前请求的 cookies
        user_info=Cookie("userInfo", required=False), # 传入 req.cookies["userInfo"]，如果没有该 cookie，则响应为 400 参数错误
        name=PathValue("name"), # 传入 req.path_values["name"]，返回路径中你路由配置中匹配 {name} 的字符串,
        session=Session() # 传入 req.getSession(True)，取得当前 request 的 Session 会话，如果没有会创建一个。
    ):
    return "<html><body>Hello, World!</body></html>"
```

从上述的例子我们看出，这些类中的参数均有默认值，即使不传入，也能返回正确的数据。除了上述的这些例子之外，我们还有一些额外的情况。例如请求的 Content-Type 是 application/json，然后我们将 JSON 字符串直接写入请求体中，我们可以这样获取信息：

```python
from simple_http_server import request_map
from simple_http_server import JSONBody

@request_map("/from_json_bldy", method=["post", "put", "delete"])
def your_json_body_controller_function(data=JSONBody()):
    ##
    #  JSONBody 是 dict 的子类，你可以直接其是一个 dict 来使用
    print(data["some_key"])
    return "<html><body>Hello, World!</body></html>"
```

我们也支持使用 multipart/form-data 上传文件，你可以这样获取文件：

```python
from simple_http_server import request_map
from simple_http_server import MultipartFile

@request_map("/upload", method="POST")
def upload(
        img=MultipartFile("img", required=True) # 如果没有传入 img 参数，或者该参数不是一个文件，均响应为 400 参数错误
        ):
    root = os.path.dirname(os.path.abspath(__file__))
    ##
    # 获取上传文件的 content-type
    print(img.content_type)
    ##
    # MultipartFile.content 在 3.6 中为 bytes 类型，在 2.7 中为字符串
    print(img.content)
    ##
    # 还可以通过内置的 save_to_file 将内容直接写入到某个文件中
    img.save_to_file(root + "/uploads/imgs/" + img.filename)
    return "<!DOCTYPE html><html><body>upload ok!</body></html>"

```

你也可以使用 Python3 的函数变量标注(variable annotation) 来定义你需要取得的数据类型。

```python
@request_map("/say_hello/to/{name}", method=["GET", "POST", "PUT"])
def your_ctroller_function(
        user_name: str, # 传入 req.parameter["user_name"]，如果该参数为空，则会响应为 400 参数错误
        password: str, # 传入 req.parameter["password"]，如果参数为空，则会响应为 400 参数错误
        skills: list, # 传入 req.parameters["skills"]，会返回一个数组，如果没有传入任何的内容，则响应为 400 参数错误
        all_headers: Headers, # 传入 req.headers
        user_token: Header, # 传入 req.headers["user_token"]，如果请求头中没有 "userToken" 字段，则响应为 400 参数错误
        all_cookies: Cookies, # 传入 req.cookies，返回所有当前请求的 cookies
        user_info: Cookie, # 传入 req.cookies["user_info"]，如果没有该 cookie，则响应为 400 参数错误
        name: PathValue, # 传入 req.path_values["name"]，返回路径中你路由配置中匹配 {name} 的字符串,
        session: Session # 传入 req.getSession(True)，取得当前 request 的 Session 会话，如果没有会创建一个。
    ):
    return "<html><body>Hello, World!</body></html>"
```

如果内置的参数绑定无法满足你的需求，你可以通过`@model_binding` 以及 `@default_model_binding` 来指定自己的绑定逻辑。

如果你只需要特定类型的数据绑定，请使用 `@model_binding` 进行。

```python
from typing import Any
from simple_http_server.models.model_bindings import ModelBinding
from simple_http_server import model_binding
from simple_http_server import HttpError, route

class Person:

    def __init__(self, name: str = "", sex: int = "", age: int = 0) -> None:
        self.name = name
        self.sex = sex
        self.age = age

@model_binding(Person)
class PersonModelBinding(ModelBinding):

    async def bind(self) -> Any:
        name = self.request.get_parameter("name", "no-one")
        sex = self.request.get_parameter("sex", "secret")
        try:
            age = int(self.request.get_parameter("age", ""))
        except:
            raise HttpError(400, "Age is required, and must be an integer")
        return Person(name, sex, age)

# 之后，你便可以在控制器方法，使用该参数定义了。
@route("/model_binding/person")
def test_model_binding(person: Person):
    return {
        "name": person.name,
        "sex": person.sex,
        "age": person.age,
    }

```

当然，你也可以使用 `@default_model_binding` 来指定默认的数据绑定逻辑，配置了该项后，所有未在内置或者是上述配置中找到的数据，均会使用该类来处理。

```python
from simple_http_server.models.model_bindings import ModelBinding
from simple_http_server import default_model_binding
from simple_http_server import HttpError, route

class Dog:

    def __init__(self, name="a dog") -> None:
        self.name = name

    def wang(self):
        return self.name

@default_model_binding
class SetAttrModelBinding(ModelBinding):

    """
    " 该类会尝试使用无参数的方法创建一个对象，然后将请求的参数通过 `setattr` 的方式设置到该对象当中。
    """

    def bind(self) -> Any:
        # bind 方法可以定义为 async 或者普通方法
        try:
            obj = self.arg_type()
            for k, v in self.request.parameter.items():
                setattr(obj, k, v)
            return obj
        except Exception as e:
            _logger.warning(
                f"Cannot create Object with given type {self.arg_type}. ", stack_info=True)
            return self.default_value

@route("/model_binding/dog")
def test_model_binding_dog(dog: Dog):
    return {
        "name": dog.wang()
    }
```

我们建议使用函数式编程来编写你的控制器（Controller），不过你更喜欢使用对象的话，你可以将你的`@request_map` 用在类方法上，下面的例子中，每一个请求进来之后，系统会自动创建一个对象来调用该方法。:

```python

class MyController:

    def __init__(self) -> None:
        self._name = "ctr object"

    @request_map("/obj/say_hello", method="GET")
    def my_ctrl_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

```

如果你想使得控制类为单例的话，你可以使用 `@controller` 装饰器。

```python

@controller
class MyController:

    def __init__(self) -> None:
        self._name = "ctr object"

    @request_map("/obj/say_hello", method="GET")
    def my_ctrl_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

```

你也可以在类上使用 `@request_map`，类上的路径会作为访问路径的一部分。

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

如果你的类有初始化变量，你也可以在 `@controller` 中设定。

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

从 `0.7.0` 开始 `@request_map` 还支持正则表达式。

```python
# url `/reg/abcef/aref/xxx` 能匹配到以下控制器:
@route(regexp="^(reg/(.+))$", method="GET")
def my_reg_ctr(reg_groups: RegGroups, reg_group: RegGroup = RegGroup(1)):
    print(reg_groups) # 输出 ("reg/abcef/aref/xxx", "abcef/aref/xxx")
    print(reg_group) # 输出 "abcef/aref/xxx"
    return f"{self._name}, {reg_group.group},{reg_group}"
```

从 `0.14.0` 开始，`@request_map` 还支持通配符。你只能使用前置通配符或者时后知通配符其中一项，不能同时配置。如有复杂需求则请使用正则表达式来进行匹配。

```python
@request_map("/star/*") # /star/c 可以匹配，但是 /star/c/d 不能。
@request_map("*/star") # /c/star 可以匹配，但是 /c/d/star 不能。
def star_path(path_val=PathValue()): # 你可以通过 PathValue 取得 url 中 匹配 * 通配符的内容。
    return f"<html><body>{path_val}</body></html>"

@request_map("/star/**") # /star/c 和 /star/c/d 均可以匹配。
@request_map("**/star") # /c/star 和 /c/d/stars 均可匹配。
def star_path(path_val=PathValue()): # 你可以通过 PathValue 通配符取得 url 中 匹配 ** 通配符的内容。
    return f"<html><body>{path_val}</body></html>"
```

你可以在 `@request_map` 中使用 `headers` 以及 `params` 参数来限制控制器的匹配。以下例子说明了 `params` 参数，`headers` 参数基本相同，不再赘述。

```python
# 使用等式过滤，当访问不带 a 参数，或者带 a 参数但是结果不是 b 的时候，不会进入该控制器。
@request("/exact_params", method="GET", params="a=b")
def exact_params(a: str):
    print(f"{a}") # b
    return {"result": "ok"}

# 使用不等式过滤，当访问不带 a 参数，或者 a 参数的结果是 b 时，不会进入该控制器。
@request("/exact_params", method="GET", params="a!=b")
def exact_not_params(a: str):
    print(f"{a}") # b
    return {"result": "ok"}

# 使用起始过滤，当访问带 a 参数，并且 a 参数以 b 开头时才会进入该控制器。
@request("/exact_params", method="GET", params="a^=b")
def exact_startswith_params(a: str):
    print(f"{a}") # b
    return {"result": "ok"}

# 使用非包含过滤，当参数包含 a 参数时，不会进入该控制器。
@request("/exact_params", method="GET", params="!a")
def no_params():
    return {"result": "ok"}

# 必须包含 a 参数才进入该控制器
@request("/exact_params", method="GET", params="a")
def must_has_params():
    return {"result": "ok"}

# 多表达式匹配，默认请求满足所有表达式才能进入该控制器。
@request("/exact_params", method="GET", params=["a=b", "c!=d"])
def multipul_params():
    return {"result": "ok"}

# 多表达式匹配，默认请求满足所有表达式才能进入该控制器，你也通过参数 `match_all_params_expressions` 设置为 False，该情况下，匹配通过其中一个表达式就会进入该控制器。
@request("/exact_params", method="GET", params=["a=b", "c!=d"], match_all_params_expressions=False)
def multipul_params():
    return {"result": "ok"}
```

如果是在控制器类中使用，将会取类参表达式会与控制器方法的表达式的并集进行匹配。

在控制器类中使用正则表达式的 request_map:

```python
@controller(args=["ctr_name"], kwargs={"desc": "this is a key word argument"})
@request_map("/obj", method="GET") # 请不要在这里配置 regexp，因为不工作
class MyController:

    def __init__(self, name, desc="") -> None:
        self._name = f"ctr[{name}] - {desc}"

    @request_map
    def my_ctrl_default_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}

    @route(regexp="^(reg/(.+))$") # 从类装饰器来的 `/obj` 会被无视, 但 `method`(GET) 则依然有用
    def my_ctrl_mth(self, name: str):
        return {"message": f"hello, {name}, {self._name} says. "}
```

### Session

默认情况下，Session 中的数据会存储到本地，如果你需要做分布式 Session，例如将 Session内容存储在 Redis 或者 Memcache，你可以自定义自己的 `Session` 和 `SessionFactory`，然后创建一个你定义的 SessionFactory 对象通过 `simple_http_server.set_session_factory` 设置到框架中。

```python
from simple_http_server import Session, SessionFactory, set_session_factory

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

你可以使用以下的 redis session 实现：https://gitee.com/keijack/python-simple-http-server-redis-session


### 响应请求

从上述的例子中可以看出，取得请求中的参数我们有许多方式，这个给了开发者很高的自由度来编写这些信息。而响应的方法一样具有各种方法。

上述的例子中是其中一种，我们直接返回了一个HTML格式的字符串，该框架会自动的将这个字符串响应为 text/html 格式。

除了 HTML5 格式的字符串，我们还可以返回以下的内容：

```python
    ##
    # 如果你返回一个 dict，那么框架将会将其响应为 application/json
    return {"success": True, "message": "Success!"}
```

```python
    ##
    # 你可以返回一个 XML 格式的字符串，框架会将其响应为 text/xml
    return "<?xml><root></root>"
```

```python
    ##
    # 返回其他的字符串，框架会将其响应为 text/plain
    return "some other string value"
```

```python
    ##
    # 响应为 HTTP 错误，可以在任何适合抛出一个 HttpError 异常
    from simple_http_server import HttpError
    raise HttpError(404, "page not found")
```

```python
    ##
    # 如果抛出其他的异常，默认会响应为 500 服务器错误
    raise Exception()
```

```python
    ##
    # 返回 Redirect 对象
    from simple_http_server import Redirect
    return Redirect("/redirect/to/this/path")
```

```python
    ##
    # 你可以返回一个 StaticFile 类，返回一个文件，这个可以编写下载用的控制器方法
    from simple_http_server import StaticFile
    return StaticFile("/path/to/file.xml", content_type="text/xml")
```

```python
    ##
    # 还可以返回一个 Response 对象，这个对象可以设置更多的信息
    from simple_http_server import Response
    from http.cookies import SimpleCookie
    res = Response(status_code=200)
    res.headers["Content-Type"] = "text/html"
    res.set_header("userToken", "user_id_token_xxxx") # set_header() 会覆盖之前设置的信息
    res.add_header("userToken", "xxxx") # add_header() 会增加多一个信息
    res.cookies = SimpleCookie()
    res.cookie["userInfo"] = "ABC"
    res.cookie["userInfo"]["path"] = "/"
    res.body = "<!DOCTYPE html><html><body>hello world</body></html>"
    return res
```

```python
    ##
    # 我们还有一个更为简便的方式，就是直接返回一个元祖(tuple)
    from simple_http_server import Headers
    from simple_http_server import Cookies
    res_cookies = Cookies()
    res_cookie["userInfo"] = "ABC"
    res_cookie["userInfo"]["path"] = "/"
    ##
    # 该元祖中，这些参数的顺序其实并无关系，
    # 第一个返回的 int 元素会将作为请求的状态码
    # 但是元组中所有 Headers 对象均将会被写入到响应头中
    # 同样，元祖中所有 http.cookies.BaseCookies 以及其子类，含 http.cookie.SimpleCookie 以及 simple_http_server.Cookies 均会被写入响应的 cookies 中
    # 而元祖中第一个出现的类型在 (str, unicode, dict, StaticFile, bytes) 会被作为响应的数据。
    # 其他不符合条件的元素将被忽略
    return 200, Headers({"userToken": "user_id_token_xxx"}), res_cookie, {"success": True, "message": "success!"}, "这个字符串会被忽略"
```

```python
    ##
    # 元祖中所有的元素均不是必须的，即使是 body 也是一样，你可以省略一些没有的内容
    # 以下的元祖只写入了头部和响应体信息
    return Headers({"userToken": "user_id_token_xxx"}), {"success": True, "message": "success!"},

```

上述的例子中描述的通过返回信息来进行响应，你也可以通过 Response 参数来响应

```python
from simple_http_server import request_map
from simple_http_server import Response

@request_map("/say_hello")
def say_hello(res=Response()):
    ##
    # Response 对象就是上述我们写在返回的那个对象，所以，上面的对 headers、cookies 等的接口这个对象均有。
    res.body = "<html><body>Hello, world! </body></html>"
    res.send_response()
    # 如果使用 res 来发送请求，就不再在控制器函数中返回任何内容了。

@request_map("/")
def redirect(res=Response()):
    res.send_redirect("/index")

@route("/res/write/bytes")
def res_writer(response: Response):
    # 你也可以通过 response 对象分段写入数据。
    response.status_code = 200
    response.add_header("Content-Type", "application/octet-stream")
    response.write_bytes(b'abcd')
    response.write_bytes(bytearray(b'efg'))
    response.close()
    
```

### Websocket


由于 Websocket 有多种事件，使用函数作为配置很多情况下反而不够直观。建议你使用类来处理 websocket 连接而非函数。并且你需要使用 `@websocket_handler` 来标识你的处理类。在你的处理类中，你需要按照制定的格式来定义处理 websocket 各事件的方法。最简单的方式是继承 `simple_http_server.WebsocketHandler` 类，实现其中你需要的事件方法（该继承并不是必需的）。

你可以通过指定 `endpoint` 或者 `regexp` 来匹配需要处理的 url。另外，该装饰器还有一个 `singleton` 的配置，该配置默认为 `True`，所有的请求都会使用一个对象来处理。当你将这个字段设置为 `False` 后，系统将会为每个 `WebsocketSession` 创建一个独立的对象来处理请求。

```python
from simple_http_server import WebsocketHandler, WebsocketRequest,WebsocketSession, websocket_handler

@websocket_handler(endpoint="/ws/{path_val}")
class WSHandler(WebsocketHandler):
    
    """
    " 继承 WebsocketHandler 为非必须，以下的事件方法也不是所有都需要实现提供，但是实现提供了，方法的参数必须按照以下签名提供。
    """

    def on_handshake(self, request: WebsocketRequest):
        """
        "
        " 你可以从 request 中取得 path/headers/path_values/cookies/query_string/query_parameters。
        " 
        " 你需要返回一个元祖 (http_status_code, headers)
        "
        " 当元祖中的 http_status_code 在 (0, None, 101) 时， websocket 会继续链接，否则会返回指定的状态码并且断开链接。 
        "
        " 如果需要额外增加响应的头，可以在元祖中增加 headers 参数。
        "
        " 元祖中的数据如无特殊，均可忽略。
        "
        """
        _logger.info(f">>{session.id}<< open! {request.path_values}")
        return 0, {}

    def on_open(self, session: WebsocketSession):
        """
        " 
        " 成功建立链接时调用
        "
        """
        _logger.info(f">>{session.id}<< open! {session.request.path_values}")

    def on_close(self, session: WebsocketSession, reason: str):
        """
        "
        " 关闭时调用
        "
        """
        _logger.info(f">>{session.id}<< close::{reason}")

    def on_text_message(self, session: WebsocketSession, message: str):
        """
        "
        " 收到文本消息时调用
        "
        """
        _logger.info(f">>{session.id}<< on text message: {message}")
        session.send(message)

@websocket_handler(regexp="^/ws-reg/([a-zA-Z0-9]+)$", singleton=False)
class WSHandler(WebsocketHandler):

    """
    " 你的事件处理代码
    """
```

但是，如果你无需处理所有的 websocket 事件，仅对其中的某个事件进行处理，那么你也可以使用函数来定义。

```python

from simple_http_server import WebsocketCloseReason, WebsocketHandler, WebsocketRequest, WebsocketSession, websocket_message, websocket_handshake, websocket_open, websocket_close, WEBSOCKET_MESSAGE_TEXT

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
# 你可以将这些事件函数定义为普通或者 `async` 模式均可。
async def ws_text(session: WebsocketSession, message: str): 
    _logger.info(f">>{session.id}<< on text message: {message}")
    session.send(f"{session.request.path_values['path_val']}-{message}")
    if message == "close":
        session.close()
```

### 自定义错误信息

你可以通过 `@error_message` 来设定错误时返回特定的错误信息。

```python
from simple_http_server import error_message
# 具体的错误码
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

# 范围错误码
@error_message("50x")
def my_error_message(code, message, explain=""):
    return f"{code}-{message}-{explain}"

# 所有错误信号
@error_message
def my_error_message(code, message, explain=""):
    return f"{code}-{message}-{explain}"
```


## 编写过滤器

参考 Java 的设计，我们增加了过滤器链式的设计，这个给了你一定的面向切面编码的能力，虽然比较弱，但是做一些权限验证，日志记录等也是够用的。

```python
from simple_http_server import request_filter


@request_filter("/tuple/**") # 使用通配符，** 可包含 /，* 不包含，上述配置
@request_filter(regexp="^/tuple") # 使用正则表达式
def filter_tuple(ctx):
    print("---------- through filter ---------------")
    # 在过滤器中加入一些信息到请求头中
    ctx.request.headers["filter-set"] = "through filter"
    if "user_name" not in ctx.request.parameter:
        ctx.response.send_redirect("/index")
    elif "pass" not in ctx.request.parameter:
        ctx.response.send_error(400, "pass should be passed")
        # 你也可以使用以下代码，通过抛出异常的方式来返回错误的响应信息。
        # raise HttpError(400, "pass should be passed")
    else:
        # 如果你需要进入下一个过滤器链条或者调用请求处理的函数，必须显式调用以下的方法。
        ctx.do_chain()
```

## 启动服务器

```python

import simple_http_server.server as server
# 如果你的控制器代码（处理请求的函数）放在别的文件中，那么在你的 main.py 中，你必须将他都 import 进来。
import my_test_ctrl


def main(*args):
    # 除了 import 外，还可以通过 scan 方法批量加载 controller 文件。
    server.scan("my_ctr_pkg", r".*controller.*")
    server.start()

if __name__ == "__main__":
    main()
```

如果需要指定IP或者端口：

```python
    server.start(host="", port=8080)
```

如果需要指定静态资源：

```python 
    server.start(resources={"/path_prefix/*", "/absolute/dir/root/path", # 通过前缀制定匹配的指定目录下的所有文件资源。
                            "/path_prefix/**", "/absolute/dir/root/path", # 通过前缀制定匹配的指定目录以及其子目录下的所有文件资源。
                            "*.suffix", "/absolute/dir/root/path", # 匹配指定目录下的特定后缀的文件。
                            "**.suffix", "/absolute/dir/root/path", # 匹配指定目录以及其子目录下的特定后缀的文件。
                            })
```

如果需要支持 HTTPS（SSL）


```python
    server.start(host="", 
                 port=8443,
                 ssl=True,
                 ssl_protocol=ssl.PROTOCOL_TLS_SERVER, # 可选，默认使用 ssl.PROTOCOL_TLS_SERVER，该配置会使得服务器取客户端和服务端均支持的最高版本的协议来进行通讯。
                 ssl_check_hostname=False, # 可选，是否检查域名，如果设为 True，那么如果不是通过该域名访问则无法建立对应链接。
                 keyfile="/path/to/your/keyfile.key",
                 certfile="/path/to/your/certfile.cert",
                 keypass="", # 可选，如果你的私钥使用了密码加密
                 )
    
```

你也可以定义自己的 SSLContext。

```python
    import ssl
    ssl_ctx = ssl.SSLContext()
    #... configure ssl_ctx here

    server.start(host="", 
                 port=8443,
                 ssl=True,
                 ssl_contex=ssl_ctx
                 )
    
```

### 协程

从 `0.12.0` 开始，你可以通过以下的方式使用协程的方式来运行你的服务。

```python
    server.start(prefer_coroutine=True)
```

从 `0.13.0` 开始，协程模式下，整个服务器将使用协程提供的异步I/O来处理请求。所以，即使你可以使用 `asnyc def` 来定义你所有的控制器了，其中也包含了 websocket 相关的回调方法。

如果你调用服务器启动的方法本身就是 `async def` 的，你可以使用启动函数的异步版本。

```python
    await server.start_async()
    # 即使你调用该函数的异步版本，你依然可以让所有的请求运行在独立的线程了。
    await server.start_async(prefer_coroutine=False)
```

### Gzip 压缩

如果你想你的响应体使用 gzip 进行压缩返回，你可以在服务器启动时设置需要压缩的 `Content-Type` 以及压缩等级。

```python
server.start(host="", 
             port=8080, 
             gzip_content_types={"text/html", "text/plain", "text/css", "application/json", "text/javascript"}, 
             gzip_compress_level=9)
```

此后，当请求包含 `Accept-Encoding` 头包含 `gzip` 后，该请求会将内容压缩后再返回。

## 日志

默认情况下，日志会输出到控制台，你创建自己的 Logging Handler 来将日志输出到别处，例如一个滚动文件中：

```python
import simple_http_server.logger as logger
import logging

_formatter = logging.Formatter(fmt='[%(asctime)s]-[%(name)s]-%(levelname)-4s: %(message)s')
_handler = logging.TimedRotatingFileHandler("/var/log/simple_http_server.log", when="midnight", backupCount=7)
_handler.setFormatter(_formatter)
_handler.setLevel("INFO")

logger.set_handler(_handler)
```

如果你想增加一个日志控制器而不是想替代内置的，那么你可以使用以下方法：

```python
logger.add_handler(_handler)
```

你也可以使用以下方法来设置日志输出级别：

```python
logger.set_level("DEBUG")
```

这个日志使用了一个背景线程来输出日志，因此其非常适合使用在多线程的场景，特别你是你有多个 logger 共用一个 `TimedRotatingFileHandler` 的时候。在多线程的场景下，这个日志控制器经常不能正常地按时切割文件。

你可以通过 `logger.LoggerFactory` 来取得新的 logger，这个 logger 将与框架默认的区分开来，通过这个方法，你可以分开控制框架和业务的日志级别。

```python
import simple_http_server.logger as logger

log = logger.get_logger("my_service", "my_log_fac")

# 如果你想为这个 logger factory 设置不同的日志等级：

log_fac = logger.get_logger_factory("my_log_fac")
log_fac.log_level = "DEBUG"
log = log_fac.get_logger("my_service")

log.info(...)

```

## WSGI 支持

你可以在 WSGI 的框架下（例如在阿里云的函数计算的 HTTP 入口中）引入本框架。

```python
import simple_http_server.server as server
import os
from simple_http_server import request_map


# 扫描你的控制器函数
server.scan("tests/ctrls", r'.*controllers.*')
# 或者在这里定义一个controller
@request_map("/hello_wsgi")
def my_controller(name: str):
    return 200, "Hello, WSGI!"
# 初始化一个 wsgi 代理，入参 resources 为可选参数。
wsgi_proxy = server.init_wsgi_proxy(resources={"/public/*": f"/you/static/files/path"})

# WSGI 标准入口
def handler(environ, start_response):
    return wsgi_proxy.app_proxy(environ, start_response)
```

## ASGI 支持

可以在 ASGI 的框架上（例如 `uvicorn`）使用本框架。

*由于 ASGI 框架的标准，在 ASGI 框架上，websocket 仅支持发送`文字`以及`二进制`消息，不支持发送 ping/pone/frame 等高级功能。*

```python

import asyncio
import uvicorn
import simple_http_server.server as server
from simple_http_server.server import ASGIProxy


asgi_proxy: ASGIProxy = None
init_asgi_proxy_lock: asyncio.Lock = asyncio.Lock()


async def init_asgi_proxy():
    global asgi_proxy
    if asgi_proxy == None:
        async with init_asgi_proxy_lock:
            if asgi_proxy == None:
                server.scan(base_dir="tests/ctrls", regx=r'.*controllers.*')
                asgi_proxy = server.init_asgi_proxy(resources={"/public/*": "tests/static"})

async def app(scope, receive, send):
    await init_asgi_proxy()
    await asgi_proxy.app_proxy(scope, receive, send)

def main():
    config = uvicorn.Config("main:app", host="0.0.0.0", port=9090, log_level="info")
    asgi_server = uvicorn.Server(config)
    asgi_server.run()

if __name__ == "__main__":
    main()

```

## 感谢

部分处理 websocket 的代码参考自开源库： https://github.com/Pithikos/python-websocket-server
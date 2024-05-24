# Naja-Atra（饭铲头）

`Naja-Atra` 是一个轻量化的 Python Web 框架。支持 HTTP 与 WebSocket 协议。

## 安装

请使用 [pip](https://pip.pypa.io/en/stable/quickstart/) 进行安装:

```
$ pip install -U naja-atra
```

一个简单的例子:

```python
from naja_atra import route

@route('/')
def hello(name: str = 'World'):
    return {'message': f'Hello, {name}!'}
```

要执行，请使用 `naja_atra` 命令来运行:

```
$ python3 -m naja_atra
```

或者，也可以使用代码来运行:

```python
from naja_atra import route
from naja_atra import server


@route("/")
def hello(name: str = 'World'):
    return {"message": f"Hello {name}"}

def main():
    server.start(host="0.0.0.0", port=9090)

if __name__ == "__main__":
    main()
```

## More

* 源代码(Gitee): [https://gitee.com/keijack/naja-atra](https://gitee.com/keijack/naja-atra)
* 问题跟踪(Github): [https://github.com/naja-atra/naja-atra/issues](https://github.com/naja-atra/naja-atra/issues)

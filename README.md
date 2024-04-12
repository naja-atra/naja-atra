# Naja-Atra

Naja-Atra is a lightweight python web framework. It's designed to make starting a web service easier. It supports both HTTP and WebSocket. 

## Installation

Install and update using [pip](https://pip.pypa.io/en/stable/quickstart/):

```
$ pip install -U naja-atra
```

A Simple Example:

```python
from naja_atra import route

@route('/')
def hello(name: str = 'World'):
    return {'message': f'Hello, {name}!'}
```

To run the app, simply execute the `naja-atra` command:

```
$ python3 -m naja_atra
```

Or, you can run it programmatically:

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

* Source Code: [https://github.com/naja-atra/naja-atra](https://github.com/naja-atra/naja-atra)
* Issues Tracker: [https://github.com/naja-atra/naja-atra/issues](https://github.com/naja-atra/naja-atra/issues)

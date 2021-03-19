# Development

## Module Structure

Once you added a module name into `config.ENABLED_MODULES`, it is required to
have `your_module.init_app(app, **kwargs)` function. Everything else is
completely optional. Thus, here is the required minimum:

```
your_module/
└── __init__.py
```

, where `__init__.py` will look like this:

```python
def init_app(app, **kwargs):
    pass
```

In this example, however, `init_app` imports `resources` and registeres `api`
(an instance of (patched) `flask_restx.Namespace`). Learn more about the
"big picture" in the next section.


## Where to start reading the code?


The easiest way to start the application is by using PyInvoke command `app.run`
implemented in `tasks/app/run.py`:

```
invoke app.run
```

The command creates an application by running
`app/__init__.py:create_app()` function, which in its turn:

1. loads an application config;
2. initializes extensions:
   `app/extensions/__init__.py:init_app()`;
3. initializes modules:
   `app/modules/__init__.py:init_app()`.

Modules initialization calls `init_app()` in every enabled module
(listed in `config.ENABLED_MODULES`).

Let's take `teams` module as an example to look further.
`app/modules/teams/__init__.py:init_app()`
imports and registers `api` instance of (patched) `flask_restx.Namespace`
from `.resources`. Flask-RESTX `Namespace` is designed to provide similar
functionality as Flask `Blueprint`.

`api.route()` is used to bind a
resource (classes inherited from `flask_restx.Resource`) to a specific
route.

Lastly, every `Resource` should have methods which are lowercased HTTP method
names (i.e. `.get()`, `.post()`, etc). This is where users' requests end up.

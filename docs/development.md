# Development

## Automatically reloading flask when code changes

This is useful during development so houston is always serving the most
up to date code.  The alternative is to manually restart the houston
server by doing `docker-compose restart houston`.

By default, reloading is turned off.  To turn this on, you can do this
in your `docker-compose.override.yml`:

```yaml
services:
  houston:
    environment: &houston-environment
      USE_RELOADER: "true"
```

After this change you would need to recreate the houston container:

```
docker-compose rm -f --stop houston
docker-compose up -d houston
```

## Running development server on port 80

Instead of using `http://localhost:84/`, you can configure the server to use
port 80 in `docker-compose.override.yml`:

```yaml
services:
  houston:
    healthcheck:
      test: [ "CMD", "curl", "-f", "http://0.0.0.0:5000/api/v1/site-settings/heartbeat", "-H", "Host: localhost" ]
    environment:
      SERVER_NAME: "localhost"

  celery-worker:
    environment:
      SERVER_NAME: "localhost"

  celery-worker2:
    environment:
      SERVER_NAME: "localhost"

  celery-worker3:
    environment:
      SERVER_NAME: "localhost"

  localhost:
    ports:
      - "80:80"
```

Then do `docker-compose up -d` to update services.

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
export HOUSTON_APP_CONTEXT=codex
export FLASK_ENV=development
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


## How to Update Schemas / Create a Migration

1. Update schema objects in `/app/modules`
2. Run `invoke app.db.migrate` to create an auto generated migration or `invoke app.db.revision` to create an empty migration for non-schema updates
3. A new file should have been created in `/app/migrations/versions`
4. Run `invoke app.db.upgrade`


## Integrations with Flask-* Projects

Since this project is only an extension to Flask, most (if not all) Flask
plugins should work.

Verified compatible projects:
* flask-sqlalchemy
* flask-login
* flask-marshmallow
* flask-oauthlib
* flask-cors
* flask-limiter

### Example integration steps

#### flask-limiter

1. Add `flask-limiter` to end of the `app/requirements.txt` file, so it gets
installed when the application is deployed.
2. Apply the relevant changes to `app/extensions/__init__.py`:

    ```python
    # ... other imports.

    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    # change limiter configs per your project needs.
    limiter = Limiter(key_func=get_remote_address, default_limits=["1 per minute"])

    from . import api

    def init_app(app):
        """
        Application extensions initialization.
        """
        for extension in (
                # ... other extensions.
                limiter,  # Add this
            ):
            extension.init_app(app)
    ```
3. (Optional) Set endpoint-specific limits:

    ```python
    from app.extensions import limiter

    @api.route('/account/verify')
    class IdentityVerify(Resource):
        """
        Handle identity verification.
        """
        # Notice this is different from the simple example at the top of flask-limiter doc page.
        # The reason is explained here: https://flask-limiter.readthedocs.io/en/stable/#using-flask-pluggable-views
        decorators = [limiter.limit("10/second")] # config as you need.

        @api.parameters(parameters.SomeParameters())
        @api.response(schemas.SomeSchema())
        def post(self, args):
            return {"verified": True}
    ```

## Marshmallow Tricks

There are a few helpers already available in the `flask_restx_patched`:

* `flask_restx_patched.parameters.Parameters` - base class, which is a thin
  wrapper on top of Marshmallow Schema.
* `flask_restx_patched.parameters.PostFormParameters` - a helper class,
  which automatically mark all the fields that has no explicitly defined
  location to be form data parameters.
* `flask_restx_patched.parameters.PatchJSONParameters` - a helper class for
  the common use-case of [RFC 6902](http://tools.ietf.org/html/rfc6902)
  describing JSON PATCH.
* `flask_restx_patched.namespace.Namespace.parameters` - a helper decorator,
  which automatically handles and documents the passed `Parameters`.

You can find the examples of the usage throughout the code base (in
`/app/modules/*`).


### JSON Parameters

While there is an implementation for JSON PATCH Parameters, there are other
use-cases, where you may need to handle JSON as input parameters. Naturally,
JSON input is just a form data body text which is treated as JSON on a server
side, so you only need define a single variable called `body` with
`location='json'`:

```python
class UserSchema(Schema):
    id = base_fields.Integer(required=False)
    username = base_fields.String(required=True)


class MyObjectSchema(Schema):
    id = base_fields.Integer(required=True)
    priority = base_fields.String(required=True)
    owner = base_fields.Nested(UserSchema, required=False)


class CreateMyObjectParameters(Parameters):
    body = base_fields.Nested(MyObjectSchema, location='json', required=True)


api = Namespace('my-objects-controller', description="My Objects Controller", path='/my-objects')


@api.route('/')
class MyObjects(Resource):
    """
    Manipulations with My Objects.
    """

    @api.parameters(CreateMyObjectParameters())
    @api.response(MyObjectSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    @api.doc(id='create_my_object')
    def post(self, args):
        """
        Create a new My Object.
        """
        return create_my_object(args)
```

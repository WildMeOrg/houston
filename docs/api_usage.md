# Houston API Usage

## Authentication Details

This example server features OAuth2 Authentication protocol support, but don't
be afraid of it! If you learn it, OAuth2 will save you from a lot of troubles.

### Authentication with Login and Password (Resource Owner Password Credentials Grant)

Here is how you authenticate with user login and password credentials using cURL:

```
$ curl 'http://127.0.0.1:5000/auth/oauth2/token?grant_type=password&client_id=documentation&username=root&password=q'
{
    "token_type": "Bearer",
    "access_token": "oqvUpO4aKg5KgYK2EUY2HPsbOlAyEZ",
    "refresh_token": "3UTjLPlnomJPx5FvgsC2wS7GfVNrfH",
    "expires_in": 3600,
    "scope": "auth:read auth:write users:read users:write teams:read teams:write"
}
```

That is it!

Well, the above request uses query parameters to pass client ID, user login and
password which is not recommended (even discouraged) for production use since
most of the web servers logs the requested URLs in plain text and we don't want
to leak sensitive data this way.  Thus, in practice you would use form
parameters to pass credentials:

```
$ curl 'http://127.0.0.1:5000/auth/oauth2/token?grant_type=password' -F 'client_id=documentation' -F 'username=root' -F 'password=q'
```

, or even pass `client_id` as Basic HTTP Auth:

```
$ curl 'http://127.0.0.1:5000/auth/oauth2/token?grant_type=password' --user 'documentation:' -F 'username=root' -F 'password=q'
```

You grab the `access_token` and put it into `Authorization` header
to request "protected" resources:

```
$ curl --header 'Authorization: Bearer oqvUpO4aKg5KgYK2EUY2HPsbOlAyEZ' 'http://127.0.0.1:5000/api/v1/users/me'
{
    "id": 1,
    "username": "root",
    "email": "root@localhost",
    "first_name": "",
    "middle_name": "",
    "last_name": "",
    "is_active": true,
    "is_regular_user": true,
    "is_admin": true,
    "created": "2016-10-20T14:00:35.912576+00:00",
    "updated": "2016-10-20T14:00:35.912602+00:00"
}
```

Once the access token expires, you can refresh it with `refresh_token`. To do
that, OAuth2 RFC defines Refresh Token Flow (notice that there is no need to
store user credentials to do the refresh procedure):

```
$ curl 'http://127.0.0.1:5000/auth/oauth2/token?grant_type=refresh_token' --user 'documentation:' -F 'refresh_token=3UTjLPlnomJPx5FvgsC2wS7GfVNrfH'
{
    "token_type": "Bearer",
    "access_token": "FwaS90XWwBpM1sLeAytaGGTubhHaok",
    "refresh_token": "YD5Rc1FojKX1ZY9vltMSnFxhm9qpbb",
    "expires_in": 3600,
    "scope": "auth:read auth:write users:read users:write teams:read teams:write"
}
```

### Authentication with Client ID and Secret (Client Credentials Grant)

Here is how you authenticate with user login and password credentials using cURL:

```
$ curl 'http://127.0.0.1:5000/auth/oauth2/token?grant_type=client_credentials' --user 'documentation:KQ()SWK)SQK)QWSKQW(SKQ)S(QWSQW(SJ*HQ&HQW*SQ*^SSQWSGQSG'
{
    "token_type": "Bearer",
    "access_token": "oqvUpO4aKg5KgYK2EUY2HPsbOlAyEZ",
    "expires_in": 3600,
    "scope": "teams:read users:read users:write teams:write"
}
```

The same way as in the previous section, you can grab the `access_token` and
access protected resources.


## API Integration


One of the key point of using OpenAPI (Swagger) specification is that it
enables automatic code generation.
[Swagger Codegen project](https://github.com/swagger-api/swagger-codegen)
implements client library and server stub generators for over 18
programming languages! There are also many other projects with OpenAPI
specification support, so if you lack anything in the official tooling,
search for third-party solutions.

I have had a need to work with my API servers from Python and JavaScript, so
I started with Swagger Codegen Python and JavaScript generators. Very soon I
realized that most (if not all) Swagger Codegen generators lack OAuth2 support,
but other than that, the client libraries look fine (I have contributed a few
changes to Python and JavaScript generators over the time, and the nice thing
all the clients benefit from contributions into a single project). Thus,
@khorolets and I implemented hacky OAuth2 support for Python client and even
more hacky out-of-client helpers for JavaScript (hopefully, one day OAuth2
support will be contributed into the Swagger Codegen upstream).

To use Swagger Codegen, you only need a `swagger.json` file describing your API
server. You can get one by accessing http://127.0.0.1:5000/api/v1/swagger.json,
or by running an Invoke task:

```bash
$ invoke app.swagger
```

NOTE: Use stdout rediction to save the output into a file.

To further simplify the codegeneration, there is another Invoke task:

```bash
$ invoke app.swagger.codegen --language python --version 1.0.0
```

To run that, however, you will need Docker installed on your machine since we
use Swagger Codegen as a Docker image. Once that is completed, you will have a
Python client in the `clients/python/dist/` folder. The `javascript` client can
be generated just the same way. Read the generated `clients/*/dist/README.md`
to learn how to use those clients.

NOTE: As mentioned above, a slightly modified Swagger Codegen version is used
to enable OAuth2 support in Python client.

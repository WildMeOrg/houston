# Design Decisions

<!-- location meant to capture formal design decisions that don't always show themselves prominently in the code. -->

## RFC 6902 Compliance

This implementation is compatible with RFC6509 with the exception that for removal of list items via patch. This implementation supports an optional value in the patch removal operation to permit deletion of associations between modules.

## Influential documents/articles


* "[The big Picture](https://identityserver.github.io/Documentation/docsv2/overview/bigPicture.html)" -
  short yet complete idea about how the modern apps should talk.
* "[Please. Don't PATCH Like An Idiot.](http://williamdurand.fr/2014/02/14/please-do-not-patch-like-an-idiot/)"
* "[A Concise RESTful API Design Guide](https://twincl.com/programming/*6af/rest-api-design)"
* "[Best Practices for Designing a Pragmatic RESTful API](http://www.vinaysahni.com/best-practices-for-a-pragmatic-restful-api)"
* "[My take on RESTful authentication](https://facundoolano.wordpress.com/2013/12/23/my-take-on-restful-authentication/)"
* "[Is it normal design to completely decouple backend and frontend web applications and allow them to communicate with (JSON) REST API?](http://softwareengineering.stackexchange.com/questions/337467/is-it-normal-design-to-completely-decouple-backend-and-frontend-web-applications)"

# -*- coding: utf-8 -*-
"""\
Our customizations to the swagger-ui components of flask-restx.
See the template override
in ``app/templates/swagger-ui.html``for where this blueprint is used.

The flask-restx route space is named ``swaggerui``,
which should not be confused with the customizations made here.

"""
from flask import Blueprint


blueprint = Blueprint(
    'customized_swagger_ui',
    __name__,
    static_url_path='/houston/static/swagger-ui',
)


def init_app(app):
    blueprint.static_folder = app.config['SWAGGER_UI_DIST']
    app.register_blueprint(blueprint)

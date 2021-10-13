#!/bin/bash

rm -rf __pycache__
rm -rf _skbuild
rm -rf dist
rm -rf build
rm -rf htmlcov
rm -rf *.egg-info

rm -rf app/static/dist-*/
rm -rf app/static/swagger-ui/

rm -rf _swagger-ui/node_modules/
rm -rf _swagger-ui/swagger_static/
rm -rf _swagger-ui/package-lock.json

rm -rf dist.*.tar.gz

rm -rf mb_work
rm -rf wheelhouse

CLEAN_PYTHON='find . -iname __pycache__ -exec rm -rv {} \; && find . -iname *.pyc -delete && find . -iname *.pyo -delete'
bash -c "$CLEAN_PYTHON"
python setup.py clean

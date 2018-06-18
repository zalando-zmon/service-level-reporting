import importlib

from typing import Callable

from flask import request


def get_resource_handler(function_name: str) -> Callable:
    """Return our handler from ResourceHandler class"""
    module_name, klass_name, func_name = function_name.rsplit('.', 2)

    module = importlib.import_module(module_name)

    klass = getattr(module, klass_name)

    return getattr(klass, func_name)


def get_operation_name(*args, **kwargs) -> str:
    if request.endpoint:
        return '_'.join(request.endpoint.lower().replace('resource', '').split('_')[-2:])
    else:
        return 'unknown'

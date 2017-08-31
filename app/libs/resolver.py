import importlib

from typing import Callable


def get_resource_handler(function_name: str) -> Callable:
    """Return our handler from ResourceHandler class"""
    module_name, klass_name, func_name = function_name.rsplit('.', 2)

    module = importlib.import_module(module_name)

    klass = getattr(module, klass_name)

    return getattr(klass, func_name)

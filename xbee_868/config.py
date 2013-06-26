"""Configuration file module."""

from __future__ import unicode_literals

import imp

from pcore import PY3, str, bytes

from xbee_868 import constants
from xbee_868.core import Error

_CONFIG = None
"""Parsed configuration file."""


def get(name):
    """Returns the specified configuration value."""

    load()

    try:
        return _CONFIG[name]
    except KeyError:
        raise Error("{0} is missing in the configuration file {1}.",
            name.upper(), constants.CONFIG_PATH)


def load():
    """Loads the configuration file."""

    global _CONFIG
    if _CONFIG is not None:
        return

    path = constants.CONFIG_PATH

    config_module = imp.new_module("config")
    config_module.__file__ = path

    try:
        with open(path) as config_file:
            exec(compile(config_file.read(), path, "exec"), config_module.__dict__)
    except OSError as e:
        raise Error("Failed to load configuration file '{0}': {1}.", path, e.strerror)

    config = {}

    try:
        for key, value in config_module.__dict__.items():
            if key.isupper():
                config[key.lower()] = _validate_value(key, value)
    except Exception as e:
        raise Error("Error while parsing configuration file '{0}': {1}", path, e)

    _CONFIG = config


def _validate_value(key, value):
    """Validates a configuration file value."""

    valid_types = ( dict, set, list, tuple, str, bytes, int )
    if not PY3:
        valid_types += ( long, )

    value_type = type(value)

    if value_type not in valid_types:
        raise Error("{0} has an invalid value type ({1}). Allowed types: {2}.",
            key, value_type.__name__, ", ".join(t.__name__ for t in valid_types))

    if value_type is bytes:
        try:
            value = value.decode()
        except UnicodeDecodeError as e:
            raise Error("{0} has an invalid value: {1}.", key, e)
    elif value_type is dict:
        for subkey, subvalue in value.items():
            subkey = _validate_value("A {0}'s key".format(key), subkey)
            subvalue = _validate_value("{0}[{1}]".format(key, repr(subkey)), subvalue)
            value[subkey] = subvalue
    elif value_type is set:
        value = set(
            _validate_value("A {0}'s key".format(key), subvalue)
            for subvalue in value)
    elif value_type in (list, tuple):
        value = value_type(
            _validate_value("{0}[{1}]".format(key, repr(index)), subvalue)
            for index, subvalue in enumerate(value))

    return value

"""Configuration file module."""

from __future__ import unicode_literals

import imp
import re

from pcore import PY3, str, bytes

from xbee_868.core import Error

_CONFIG = None
"""Parsed configuration file."""

_CONFIG_PATH = "/etc/xbee-868-monitor.conf"
"""Configuration file path."""


def get(name):
    """Returns the specified configuration value."""

    return _get(load(), name)


def load():
    """Loads the configuration file."""

    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    path = _CONFIG_PATH

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

    _CONFIG = _validate_config(config)

    return _CONFIG


def _get(config, name):
    """Returns the specified configuration value."""

    try:
        return config[name]
    except KeyError:
        raise Error("{0} is missing in the configuration file {1}.",
            name.upper(), _CONFIG_PATH)


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
        value = _validate_dict_value(key, value)
    elif value_type in (list, tuple, set):
        value = _validate_list_like_value(key, value)

    return value


def _validate_dict_value(key, value):
    """Validates a dict value."""

    new_value = {}

    for subkey, subvalue in value.items():
        subkey = _validate_value("A {0}'s key".format(key), subkey)
        subvalue = _validate_value("{0}[{1}]".format(key, repr(subkey)), subvalue)
        new_value[subkey] = subvalue

    return new_value


def _validate_list_like_value(key, value):
    """Validates a list-like value."""

    if type(value) is set:
        return [
            _validate_value("A {0}'s key".format(key), subvalue)
            for subvalue in value
        ]
    else:
        return [
            _validate_value("{0}[{1}]".format(key, repr(index)), subvalue)
            for index, subvalue in enumerate(value)
        ]


def _validate_config(config):
    """Validates all config values."""

    for host, address in _get(config, "hosts").items():
        if type(host) is not str:
            raise Error("Invalid host name ({0}} - it must be a string.", host)

        if type(address) is not str or not re.search("^[0-9a-zA-Z]{16}$", address):
            raise Error("Invalid XBee 868 sensor address ({0}) - it must be a 64-bit hex value (string).", address)

    return config

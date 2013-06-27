"""Configuration file module."""

from __future__ import unicode_literals

import imp
import re

from pcore import PY3, str, bytes

from xbee.common.core import Error


HOSTS = set()
"""Known hosts."""

ADDRESSES = {}
"""Sensor MAC address to host mappings."""

_CONFIG_PATH = "/etc/xbee-monitor.conf"
"""Configuration file path."""


def load():
    """Loads the configuration file."""

    path = _CONFIG_PATH

    config_module = imp.new_module("config")
    config_module.__file__ = path

    try:
        with open(path) as config_file:
            exec(compile(config_file.read(), path, "exec"), config_module.__dict__)
    except OSError as e:
        raise Error("Failed to load configuration file '{0}': {1}.", path, e.strerror)

    try:
        config = {}

        for key, value in config_module.__dict__.items():
            if key.isupper():
                config[key] = _validate_value(key, value)

        _validate_config(config)
    except Exception as e:
        raise Error("Error while parsing configuration file '{0}': {1}", path, e)


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

    global HOSTS
    global ADDRESSES

    try:
        hosts = config["HOSTS"]
    except KeyError as e:
        raise Error("{0} is missing in the configuration file '{0}'.", e, _CONFIG_PATH)

    for host, address in hosts.items():
        if type(host) is not str:
            raise Error("Invalid host name ({0}} - it must be a string.", host)

        if type(address) is not str or not re.search("^[0-9a-zA-Z]{16}$", address):
            raise Error("Invalid XBee sensor address ({0}) - it must be a 64-bit hex value (string).", address)

        ADDRESSES[int(address, 16)] = host

    HOSTS.update(hosts)

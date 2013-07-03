"""Configuration file module."""

from __future__ import unicode_literals

import re

from pcore import str

import python_config

from xbee.common.core import Error


HOSTS = set()
"""Known hosts."""

ADDRESSES = {}
"""Sensor MAC address to host mappings."""


def load():
    """Loads the configuration file."""

    path = "/etc/xbee-monitor.conf"

    config = python_config.load(path)

    try:
        _validate_config(config)
    except Exception as e:
        raise Error("Error while parsing configuration file '{0}': {1}", path, e)

    global HOSTS
    global ADDRESSES

    HOSTS.update(config["hosts"])
    ADDRESSES.update(
        (int(address, 16), host) for host, address in config["hosts"].items())


def _validate_config(config):
    """Validates all configuration values."""

    if "hosts" not in config:
        raise Error("HOSTS is missing.")

    if type(config["hosts"]) is not dict:
        raise Error("HOSTS must be a dictionary.")

    for host, address in config["hosts"].items():
        if type(host) is not str:
            raise Error("Invalid host name ({0}} - it must be a string.", host)

        if type(address) is not str or not re.search("^[0-9a-zA-Z]{16}$", address):
            raise Error("Invalid XBee sensor address ({0}) - it must be a 64-bit hex value (string).", address)

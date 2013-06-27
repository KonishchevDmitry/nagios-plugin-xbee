#!/usr/bin/env python

"""Checks XBee sensor."""

from __future__ import unicode_literals

import argparse
import sys
import time

from pcore import str
from xbee.common.core import Error, LogicalError

import xbee.nagios.client
from xbee import nagios

xbee # Suppress PyFlakes warnings


_STATUS_OK = "OK"
"""OK Nagios status."""

_STATUS_WARNING = "WARNING"
"""Warning Nagios status."""

_STATUS_CRITICAL = "CRITICAL"
"""Critical Nagios status."""

_STATUS_UNKNOWN = "UNKNOWN"
"""Unknown Nagios status."""


_METRIC_TIMEOUT = 10
"""Timeout for metric values."""


class _RangeFormatError(Error):
    """Raised on range format error."""

    def __init__(self):
        super(_RangeFormatError, self).__init__("Range format error.")


def main():
    """The script's main function."""

    try:
        parser = argparse.ArgumentParser(
            description="XBee Nagios plugin")

        parser.add_argument("host", help="host")
        parser.add_argument("metric", choices=["temperature"], help="metric name")

        parser.add_argument("-w", "--warning", metavar="VALUE",
            help="warning threshold", required=True)

        parser.add_argument("-c", "--critical", metavar="VALUE",
            help="critical threshold", required=True)

        args = parser.parse_args()

        if args.metric == "temperature":
            _check_and_response(_get_temperature(args.host),
                args.warning, args.critical)
        else:
            raise LogicalError()
    except Exception as e:
        _response(_STATUS_CRITICAL if isinstance(e, Error) else _STATUS_UNKNOWN, str(e))


def _get_temperature(host):
    """Returns temperature of the specified host."""

    metrics = nagios.client.metrics(host)

    if "temperature" in metrics:
        metric = metrics["temperature"]

        if time.time() - metric["time"] < _METRIC_TIMEOUT:
            return metric["value"]
        else:
            _response(_STATUS_CRITICAL, "Outdated ({0})".format(metric["value"]))
    else:
        if nagios.client.uptime() < _METRIC_TIMEOUT:
            _response(_STATUS_UNKNOWN, "Not collected yet")
        else:
            _response(_STATUS_CRITICAL, "No data")


def _check_and_response(value, warning, critical):
    """Checks a value and responds with an appropriate code."""

    try:
        if not _check_range(critical, value):
            _response(_STATUS_CRITICAL, str(value))
        elif not _check_range(warning, value):
            _response(_STATUS_WARNING, str(value))
        else:
            _response(_STATUS_OK, str(value))
    except _RangeFormatError as e:
        _response(_STATUS_UNKNOWN, str(e))


def _check_range(spec, value):
    """Checks a value."""

    spec = spec.strip()
    if not spec:
        raise _RangeFormatError()

    inside = True

    if spec.startswith("@"):
        inside = False
        spec = spec[1:]

    if spec.find(":") < 0:
        spec = ":" + spec

    start, end = spec.split(":")
    start = _parse_spec_num(start, True)
    end = _parse_spec_num(end, False)

    if start is None and end is not None and start > end:
        raise _RangeFormatError()

    if inside:
        return (
            ( start is None or value >= start ) and
            ( end is None or value <= end )
        )
    else:
        return (
            ( start is not None and value < start ) or
            ( end is not None and value > end )
        )


def _parse_spec_num(number, is_start):
    """Parses a Nagios range number."""

    number = number.strip()

    if number:
        if number == "~" and is_start:
            return None
        else:
            try:
                return int(number)
            except ValueError:
                raise _RangeFormatError()
    else:
        if is_start:
            return 0
        else:
            return None


def _response(status, message, *args):
    """Responds in a proper way to the caller process."""

    if status == _STATUS_OK:
        code = 0
    elif status == _STATUS_WARNING:
        code = 1
    elif status == _STATUS_CRITICAL:
        code = 2
    else:
        code = 3

    print("{0}: {1}".format(status, message.format(*args) if args else message))
    sys.exit(code)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit("Error: {0}".format(e))

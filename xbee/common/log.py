"""Configures logging."""

from __future__ import unicode_literals

import logging
import logging.handlers

from xbee.common import constants


def setup(name, debug_mode=False, max_size=constants.MEGABYTE, backup_count=4):
    """Sets up the logging."""

    logging.addLevelName(logging.DEBUG,   "D")
    logging.addLevelName(logging.INFO,    "I")
    logging.addLevelName(logging.WARNING, "W")
    logging.addLevelName(logging.ERROR,   "E")

    log = logging.getLogger(__name__.split(".")[0])
    log.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    log_format = "%(asctime)s.%(msecs)03d"
    if debug_mode:
        log_format += " (%(filename)12.12s:%(lineno)04d)"
    log_format += ": %(levelname)s: %(message)s"

    if debug_mode:
        handler = logging.StreamHandler()
    else:
        handler = logging.handlers.RotatingFileHandler(
            "/var/log/{0}.log".format(name),
            maxBytes=max_size, backupCount=backup_count)

    handler.setFormatter(logging.Formatter(log_format, "%Y.%m.%d %H:%M:%S"))
    log.addHandler(handler)

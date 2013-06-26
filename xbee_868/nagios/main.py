#!/usr/bin/env python

from __future__ import unicode_literals

"""Checks XBee 868 sensor."""

import pprint

import xbee_868.nagios.client
from xbee_868 import nagios

xbee_868 # Suppress PyFlakes warnings

stats = nagios.client.uptime()
pprint.pprint(stats)

metrics = nagios.client.metrics("test")
pprint.pprint(metrics)

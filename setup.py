"""XBee monitor and Nagios plugin setup script."""

import sys
from setuptools import find_packages, setup

requires = ["pyserial", "psys", "python-config"]
if sys.version_info < (2, 7):
    requires.append("argparse")

with open("README") as readme:
    setup(
        name = "nagios-plugin-xbee",
        version = "0.1",

        license = "GPL",
        description = readme.readline().strip(),
        long_description = readme.read().strip(),
        url = "https://ghe.cloud.croc.ru/dvs/nagios-plugin-xbee",

        install_requires = requires,

        author = "Dmitry Konishchev",
        author_email = "konishchev@gmail.com",

        packages = find_packages(),
        entry_points = {
            "console_scripts": [
                "check_xbee = xbee.nagios.main:main",
                "xbee-monitor = xbee.monitor.main:main",
            ],
        },
    )

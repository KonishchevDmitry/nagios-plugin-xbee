.PHONY: build install dist srpm rpm clean

NAME := nagios-plugin-xbee
RPM_NAME := nagios-plugins-xbee
PYTHON := python

build:
	$(PYTHON) setup.py build

install:
	$(PYTHON) setup.py install --skip-build --install-scripts /usr/sbin $(INSTALL_FLAGS)

dist: clean
	$(PYTHON) setup.py sdist
	mv dist/nagios-plugin-xbee-*.tar.gz .

srpm: dist
	rpmbuild -bs --define "_sourcedir $(CURDIR)" $(RPM_NAME).spec

rpm: dist
	rpmbuild -ba --define "_sourcedir $(CURDIR)" $(RPM_NAME).spec

clean:
	rm -rf build dist $(NAME)-*.tar.gz nagios_plugin_xbee.egg-info

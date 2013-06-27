.PHONY: build install dist srpm rpm clean

NAME := nagios-plugin-xbee
RPM_NAME := nagios-plugins-xbee

PYTHON := python
DISTDIR := $(CURDIR)/dist

build:
	$(PYTHON) setup.py build

install:
	$(PYTHON) setup.py install --skip-build --install-scripts /usr/sbin $(INSTALL_FLAGS)

dist: clean
	$(PYTHON) setup.py sdist

srpm:
	rpmbuild -bs --define "_sourcedir $(DISTDIR)" $(RPM_NAME).spec

rpm: dist
	rpmbuild -ba --define "_sourcedir $(DISTDIR)" $(RPM_NAME).spec

clean:
	rm -rf build $(DISTDIR) $(NAME).egg-info *.egg

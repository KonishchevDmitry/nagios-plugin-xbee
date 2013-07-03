%define project_name nagios-plugin-xbee
%define python_less_27 %(%{__python} -c "import sys; print(int(sys.version_info < (2, 7)))")
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}

Name:    nagios-plugins-xbee
Version: 0.1
Release: 2%{?dist}
Summary: XBee monitor + Nagios plugin for checking servers' temperature

Group:   Applications/System
License: GPLv3
URL:     https://ghe.cloud.croc.ru/dvs/nagios-plugin-xbee
Source0: %project_name-%version.tar.gz
Source1: xbee-monitor.conf
Source2: xbee-monitor.upstart.conf


BuildArch:     noarch
BuildRequires: python-setuptools, make

Requires: python, pyserial, python-psys, python-config
%if %python_less_27
Requires: python-argparse
%endif

%description
XBee monitor + Nagios plugin for checking servers' temperature


%prep
%setup -n %project_name-%version -q


%build
make PYTHON=%__python


%install
[ "%buildroot" = "/" ] || rm -rf "%buildroot"

make PYTHON=%__python INSTALL_FLAGS="-O1 --root '%buildroot' --install-scripts '%_sbindir'" install

mkdir -p "%buildroot/%_libdir/nagios/plugins"
mv "%buildroot/%_sbindir/check_xbee" "%buildroot/%_libdir/nagios/plugins/"

install -p -D -m 644 "%SOURCE1" "%buildroot/%_sysconfdir/xbee-monitor.conf"
install -p -D -m 644 "%SOURCE2" "%buildroot/%_sysconfdir/init/xbee-monitor.conf"


%files
%defattr(-,root,root,-)

%python_sitelib/xbee
%python_sitelib/nagios_plugin_xbee-*.egg-info

%_sbindir/xbee-monitor
%_libdir/nagios/plugins/check_xbee

%config(noreplace) %_sysconfdir/xbee-monitor.conf
%config(noreplace) %_sysconfdir/init/xbee-monitor.conf


%clean
[ "%buildroot" = "/" ] || rm -rf "%buildroot"


%changelog
* Thu Jun 27 2013 Dmitry Konishchev <konishchev@gmail.com> - 0.1-2
- A few changes in spec file.

* Thu Jun 27 2013 Dmitry Konishchev <konishchev@gmail.com> - 0.1-1
- New package.

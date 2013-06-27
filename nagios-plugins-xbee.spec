%define project_name nagios-plugin-xbee
%define python_less_27 %(%{__python} -c "import sys; print(int(sys.version_info < (2, 7)))")
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}

Name:    nagios-plugins-xbee
Version: 0.1
Release: 1%{?dist}
Summary: XBee monitor + Nagios plugin for checking servers' temperature

Group:   Applications/System
License: GPLv3
URL:     https://ghe.cloud.croc.ru/dvs/nagios-plugin-xbee
Source:  %{project_name}-%{version}.tar.gz

BuildArch:     noarch
BuildRequires: python-setuptools, make

Requires: python
Requires: pyserial
%if %python_less_27
Requires: python-argparse
%endif

%description
XBee monitor + Nagios plugin for checking servers' temperature


%prep
%setup -n %{project_name}-%{version} -q


%build
make PYTHON=%{__python}


%install
[ %buildroot = "/" ] || rm -rf %buildroot

make PYTHON=%{__python} INSTALL_FLAGS="-O1 --root '%buildroot' --install-scripts '%_sbindir'" install
mkdir -p %buildroot/%_libdir/nagios/plugins
mv %buildroot/%_sbindir/check_xbee %buildroot/%_libdir/nagios/plugins/


%files
%defattr(-,root,root,-)
%{python_sitelib}/*
%_sbindir/xbee-monitor
%_libdir/nagios/plugins/check_xbee


%clean
[ %buildroot = "/" ] || rm -rf %buildroot


%changelog
* Thu Jun 27 2013 Dmitry Konishchev <konishchev@gmail.com> - 0.1-1
- New package.

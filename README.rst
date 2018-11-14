DEPRECATED
==========

Transifex had stopped opensource development of their server software. The last release was Jan 8 2012.
This project is now officially deprecated.

Description
===========

.. image:: https://secure.travis-ci.org/rvanlaar/easy-transifex.png?branch=master
   :target: http://travis-ci.org/rvanlaar/easy-transifex/


This is a buildout configuration to install 
`Transifex <http://www.transifex.net>`_ the easy way.
Mainly for my employer `Nelen en Schuurmans <http://www.nelen-schuurmans.nl>`_.

Transifex is a translation service and software.
The Transifex is a bit hard to install and configure.
This buildout can be used to ease the pain.

It includes gunicorn and uses solr as the haystack backend.

There is probably some configuration needed for your specific installation
case. easy-transifex is meant to be configurable in an easy way.

Transifex is included because the tarball on pypi is broken with regards
to the staticfiles.

Installation
============

The following packages are needed::
  
  sudo apt-get install git python-dev openjdk-6-jre-headless gettext intltool

To install transifex run::

  python bootstrap.py
  bin/buildout
  bin/supervisord

Configuration
=============

The configuration for easy-transifex is located in 
``easy_transifex/settings.py``.
This overrides Transifex defaults settings.

By default Transifex uses a sqlite database. 
To change the default database and other configuration options read
the `Django settings documentation <https://docs.djangoproject.com/en/dev/topics/settings/>`_.

Read ``parts/ommelette/transifex/settings/*.conf`` to see which settings
are used and can be overridden.

Static Media
============

Make sure to serve the static media via Apache or Nginx.
An Nginx configuration file is included.

Description
===========

This is a buildout configuration to install transifex the easy way.
Mainly for my employer Nelen en Schuurmans.

Transifex is a translation service and software.
The Transifex is a bit hard to install and configure.
This buildout can be used to ease the pain.

It includes gunicorn and uses solr as the haystack backend.

There is probably some configuration needed for your specific installation
case. nens-transifex is meant to be configurable in an easy way.

Installation
============

To install transifex run::

  python bootstrap.py
  bin/buildout
  bin/supervisord

Configuration
=============

Read ``parts/ommelette/transifex/settings/*.conf`` to see which settings
are used and can be overridden in nens_transifex.settings.

Static Media
============

Make sure to serve the static media via Apache or Nginx.

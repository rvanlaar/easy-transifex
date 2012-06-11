# -*- coding: utf-8 -*-

"""
Mozilla properties file handler/compiler
"""
import os, re
from django.utils.hashcompat import md5_constructor

from transifex.txcommon.log import logger
from transifex.resources.models import SourceEntity
from transifex.resources.formats.utils.decorators import *
from transifex.resources.formats.utils.hash_tag import hash_tag
from transifex.resources.formats.core import Handler, ParseError, CompileError
from transifex.resources.formats.resource_collections import StringSet, \
        GenericTranslation
from transifex.resources.formats.properties import PropertiesHandler, \
        PropertiesParseError, PropertiesCompileError

class MozillaPropertiesParseError(PropertiesParseError):
    pass

class MozillaPropertiesCompileError(PropertiesCompileError):
    pass

class MozillaPropertiesHandler(PropertiesHandler):
    name = "Mozilla *.PROPERTIES file handler"
    format = "Mozilla PROPERTIES (*.properties)"
    method_name = 'MOZILLAPROPERTIES'
    format_encoding = 'UTF-8'

    HandlerParseError = MozillaPropertiesParseError
    HandlerCompileError = MozillaPropertiesCompileError

    def _escape(self, s):
        """
        Escape special characters in Mozilla properties files.

        Java escapes the '=' and ':' in the value
        string with backslashes in the store method.
        Mozilla escapes only '\\'.
        """
        return s.replace('\\', '\\\\')

    def _unescape(self, value):
        """Reverse the escape of special characters."""
        return value.replace('\\\\', '\\')

    def _replace_translation(self, original, replacement, text):
        return text.replace(
            original, self._pseudo_decorate(self._escape(replacement))
        )



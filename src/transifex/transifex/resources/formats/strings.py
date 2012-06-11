# -*- coding: utf-8 -*-

"""
Apple strings file handler/compiler
"""
import codecs, os, re, chardet

from transifex.txcommon.log import logger
from transifex.resources.models import SourceEntity, Template
from transifex.resources.formats.utils.decorators import *
from transifex.resources.formats.utils.hash_tag import hash_tag
from transifex.resources.formats.core import Handler, ParseError, CompileError
from transifex.resources.formats.resource_collections import StringSet, \
        GenericTranslation


class StringsParseError(ParseError):
    pass


class StringsCompileError(ParseError):
    pass


class AppleStringsHandler(Handler):
    """
    Handler for Apple STRINGS translation files.

    Apple strings files *must* be encoded in cls.ENCODING encoding.
    """

    name = "Apple *.STRINGS file handler"
    format = "Apple STRINGS (*.strings)"
    method_name = 'STRINGS'
    format_encoding = 'UTF-16'

    HandlerParseError = StringsParseError
    HandlerCompileError = StringsCompileError

    def _post_compile(self, *args, **kwargs):
        self.compiled_template = self.compiled_template.decode(
                self.format_encoding).encode(self.format_encoding)

    def _escape(self, s):
        return s.replace('"', '\\"')

    def _unescape(self, s):
        return s.replace('\\"', '"')

    def _get_content(self, filename=None, content=None):
        """Try decoding a file with UTF-8, too."""
        try:
            return super(AppleStringsHandler, self)._get_content(filename, content)
        except UnicodeError, e:
            return self._get_content_from_file(filename, self.default_encoding)

    def _get_content_from_file(self, filename, encoding):
        f = open(filename, 'r')
        try:
            content = f.read()
            if chardet.detect(content)['encoding'].startswith(self.format_encoding):
                #f = f.decode(self.format_encoding)
                encoding = self.format_encoding
            else:
                #f = f.decode(self.default_encoding)
                encoding = 'utf-8'
            f.close()
            f = codecs.open(filename, 'r', encoding=encoding)
            return f.read()
        except IOError, e:
            logger.warning(
                "Error opening file %s with encoding %s: %s" %\
                    (filename, self.format_encoding, e.message),
                exc_info=True
            )
            raise FormatError(e.message)
        except Exception, e:
            logger.error("Unhandled exception: %s" % e.message, exc_info=True)
            raise
        finally:
            f.close()

    def _parse(self, is_source, lang_rules):
        """Parse an apple .strings file and create a stringset with
        all entries in the file.

        See
        http://developer.apple.com/library/mac/#documentation/MacOSX/Conceptual/BPInternational/Articles/StringsFiles.html
        for details.
        """
        resource = self.resource
        context = ""
        f = self.content
        p = re.compile(r'(?P<line>(("(?P<key>[^"\\]*(?:\\.[^"\\]*)*)")|(?P<property>\w+))\s*=\s*"(?P<value>[^"\\]*(?:\\.[^"\\]*)*)"\s*;)', re.U)
        c = re.compile(r'\s*/\*(.|\s)*?\*/\s*', re.U)
        ws = re.compile(r'\s+', re.U)
        buf = u""
        end=0
        start = 0
        for i in p.finditer(f):
            start = i.start()
            end_ = i.end()
            line = i.group('line')
            key = i.group('key')
            if not key:
                key = i.group('property')
            value = i.group('value')
            while end < start:
                m = c.match(f, end, start) or ws.match(f, end, start)
                if not m or m.start() != end:
                    raise StringsParseError("Invalid syntax.")
                if is_source:
                    buf += f[end:m.end()]
                end = m.end()
            end = end_
            if is_source:
                if not value.strip():
                    buf += line
                    continue
                else:
                    line = f[start:end]
                    buf += line[0:i.start('value')-start]
                    buf += re.sub(
                        re.escape(value),
                        "%(hash)s_tr" % {'hash': hash_tag(key, context)},
                        line[i.start('value')-start:i.end('value')-start]
                    )
                    buf += line[i.end('value')-start:]
            elif not SourceEntity.objects.filter(resource=resource, string=key).exists() or not value.strip():
                # ignore keys with no translation
                continue
            self.stringset.strings.append(GenericTranslation(key,
                self._unescape(value), rule=5, context=context,
                pluralized=False, fuzzy=False,
                obsolete=False))
        while len(f[end:]):
            m = c.match(f, end) or ws.match(f, end)
            if not m or m.start() != end:
                raise StringsParseError("Invalid syntax.")
            if is_source:
                buf += f[end:m.end()]
            end = m.end()
            if end == 0:
                break
        return buf


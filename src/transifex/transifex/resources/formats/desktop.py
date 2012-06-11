# -*- coding: utf-8 -*-
"""
Handler for .desktop files.
"""

import re
import codecs
from django.utils.translation import ugettext as _
from collections import defaultdict
from transifex.txcommon.log import logger
from transifex.languages.models import Language
from transifex.resources.models import Translation, Template
from transifex.resources.formats.utils.decorators import *
from transifex.resources.formats.utils.hash_tag import hash_tag
from transifex.resources.formats.core import Handler, ParseError, CompileError
from transifex.resources.formats.resource_collections import StringSet, \
        GenericTranslation


class DesktopParseError(ParseError):
    pass


class DesktopCompileError(CompileError):
    pass


class DesktopHandler(Handler):
    """Class for .desktop files.

    See http://standards.freedesktop.org/desktop-entry-spec/latest/.
    """

    name = ".desktop file handler"
    format = ".desktop (*.desktop)"
    method_name = 'DESKTOP'

    HandlerParseError = DesktopParseError
    handlerCompileError = DesktopCompileError

    comment_chars = ('#', )
    delimiter = '='
    # We are only intrested in localestrings, see
    # http://standards.freedesktop.org/desktop-entry-spec/latest/ar01s05.html
    localized_keys = ['Name', 'GenericName', 'Comment', 'Icon', ]

    def _apply_translation(self, source, trans, content):
        return ''.join([
                content, string.string.encode(self.default_encoding),
                '[', language.code, ']=',
                trans.string.encode(self.default_encoding), '\n',
            ])

    def _compile_translation(self, content, language, *args, **kwargs):
        """Compile a translation file."""
        return super(Desktophandler, self)._compile(content, language)

    def _compile_source(self, content, *args, **kwargs):
        """Compile a source file.

        Add all translations to the file.
        """
        all_languages = set(self.resource.available_languages_without_teams)
        source_language = set([self.resource.source_language, ])
        translated_to = all_languages - source_language
        content = ''
        for language in translated_to:
            content = self._compile_translation(content, language)
        return content

    def _is_comment_line(self, line):
        """Return True, if the line is a comment."""
        return line[0] in self.comment_chars

    def _is_empty_line(self, line):
        """Return True, if the line is empty."""
        return re.match('\s*$', line) is not None

    def _is_group_header_line(self, line):
        """Return True, if this is a group header."""
        return line[0] == '[' and line[-1] == ']'

    def _get_elements(self, line):
        """Get the key and the value of a line."""
        return line.split(self.delimiter, 1)

    def _get_lang_code(self, locale):
        """Return the lang_code part from a locale string.

        locale is of the form lang_COUNTRY.ENCODING@MODIFIER
        (in general)
        We care for lang_COUNTRY part.
        """
        modifier = ''
        at_pos = locale.find('@')
        if at_pos != -1:
            modifier = locale[at_pos:]
            locale = locale[:at_pos]
        dot_pos = locale.find('.')
        if dot_pos != -1:
            locale = locale[:dot_pos]
        return ''.join([locale, modifier])

    def _get_locale(self, key):
        """Get the locale part of a key."""
        return key[key.find('[') + 1:-1]

    def _should_skip(self, line):
        """Return True, if we should skip the line.

        This is the case if the line is an empty line, a comment or
        a group header line.

        """
        return self._is_empty_line(line) or\
                self._is_comment_line(line) or\
                self._is_group_header_line(line) or\
                self.delimiter not in line

    def _parse(self, is_source=False, lang_rules=None):
        """
        Parse a .desktop file.

        If it is a source file, the file will have every translation in it.
        Otherwise, it will have just the translation for the specific language.
        """
        # entries is a dictionary with the entry keys in the file
        entries = defaultdict(list)

        template = u''
        for line in self._iter_by_line(self.content):
            if self._should_skip(line) :
                template += line + "\n"
                continue
            key, value = self._get_elements(line)
            if '[' in key:
                # this is a translation
                # find the language of it
                # Skip the template
                actual_key = key[:key.find('[')]
                locale = self._get_locale(key)
                lang_code = self._get_lang_code(locale)
                if lang_code == "x-test":
                    template += line + "\n"
                    continue
                try:
                    lang = Language.objects.by_code_or_alias(lang_code)
                except Language.DoesNotExist, e:
                    msg = _("Unknown language specified: %s" % lang_code)
                    logger.warning(msg)
                    raise DesktopParseError(msg)
            else:
                lang = False    # Use False to mark source string
                actual_key = key
                template += line + "\n"

            if actual_key not in self.localized_keys:
                # Translate only standard localestring keys
                continue
            entries[actual_key].append((value, lang))

        context = ""
        template += '\n# Translations\n'

        for key, value in entries.iteritems():
            for translation, language in value:
                if is_source and language:
                    # Skip other languages when parsing a source file
                    continue
                elif not is_source and language != self.language:
                    # Skip other languages than the one the parsing is for
                    continue
                self._add_translation_string(key, translation, context=context)

        return template

    def _compile(self, content, language):
        if language == self.resource.source_language:
            return self._compile_source(content, language)
        else:
            return self._compile_translation(content, language)

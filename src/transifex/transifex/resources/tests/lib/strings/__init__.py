import os
import re
import unittest
from transifex.txcommon.tests.base import BaseTestCase
from transifex.languages.models import Language
from transifex.resources.models import *
from transifex.resources.formats.strings import AppleStringsHandler, \
        StringsParseError

from transifex.addons.suggestions.models import Suggestion

class TestAppleStrings(BaseTestCase):
    """Suite of tests for the strings file lib."""

    def setUp(self):
        super(TestAppleStrings, self).setUp()
        self.resource.i18n_method = 'STRINGS'
        self.resource.save()

    def test_regex(self):
        """Test regex used in the parser"""
        p = re.compile(r'(?P<line>(("(?P<key>[^"\\]*(?:\\.[^"\\]*)*)")|(?P<property>\w+))\s*=\s*"(?P<value>[^"\\]*(?:\\.[^"\\]*)*)"\s*;)', re.U)
        c = re.compile(r'\s*/\*(.|\s)*?\*/\s*', re.U)
        ws = re.compile(r'\s+', re.U)

        good_lines = [
                      '"key" = "value";',
                      'key = "value";',
                      '"key"\t=\n\t"value"  \n ;',
                      '"key with \\" double quote"\n=\t"value with \\" double quote";',
                      '''"key with ' single quote"\t=\n"Value with ' single quote";''',
                      ]
        bad_lines = [
                     '"key = "value";',
                     '"key" = "value"',
                     '"key" foo" = "value \"foo";',
                     '"key" = "value " foo";',
                     '"key\' = "value";',
                     'key foo = "value";',
                     'key = value',
                     ]
        good_comment = '/* foo\n\tfoo\'"@ $***/'
        bad_comments = ['//foo\n',
                        '/*foo*',
                        '*foo*',
                        ]
        whitespaces = ['\t','\n','\r', ' ']

        for i in good_lines:
            self.assertTrue(p.match(i))

        for i in bad_lines:
            self.assertFalse(p.match(i))

        self.assertTrue(c.match(good_comment))

        for i in bad_comments:
            self.assertFalse(c.match(i))

        for i in whitespaces:
            self.assertTrue(ws.match(i))

    def test_strings_parser(self):
        """STRINGS parsing tests."""
        # Parsing STRINGS content
        files = ['test_utf_16.strings', 'test_utf_8.strings',]
        for i in range(1, 9):
            files.append('bad%d.strings'%i)
        for file_ in files:
            handler = AppleStringsHandler()
            handler.bind_file(os.path.join(os.path.dirname(__file__), file_))
            handler.set_language(self.resource.source_language)
            if file_ in ['test_utf_16.strings', 'test_utf_8.strings']:
                handler.parse_file(is_source=True)
                self.stringset = handler.stringset
                entities = 0
                translations = 0
                for s in self.stringset.strings:
                    entities += 1
                    if s.translation.strip() != '':
                        translations += 1
                self.assertEqual(entities, 4)
                self.assertEqual(translations, 4)
            else:
                self.assertRaises(StringsParseError, handler.parse_file, is_source=True)

    def test_strings_save2db(self):
        """Test creating source strings from a STRINGS file works"""
        source_file = 'test_utf_16.strings'
        trans_file = 'test_translation.strings'
        handler = AppleStringsHandler()
        handler.bind_file(os.path.join(os.path.dirname(__file__), source_file))

        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)

        r = self.resource
        l = r.source_language

        handler.bind_resource(r)

        handler.save2db(is_source=True)

        # Check that all 4 entities are created in the db
        self.assertEqual( SourceEntity.objects.filter(resource=r).count(), 4)

        # Check that all source translations are there
        self.assertEqual(
            len(Translation.objects.filter(source_entity__resource=r, language=l)), 4
        )

        # Import and save the finish translation
        handler.bind_file(os.path.join(os.path.dirname(__file__), trans_file))
        l = self.language_ar
        handler.set_language(l)
        handler.parse_file()

        entities = 0
        translations = 0
        for s in handler.stringset.strings:
            entities += 1
            if s.translation.strip() != '':
                translations += 1

        self.assertEqual(entities, 2)
        self.assertEqual(translations, 2)

        handler.save2db()
        # Check if all Source strings are untouched
        self.assertEqual(SourceEntity.objects.filter(resource=r).count(), 4)
        # Check that all translations are there
        self.assertEqual(len(Translation.objects.filter(source_entity__resource=r,
            language=l)), 2)

        r.delete()


# -*- coding: utf-8 -*-

import os, chardet
import unittest
from transifex.txcommon.tests.base import BaseTestCase
from transifex.languages.models import Language
from transifex.resources.models import *
from transifex.resources.formats.mozillaproperties import  MozillaPropertiesHandler

from transifex.addons.suggestions.models import Suggestion

class TestMozillaProperties(BaseTestCase):
    """Suite of tests for the propertiesfile lib."""

    def setUp(self):
        super(TestMozillaProperties, self).setUp()
        self.resource.i18n_method = 'MOZILLA_PROPERTIES'
        self.resource.save()

    def test_escaped(self):
        j = MozillaPropertiesHandler()
        self.assertFalse(j._is_escaped(r"es blah", 2))
        self.assertTrue(j._is_escaped(r"e\ blah", 2))
        self.assertFalse(j._is_escaped(r"\\ blah", 2))
        self.assertTrue(j._is_escaped(r"e\\\ blah", 4))

    def test_accept(self):
        parser = MozillaPropertiesHandler()
        self.assertTrue(parser.accepts('MOZILLAPROPERTIES'))

    def test_split(self):
        j = MozillaPropertiesHandler()
        res = j._split("asd sadsf")
        self.assertEqual(res[0], "asd")
        self.assertEqual(res[1], "sadsf")
        res = j._split("asd=sadsf")
        self.assertEqual(res[0], "asd")
        self.assertEqual(res[1], "sadsf")
        res = j._split("asd:sadsf")
        self.assertEqual(res[0], "asd")
        self.assertEqual(res[1], "sadsf")
        res = j._split("asd\tsadsf")
        self.assertEqual(res[0], "asd")
        self.assertEqual(res[1], "sadsf")
        res = j._split(r"asd\ =sadsf")
        self.assertEqual(res[0], "asd\ ")
        self.assertEqual(res[1], "sadsf")
        res = j._split(r"asd = sadsf")
        self.assertEqual(res[0], "asd")
        self.assertEqual(res[1], "sadsf")
        res = j._split(r"asd\\=sadsf")
        self.assertEqual(res[0], r"asd\\")
        self.assertEqual(res[1], "sadsf")
        res = j._split(r"asd\\\=sadsf")
        self.assertEqual(res[0], r"asd\\\=sadsf")
        self.assertEqual(res[1], None)
        res = j._split(r"asd\\\\=sadsf")
        self.assertEqual(res[0], r"asd\\\\")
        self.assertEqual(res[1], "sadsf")
        res = j._split(r"Key21\:WithColon : Value21")
        self.assertEqual(res[0], r"Key21\:WithColon")
        self.assertEqual(res[1], "Value21")

    def test_properties_parser(self):
        """PROPERTIES file tests."""
        # Parsing PROPERTIES file
        handler = MozillaPropertiesHandler(
            os.path.join(os.path.dirname(__file__), 'complex.properties')
        )

        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)
        self.stringset = handler.stringset
        entities = 0
        translations = 0
        for s in self.stringset.strings:
            entities += 1
            if s.translation.strip() != '':
                translations += 1

        # Asserting number of entities - PROPERTIES file has 25 entries.
        # we ignore keys without a value
        self.assertEqual(entities, 25)
        self.assertEqual(translations, 25)

    def test_properties_save2db(self, delete=True):
        """Test creating source strings from a PROPERTIES file works"""
        handler = MozillaPropertiesHandler(
            os.path.join(os.path.dirname(__file__), 'complex.properties')
        )

        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)

        r = self.resource
        l = self.resource.source_language

        handler.bind_resource(r)

        handler.save2db(is_source=True)

        # Check that all 25 entities are created in the db
        self.assertEqual( SourceEntity.objects.filter(resource=r).count(), 25)

        # Check that all source translations are there
        self.assertEqual(
            len(Translation.objects.filter(source_entity__resource=r, language=l)), 25
        )

        # Import and save the finish translation
        handler.bind_file(os.path.join(os.path.dirname(__file__),'complex_hi_IN.properties'))
        l = Language.objects.get(code='hi_IN')
        handler.set_language(l)
        handler.parse_file()

        entities = 0
        translations = 0
        for s in handler.stringset.strings:
            entities += 1
            if s.translation.strip() != '':
                translations += 1

        self.assertEqual(entities, 23)
        self.assertEqual(translations, 23)

        handler.save2db()
        # Check if all Source strings are untouched
        self.assertEqual(SourceEntity.objects.filter(resource=r).count(), 25)
        # Check that all translations are there
        self.assertEqual(len(Translation.objects.filter(source_entity__resource=r,
            language=l)), 23)

        if delete:
            r.delete()
        else:
            return r

    def test_properties_compile(self):
        """Test compiling translations for PROPERTIES files"""

        self.test_properties_save2db(delete=False)
        handler = MozillaPropertiesHandler()
        handler.bind_resource(self.resource)
        handler.set_language(self.resource.source_language)
        old_template = handler.compiled_template
        handler.compile()
        self.assertNotEqual(old_template, handler.compiled_template)

        handler.set_language(Language.objects.get(code='hi_IN'))
        old_template = handler.compiled_template
        handler.compile()
        self.assertNotEqual(old_template, handler.compiled_template)

        #Cleanup
        self.resource.delete()



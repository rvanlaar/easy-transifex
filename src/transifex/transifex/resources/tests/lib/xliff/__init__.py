import os
import re
import unittest
from transifex.txcommon.tests.base import BaseTestCase
from transifex.languages.models import Language
from transifex.resources.models import *
from transifex.resources.formats.xliff import XliffHandler

class TestXliffParser(BaseTestCase):
    """Suite of tests for XLIFF file lib."""

    def setUp(self):
        super(TestXliffParser, self).setUp()
        self.resource.i18n_method = "XLIFF"
        self.resource.save()
        self.resource_new = Resource.objects.create(
            slug="resource_new", name="Resource New", project=self.project,
            source_language=self.language_en, i18n_type='PO'
        )
        self.resource_new.i18n_method = "XLIFF"
        self.resource_new.save()

    def test_accept(self):
        """Test whether parser accepts XLIFF file format"""
        parser = XliffHandler()
        self.assertTrue(parser.accepts("XLIFF"))

    def test_xliff_parser(self):
        """XLIFF parsing tests."""
        # Parsing XLIFF content
        files = ['example.xlf','example.xml']
        for file in files:
            handler = XliffHandler(os.path.join(os.path.dirname(__file__), file))
            handler.set_language(self.resource.source_language)
            handler.parse_file(is_source=True)
            self.stringset = handler.stringset
            entities = 0
            translations = 0
            for s in self.stringset.strings:
                entities += 1
                if s.translation.strip() != '':
                    translations += 1
            self.assertEqual(entities, 7)
            self.assertEqual(translations, 7)

    def test_xliff_save2db(self, delete=True):
        """Test creating source strings from a XLIFF file"""
        source_file = 'example.xlf'
        trans_file = 'translation_ar.xlf'
        handler = XliffHandler(os.path.join(os.path.dirname(__file__), source_file))
        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)
        handler.bind_resource(self.resource)
        handler.save2db(is_source=True)
        r = self.resource
        l = r.source_language
        # Check that all entities with not null are created in the db
        self.assertEqual( SourceEntity.objects.filter(resource=r).count(), 6)

        # Check that all source translations are there
        self.assertEqual(
            len(Translation.objects.filter(source_entity__resource=r, language=l)), 7
        )

        # Import and save the finish translation
        l = self.language_ar
        handler.bind_file(os.path.join(os.path.dirname(__file__), trans_file))
        handler.set_language(l)
        handler.parse_file()

        entities = 0
        translations = 0
        for s in handler.stringset.strings:
            entities += 1
            if s.translation.strip() != '':
                translations += 1
        self.assertEqual(entities, 7)
        self.assertEqual(translations, 7)

        handler.save2db()
        # Check if all Source strings are untouched
        self.assertEqual(SourceEntity.objects.filter(resource=r).count(), 6)
        # Check that all translations are there
        self.assertEqual(len(Translation.objects.filter(source_entity__resource=r,
            language=l)), 7)

        #Save updated translation file
        handler.bind_file(os.path.join(os.path.dirname(__file__), 'translation_ar_updated.xlf'))
        handler.set_language(l)
        handler.parse_file()

        entities = 0
        translations = 0
        for s in handler.stringset.strings:
            entities += 1
            if s.translation.strip() != '':
                translations += 1
        self.assertEqual(entities, 9)
        self.assertEqual(translations, 9)

        handler.save2db()
        # Check if all Source strings are untouched
        self.assertEqual(SourceEntity.objects.filter(resource=r).count(), 6)
        # Check that all translations are there
        self.assertEqual(len(Translation.objects.filter(source_entity__resource=r,
            language=l)), 9)

        #Create another resource with files with no plural data
        r1 = self.resource_new
        l = r1.source_language
        source_file = 'example1.xlf'
        trans_file = 'translation1_ar.xlf'
        handler = XliffHandler(os.path.join(os.path.dirname(__file__), source_file))
        handler.set_language(l)
        handler.parse_file(is_source=True)
        handler.bind_resource(r1)
        handler.save2db(is_source=True)
        # Check that all entities with not null are created in the db
        self.assertEqual(SourceEntity.objects.filter(resource=r1).count(), 5)

        #Check that all source translations are there
        self.assertEqual(
            len(Translation.objects.filter(source_entity__resource=r1, language=l)),5
        )

        # Import and save the finished translations
        l = self.language_ar
        handler.bind_file(os.path.join(os.path.dirname(__file__), trans_file))
        handler.set_language(l)
        handler.parse_file(l)

        entities = 0
        translations = 0
        for s in handler.stringset.strings:
            entities += 1
            if s.translation.strip() != '':
                translations += 1
        self.assertEqual(entities, 5)
        self.assertEqual(translations, 5)

        handler.save2db()
        #Check if all source strings are untouched
        self.assertEqual(SourceEntity.objects.filter(resource=r1).count(), 5)
        #Check that all translations are there
        self.assertEqual(len(Translation.objects.filter(source_entity__resource=r1,
            language=l)), 5)

        if delete:
            r.delete()
            r1.delete()

    def test_xliff_compile(self):
        """Test compiling translations for XLIFF files"""

        self.test_xliff_save2db(delete=False)
        handler = XliffHandler()
        handler.bind_resource(self.resource)
        handler.set_language(self.resource.source_language)
        old_template = handler.compiled_template
        handler.compile()
        self.assertNotEqual(old_template, handler.compiled_template)

        handler.set_language(self.language_ar)
        old_template = handler.compiled_template
        handler.compile()
        self.assertNotEqual(old_template, handler.compiled_template)

        handler.bind_resource(self.resource_new)
        handler.set_language(self.resource_new.source_language)
        old_template = handler.compiled_template
        handler.compile()
        self.assertNotEqual(old_template, handler.compiled_template)

        handler.set_language(self.language_ar)
        old_template = handler.compiled_template
        handler.compile()
        self.assertNotEqual(old_template, handler.compiled_template)

        #Cleanup
        self.resource.delete()
        self.resource_new.delete()



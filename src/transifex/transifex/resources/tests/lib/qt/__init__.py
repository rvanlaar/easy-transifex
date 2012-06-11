import os
import unittest
import xml.dom.minidom
from xml.etree.ElementTree import parse
from transifex.languages.models import Language
from transifex.resources.models import *
from transifex.resources.formats.qt import LinguistHandler, \
        _getElementByTagName, _getText
from transifex.addons.suggestions.models import Suggestion
from transifex.resources.tests.lib.base import FormatsBaseTestCase


class TestQtFile(FormatsBaseTestCase):
    """Suite of tests for the qt lib."""

    def setUp(self):
        super(TestQtFile, self).setUp()
        self.resource.i18n_method = 'QT'
        self.resource.save()

    def test_problematic_file(self):
        filename = 'problem.ts'
        handler = LinguistHandler(os.path.join(
                os.path.dirname(__file__),
                filename
        ))
        handler.set_language(self.resource.source_language)
        handler.parse_file(True)
        # OK, it doesn't raise any Exceptions

    def test_qt_parser(self):
        """TS file tests."""
        path = os.path.join(os.path.split(__file__)[0], 'en.ts')
        # Parsing POT file
        handler = LinguistHandler(path)

        # Create a dict of source_strings - translations
        root = parse(path).getroot()
        messages = {}
        for context in list(root):
            for message in list(context):
                children = list(message)
                if not children:
                    continue
                source = message.find('source').text
                translation = message.find('translation').text
                messages[source] = translation or source

        handler.set_language(self.resource.source_language)
        handler.parse_file(True)
        self.stringset = handler.stringset
        entities = 0

        for s in self.stringset.strings:
            # Testing if source entity and translation are the same
            if not s.pluralized:
                self.assertEqual(messages[s.source_entity], s.translation)

            # Testing plural number
            if s.source_entity == '%n FILES PROCESSED.':
                self.assertTrue(s.rule in [1, 5])

            # Counting number of entities
            if s.rule == 5:
                entities += 1

        # Asserting number of entities - Qt file has 43 entries +1 plural.
        self.assertEqual(entities, 43)

    def test_qt_parser_fi(self):
        """Tests for fi Qt file."""
        handler = LinguistHandler('%s/fi.ts' %
            os.path.split(__file__)[0])

        handler.set_language(self.language)
        handler.parse_file()
        self.stringset = handler.stringset

        nplurals = 0
        entities = 0

        for s in self.stringset.strings:

            # Testing plural number
            if s.source_entity == '%n FILES PROCESSED.' and s.pluralized:
                nplurals += 1

            entities += 1

        # Asserting nplurals based on the number of plurals of the
        # '%n FILES PROCESSED.' entity - fi has nplurals=2
        self.assertEqual(nplurals, 2)

        # Asserting number of entities - Qt file has 43 entries.
        self.assertEqual(entities, 44)

    def test_qt_save2db(self):
        """Test creating source strings from a Qt file works"""
        handler = LinguistHandler(
            os.path.join(os.path.split(__file__)[0], 'en.ts')
        )

        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)

        r = self.resource
        l = self.resource.source_language

        handler.bind_resource(r)

        handler.save2db(is_source=True)

        # Check that all 43 entities are created in the db
        self.assertEqual(SourceEntity.objects.filter(resource=r).count(), 43)

        # Check that all source translations are there
        self.assertEqual(
            len(Translation.objects.filter(resource=r, language=l)), 44
        )

        # Import and save the finish translation
        handler.bind_file('%s/fi.ts' % os.path.split(__file__)[0])
        l = Language.objects.by_code_or_alias('fi')
        handler.set_language(l)
        handler.parse_file()

        handler.save2db()

        # Check if all Source strings are untouched
        self.assertEqual(SourceEntity.objects.filter(resource=r).count(), 43)

        # Check that all translations are there
        self.assertEqual(
            len(Translation.objects.filter(resource=r, language=l)), 44
        )

        r.delete()

    def test_convert_to_suggestions(self):
        """Test convert to suggestions when importing new source files"""

        # Empty our resource
        SourceEntity.objects.filter(resource=self.resource).delete()

        # Make sure that we have no suggestions to begin with
        self.assertEqual(Suggestion.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 0)

        # Import file with two senteces
        handler = LinguistHandler('%s/suggestions/en.ts' %
            os.path.split(__file__)[0])
        handler.bind_resource(self.resource)
        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)
        handler.save2db(is_source=True)

        # import pt_BR translation
        handler = LinguistHandler('%s/suggestions/pt_BR.ts' %
            os.path.split(__file__)[0])
        handler.bind_resource(self.resource)
        handler.set_language(self.language)
        handler.parse_file()
        handler.save2db()

        # Make sure that we have all translations in the db
        self.assertEqual(Translation.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 8)

        # import source with small modifications
        handler = LinguistHandler('%s/suggestions/en-diff.ts' %
            os.path.split(__file__)[0])
        handler.bind_resource(self.resource)
        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)
        handler.save2db(is_source=True)

        # Make sure that all suggestions were added
        self.assertEqual(Suggestion.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 1)

        # Make sure one string is now untranslated
        self.assertEqual(Translation.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 4)

    def test_special_characters(self):
        """Test that escaping/unescaping happens correctly"""

        unescaped_string = "& < > \" '"
        escaped_string = "&amp; &lt; &gt; &quot; &apos;"

        # Empty our resource
        SourceEntity.objects.filter(resource=self.resource).delete()

        # Make sure that we have no suggestions to begin with
        self.assertEqual(Suggestion.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 0)

        # Import file with two senteces
        handler = LinguistHandler('%s/special_characters/en.ts' %
            os.path.split(__file__)[0])
        handler.bind_resource(self.resource)
        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)
        handler.save2db(is_source=True)

        # Make sure that we have all sources in the db
        self.assertEqual(SourceEntity.objects.filter(
            resource=self.resource).values('id').count(), 1)

        # Make sure that we have all translations in the db
        self.assertEqual(Translation.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(),1)

        source = SourceEntity.objects.filter(resource=self.resource)[0]
        translation = Translation.objects.get(source_entity=source)

        self.assertEqual(source.string, unescaped_string)
        self.assertEqual(translation.string, unescaped_string)

        handler.compile()

        self.assertTrue(escaped_string in handler.compiled_template)
        self.assertFalse(unescaped_string in handler.compiled_template)

    def test_unfinished_entries(self):
        """Test that unfinished entries are not added in the database"""
        # Empty our resource
        SourceEntity.objects.filter(resource=self.resource).delete()

        # Make sure that we have no translations to begin with
        self.assertEqual(Translation.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 0)

        # Import file with two senteces
        handler = LinguistHandler('%s/general/unfinished.ts' %
            os.path.split(__file__)[0])
        handler.bind_resource(self.resource)
        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)
        handler.save2db(is_source=True)

        # Make sure that we have all sources in the db
        self.assertEqual(SourceEntity.objects.filter(
            resource=self.resource).values('id').count(), 2)

        # Make sure that we have all translations in the db
        self.assertEqual(Translation.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 2)

        # Import the same file as a translation file in pt_BR.
        handler = LinguistHandler('%s/general/unfinished.ts' %
            os.path.split(__file__)[0])
        handler.bind_resource(self.resource)
        handler.set_language(self.language)
        handler.parse_file()
        handler.save2db()

        # Make sure that we have all sources in the db
        self.assertEqual(SourceEntity.objects.filter(
            resource=self.resource).values('id').count(), 2)

        # Make sure that we have all translations in the db
        # One is marked as unfinished so it shouldn't be saved
        self.assertEqual(Translation.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 3)

        # The unfinished translation should be added as a translation
        self.assertEqual(Suggestion.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 1)

    def test_obsolete_entries(self):
        """Test that obsolete entries are not added in the database"""
        # Empty our resource
        SourceEntity.objects.filter(resource=self.resource).delete()

        # Make sure that we have no translations to begin with
        self.assertEqual(Translation.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 0)

        # Import file with two senteces
        handler = LinguistHandler('%s/general/obsolete.ts' %
            os.path.split(__file__)[0])
        handler.bind_resource(self.resource)
        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)
        handler.save2db(is_source=True)

        # Make sure that we have all sources in the db
        self.assertEqual(SourceEntity.objects.filter(
            resource=self.resource).values('id').count(), 1)

        # Make sure that we have all translations in the db
        self.assertEqual(Translation.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 1)

        # Import the same file as a translation file in pt_BR.
        handler = LinguistHandler('%s/general/unfinished.ts' %
            os.path.split(__file__)[0])
        handler.bind_resource(self.resource)
        handler.set_language(self.language)
        handler.parse_file()
        handler.save2db()

        # Make sure that we have all sources in the db
        self.assertEqual(SourceEntity.objects.filter(
            resource=self.resource).values('id').count(), 1)

        # Make sure that we have all translations in the db
        # One is marked as unfinished so it shouldn't be saved
        self.assertEqual(Translation.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 2)

        # The unfinished translation should be added as a translation
        self.assertEqual(Suggestion.objects.filter(source_entity__in=
            SourceEntity.objects.filter(resource=self.resource).values('id')).count(), 0)

    def test_unfinished_entries(self):
        testfile = os.path.join(
            os.path.dirname(__file__),
            'en-untranslated.ts'
        )
        handler = LinguistHandler(testfile)
        handler.bind_resource(self.resource)
        handler.set_language(self.language)
        handler.parse_file(is_source=True)
        handler.save2db(is_source=True)
        lang = Language.objects.by_code_or_alias('el')
        testfile = os.path.join(
            os.path.dirname(__file__),
            'gr-untranslated.ts'
        )
        handler = LinguistHandler(testfile)
        handler.bind_resource(self.resource)
        handler.set_language(lang)
        handler.parse_file()
        handler.save2db()
        handler.compile()
        self.assertEqual(handler.compiled_template.count('unfinished'), 2)


    def test_entries_with_comment_tag(self):
        """
        Test entries with <comment>.

        This should be treated as a uniqueness value.
        """
        testfile = os.path.join(
            os.path.dirname(__file__),
            'comment/en.ts'
        )
        handler = LinguistHandler(testfile)
        handler.bind_resource(self.resource)
        handler.set_language(self.language)
        handler.parse_file(is_source=True)
        handler.save2db(is_source=True)

        self.assertEqual(SourceEntity.objects.get(resource=self.resource,
            string='It exists').context_string,
            u'QCoreApplication\\:bar:QSystemSemaphore')

        self.assertEqual(SourceEntity.objects.get(resource=self.resource,
            string='This failed').context_string,
            u'QCoreApplication\\:bar')

        self.assertEqual(SourceEntity.objects.get(resource=self.resource,
            string='One Entry').context_string, u'QSystemSemaphore\\: foo')

        self.assertEqual(SourceEntity.objects.get(resource=self.resource,
            string='Two Entries').context_string, u'None')

        self.assertEqual(SourceEntity.objects.get(resource=self.resource,
            string='Unable to connect').context_string, u'QDB2Driver')

    def test_context_generation(self):
        """Test creating the context of a source entity."""
        testfile = os.path.join(
            os.path.dirname(__file__),
            'comment/en.ts'
        )
        handler = LinguistHandler(testfile)
        handler.bind_resource(self.resource)
        handler.set_language(self.language)
        handler.parse_file(is_source=True)
        handler.save2db(is_source=True)
        handler.compile()
        doc = xml.dom.minidom.parseString(handler.compiled_template)
        root = doc.documentElement
        for message in doc.getElementsByTagName("message"):
            source = _getElementByTagName(message, "source")
            sourceString = _getText(source.childNodes)
            generated_context = handler._context_of_message(message)
            # this shouldn't raise any exceptions
            se = SourceEntity.objects.get(
                resource=self.resource, string=sourceString,
                context=generated_context or u"None"
            )

    def test_source_parsing(self):
        """Test different forms of messages in source files."""
        file_ = os.path.join(
            os.path.dirname(__file__), "source_parsing/source.ts"
        )
        handler = LinguistHandler(file_)
        handler.bind_resource(self.resource)
        handler.set_language(self.language)
        handler.parse_file(is_source=True)
        strings = handler.stringset.strings
        self.assertEquals(len(strings), 15)
        for s in strings:
            if s.source_entity == "PROCESSING START...":
                self.assertEquals(
                    s.translation, "Starting scan and copy process..."
                )
            elif s.source_entity == "USER ABORT.":
                self.assertEquals(s.translation, s.source_entity)
            elif s.source_entity == '%n FILES':
                self.assertTrue(
                    s.translation=='One (%n) file processed.' or\
                        s.translation=='%n files processed.'
                )
            elif s.source_entity == '%n FILES PROCESSING.':
                self.assertEquals(s.translation, '%n FILES PROCESSING.')
            elif s.source_entity == 'asad':
                self.assertEquals(
                    s.translation, 'Starting scan and copy process...'
                )
            elif s.source_entity == 'asadasdf':
                self.assertEquals(s.translation, "Scan")
            elif s.source_entity == 'asaadasdf':
                self.assertEquals(s.translation, "%n FILES PR.")
            elif s.source_entity == 'asadfasdf':
                self.assertTrue(
                    s.translation == 'One (%n) file processed.' or\
                        s.translation == '%n files processed.'
                )
            elif s.source_entity == 'asadgfasdf':
                self.assertEquals(s.translation, 'asadgfasdf')
            elif s.source_entity == 'asadfzasdf':
                self.assertEquals(s.translation, 'asadfzasdf')
            else:
                self.assertTrue(False, "Not supposed to happen")

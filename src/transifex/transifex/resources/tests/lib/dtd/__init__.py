# -*- coding: utf-8 -*-

import os
import unittest
from django.conf import settings
from transifex.txcommon.tests.base import BaseTestCase
from transifex.languages.models import Language
from transifex.resources.models import *
from transifex.resources.formats.dtd import DTDHandler, DTDParseError

class TestDTDHandler(BaseTestCase):
    """Suite of tests for the .DTD files."""

    def setUp(self):
        super(TestDTDHandler, self).setUp()
        self.resource.i18n_method = 'MOZILLA_PROPERTIES'
        self.resource.save()

    def test_dtd_parser(self):
        """DTD file tests."""
        handler = DTDHandler(
            os.path.join(os.path.dirname(__file__), 'aboutRobots.dtd')
        )
        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)
        self.assertEqual(len(handler.stringset.strings), 3)
        content = [
            (u' Nonsense line from the movie "The Day The Earth Stood Still". ',
                u"robots.pagetitle",
                u'Gort! Klaatu barada nikto!'),
            (u" Movie: Logan's Run... Box (cybog):\n"
             u'     "Welcome Humans! I am ready for you." ',
                u"robots.errorTitleText",
                u"Welcome Humans!"),
            (u" Movie: The Day The Earth Stood Still. Spoken by Klaatu. ",
                u"robots.errorShortDescText",
                u"We have come to visit you in peace & with goodwill!"),
            ]
        self.assertEqual(len(handler.stringset.strings), 3)
        for i in range(0, 3):
            s = handler.stringset.strings[i]
            self.assertEqual(s.comment, content[i][0])
            self.assertEqual(s.source_entity, content[i][1])
            self.assertEqual(s.translation, content[i][2])

        template = open(
            os.path.join(os.path.dirname(__file__), 'template.dtd')
            ).read()
        self.assertEqual(handler.template, template)

    def test_utf8(self):
        """test reading of UTF-8 encoded file."""
        handler = DTDHandler(
            os.path.join(os.path.dirname(__file__), 'aboutRobots_uk.dtd')
        )
        handler.set_language(self.resource.source_language)
        handler.parse_file(is_source=True)
        self.assertEqual(len(handler.stringset.strings), 3)
        content = [
            (u"robots.pagetitle",
                u'Ґорт! Клаату барада ніхто!'),
            (u"robots.errorTitleText",
                u"Привіт людинам!"),
            (u"robots.errorShortDescText",
                u"Ми прийшли до вас з миром!"),
            ]
        self.assertEqual(len(handler.stringset.strings), 3)
        for i in range(0, 3):
            s = handler.stringset.strings[i]
            self.assertEqual(s.source_entity, content[i][0])
            self.assertEqual(s.translation, content[i][1])

        self.assertRaises(DTDParseError, handler.bind_file, os.path.join(os.path.dirname(__file__),'aboutRobots_uk_1251.dtd'))

    def test_escaping(self):
        """Test escaping and unescaping"""
        j = DTDHandler()
        self.assertEqual(j._escape('& < > "\''),"&amp; &lt; &gt; &quot;'" )
        self.assertEqual(j._unescape("&amp; &lt; &gt; &quot;&#39;"), '& < > "\'' )

    def test_accept(self):
        parser = DTDHandler()
        self.assertTrue(parser.accepts('DTD'))

    def test_save2db_compile(self):
        """Test save2db and compilation of template"""
        handler = DTDHandler(
            os.path.join(os.path.dirname(__file__), 'aboutRobots.dtd')
        )
        r = self.resource
        l = self.resource.source_language

        handler.set_language(l)
        handler.bind_resource(r)
        handler.parse_file(is_source=True)
        handler.save2db(is_source=True)

        # Import and save the finish translation
        handler.bind_file(
            os.path.join(os.path.dirname(__file__),
             'aboutRobots_uk.dtd')
        )
        l = Language.objects.get(code='uk')
        handler.set_language(l)
        handler.parse_file()
        handler.save2db()

        # check number of source entities imported
        self.assertEqual(SourceEntity.objects.filter(resource=r).count(), 3)

        # Check that all source translations are there
        self.assertEqual(
            Translation.objects.filter(
                source_entity__resource=r, language=l).count(), 3
            )

        handler.compile()
        # comments should be in place
        self.assertTrue("I am ready for you" in
            handler.compiled_template.decode("utf-8"))

        # template should be in UTF-8, and single quotes should be doubled
        self.assertTrue(u'<!ENTITY robots.errorTitleText "Привіт людинам!">' in
            handler.compiled_template.decode("utf-8"))

        r.delete()

# -*- coding: utf-8 -*-

from django.test import TestCase
from transifex.resources.formats.resource_collections import StringSet
from transifex.resources.formats.wiki import WikiHandler


class TestWikiHandler(TestCase):

    def test_parse_wiki_text(self):
        handler = WikiHandler()
        handler.stringset = StringSet()
        content = "Text {{italics|is}}\n\nnew {{italics|par\n\npar}}.\n\nTers"
        handler.content = content
        handler._parse(None, None)
        self.assertEquals(len(handler.stringset.strings), 3)

        handler.stringset = StringSet()
        content = "Text {{italics|is}}\n\n\n\nnew {{italics|par\n\npar}}.\n\nTers"
        handler.content = content
        handler._parse(None, None)
        self.assertEquals(len(handler.stringset.strings), 3)

        handler.stringset = StringSet()
        content = ("Text {{italics|is}} {{bold|bold}}\n\n\n\nnew "
                   "{{italics|par\n\npar}}.\n\nTers")
        handler.content = content
        handler._parse(None, None)
        self.assertEquals(len(handler.stringset.strings), 3)

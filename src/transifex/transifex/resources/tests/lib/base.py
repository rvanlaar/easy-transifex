# -*- coding: utf-8 -*-
import logging
from django.conf import settings
from django.utils.hashcompat import md5_constructor
from transifex.txcommon.tests import base

class FormatsBaseTestCase(base.BaseTestCase):
    """Base class for tests on supported formats."""

    def setUp(self):
        super(FormatsBaseTestCase, self).setUp()
        logging.disable(logging.CRITICAL)

    def compare_to_actual_file(self, handler, actual_file):
        template = handler.template
        for s in handler.stringset.strings:
            trans = s.translation
            source = s.source_entity
            source = "%(hash)s_tr" % {'hash':md5_constructor(
                    ':'.join([source, ""]).encode('utf-8')).hexdigest()}
            template = handler._replace_translation(
                "%s" % source.encode('utf-8'),
                trans and trans.encode('utf-8') or "",
                template
            )
        with open(actual_file, 'r') as f:
            actual_content = f.read()
        self.assertEquals(template, actual_content)

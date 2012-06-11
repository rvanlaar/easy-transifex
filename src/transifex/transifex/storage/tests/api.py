# -*- coding: utf-8 -*-
import os
from django.core.urlresolvers import reverse
from transifex.txcommon.tests.base import BaseTestCase

FILENAME = 'pt_BR.po'

class BaseStorageTests(BaseTestCase):
    """Base test abstraction for storage app."""

    def create_storage(self):
        """Create StorageFile"""

        upload_file = open('%s/%s' % (os.path.split(__file__)[0], FILENAME))
        data = {'language': self.language_en.code, 'file': upload_file}
        resp = self.client['anonymous'].post(reverse('api.storage'), data)
        self.assertEqual(resp.status_code, 401)

        upload_file = open('%s/%s' % (os.path.split(__file__)[0], FILENAME))
        data = {'language': self.language_en.code, 'file': upload_file}
        resp = self.client['registered'].post(reverse('api.storage'), data)
        self.assertTrue(FILENAME in resp.content)

        for f in eval(resp.content)['files']:
            if f['name'] == FILENAME:
                self.uuid = f['uuid']
                break

class StorageTests(BaseStorageTests):
    """Test the storage app."""

    def test_create_storage_with_invalid_file(self):
        """Create StorageFile with invalid file."""

        # Test empty file
        upload_file = open('%s/empty.pot' % os.path.split(__file__)[0]) # hack
        data = {'language': self.language_en.code, 'file': upload_file}
        resp = self.client['registered'].post(reverse('api.storage'), data)
        self.assertIn('Uploaded file is empty', resp.content)


    def test_update_storage_language(self):
        """Test update of language for StorageFile."""
        self.create_storage()
        data = '{"language": "%s"}' % self.language.code
        resp = self.client['registered'].post(reverse('api.storage.file',
            args=[self.uuid]), data=data, content_type="application/json")
        print resp.content
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('OK' in resp.content)


    def test_get_storage(self):
        """Get info for StorageFile"""
        self.create_storage()

        resp = self.client['registered'].get(reverse('api.storage.file',
            args=[self.uuid]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.uuid in resp.content)
        self.assertTrue(self.language_en.name in resp.content)


    def test_delete_storage(self):
        """Delete StorageFile"""
        self.create_storage()

        # Storage only can be deleted by the person who created it
        resp = self.client['maintainer'].delete(reverse('api.storage.file',
            args=[self.uuid]))
        self.assertEqual(resp.status_code, 404)

        resp = self.client['registered'].delete(reverse('api.storage.file',
            args=[self.uuid]))
        self.assertEqual(resp.status_code, 204)

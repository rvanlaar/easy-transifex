# -*- coding: utf-8 -*-
import os
from django.core.urlresolvers import reverse
from django.utils import simplejson
from django.test import TransactionTestCase
from django.conf import settings
from django.contrib.auth.models import User, Permission
from transifex.txcommon.tests.base import Users, TransactionNoticeTypes
from transifex.resources.models import Resource, RLStats
from transifex.resources.api import ResourceHandler
from transifex.resources.formats.registry import registry
from transifex.resources.tests.api.base import APIBaseTests
from transifex.projects.models import Project
from transifex.languages.models import Language
from transifex.settings import PROJECT_PATH


class TestResourceAPI(APIBaseTests):

    def setUp(self):
        super(TestResourceAPI, self).setUp()
        self.po_file = os.path.join(self.pofile_path, "pt_BR.po")
        self.url_resources = reverse(
            'apiv2_resources', kwargs={'project_slug': 'project1'}
        )
        self.url_resources_private = reverse(
            'apiv2_resources', kwargs={'project_slug': 'project2'}
        )
        self.url_resource = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'project1', 'resource_slug': 'resource1'}
        )
        self.url_resource_private = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'project2', 'resource_slug': 'resource1'}
        )
        self.url_new_project = reverse(
            'apiv2_projects'
        )
        self.url_create_resource = reverse(
            'apiv2_resources', kwargs={'project_slug': 'new_pr'}
        )
        self.url_new_resource = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'new_pr', 'resource_slug': 'r1', }
        )
        self.url_new_translation = reverse(
            'apiv2_translation',
            kwargs={
                'project_slug': 'new_pr',
                'resource_slug': 'new_r',
                'lang_code': 'el'
            }
        )

    def test_get(self):
        res = self.client['anonymous'].get(self.url_resources)
        self.assertEquals(res.status_code, 401)
        res = self.client['registered'].get(
            reverse(
                'apiv2_resource',
                kwargs={'project_slug': 'not_exists', 'resource_slug': 'resource1'}
            )
        )
        self.assertEquals(res.status_code, 404)
        res = self.client['registered'].get(self.url_resources)
        self.assertEquals(res.status_code, 200)
        self.assertFalse('created' in simplejson.loads(res.content)[0])
        res = self.client['registered'].get(self.url_resources)
        self.assertEquals(res.status_code, 200)
        self.assertEquals(len(simplejson.loads(res.content)), 1)
        self.assertFalse('created' in simplejson.loads(res.content)[0])
        res = self.client['registered'].get(self.url_resources_private)
        self.assertEquals(res.status_code, 401)
        res = self.client['maintainer'].get(self.url_resources_private + "?details")
        self.assertEquals(res.status_code, 501)
        res = self.client['maintainer'].get(self.url_resources_private)
        self.assertEquals(res.status_code, 200)
        self.assertEqual(len(simplejson.loads(res.content)), 1)
        self.assertFalse('created' in simplejson.loads(res.content)[0])
        self.assertTrue('slug' in simplejson.loads(res.content)[0])
        self.assertTrue('name' in simplejson.loads(res.content)[0])
        res = self.client['anonymous'].get(self.url_resource)
        self.assertEquals(res.status_code, 401)
        url_not_exists = self.url_resource[:-1] + "none/"
        res = self.client['registered'].get(url_not_exists)
        self.assertEquals(res.status_code, 404)
        res = self.client['registered'].get(self.url_resource_private)
        self.assertEquals(res.status_code, 401)
        res = self.client['maintainer'].get(self.url_resource_private)
        self.assertEquals(res.status_code, 200)
        res = self.client['maintainer'].get(self.url_resource_private)
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertEquals(len(data), 5)
        self.assertTrue('slug' in  data)
        self.assertTrue('name' in data)
        self.assertTrue('source_language', data)
        res = self.client['maintainer'].get(self.url_resource_private + "?details")
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertTrue('source_language_code' in data)
        self._create_resource()
        res = self.client['registered'].get(self.url_new_resource)
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertTrue('source_language_code' in data)
        res = self.client['registered'].get(
            self.url_new_resource + "content/"
        )
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertTrue('content' in data)
        res = self.client['registered'].get(
            self.url_new_resource + "content/?file"
        )
        self.assertEquals(res.status_code, 200)


    def test_post_errors(self):
        res = self.client['anonymous'].post(
            self.url_resource, content_type='application/json'
        )
        self.assertEquals(res.status_code, 401)
        res = self.client['registered'].post(
            self.url_resource, content_type='application/json'
        )
        self.assertEquals(res.status_code, 403)
        self._create_resource()
        url = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'new_pr', 'resource_slug': 'new_r'}
        )
        res = self.client['registered'].post(
            url, content_type='application/json'
        )
        self.assertContains(res, "POSTing to this url is not allowed", status_code=400)
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "resource1",
                    'slug': 'r1',
                    'foo': 'foo'
            }),
            content_type='application/json'
        )
        self.assertContains(res, "Field 'foo'", status_code=400)
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "resource1",
                    'name': "resource2",
                    'slug': 'r2',
            }),
            content_type='application/json'
        )
        self.assertContains(res, "Field 'i18n_type'", status_code=400)

    def test_post_files(self):
        self._create_project()
        # send files
        f = open(self.po_file)
        res = self.client['registered'].post(
            self.url_create_resource,
            data={
                'name': "resource1",
                'slug': 'r1',
                'i18n_type': 'PO',
                'name': 'name.po',
                'attachment': f
            },
        )
        f.close()
        r = Resource.objects.get(slug='r1', project__slug='new_pr')
        self.assertEquals(len(r.available_languages_without_teams), 1)

    def test_put(self):
        self._create_resource()
        res = self.client['anonymous'].put(
            self.url_create_resource,
            data=simplejson.dumps({}),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 401)
        res = self.client['registered'].put(
            self.url_create_resource,
            data=simplejson.dumps({}),
            content_type='application/json'
        )
        self.assertContains(res, "No resource", status_code=400)
        url = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'new_pr_not', 'resource_slug': 'r1'}
        )
        res = self.client['registered'].put(
            url, data=simplejson.dumps({}),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 404)
        url = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'new_pr', 'resource_slug': 'r1'}
        )
        res = self.client['registered'].put(
            url, data=simplejson.dumps({}),
            content_type='application/json'
        )
        self.assertContains(res, "Empty request", status_code=400)
        url = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'new_pr', 'resource_slug': 'r1'}
        )
        res = self.client['registered'].put(
            url,
            data=simplejson.dumps({
                    'i18n_type': "PO",
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 400)
        res = self.client['registered'].put(
            url,
            data=simplejson.dumps({
                    'foo': 'foo',
            }),
            content_type='application/json'
        )
        self.assertContains(res,"Field 'foo'", status_code=400)

    def test_delete(self):
        res = self.client['anonymous'].delete(self.url_resource)
        self.assertEquals(res.status_code, 401)
        res = self.client['registered'].delete(self.url_resource)
        self.assertEquals(res.status_code, 403)
        self._create_resource()
        url = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'new_pr', 'resource_slug': 'r1'}
        )
        res = self.client['registered'].delete(url)
        self.assertEquals(res.status_code, 204)

    def _create_project(self):
        res = self.client['registered'].post(
            self.url_new_project,
            data=simplejson.dumps({
                    'slug': 'new_pr', 'name': 'Project from API',
                    'source_language_code': 'el',
                    'maintainers': 'registered',
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)

    def _create_resource(self):
        self._create_project()
        with open(self.po_file) as f:
            content = f.read()
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "resource1",
                    'slug': 'r1',
                    'i18n_type': 'PO',
                    'content': content,
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)
        r = Resource.objects.get(slug='r1', project__slug='new_pr')
        self.assertEquals(len(r.available_languages_without_teams), 1)


class TestTransactionResourceCreate(Users, TransactionNoticeTypes,
                                    TransactionTestCase):

    def setUp(self):
        super(TestTransactionResourceCreate, self).setUp()
        self.pofile_path = os.path.join(
            settings.TX_ROOT, 'resources/tests/lib/pofile'
        )
        self.po_file = os.path.join(self.pofile_path, "pt_BR.po")
        self.url_resources = reverse(
            'apiv2_resources', kwargs={'project_slug': 'project1'}
        )
        self.url_resources_private = reverse(
            'apiv2_resources', kwargs={'project_slug': 'project2'}
        )
        self.url_resource = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'project1', 'resource_slug': 'resource1'}
        )
        self.url_resource_private = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'project2', 'resource_slug': 'resource1'}
        )
        self.url_new_project = reverse(
            'apiv2_projects'
        )
        self.url_create_resource = reverse(
            'apiv2_resources', kwargs={'project_slug': 'new_pr'}
        )
        self.url_new_resource = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'new_pr', 'resource_slug': 'r1', }
        )
        self.url_new_translation = reverse(
            'apiv2_translation',
            kwargs={
                'project_slug': 'new_pr',
                'resource_slug': 'new_r',
                'lang_code': 'el'
            }
        )

    def test_long_slug(self):
        """Test error in case of a very long slug."""
        res = self.client['registered'].post(
            self.url_new_project,
            data=simplejson.dumps({
                    'slug': 'new_pr', 'name': 'Project from API',
                    'source_language_code': 'el',
                    'maintainers': 'registered',
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)
        with open(self.po_file) as f:
            content = f.read()
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "resource1",
                    'slug': 'a-very-long-slug' * 10,
                    'i18n_type': 'PO',
                    'content': content,
            }),
            content_type='application/json'
        )
        self.assertContains(res, 'value for slug is too long', status_code=400)

    def test_post_errors(self):
        res = self.client['registered'].post(
            self.url_new_project,
            data=simplejson.dumps({
                    'slug': 'new_pr', 'name': 'Project from API',
                    'source_language_code': 'el',
                    'maintainers': 'registered',
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)
        with open(self.po_file) as f:
            content = f.read()
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "resource1",
                    'slug': 'r1',
                    'i18n_type': 'PO',
                    'content': content,
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)
        r = Resource.objects.get(slug='r1', project__slug='new_pr')
        self.assertEquals(len(r.available_languages_without_teams), 1)
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "resource1",
                    'slug': 'r1',
                    'i18n_type': 'PO',
                    'content': content,
            }),
            content_type='application/json'
        )
        self.assertContains(res, "same slug exists", status_code=400)
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "resource2",
                    'slug': 'r2',
                    'i18n_type': 'PO',
            }),
            content_type='application/json'
        )
        self.assertContains(res, "No content", status_code=400)
        self.assertRaises(
            Resource.DoesNotExist,
            Resource.objects.get,
            slug="r2", project__slug="new_pr"
        )


class TestTranslationAPI(APIBaseTests):

    def setUp(self):
        super(TestTranslationAPI, self).setUp()
        self.po_file = os.path.join(self.pofile_path, "pt_BR.po")
        self.url_resources = reverse(
            'apiv2_resources', kwargs={'project_slug': 'project1'}
        )
        self.url_resources_private = reverse(
            'apiv2_resources', kwargs={'project_slug': 'project2'}
        )
        self.url_resource = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'project1', 'resource_slug': 'resource1'}
        )
        self.url_resource_private = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'project2', 'resource_slug': 'resource1'}
        )
        self.url_new_project = reverse(
            'apiv2_projects'
        )
        self.url_create_resource = reverse(
            'apiv2_resources', kwargs={'project_slug': 'new_pr'}
        )
        self.url_new_resource = reverse(
            'apiv2_resource',
            kwargs={'project_slug': 'new_pr', 'resource_slug': 'r1', }
        )
        self.url_new_translation = reverse(
            'apiv2_translation',
            kwargs={
                'project_slug': 'new_pr',
                'resource_slug': 'new_r',
                'lang_code': 'el'
            }
        )

    def test_get_translation(self):
        res = self.client['anonymous'].get(self.url_new_translation)
        self.assertEquals(res.status_code, 401)
        res = self.client['registered'].get(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'project1',
                    'resource_slug': 'resource-not',
                    'lang_code': 'en_US',
                }
            )
        )
        self.assertEquals(res.status_code, 404)
        res = self.client['registered'].get(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'project1',
                    'resource_slug': 'resource1',
                    'lang_code': 'en_US',
                }
            )
        )
        self.assertEquals(len(simplejson.loads(res.content)), 2)
        self.assertEquals(res.status_code, 200)
        url = "".join([
                reverse(
                    'apiv2_translation',
                    kwargs={
                        'project_slug': 'project1',
                        'resource_slug': 'resource1',
                            'lang_code': 'en_US',
                    }),
                "?file"
        ])
        res = self.client['registered'].get(url)
        self.assertEquals(res.status_code, 200)

    def test_delete_translations(self):
        self._create_resource()
        f = open(self.po_file)
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'fi'
                }
            ),
            data={
                'name': 'name.po',
                'attachment': f
            },
        )
        f.close()
        self.assertEquals(res.status_code, 200)
        res = self.client['anonymous'].delete(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'fi'
                }
            )
        )
        self.assertEquals(res.status_code, 401)
        res = self.client['registered'].delete(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'fi'
                }
            )
        )
        self.assertEquals(res.status_code, 204)
        res = self.client['registered'].delete(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'el'
                }
            )
        )
        self.assertContains(res, "source language", status_code=400)
        res = self.client['registered'].delete(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'no_resource',
                    'lang_code': 'fi'
                }
            )
        )
        self.assertEquals(res.status_code, 404)
        res = self.client['registered'].delete(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'no_project',
                    'resource_slug': 'r1',
                    'lang_code': 'fi'
                }
            )
        )
        self.assertEquals(res.status_code, 404)
        res = self.client['registered'].delete(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'en_NN'
                }
            )
        )
        self.assertEquals(res.status_code, 404)
        res = self.client['registered'].delete(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'no_project',
                    'resource_slug': 'r1',
                    'lang_code': 'source'
                }
            )
        )
        self.assertEquals(res.status_code, 404)
        res = self.client['maintainer'].delete(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'fi'
                }
            )
        )
        self.assertEquals(res.status_code, 403)
        res = self.client['registered'].delete(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'fi'
                }
            )
        )
        self.assertEquals(res.status_code, 404)
        res = self.client['registered'].delete(
            reverse(
                'apiv2_source_content',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                }
            )
        )
        self.assertContains(res, "source language", status_code=400)

    def test_put_translations(self):
        self._create_resource()
        # test strings
        res = self.client['registered'].post(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'el_GR',
                }
            )
        )
        self.assertEquals(res.status_code, 405)
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'el',
                }
            )
        )
        self.assertContains(res, "No file", status_code=400)
        with open(self.po_file) as f:
            content = f.read()
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr_not',
                    'resource_slug': 'r1',
                    'lang_code': 'el',
                }
            ),
            data=simplejson.dumps([{
                    'content': content,
            }]),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 404)
        r = Resource.objects.get(slug="r1", project__slug="new_pr")
        self.assertEquals(len(r.available_languages_without_teams), 1)
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'el',
                }
            ),
            data=simplejson.dumps({
                    'content': content,
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 200)
        self.assertEquals(len(r.available_languages_without_teams), 1)
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'enb'
                }
            ),
            data=simplejson.dumps({
                    'content': content,
            }),
            content_type='application/json'
        )
        self.assertContains(res, "language code", status_code=400)

        # test files
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'fi'
                }
            ),
            data={},
        )
        self.assertContains(res, "No file", status_code=400)
        f = open(self.po_file)
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'fi'
                }
            ),
            data={
                'name': 'name.po',
                'attachment': f
            },
        )
        f.close()
        self.assertEquals(res.status_code, 200)
        self.assertEquals(len(r.available_languages_without_teams), 2)

        res = self.client['anonymous'].post(self.url_new_translation)
        self.assertEquals(res.status_code, 401)

        f = open(self.po_file)
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'el',
                }
            ),
            data={
                'name': 'name.po',
                'attachment': f
            },
        )
        f.close()
        self.assertEquals(res.status_code, 200)

    def test_rlstats_updated(self):
        self._create_project()
        content = 'key = value'
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "resource1",
                    'slug': 'r1',
                    'i18n_type': 'INI',
                    'content': content,
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)
        translation = u'key = τιμή'
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                    'lang_code': 'fi',
                }
            ),
            data=simplejson.dumps({
                    'content': translation,
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 200)
        r = Resource.objects.get(slug='r1', project__slug='new_pr')
        l = Language.objects.by_code_or_alias('fi')
        rl = RLStats.objects.get(resource=r, language=l)
        self.assertEquals(rl.translated_perc, 100)
        content += '\nother = other'
        res = self.client['registered'].put(
            reverse(
                'apiv2_source_content',
                kwargs={
                    'project_slug': 'new_pr',
                    'resource_slug': 'r1',
                }
            ),
            data=simplejson.dumps({
                    'content': content,
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 200)
        rl = RLStats.objects.get(resource=r, language=l)
        self.assertEquals(rl.translated_perc, 50)

    def test_unicode_resource_name(self):
        self._create_project()
        with open(self.po_file) as f:
            content = f.read()
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "rα",
                    'slug': 'r1',
                    'i18n_type': 'PO',
                    'content': content,
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)
        url = "".join([
                reverse(
                    'apiv2_translation',
                    kwargs={
                        'project_slug': 'new_pr',
                        'resource_slug': 'r1',
                            'lang_code': 'en_US',
                    }),
                "?file"
        ])
        res = self.client['registered'].get(url)
        self.assertEquals(res.status_code, 200)

    def _create_project(self):
        res = self.client['registered'].post(
            self.url_new_project,
            data=simplejson.dumps({
                    'slug': 'new_pr', 'name': 'Project from API',
                    'source_language_code': 'el',
                    'maintainers': 'registered',
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)

    def _create_resource(self):
        self._create_project()
        with open(self.po_file) as f:
            content = f.read()
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "resource1",
                    'slug': 'r1',
                    'i18n_type': 'PO',
                    'content': content,
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)
        r = Resource.objects.get(slug='r1', project__slug='new_pr')
        self.assertEquals(len(r.available_languages_without_teams), 1)


class TestStatsAPI(APIBaseTests):

    def setUp(self):
        super(TestStatsAPI, self).setUp()
        self.content = 'KEY1="Translation"\nKEY2="Translation with "_QQ_"quotes"_QQ_""'
        self.project_slug = 'new_pr'
        self.resource_slug='r1'
        self.url_new_project = reverse(
            'apiv2_projects'
        )
        self.url_create_resource = reverse(
            'apiv2_resources', kwargs={'project_slug': self.project_slug}
        )
        self._create_project()
        self._create_resource()

    def test_get_stats(self):
        r = Resource.objects.get(slug='r1')
        greek = 'KEY1="Μετάφραση"\nKEY2="Μετάφραση με "_QQ_"εισαγωγικά"_QQ_""'
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': self.project_slug,
                    'resource_slug': self.resource_slug,
                    'lang_code': 'el'
                }
            ),
            data=simplejson.dumps({'content': greek}),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 200)
        res = self.client['registered'].get(
            reverse(
                'apiv2_stats',
                kwargs={
                    'project_slug': self.project_slug,
                    'resource_slug': self.resource_slug,
                    'lang_code': 'el',
                }
            )
        )
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertEquals(data['completed'], '100%')
        german = 'KEY1="Übersetzung"\nKEY2="Übersetzung mit "_QQ_"Zitate"_QQ_""'
        res = self.client['registered'].put(
            reverse(
                'apiv2_translation',
                kwargs={
                    'project_slug': self.project_slug,
                    'resource_slug': self.resource_slug,
                    'lang_code': 'af'
                }
            ),
            data=simplejson.dumps({'content': german}),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 200)
        res = self.client['registered'].get(
            reverse(
                'apiv2_stats',
                kwargs={
                    'project_slug': self.project_slug,
                    'resource_slug': self.resource_slug,
                    'lang_code': 'af',
                }
            )
        )
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertEquals(data['completed'], '100%')
        res = self.client['registered'].get(
            reverse(
                'apiv2_stats',
                kwargs={
                    'project_slug': self.project_slug,
                    'resource_slug': self.resource_slug,
                }
            )
        )
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertEquals(data['el']['completed'], '100%')
        self.assertEquals(data['af']['completed'], '100%')

    def _create_project(self):
        res = self.client['registered'].post(
            self.url_new_project,
            data=simplejson.dumps({
                    'slug': self.project_slug, 'name': 'Project from API',
                    'source_language_code': 'el',
                    'maintainers': 'registered',
            }),
            content_type='application/json'
        )

    def _create_resource(self):
        res = self.client['registered'].post(
            self.url_create_resource,
            data=simplejson.dumps({
                    'name': "resource1",
                    'slug': self.resource_slug,
                    'i18n_type': 'INI',
                    'content': self.content,
            }),
            content_type='application/json'
        )

class TestFormatsAPI(APIBaseTests):
    def test_formats_api(self):
        res = self.client['registered'].get(
            reverse('supported_formats')
        )
        self.assertEqual(res.status_code, 200)
        json = simplejson.loads(res.content)
        self.assertEqual(registry.available_methods, json)

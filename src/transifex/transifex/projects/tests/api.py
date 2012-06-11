# -*- coding: utf-8 -*-
import os
from django.core.urlresolvers import reverse
from django.conf import settings
from django.utils import simplejson
from django.test import TransactionTestCase
from django.contrib.auth.models import User, Permission
from transifex.txcommon.tests.base import BaseTestCase, Users, Languages, \
        NoticeTypes, Projects, TransactionNoticeTypes, TransactionLanguages
from transifex.resources.models import RLStats, Resource
from transifex.projects.models import Project
from transifex.storage.models import StorageFile
from transifex.storage.tests.api import BaseStorageTests

class ProjectResourceAPITests(BaseStorageTests):
    """
    Test the status codes.
    """
    def test_resource_creation(self):
        """Test creation of resource through the API."""

        self.create_storage()

        data = '{"uuid": "%s"}' % self.uuid
        resp = self.client['registered'].post(reverse('api_project_files',
            args=[self.project.slug]), data, content_type="application/json")
        self.assertTrue('Forbidden access' in resp.content)
        self.assertEqual(resp.status_code, 403)

        resp = self.client['maintainer'].post(reverse('api_project_files',
            args=[self.project.slug]), data, content_type="application/json")
        r = simplejson.loads(resp.content)
        self.assertEqual(r['strings_added'], 3)
        self.assertEqual(resp.status_code, 200)

        # To be used in other tests
        self.resource_slug = eval(resp.content)['redirect'].split(
            '/resource/')[1].replace('/','')

        # Some extra check around denormalization
        rls = RLStats.objects.get(resource__project=self.project,
            resource__slug=self.resource_slug, language=self.language_en)

        self.assertEqual(rls.translated, 3)
        self.assertEqual(rls.total, 3)
        self.assertEqual(rls.translated_perc, 100)

    def test_submission_translation(self):
        """Test submission of translation through the API."""

        self.test_resource_creation()

        # Changing language of the storagefile object
        sf = StorageFile.objects.get(uuid=self.uuid)
        sf.language = self.language
        sf.save()

        data = '{"uuid": "%s"}' % self.uuid
        resp = self.client['maintainer'].put(reverse('api_resource_storage',
            args=[self.project.slug, self.resource_slug, self.language.code]),
            data, content_type="application/json")
        self.assertEqual(eval(resp.content)['strings_added'], 3)

        # Some extra check around denormalization
        rls = RLStats.objects.get(resource__project=self.project,
            resource__slug=self.resource_slug, language=self.language)

        resource = Resource.objects.get(project=self.project,
            slug=self.resource_slug)

        self.assertEqual(rls.translated, 3)
        self.assertEqual(rls.total, 3)
        self.assertEqual(rls.translated_perc, 100)

    def test_same_source_language(self):
        filename = 'pt_BR.po'
        path = os.path.join(settings.TX_ROOT, 'storage/tests/', filename)

        # same language: success
        upload_file = open(path)
        data = {'language': self.language_en.code, 'file': upload_file}
        resp = self.client['registered'].post(reverse('api.storage'), data)
        uuid = simplejson.loads(resp.content)['files'][0]['uuid']
        data = '{"uuid": "%s"}' % uuid
        resp = self.client['maintainer'].post(
            reverse('api_project_files', args=[self.project.slug]),
            data, content_type="application/json"
        )
        self.assertEqual(eval(resp.content)['strings_added'], 3)
        self.assertEqual(resp.status_code, 200)
        upload_file.close()

        # different language: error
        upload_file = open(path)
        data = {'language': self.language_ar.code, 'file': upload_file}
        resp = self.client['registered'].post(reverse('api.storage'), data)
        uuid = simplejson.loads(resp.content)['files'][0]['uuid']
        data = '{"uuid": "%s"}' % uuid
        resp = self.client['maintainer'].post(
            reverse('api_project_files', args=[self.project.slug]),
            data, content_type="application/json"
        )
        self.assertContains(resp, "for source language", status_code=400)
        upload_file.close()

class TestTransactionProjectResourceAPI(TransactionNoticeTypes,
                                        TransactionLanguages,
                                        Users, Projects, TransactionTestCase):

    def setUp(self):
        # Have to run now, because the TransactionTestCase resets
        # the database *every* time.
        super(TestTransactionProjectResourceAPI, self).setUp()
        self.project = Project.objects.get(slug='project1')
        self.project.maintainers.add(self.user['maintainer'])
        self.project.owner = self.user['maintainer']
        self.project.save()

    def test_second_create_with_error(self):
        """Test that calling create a second time with the same parameters
        and a bogus source file does not delete the resource.
        """
        rslug = "oops"
        self.assertEqual(Resource.objects.filter(slug=rslug).count(), 0)

        upload_file = open(os.path.join(
                settings.TX_ROOT,
                'resources/tests/lib/qt/en.ts'
        ))
        data = {'language': self.language_en.code, 'file': upload_file}
        resp = self.client['registered'].post(reverse('api.storage'), data)
        self.assertEqual(resp.status_code, 200)
        uuid = simplejson.loads(resp.content)['files'][0]['uuid']

        resp = self.client['maintainer'].post(
            reverse('api_project_files', args=[self.project.slug]),
            data='{"uuid": "%s", "slug": "%s"}' % (uuid, rslug),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Resource.objects.filter(slug=rslug).count(), 1)

        upload_file = open(os.path.join(
                settings.TX_ROOT,
                'resources/tests/lib/qt/error.ts'
        ))
        data = {'language': self.language_en.code, 'file': upload_file}
        resp = self.client['registered'].post(reverse('api.storage'), data)
        self.assertEqual(resp.status_code, 200)
        uuid = simplejson.loads(resp.content)['files'][0]['uuid']

        resp = self.client['maintainer'].post(
            reverse('api_project_files', args=[self.project.slug]),
            data='{"uuid": "%s", "slug": "%s"}' % (uuid, rslug),
            content_type="application/json"
        )
        self.assertEqual(Resource.objects.filter(slug=rslug).count(), 1)

        rslug = 'noop'
        upload_file = open(os.path.join(
                settings.TX_ROOT,
                'resources/tests/lib/qt/error.ts'
        ))
        data = {'language': self.language_en.code, 'file': upload_file}
        resp = self.client['registered'].post(reverse('api.storage'), data)
        self.assertEqual(resp.status_code, 200)
        uuid = simplejson.loads(resp.content)['files'][0]['uuid']

        resp = self.client['maintainer'].post(
            reverse('api_project_files', args=[self.project.slug]),
            data='{"uuid": "%s", "slug": "%s"}' % (uuid, rslug),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Resource.objects.filter(slug=rslug).count(), 0)


class TestProjectAPI(BaseTestCase):

    def setUp(self):
        super(TestProjectAPI, self).setUp()
        self.url_projects = reverse('apiv2_projects')
        self.url_project = reverse('apiv2_project', kwargs={'project_slug': 'foo'})

    def test_get(self):
        res = self.client['anonymous'].get(self.url_projects)
        self.assertEquals(res.status_code, 401)
        res = self.client['maintainer'].get(self.url_projects + "?details")
        self.assertEquals(res.status_code, 501)
        res = self.client['maintainer'].get(self.url_projects)
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertEquals(len(data), 7)
        self.assertFalse('created' in data[0])
        self.assertTrue('slug' in data[0])
        self.assertTrue('name' in data[0])
        res = self.client['registered'].get(self.url_projects)
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertEquals(len(data), 6)
        res = self.client['anonymous'].get(self.url_project)
        self.assertEquals(res.status_code, 401)
        res = self.client['registered'].get(self.url_project)
        self.assertEquals(res.status_code, 404)
        private_url = "/".join([self.url_projects[:-2], self.project_private.slug, ''])
        res = self.client['registered'].get(private_url)
        self.assertEquals(res.status_code, 401)
        res = self.client['maintainer'].get(private_url)
        self.assertEquals(res.status_code, 200)
        public_url = "/".join([self.url_projects[:-2], self.project.slug, ''])
        res = self.client['registered'].get(public_url + "?details")
        self.assertEquals(res.status_code, 200)
        self.assertEquals(len(simplejson.loads(res.content)), 17)
        self.assertTrue('created' in simplejson.loads(res.content))
        public_url = "/".join(
            [self.url_projects[:-2], self.project.slug, ""]
        )
        res = self.client['registered'].get(public_url)
        self.assertEquals(res.status_code, 200)
        self.assertTrue('slug' in simplejson.loads(res.content))
        self.assertTrue('name' in simplejson.loads(res.content))
        self.assertTrue('description' in simplejson.loads(res.content))
        self.assertTrue('source_language_code' in simplejson.loads(res.content))
        self.assertEquals(len(simplejson.loads(res.content)), 4)

        # Test pagination
        res = self.client['registered'].get(self.url_projects + "?start=5")
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertEquals(len(data), 2)
        res = self.client['registered'].get(self.url_projects + "?end=5")
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertEquals(len(data), 4)
        res = self.client['registered'].get(self.url_projects + "?start=a")
        self.assertEquals(res.status_code, 400)
        res = self.client['registered'].get(self.url_projects + "?start=0")
        self.assertEquals(res.status_code, 400)
        res = self.client['registered'].get(self.url_projects + "?end=0")
        self.assertEquals(res.status_code, 400)
        res = self.client['registered'].get(self.url_projects + "?start=1&end=4")
        self.assertEquals(res.status_code, 200)
        data = simplejson.loads(res.content)
        self.assertEquals(len(data), 3)
        res = self.client['registered'].get(self.url_projects + "?start=1&end=4")
        data = simplejson.loads(res.content)
        self.assertEquals(len(data), 3)
        self.assertEquals(res.status_code, 200)

    def test_get_teams(self):
        """Test the teams field for the project."""
        url = reverse(
            'apiv2_project', kwargs={'project_slug': self.project.slug}
        )
        res = self.client['registered'].get(url + '?details')
        self.assertContains(res, 'teams', status_code=200)
        self.assertIsInstance(simplejson.loads(res.content)['teams'], list)

    def test_post(self):
        res = self.client['anonymous'].post(self.url_projects, content_type='application/json')
        self.assertEquals(res.status_code, 401)
        res = self.client['registered'].post(self.url_project, content_type='application/json')
        self.assertContains(res, "POSTing to this url is not allowed", status_code=400)
        res = self.client['registered'].post(self.url_projects)
        self.assertContains(res, "Bad Request", status_code=400)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({'name': 'name of project'}),
            content_type="application/json"
        )
        self.assertContains(res, "Field 'slug' is required to create", status_code=400)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({'slug': 'slug'}), content_type='application/json'
        )
        self.assertContains(res, "Field 'name' is required to create", status_code=400)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({'slug': 'slug', 'name': 'name'}),
            content_type='application/json'
        )
        self.assertContains(res, "Field 'source_language_code' is required to create", status_code=400)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({
                'slug': 'slug', 'name': 'name', 'owner': 'owner',
                'source_language_code': 'en',
            }),
            content_type='application/json'
        )
        self.assertContains(res, "Owner cannot be set explicitly.", status_code=400)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({
                'slug': 'api_project',
                'name': 'Project from API',
                'source_language_code': 'en',
                'outsource': 'not_exists',
            }),
            content_type='application/json'
        )
        self.assertContains(res, "Project for outsource does not exist", status_code=400)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({
                'slug': 'api_project', 'name': 'Project from API',
                'source_language_code': 'en', 'maintainers': 'not_exists',
            }),
            content_type='application/json'
        )
        self.assertContains(res, "User", status_code=400)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({
                'slug': 'api_project_maintainers',
                'name': 'Project from API',
                'source_language_code': 'en',
                'maintainers': 'registered',
                'none': 'none'
            }),
            content_type='application/json'
        )
        self.assertContains(res, "Field 'none'", status_code=400)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({
                'slug': 'api_project_maintainers',
                'name': 'Project from API',
                'source_language_code': 'en',
                'maintainers': 'registered'
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)
        self.assertEquals(len(Project.objects.all()), 8)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({
                'slug': 'api_project', 'name': 'Project from API',
                'source_language_code': 'en_US'
            }),
            content_type='application/json'
        )
        p = Project.objects.get(slug='api_project')
        user = User.objects.get(username='registered')
        self.assertTrue(user in p.maintainers.all())
        self.assertEquals(res.status_code, 201)
        self.assertEquals(len(Project.objects.all()), 9)
        self.assertEquals(p.source_language, self.language_en)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({
                'slug': 'api_project', 'name': 'Project from API',
                'source_language_code': 'en_US'
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 409)
        # Check permissions
        user = User.objects.get(username='registered')
        user.groups = []
        user.save()
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({
                'slug': 'api_project_2', 'name': 'Project from API - second',
                'source_language_code': 'en_US'
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 403)

    def test_put(self):
        res = self.client['anonymous'].put(
            self.url_project, data=simplejson.dumps({}),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 401)
        res = self.client['registered'].put(self.url_project)
        self.assertEquals(res.status_code, 400)
        res = self.client['registered'].put(
            self.url_project[:-1] + "1/",
            simplejson.dumps({'name': 'name of project'}),
            content_type="application/json"
        )
        self.assertEquals(res.status_code, 404)
        res = self.client['maintainer'].post(
            self.url_projects, simplejson.dumps({
                'slug': 'foo', 'name': 'Foo Project',
                'source_language_code': 'en',
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)
        res = self.client['registered'].put(
            self.url_project, data=simplejson.dumps({}),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 403)
        user = User.objects.get(username='registered')
        user.user_permissions.add(
            Permission.objects.get(codename="change_project")
        )
        res = self.client['registered'].put(
            self.url_project,
            data=simplejson.dumps({'foo': 'foo'}),
            content_type='application/json'
        )
        self.assertContains(res, "Field 'foo'", status_code=400)
        res = self.client['registered'].put(
            self.url_project, data=simplejson.dumps({}),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 200)
        name = 'New name for foo'
        res = self.client['registered'].put(
            self.url_project,
            data=simplejson.dumps({'name': name}),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 200)
        p_foo = Project.objects.get(slug="foo")
        self.assertEquals(p_foo.name, name)
        res = self.client['registered'].put(
            self.url_project,
            data=simplejson.dumps({'outsource': "foo"}),
            content_type='application/json'
        )
        self.assertContains(res, "Original and outsource projects are the same", status_code=400)
        res = self.client['registered'].put(
            self.url_project,
            data=simplejson.dumps({'outsource': "bar"}),
            content_type='application/json'
        )
        self.assertContains(res, "Project for outsource does not exist", status_code=400)
        res = self.client['registered'].put(
            self.url_project,
            data=simplejson.dumps({'maintainers': 'none, not'}),
            content_type='application/json'
        )
        self.assertContains(res, "User", status_code=400)

        # update source language for project with no resources
        res = self.client['registered'].put(
            self.url_project,
            data=simplejson.dumps({'source_language_code': 'en'}),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 200)
        p_foo = Project.objects.get(slug="foo")
        self.assertEquals(p_foo.source_language.code, 'en')
        url = reverse(
            'apiv2_project', kwargs={'project_slug': self.project.slug}
        )
        res = self.client['registered'].put(
            url,
            data=simplejson.dumps({'source_language_code': 'en'}),
            content_type='application/json'
        )
        self.assertContains(
            res, "source language is not allowed", status_code=400
        )

    def test_project_validation(self):
        """Test that a project created through the API gets validated."""
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({
                'ab+cd': 'api_project', 'name': 'Project from API',
                'source_language_code': 'en_US'
            }),
            content_type='application/json'
        )
        self.assertContains(res, "'slug' is required", status_code=400)

    def test_delete(self):
        res = self.client['anonymous'].delete(self.url_project)
        self.assertEquals(res.status_code, 401)
        res = self.client['registered'].delete(self.url_projects)
        self.assertEquals(res.status_code, 403)
        user = User.objects.get(username='registered')
        user.user_permissions.add(
            Permission.objects.get(codename="delete_project")
        )
        res = self.client['registered'].delete(self.url_projects)
        self.assertEquals(res.status_code, 400)
        self.assertContains(res, "Project slug not specified", status_code=400)
        res = self.client['registered'].delete(self.url_project)
        self.assertEquals(res.status_code, 404)
        res = self.client['registered'].post(
            self.url_projects, simplejson.dumps({
                'slug': 'foo', 'name': 'Foo Project',
                'source_language_code': 'en'
            }),
            content_type='application/json'
        )
        self.assertEquals(res.status_code, 201)
        res = self.client['registered'].delete(self.url_project)
        self.assertEquals(res.status_code, 204)

    def _set_permissions(self, username='registered', perms=['change_project']):
        """Set the permissions for the user ``username`` to
        update a project.
        """
        user = User.objects.get(username=username)
        for perm in perms:
            user.user_permissions.add(
                Permission.objects.get(codename=perm)
            )

    def test_update_slug(self):
        """Test that updating the slug through the API is not allowed."""
        self._set_permissions()
        url = reverse(
            'apiv2_project', kwargs={'project_slug': self.project.slug}
        )
        res = self.client['registered'].put(
            url,
            data=simplejson.dumps({'slug': 'blah'}),
            content_type='application/json'
        )
        self.assertContains(
            res, "'slug' is not available", status_code=400
        )

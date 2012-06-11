# -*- coding: utf-8 -*-
import datetime
from django.db.models import get_model
from django.core.urlresolvers import reverse
from transifex.txcommon.tests import base

Resource = get_model('resources', 'Resource')
Release = get_model('releases', 'Release')

class ReleasesViewsTests(base.BaseTestCase):

    # Note: The Resource lookup field is tested in the resources app.

    def test_release_list(self):
        self.assertTrue(self.project.releases.all())

        # Anonymous and maintainer should see it
        resp = self.client['anonymous'].get(self.urls['project'])
        self.assertContains(resp, self.release.name)
        resp = self.client['maintainer'].get(self.urls['project'])
        self.assertContains(resp, self.release.name)

    def test_release_list_noreleases(self):
        self.project.releases.all().delete()

        # Maintainer should see things
        resp = self.client['maintainer'].get(self.urls['project'])
        self.assertContains(resp, "No releases are registered")

        # Anonymous should not see anything
        resp = self.client['anonymous'].get(self.urls['project'])
        self.assertNotContains(resp, "PROJECT RELEASES")

    def test_release_details_resources(self):
        """Test whether the right resources show up on details page."""
        resp = self.client['anonymous'].get(self.urls['release'])

        # The list at the top of the page should include this resource.
        self.assertContains(resp, "Test Project: Resource1")

        # One of the languages is totally untranslated.
        self.assertContains(resp, "Untranslated: %s" % self.resource.source_entities.count())

    def test_release_language_detail(self):
        """Test langauge detail for a release"""
        url = reverse('release_language_detail', args=[self.project.slug, self.release.slug, self.language_ar.code])
        resp = self.client['anonymous'].get(url)
        self.assertContains(resp,'50%', status_code=200)

    def test_release_create_good_private_resources(self):
        """Test Release creation with private resources.

        User with access to a private resource should be able to add it to a
        release.
        """

        resp = self.client['maintainer'].post(self.urls['release_create'],
            {'slug': 'nice-release', 'name': 'Nice Release',
            'project': self.project.id, 'resources': '|2|',
            'description': '', 'release_date': '', 'resources_text': '',
            'stringfreeze_date': '', 'homepage': '', 'long_description': '',
             'develfreeze_date': '', }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "projects/release_detail.html")

        # Test that a maintainer can see the private resource.
        resp = self.client['maintainer'].get(reverse('release_detail',
            args=[self.project.slug, 'nice-release']))
        self.assertContains(resp, "Release 'Nice Release'", status_code=200)
        self.assertContains(resp, "1 private resources you have access to.")
        self.assertContains(resp, "Portuguese (Brazilian)")

        # Priv proj member can see the private resource.
        resp = self.client['team_member'].get(reverse('release_detail',
            args=[self.project.slug, 'nice-release']))
        self.assertContains(resp, "Release 'Nice Release'", status_code=200)
        self.assertContains(resp, "1 private resources you have access to.")
        self.assertContains(resp, "Portuguese (Brazilian)")

        # Priv proj non-member cannot see the private resource.
        resp = self.client['registered'].get(reverse('release_detail',
            args=[self.project.slug, 'nice-release']))
        self.assertContains(resp, "Release 'Nice Release'", status_code=200)
        self.assertNotContains(resp, "private resources")
        self.assertNotContains(resp, "Portuguese (Brazilian)")

        # ...even if he is a member of the public project teams.
        resp = self.client['registered'].get(reverse('release_detail',
            args=[self.project.slug, 'nice-release']))
        self.team.members.add(self.user['registered'])
        self.assertTrue(self.user['registered'] in self.team.members.all())
        self.assertContains(resp, "Release 'Nice Release'", status_code=200)
        self.assertNotContains(resp, "private resources")
        self.assertNotContains(resp, "Portuguese (Brazilian)")


    def test_release_delete(self):
        """Test deleting a release"""
        resp = self.client['maintainer'].post(self.urls['release_create'],
            {'slug': 'nice-release', 'name': 'Nice Release',
            'project': self.project.id, 'resources': '|2|',
            'description': '', 'release_date': '', 'resources_text': '',
            'stringfreeze_date': '', 'homepage': '', 'long_description': '',
             'develfreeze_date': '', }, follow=True)
        self.assertEqual(resp.status_code, 200)
        release = Release.objects.get(slug='nice-release', project=self.project)
        url = reverse('release_delete', args=[self.project.slug, release.slug])
        resp = self.client['maintainer'].post(url, {}, follow=True)
        self.assertContains(resp, "was deleted.", status_code=200)

    def test_release_create_bad_private_resources(self):
        """Test Release creation with private resource w/o access.

        Public project release with a private resource I don't have access to.
        Use the registered user as the giunea pig.
        """
        self.project.maintainers.add(self.user['registered'])
        self.assertFalse(
            self.user['registered'] in self.project_private.maintainers.all()
        )
        r = self.client['registered'].post(self.urls['release_create'],
            {'slug': 'nice-release', 'name': 'Nice Release',
            'project': self.project.id, 'resources': '|2|',
            'description': '', 'release_date': '', 'resources_text': '',
            'stringfreeze_date': '', 'homepage': '', 'long_description': '',
             'develfreeze_date': '', }, follow=True)
        # The release shouldn't even be allowed to be created.
        self.assertRaises(
            Release.DoesNotExist, self.project.releases.get, slug='nice-release'
        )
        self.assertTemplateUsed(r, "projects/release_form.html")
        self.assertContains(r, "unaccessible private resource")

    def test_add_release_button_shown_on_project_deatils_page(self):
        response = self.client['maintainer'].get(self.urls['project'])
        self.assertContains(response, 'Add')
        self.assertContains(response, 'href="%sadd-release/"' % self.urls['project'])


class AllReleaseTests(base.BaseTestCase):
    """Test the All Release model."""

    def test_no_resource(self):
        self.project.resources.all().delete()
        self.assertEquals(self.project.releases.filter(slug='all-resources').count(), 0)

    def _create_new_resource(self):
        self.res2 = Resource.objects.create(
            slug="resource2", name="Resource2",
            project=self.project, source_language=self.language_en,
            i18n_type='PO')

    def test_first_resource(self):
        self.project.resources.all().delete()
        self._create_new_resource()
        self.assertTrue(self.res2 in
            self.project.releases.get(slug='all-resources').resources.all())

    def test_extra_resource(self):
        self._create_new_resource()
        rel_resources = self.project.releases.get(slug='all-resources').resources.all()
        self.assertTrue(self.resource in rel_resources)
        self.assertTrue(self.res2 in rel_resources)

    def test_extra_resource_deletion(self):
        self._create_new_resource()
        self.res2.delete()
        rel_resources = self.project.releases.get(slug='all-resources').resources.all()
        self.assertTrue(self.resource in rel_resources)
        self.assertFalse(self.res2 in rel_resources)

    def test_all_resources_deleted_no_all_release(self):
        self.resource.delete()
        self.assertFalse(self.project.releases.filter(slug='all-resources').count())

    def test_reserved_slug(self):
        resp = self.client['maintainer'].post('/projects/p/project1/add-release/', {'slug': 'all-resources', 'project': '1', 'name': 'test', })
        self.assertContains(resp, "value is reserved")
        # Still at the right URL
        self.assertContains(resp, "Add a release")

        resp = self.client['maintainer'].post('/projects/p/project1/add-release/', {'slug': 'foobar', 'project': '1', 'name': 'test', })
        self.assertNotContains(resp, "value is reserved")



class ReleaseFormDateFieldsTests(base.BaseTestCase):
    """
    Test the datetime field validations for the release form as well as the
    use of a custom widget for rendering the datetime fields.
    """

    url = reverse('release_create', args=['project1'])

    def setUp(self):
        super(ReleaseFormDateFieldsTests, self).setUp()
        self.data = {
            'slug': 'r1',
            'project': '1',
            'name': 'release',
        }

    def tearDown(self):
        super(ReleaseFormDateFieldsTests, self).tearDown()
        Release.objects.filter(slug='r1', project__id=1).delete()

    def test_release_date(self):
        """Test the release date field of release form."""
        now = datetime.datetime.now()
        release_date = {
            'release_date': now.strftime('%Y-%m-%d')
        }
        self.data.update(release_date)

        now = now + datetime.timedelta(days=1)
        develfreeze_date = {
            'develfreeze_date': now.strftime('%Y-%m-%d')
        }
        self.data.update(develfreeze_date)

        resp = self.client['maintainer'].post(self.url, self.data)
        self.assertContains(resp, "Release date must be after the Devel freeze date.")


    def test_develfreeze_date(self):
        """Test the devel freeze date field of release form."""
        # Update form data with develfreeze_date
        now = datetime.datetime.now()
        develfreeze_date = {
            'develfreeze_date': now.strftime('%Y-%m-%d')
        }
        self.data.update(develfreeze_date)

        now = now + datetime.timedelta(days=1)
        stringfreeze_date = {
            'stringfreeze_date': now.strftime('%Y-%m-%d')
        }
        self.data.update(stringfreeze_date)

        resp = self.client['maintainer'].post(self.url, self.data)
        self.assertContains(resp, "Devel freeze date must be after the String freeze date.")


from django.core.urlresolvers import reverse
from django.test.client import Client
from django.contrib.auth.models import User

from languages.models import Language
from transifex.teams.models import TeamRequest
from transifex.teams.models import Team
from txcommon.tests import base, utils

class TestTeams(base.BaseTestCase):

    def setUp(self):
        super(TestTeams, self).setUp()

    def test_team_list(self):
        url = reverse('team_list', args=[self.project.slug])
        resp = self.client['registered'].get(url)
        self.assertContains(resp, '(pt_BR)', status_code=200)

    def test_team_details(self):
        url = reverse('team_detail', args=[self.project.slug, self.language.code])
        resp = self.client['registered'].get(url)
        self.assertContains(resp, '(Brazilian)', status_code=200)

    def test_create_team(self):
        """Test a successful team creation."""
        url = reverse('team_create', args=[self.project.slug])
        # Testmaker POST data:
        # r = self.client.post('/projects/p/desktop-effects/teams/add/', {'language': '1', 'creator': '', 'mainlist': '', 'save_team': 'Save team', 'members_text': '', 'next': '', 'project': '20', 'coordinators': '|1|', 'coordinators_text': '', 'members': '|', 'csrfmiddlewaretoken': 'faac51cbc36b415e98599da53e798bd2', })
        DATA = {'language': self.language_ar.id,
                'project': self.project.id,
                'coordinators': '|%s|' % User.objects.all()[0].id,
                'members': '|',}
        resp = self.client['maintainer'].post(url, data=DATA, follow=True)
        self.assertContains(resp, 'Translation Teams - Arabic', status_code=200)
        self.assertNotContains(resp, 'Enter a valid value')

    def team_details_release(self):
        """Test releases appear correctly on team details page."""
        self.assertTrue(self.project.teams.all().count())
        url = reverse('team_detail', args=[self.project.slug, self.language.code])
        resp = self.client['team_member'].get(url)
        self.assertContains(resp, 'releaseslug', status_code=200)

    def test_team_request(self, lang_code=None):
        """Test creation of a team request"""
        url = reverse('team_request', args=[self.project.slug])
        if lang_code != None:
            language = Language.objects.get(code='ar')
        else:
            language = self.language_ar
        resp = self.client['registered'].post(url,
            {'language':language.id}, follow=True)
        self.assertContains(resp, "You requested creation of the &#39;%s&#39; team."%(language.name))
        self.assertEqual(resp.status_code, 200)

    def test_team_request_deny(self):
        """Test denial of a team request"""
        self.test_team_request()
        language = self.language_ar
        url = reverse('team_request_deny', args=[self.project.slug, language.code])
        resp = self.client['maintainer'].post(url, {"team_request_deny":"Deny"}, follow=True)
        self.assertContains(resp, 'You rejected the request by', status_code=200)

    def test_team_request_approve(self):
        """Test approval of a team request"""
        self.test_team_request()
        url = reverse('team_request_approve', args=[self.project.slug, self.language_ar.code])
        resp = self.client['maintainer'].post(url, {'team_request_approve':'Approve'}, follow=True)
        self.assertContains(resp, 'You approved the', status_code=200)

    def test_team_join_request(self):
        """Test joining request to a team"""
        url = reverse('team_join_request', args=[self.project.slug, self.language.code])
        DATA = {'team_join':'Join this Team'}
        resp = self.client['registered'].post(url, DATA, follow=True)
        self.assertContains(resp, 'You requested to join the', status_code=200)

    def test_team_join_approve(self):
        '''Test approval of a joining request to a team'''
        self.test_team_join_request()
        url = reverse('team_join_approve', args=[self.project.slug, self.language.code, 'registered'])
        DATA = {'team_join_approve':'Approve'}
        resp = self.client['team_coordinator'].post(url, DATA, follow=True)
        self.assertContains(resp, 'You added', status_code=200)

    def test_team_join_deny(self):
        """Test denial of a joining request to a team"""
        self.test_team_join_request()
        url = reverse('team_join_deny', args=[self.project.slug, self.language.code, 'registered'])
        DATA = {'team_join_deny':'Deny'}
        resp = self.client['team_coordinator'].post(url, DATA, follow=True)
        self.assertContains(resp, 'You rejected', status_code=200)

    def test_team_join_withdraw(self):
        """Test the withdrawal of a team join request by the user"""
        self.test_team_join_request()
        url = reverse('team_join_withdraw', args=[self.project.slug, self.language.code])
        DATA = {"team_join_withdraw" : "Withdraw"}
        resp = self.client['registered'].post(url, DATA, follow=True)
        self.assertContains(resp, 'You withdrew your request to join the', status_code=200)

    def test_team_leave(self):
        """Test leaving a team"""
        self.test_team_join_approve()
        url = reverse('team_leave', args=[self.project.slug, self.language.code])
        DATA = {'team_leave' : 'Leave'}
        resp = self.client['registered'].post(url, DATA, follow=True)
        self.assertContains(resp, 'You left the', status_code=200)

    def test_team_delete(self):
        """Test team delete """
        self.test_create_team()
        url = reverse('team_delete', args=[self.project.slug, self.language_ar.code])
        DATA = {'team_delete':"Yes, I'm sure!",}
        resp = self.client['maintainer'].post(url, DATA, follow=True)
        self.assertContains(resp, 'was deleted', status_code=200)

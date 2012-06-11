# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *
from django.conf import settings
from tagging.views import tagged_object_list

from transifex.projects.feeds import LatestProjects, ProjectFeed
from transifex.projects.models import Project
from transifex.projects.views import *
from transifex.projects.views.project import *
from transifex.projects.views.permission import *
from transifex.projects.views.team import *
from transifex.txcommon.decorators import one_perm_required_or_403
from transifex.urls import PROJECTS_URL

project_list = {
    'queryset': Project.objects.all(),
    'template_object_name': 'project',
}

public_project_list = {
    'queryset': Project.public.all(),
    'template_object_name': 'project',
    'extra_context' : {'type_of_qset' : 'projects.all',},
}

feeds = {
    'latest': LatestProjects,
    'project': ProjectFeed,
}

# Used only in urls already under projects/, such as this one and
# resources/urls.py. For addons, use PROJECT_URL instead.
PROJECT_URL_PARTIAL = '^p/(?P<project_slug>[-\w]+)/'

# Full URL (including /projects/ prefix). The ^ on ^p/ must be escaped.
PROJECT_URL = PROJECTS_URL + PROJECT_URL_PARTIAL[1:]

#TODO: Temporary until we import view from a common place
urlpatterns = patterns('',
    url(
        regex = r'^feed/$',
        view = 'projects.views.slug_feed',
        name = 'project_latest_feed',
        kwargs = {'feed_dict': feeds,
                  'slug': 'latest'}),
    url(
        regex = '^p/(?P<param>[-\w]+)/resources/feed/$',
        view = 'projects.views.project_feed',
        name = 'project_feed',
        kwargs = {'feed_dict': feeds,
                  'slug': 'project'}),
)


# Project
urlpatterns += patterns('',
    url(
        regex = '^myprojects/$',
        view = myprojects,
        name = 'myprojects'),
    url(
        regex = '^add/$',
        view = project_create,
        name = 'project_create'),
    url(
        regex = PROJECT_URL_PARTIAL+r'edit/$',
        view = project_update,
        name = 'project_edit',),
    url(
        regex = PROJECT_URL_PARTIAL+r'edit/access/$',
        view = project_access_control_edit,
        name = 'project_access_control_edit',),
    url(
        regex = PROJECT_URL_PARTIAL+r'delete/$',
        view = project_delete,
        name = 'project_delete',),
    url(
        regex = PROJECT_URL_PARTIAL+r'access/pm/add/$',
        view = project_add_permission,
        name = 'project_add_permission'),
    url(
        regex = PROJECT_URL_PARTIAL+r'access/pm/(?P<permission_pk>\d+)/delete/$',
        view = project_delete_permission,
        name = 'project_delete_permission'),
    #url(
        #regex = PROJECT_URL_PARTIAL+r'access/rq/add/$',
        #view = project_add_permission_request,
        #name = 'project_add_permission_request'),
    url(
        regex = PROJECT_URL_PARTIAL+r'access/rq/(?P<permission_pk>\d+)/delete/$',
        view = project_delete_permission_request,
        name = 'project_delete_permission_request'),

    url(regex = PROJECT_URL_PARTIAL+r'access/rq/(?P<permission_pk>\d+)/approve/$',
        view = project_approve_permission_request,
        name = "project_approve_permission_request"),
    url(
        regex = PROJECT_URL_PARTIAL+r'$',
        view = project_detail,
        name = 'project_detail'),
)


urlpatterns += patterns('django.views.generic',
    url(
        regex = '^$',
        view = 'list_detail.object_list',
        kwargs = public_project_list,
        name = 'project_list'),
    url(
        '^recent/$', 'list_detail.object_list',
        kwargs = {
            'queryset': Project.public.recent(),
            'template_object_name': 'project',
            'extra_context' : {'type_of_qset' : 'projects.recent',},
        },
        name = 'project_list_recent'),
    url (
        regex = '^open_translations/$',
        view = 'list_detail.object_list',
        kwargs = {
            'queryset': Project.public.open_translations(),
            'template_object_name': 'project',
            'extra_context' : {'type_of_qset' : 'projects.open_translations',},
        },
        name = 'project_list_open_translations'),
    url(
        r'^tag/(?P<tag>[^/]+)/$',
        tagged_object_list,
        dict(queryset_or_model=Project, allow_empty=True,
             template_object_name='project'),
        name='project_tag_list'),
)

# Teams

TEAM_URL = PROJECT_URL_PARTIAL + r'team/(?P<language_code>[\-_@\w\.]+)/'

urlpatterns += patterns('',
    url(
        regex = PROJECT_URL_PARTIAL+r'teams/add/$',
        view = team_create,
        name = 'team_create',),
    url(
        regex = TEAM_URL+r'edit/$',
        view = team_update,
        name = 'team_update',),
    url(
        regex = PROJECT_URL_PARTIAL+r'teams/$',
        view = team_list,
        name = 'team_list',),
    url(
        regex = TEAM_URL+r'$',
        view = team_detail,
        name = 'team_detail',),
    url(
        regex = TEAM_URL+r'delete/$',
        view = team_delete,
        name = 'team_delete',),
    url(
        regex = TEAM_URL+r'request/$',
        view = team_join_request,
        name = 'team_join_request',),
    url(
        regex = TEAM_URL+r'approve/(?P<username>[\.\-\w]+)/$',
        view = team_join_approve,
        name = 'team_join_approve',),
    url(
        regex = TEAM_URL+r'deny/(?P<username>[\.\-\w]+)/$',
        view = team_join_deny,
        name = 'team_join_deny',),
    url(
        regex = TEAM_URL+r'withdraw/$',
        view = team_join_withdraw,
        name = 'team_join_withdraw',),
    url(
        regex = TEAM_URL+r'leave/$',
        view = team_leave,
        name = 'team_leave',),
    url(
        regex = PROJECT_URL_PARTIAL+r'teams/request/$',
        view = team_request,
        name = 'team_request',),
    url(
        regex = TEAM_URL+r'approve/$',
        view = team_request_approve,
        name = 'team_request_approve',),
    url(
        regex = TEAM_URL+r'deny/$',
        view = team_request_deny,
        name = 'team_request_deny',),
)


# Resources
urlpatterns += patterns('',
    url('', include('resources.urls')),
    url('', include('releases.urls')),
)

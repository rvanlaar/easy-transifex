# -*- coding: utf-8 -*-
from django.core.urlresolvers import reverse
from django.db.models import Q, get_model
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.dispatch import Signal
from django.utils.translation import ugettext as _
from django.conf import settings
from django.views.generic import list_detail
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from actionlog.models import action_logging, LogEntry
from actionlog.filters import LogEntryFilter
from notification import models as notification
from transifex.projects.models import Project
from transifex.projects.forms import ProjectAccessControlForm, \
    ProjectForm, ProjectDeleteForm
from transifex.projects.permissions import *
from transifex.projects import signals

from transifex.languages.models import Language
from transifex.resources.models import RLStats
from transifex.resources.utils import invalidate_template_cache

# Temporary
from transifex.txcommon import notifications as txnotification

from transifex.txcommon.decorators import one_perm_required_or_403
from transifex.txcommon.log import logger
from transifex.txcommon.views import json_result, json_error
# To calculate user_teams
from transifex.teams.models import Team

Lock = get_model('locks', 'Lock')
TranslationWatch = get_model('watches', 'TranslationWatch')

def _project_create_update(request, project_slug=None,
    template_name='projects/project_form.html'):
    """
    Handler for creating and updating a project.

    This function helps to eliminate duplication of code between those two
    actions, and also allows to apply different permission checks in the
    respective views.
    """

    if project_slug:
        project = get_object_or_404(Project, slug=project_slug)
    else:
        project = None

    if request.method == 'POST':
        project_form = ProjectForm(request.POST, instance=project,
                                prefix='project')
        if project_form.is_valid():
            project = project_form.save(commit=False)
            project_id = project.id
            # Only here the owner is written to the project model
            if not project_id:
                project.owner = request.user

            # provide the form data to any signal handlers before project_save
            Signal.send(signals.pre_proj_save, sender=Project, instance=project,
                        form=project_form)
            project.save()
            project_form.save_m2m()

            # TODO: Not sure if here is the best place to put it
            Signal.send(signals.post_proj_save_m2m, sender=Project,
                        instance=project, form=project_form)

            # ActionLog & Notification
            context = {'project': project}
            if not project_id:
                nt = 'project_added'
                action_logging(request.user, [project], nt, context=context)
            else:
                nt = 'project_changed'
                action_logging(request.user, [project], nt, context=context)
                if settings.ENABLE_NOTICES:
                    txnotification.send_observation_notices_for(project,
                                        signal=nt, extra_context=context)

            return HttpResponseRedirect(reverse('project_detail',
                                        args=[project.slug]),)
    else:
        # Make the current user the maintainer when adding a project
        if project:
            initial_data = {}
        else:
            initial_data = {"maintainers": [request.user.pk]}

        project_form = ProjectForm(instance=project, prefix='project',
                                   initial=initial_data)

    return render_to_response(template_name, {
        'project_form': project_form,
        'project': project,
    }, context_instance=RequestContext(request))


# Projects
@login_required
@one_perm_required_or_403(pr_project_add)
def project_create(request):
    return _project_create_update(request)

@login_required
@one_perm_required_or_403(pr_project_add_change,
    (Project, 'slug__exact', 'project_slug'))
def project_update(request, project_slug):
        return _project_create_update(request, project_slug)


@login_required
@one_perm_required_or_403(pr_project_add_change,
    (Project, 'slug__exact', 'project_slug'))
def project_access_control_edit(request, project_slug):

    project = get_object_or_404(Project, slug=project_slug)
    if request.method == 'POST':
        access_control_form = ProjectAccessControlForm(request.POST,
            instance=project, user=request.user)
        if access_control_form.is_valid():
            access_control = access_control_form.cleaned_data['access_control']
            project = access_control_form.save()
            if 'free_for_all' == access_control:
                project.anyone_submit=True
            else:
                project.anyone_submit=False
            if 'outsourced_access' != access_control:
                project.outsource=None
            else:
                # TODO: Send notification for these projects, telling the
                # maintainers that the outsource project is not accepting
                # outsourcing anymore
                for p in project.project_set.all():
                    p.outsource=None
                    p.save()
            # Check if cla form exists before sending the signal
            if 'limited_access' == access_control and \
              access_control_form.cleaned_data.has_key('cla_license_text'):
                # send signal to save CLA
                signals.cla_create.send(
                    sender='project_access_control_edit_view',
                    project=project,
                    license_text=access_control_form.cleaned_data['cla_license_text'],
                    request=request
                )
            project.save()
            handle_stats_on_access_control_edit(project)
            return HttpResponseRedirect(request.POST['next'])
    else:
        access_control_form = ProjectAccessControlForm(instance=project,
            user=request.user)
    return render_to_response('projects/project_form_access_control.html', {
        'project_permission': True,
        'project': project,
        'project_access_control_form': access_control_form,
    }, context_instance=RequestContext(request))


def handle_stats_on_access_control_edit(project):
    """
    This function is called in the access_control_edit of a project and deals
    with add/remove of RLStats for existing teams based on whether the project
    is outsourced or not.
    """
    if project.outsource:
        # The project got outsourced. Create RLStats for all teams of the
        # master project
        teams = project.outsource.team_set.all()
        for resource in project.resources.all():
            new_stats = teams.exclude(language__in=RLStats.objects.filter(resource=resource).values(
                'language'))
            for stat in new_stats:
                RLStats.objects.get_or_create(resource=resource,
                    language=stat.language)
            invalidate_template_cache("project_resource_details",
                project.slug, resource.slug)
            invalidate_template_cache("resource_details",
                project.slug, resource.slug)
    else:
        teams = project.team_set.all()
        for resource in project.resources.all():
            old_stats = RLStats.objects.filter(Q(resource=resource) &
                Q(translated=0) & ~Q(language__in=teams.values('language')))
            for stat in old_stats:
                stat.delete()
            invalidate_template_cache("project_resource_details",
                project.slug, resource.slug)
            invalidate_template_cache("resource_details",
                project.slug, resource.slug)


def _delete_project(request, project):
    import copy
    project_ = copy.copy(project)
    project.delete()

    messages.success(request, _("The project '%s' was deleted." % project.name))

    # ActionLog & Notification
    nt = 'project_deleted'
    context = {'project': project_}
    action_logging(request.user, [project_], nt, context=context)
    if settings.ENABLE_NOTICES:
        txnotification.send_observation_notices_for(project_,
            signal=nt, extra_context=context)


@login_required
@one_perm_required_or_403(pr_project_delete,
    (Project, 'slug__exact', 'project_slug'))
def project_delete(request, project_slug):
    project = get_object_or_404(Project, slug=project_slug)
    if request.method == 'POST':
        delete_form = ProjectDeleteForm(data=request.POST, request=request)
        if delete_form.is_valid():
            _delete_project(request, project)
            return HttpResponseRedirect(reverse(getattr(settings,
                    "REDIRECT_AFTER_PROJECT_DELETE", "project_list")))
        else:
            return render_to_response('projects/project_delete.html', {
                'project': project,
                'delete_form': delete_form,
            }, context_instance=RequestContext(request))
    else:
        delete_form = ProjectDeleteForm(request=request)
        return render_to_response('projects/project_delete.html', {
            'project': project,
            'delete_form': delete_form,
        }, context_instance=RequestContext(request))


@one_perm_required_or_403(pr_project_private_perm,
    (Project, 'slug__exact', 'project_slug'), anonymous_access=True)
def project_detail(request, project_slug):
    project = get_object_or_404(Project.objects.select_related(), slug=project_slug)

    if not request.user.is_anonymous():
        user_teams = Team.objects.filter(project=project).filter(
             Q(coordinators=request.user)|
             Q(members=request.user)).distinct(),
    else:
        user_teams = []

    statslist = RLStats.objects.select_related(
        'resource', 'resource__project', 'resource__category',
        'last_committer', 'resource__priority'
    ).by_project_aggregated(project)

    return list_detail.object_detail(
        request,
        queryset = Project.objects.for_user(request.user),
        object_id=project.id,
        template_object_name = 'project',
        extra_context= {
          'project_overview': True,
          'user_teams': user_teams,
          'languages': Language.objects.all(),
          'statslist': statslist,
        })

@login_required
def myprojects(request):
    user = request.user

    maintain = Project.objects.maintained_by(user)
    submit_projects = Project.objects.translated_by(user)
    watched_projects = Project.get_watched(user)
    watched_resource_translations = TranslationWatch.get_watched(user)
    locks = Lock.objects.valid().filter(owner=user)

    context_var = {
        'maintain_projects': maintain,
        'submit_project_permissions': submit_projects,
        'watched_projects': watched_projects,
        'watched_resource_translations': watched_resource_translations,
        'locks': locks,
        'coordinator_teams': user.team_coordinators.all(),
        'member_teams': user.team_members.all(),
    }

    return render_to_response("projects/project_myprojects.html",
            context_var,
            context_instance = RequestContext(request))




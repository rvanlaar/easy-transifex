# -*- coding: utf-8 -*-
import copy
import itertools
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.db import transaction
from django.dispatch import Signal
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils.translation import ugettext as _

from actionlog.models import action_logging
from transifex.languages.models import Language
from notification import models as notification
from transifex.projects.models import Project
from transifex.projects.permissions import *
from transifex.projects.signals import pre_team_request, pre_team_join, ClaNotSignedError
from transifex.resources.models import RLStats
from transifex.teams.forms import TeamSimpleForm, TeamRequestSimpleForm
from transifex.teams.models import Team, TeamAccessRequest, TeamRequest
# Temporary
from transifex.txcommon import notifications as txnotification

from transifex.txcommon.decorators import one_perm_required_or_403, access_off
from transifex.txcommon.log import logger


def team_off(request, project, *args, **kwargs):
    """
    This view is used by the decorator 'access_off' to redirect a user when
    a project outsources its teams or allow anyone to submit files.

    Usage: '@access_off(team_off)' in front on any team view.
    """
    return render_to_response('teams/team_off.html', {
        'project_team_page': True,
        'project': project,
    }, context_instance=RequestContext(request))


def _team_create_update(request, project_slug, language_code=None):
    """
    Handler for creating and updating a team of a project.

    This function helps to eliminate duplication of code between those two
    actions, and also allows to apply different permission checks in the
    respective views.
    """
    project = get_object_or_404(Project, slug=project_slug)
    team = None

    if language_code:
        try:
            team = Team.objects.get(project__pk=project.pk,
                language__code=language_code)
        except Team.DoesNotExist:
            pass

    if request.POST:
        form = TeamSimpleForm(project, language_code, request.POST, instance=team)
        form.data["creator"] = request.user.pk
        if form.is_valid():
            team=form.save(commit=False)
            team_id = team.id
            team.save()
            form.save_m2m()

            # Delete access requests for users that were added
            for member in itertools.chain(team.members.all(),
                team.coordinators.all()):
                tr = TeamAccessRequest.objects.get_or_none(team, member)
                if tr:
                    tr.delete()

            # ActionLog & Notification
            # TODO: Use signals
            if not team_id:
                nt = 'project_team_added'
            else:
                nt = 'project_team_changed'

            context = {'team': team}

            # Logging action
            action_logging(request.user, [project, team], nt, context=context)

            if settings.ENABLE_NOTICES:
                # Send notification for those that are observing this project
                txnotification.send_observation_notices_for(project,
                        signal=nt, extra_context=context)
                # Send notification for maintainers and coordinators
                from notification.models import NoticeType
                try:
                    notification.send(set(itertools.chain(project.maintainers.all(),
                        team.coordinators.all())), nt, context)
                except NoticeType.DoesNotExist:
                    pass

            return HttpResponseRedirect(reverse("team_detail",
                                        args=[project.slug, team.language.code]))
    else:
        form=TeamSimpleForm(project, language_code, instance=team)

    return render_to_response("teams/team_form.html",
                              {"project": project,
                               "team": team,
                               "project_team_form": form,
                               "project_team_page": True},
                                context_instance=RequestContext(request))


pr_team_add=(("granular", "project_perm.maintain"),)
@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_team_add,
    (Project, "slug__exact", "project_slug"))
def team_create(request, project_slug):
    return _team_create_update(request, project_slug)


pr_team_update=(("granular", "project_perm.coordinate_team"),)
@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_team_update,
    (Project, 'slug__exact', 'project_slug'),
    (Language, "code__exact", "language_code"))
def team_update(request, project_slug, language_code):
        return _team_create_update(request, project_slug, language_code)


@access_off(team_off)
@one_perm_required_or_403(pr_project_private_perm,
    (Project, 'slug__exact', 'project_slug'), anonymous_access=True)
def team_list(request, project_slug):

    project = get_object_or_404(Project, slug=project_slug)
    team_request_form = TeamRequestSimpleForm(project)

    return render_to_response("teams/team_list.html",
                              {"project": project,
                              "team_request_form": team_request_form,
                               "project_team_page": True, },
                               context_instance=RequestContext(request))

@access_off(team_off)
@one_perm_required_or_403(pr_project_private_perm,
    (Project, 'slug__exact', 'project_slug'), anonymous_access=True)
def team_detail(request, project_slug, language_code):

    project = get_object_or_404(Project.objects.select_related(), slug=project_slug)
    language = get_object_or_404(Language.objects.select_related(), code=language_code)
    team = get_object_or_404(Team.objects.select_related(), project__pk=project.pk,
        language__pk=language.pk)

    team_access_requests = TeamAccessRequest.objects.filter(team__pk=team.pk)

    if request.user.is_authenticated():
        user_access_request = request.user.teamaccessrequest_set.filter(
            team__pk=team.pk)
    else:
        user_access_request = None

    statslist = RLStats.objects.select_related('resource',
        'resource__priority').by_project_and_language(project, language)

    team_members = team.members.all()
    team_reviewers = team.reviewers.all()
    team_all = team_members | team_reviewers

    return render_to_response("teams/team_detail.html", {
        "project": project,
        "team": team,
        "team_members": team_members,
        "team_reviewers": team_reviewers,
        "team_all": team_all,
        "team_access_requests": team_access_requests,
        "user_access_request": user_access_request,
        "project_team_page": True,
        "statslist": statslist,
    }, context_instance=RequestContext(request))


pr_team_delete=(("granular", "project_perm.maintain"),
                ("general",  "teams.delete_team"),)
@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_team_delete,
    (Project, "slug__exact", "project_slug"))
def team_delete(request, project_slug, language_code):

    project = get_object_or_404(Project, slug=project_slug)
    team = get_object_or_404(Team, project__pk=project.pk,
        language__code=language_code)

    if request.method == "POST":
        _team = copy.copy(team)
        team.delete()
        messages.success(request, _("The team '%s' was deleted.") % _team.language.name)

        # ActionLog & Notification
        # TODO: Use signals
        nt = 'project_team_deleted'
        context = {'team': _team}

        #Delete rlstats for this team in outsourced projects
        for p in project.project_set.all():
            RLStats.objects.select_related('resource').by_project_and_language(
                    p, _team.language).filter(translated=0).delete()

        # Logging action
        action_logging(request.user, [project, _team], nt, context=context)

        if settings.ENABLE_NOTICES:
            # Send notification for those that are observing this project
            txnotification.send_observation_notices_for(project,
                    signal=nt, extra_context=context)
            # Send notification for maintainers
            notification.send(project.maintainers.all(), nt, context)

        return HttpResponseRedirect(reverse("team_list",
                                     args=(project_slug,)))
    else:
        return render_to_response("teams/team_confirm_delete.html",
                                  {"team": team,},
                                  context_instance=RequestContext(request))


@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_project_private_perm,
    (Project, 'slug__exact', 'project_slug'))
@transaction.commit_on_success
def team_join_request(request, project_slug, language_code):

    team = get_object_or_404(Team, project__slug=project_slug,
        language__code=language_code)
    project = team.project

    if request.POST:
        if request.user in team.members.all() or \
            request.user in team.coordinators.all():
            messages.warning(request,
                          _("You are already on the '%s' team.") % team.language.name)
        try:
            # send pre_team_join signal
            cla_sign = 'cla_sign' in request.POST and request.POST['cla_sign']
            cla_sign = cla_sign and True
            pre_team_join.send(sender='join_team_view', project=project,
                               user=request.user, cla_sign=cla_sign)

            access_request = TeamAccessRequest(team=team, user=request.user)
            access_request.save()
            messages.success(request,
                _("You requested to join the '%s' team.") % team.language.name)
            # ActionLog & Notification
            # TODO: Use signals
            nt = 'project_team_join_requested'
            context = {'access_request': access_request}

            # Logging action
            action_logging(request.user, [project, team], nt, context=context)

            if settings.ENABLE_NOTICES:
                # Send notification for those that are observing this project
                txnotification.send_observation_notices_for(project,
                        signal=nt, extra_context=context)
                # Send notification for maintainers and coordinators
                notification.send(set(itertools.chain(project.maintainers.all(),
                    team.coordinators.all())), nt, context)


        except IntegrityError:
            transaction.rollback()
            messages.error(request,
                            _("You already requested to join the '%s' team.")
                             % team.language.name)
        except ClaNotSignedError, e:
            messages.error(request,
                             _("You need to sign the Contribution License Agreement for this "\
                "project before you join a translation team"))


    return HttpResponseRedirect(reverse("team_detail",
                                        args=[project_slug, language_code]))



pr_team_add_member_perm=(("granular", "project_perm.coordinate_team"),)
@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_team_add_member_perm,
    (Project, "slug__exact", "project_slug"),
    (Language, "code__exact", "language_code"))
@transaction.commit_on_success
def team_join_approve(request, project_slug, language_code, username):

    team = get_object_or_404(Team, project__slug=project_slug,
        language__code=language_code)
    project = team.project
    user = get_object_or_404(User, username=username)
    access_request = get_object_or_404(TeamAccessRequest, team__pk=team.pk,
        user__pk=user.pk)

    if request.POST:
        if user in team.members.all() or \
            user in team.coordinators.all():
            messages.warning(request,
                            _("User '%(user)s' is already on the '%(team)s' team.")
                            % {'user':user, 'team':team.language.name})
            access_request.delete()
        try:
            team.members.add(user)
            team.save()
            messages.success(request,
                            _("You added '%(user)s' to the '%(team)s' team.")
                            % {'user':user, 'team':team.language.name})
            access_request.delete()

            # ActionLog & Notification
            # TODO: Use signals
            nt = 'project_team_join_approved'
            context = {'access_request': access_request}

            # Logging action
            action_logging(request.user, [project, team], nt, context=context)

            if settings.ENABLE_NOTICES:
                # Send notification for those that are observing this project
                txnotification.send_observation_notices_for(project,
                        signal=nt, extra_context=context)
                # Send notification for maintainers, coordinators and the user
                notification.send(set(itertools.chain(project.maintainers.all(),
                    team.coordinators.all(), [access_request.user])), nt, context)

        except IntegrityError, e:
            transaction.rollback()
            logger.error("Something weird happened: %s" % str(e))

    return HttpResponseRedirect(reverse("team_detail",
                                        args=[project_slug, language_code]))


pr_team_deny_member_perm=(("granular", "project_perm.coordinate_team"),)
@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_team_deny_member_perm,
    (Project, "slug__exact", "project_slug"),
    (Language, "code__exact", "language_code"))
@transaction.commit_on_success
def team_join_deny(request, project_slug, language_code, username):

    team = get_object_or_404(Team, project__slug=project_slug,
        language__code=language_code)
    project = team.project
    user = get_object_or_404(User, username=username)
    access_request = get_object_or_404(TeamAccessRequest, team__pk=team.pk,
        user__pk=user.pk)

    if request.POST:
        try:
            access_request.delete()
            messages.info(request,_(
                "You rejected the request by user '%(user)s' to join the "
                "'%(team)s' team."
                ) % {'user':user, 'team':team.language.name})

            # ActionLog & Notification
            # TODO: Use signals
            nt = 'project_team_join_denied'
            context = {'access_request': access_request,
                       'performer': request.user,}

            # Logging action
            action_logging(request.user, [project, team], nt, context=context)

            if settings.ENABLE_NOTICES:
                # Send notification for those that are observing this project
                txnotification.send_observation_notices_for(project,
                        signal=nt, extra_context=context)
                # Send notification for maintainers, coordinators and the user
                notification.send(set(itertools.chain(project.maintainers.all(),
                    team.coordinators.all(), [access_request.user])), nt, context)

        except IntegrityError, e:
            transaction.rollback()
            logger.error("Something weird happened: %s" % str(e))

    return HttpResponseRedirect(reverse("team_detail",
                                        args=[project_slug, language_code]))

@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_project_private_perm,
    (Project, 'slug__exact', 'project_slug'))
@transaction.commit_on_success
def team_join_withdraw(request, project_slug, language_code):

    team = get_object_or_404(Team, project__slug=project_slug,
        language__code=language_code)
    project = team.project
    access_request = get_object_or_404(TeamAccessRequest, team__pk=team.pk,
        user__pk=request.user.pk)

    if request.POST:
        try:
            access_request.delete()
            messages.success(request,_(
                "You withdrew your request to join the '%s' team."
                ) % team.language.name)

            # ActionLog & Notification
            # TODO: Use signals
            nt = 'project_team_join_withdrawn'
            context = {'access_request': access_request,
                       'performer': request.user,}

            # Logging action
            action_logging(request.user, [project, team], nt, context=context)

            if settings.ENABLE_NOTICES:
                # Send notification for those that are observing this project
                txnotification.send_observation_notices_for(project,
                        signal=nt, extra_context=context)
                # Send notification for maintainers, coordinators
                notification.send(set(itertools.chain(project.maintainers.all(),
                    team.coordinators.all())), nt, context)

        except IntegrityError, e:
            transaction.rollback()
            logger.error("Something weird happened: %s" % str(e))

    return HttpResponseRedirect(reverse("team_detail",
                                        args=[project_slug, language_code]))

@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_project_private_perm,
    (Project, 'slug__exact', 'project_slug'))
@transaction.commit_on_success
def team_leave(request, project_slug, language_code):

    team = get_object_or_404(Team, project__slug=project_slug,
        language__code=language_code)
    project = team.project

    if request.POST:
        try:
            if request.user in team.members.all():
                team.members.remove(request.user)
                messages.info(request, _(
                    "You left the '%s' team."
                    ) % team.language.name)

                # ActionLog & Notification
                # TODO: Use signals
                nt = 'project_team_left'
                context = {'team': team,
                        'performer': request.user,}

                # Logging action
                action_logging(request.user, [project, team], nt, context=context)

                if settings.ENABLE_NOTICES:
                    # Send notification for those that are observing this project
                    txnotification.send_observation_notices_for(project,
                            signal=nt, extra_context=context)
                    # Send notification for maintainers, coordinators
                    notification.send(set(itertools.chain(project.maintainers.all(),
                        team.coordinators.all())), nt, context)
            else:
                messages.info(request, _(
                    "You are not in the '%s' team."
                    ) % team.language.name)

        except IntegrityError, e:
            transaction.rollback()
            logger.error("Something weird happened: %s" % str(e))

    return HttpResponseRedirect(reverse("team_detail",
                                        args=[project_slug, language_code]))


# Team Creation
@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_project_private_perm,
    (Project, 'slug__exact', 'project_slug'))
@transaction.commit_on_success
def team_request(request, project_slug):

    if request.POST:
        language_pk = request.POST.get('language', None)
        if not language_pk:
            messages.error(request, _(
                "Please select a language before submitting the form."))
            return HttpResponseRedirect(reverse("team_list",
                                        args=[project_slug,]))


        project = get_object_or_404(Project, slug=project_slug)

        language = get_object_or_404(Language, pk=int(language_pk))

        try:
            team = Team.objects.get(project__pk=project.pk,
                language__pk=language.pk)
            messages.warning(request,_(
                "'%s' team already exists.") % team.language.name)
        except Team.DoesNotExist:
            try:
                team_request = TeamRequest.objects.get(project__pk=project.pk,
                    language__pk=language.pk)
                messages.warning(request, _(
                    "A request to create the '%s' team already exists.")
                    % team_request.language.name)
            except TeamRequest.DoesNotExist:
                try:
                    # send pre_team_request signal
                    cla_sign = 'cla_sign' in request.POST and \
                            request.POST['cla_sign']
                    cla_sign = cla_sign and True
                    pre_team_request.send(sender='request_team_view',
                                          project=project,
                                          user=request.user,
                                          cla_sign=cla_sign)

                    team_request = TeamRequest(project=project,
                        language=language, user=request.user)
                    team_request.save()
                    messages.info(request, _(
                        "You requested creation of the '%s' team.")
                        % team_request.language.name)

                    # ActionLog & Notification
                    # TODO: Use signals
                    nt = 'project_team_requested'
                    context = {'team_request': team_request}

                    # Logging action
                    action_logging(request.user, [project], nt, context=context)

                    if settings.ENABLE_NOTICES:
                        # Send notification for those that are observing this project
                        txnotification.send_observation_notices_for(project,
                                signal=nt, extra_context=context)
                        # Send notification for maintainers
                        notification.send(project.maintainers.all(), nt, context)

                except IntegrityError, e:
                    transaction.rollback()
                    logger.error("Something weird happened: %s" % str(e))
                except ClaNotSignedError, e:
                    messages.error(request, _(
                        "You need to sign the Contribution License Agreement "\
                        "for this project before you submit a team creation "\
                        "request."
                    ))

    return HttpResponseRedirect(reverse("team_list", args=[project_slug,]))


pr_team_request_approve=(("granular", "project_perm.maintain"),)
@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_team_request_approve,
    (Project, "slug__exact", "project_slug"),)
@transaction.commit_on_success
def team_request_approve(request, project_slug, language_code):

    team_request = get_object_or_404(TeamRequest, project__slug=project_slug,
        language__code=language_code)
    project = team_request.project

    if request.POST:
        try:
            team = Team(project=team_request.project,
                language=team_request.language, creator=request.user)
            team.save()
            team.coordinators.add(team_request.user)
            team.save()
            team_request.delete()
            messages.success(request, _(
                "You approved the '%(team)s' team requested by '%(user)s'."
                ) % {'team':team.language.name, 'user':team_request.user})

            # ActionLog & Notification
            # TODO: Use signals
            nt = 'project_team_added'
            context = {'team': team}

            # Logging action
            action_logging(request.user, [project, team], nt, context=context)

            if settings.ENABLE_NOTICES:
                # Send notification for those that are observing this project
                txnotification.send_observation_notices_for(project,
                        signal=nt, extra_context=context)
                # Send notification for maintainers and coordinators
                notification.send(set(itertools.chain(project.maintainers.all(),
                    team.coordinators.all())), nt, context)

        except IntegrityError, e:
            transaction.rollback()
            logger.error("Something weird happened: %s" % str(e))

    return HttpResponseRedirect(reverse("team_list",
                                        args=[project_slug,]))


pr_team_request_deny=(("granular", "project_perm.maintain"),)
@access_off(team_off)
@login_required
@one_perm_required_or_403(pr_team_request_deny,
    (Project, "slug__exact", "project_slug"),)
@transaction.commit_on_success
def team_request_deny(request, project_slug, language_code):

    team_request = get_object_or_404(TeamRequest, project__slug=project_slug,
        language__code=language_code)
    project = team_request.project

    if request.POST:
        try:
            team_request.delete()
            messages.success(request, _(
                "You rejected the request by '%(user)s' for a '%(team)s' team."
                ) % {'team':team_request.language.name,
                     'user':team_request.user})

            # ActionLog & Notification
            # TODO: Use signals
            nt = 'project_team_request_denied'
            context = {'team_request': team_request,
                       'performer': request.user}

            # Logging action
            action_logging(request.user, [project], nt, context=context)

            if settings.ENABLE_NOTICES:
                # Send notification for those that are observing this project
                txnotification.send_observation_notices_for(project,
                        signal=nt, extra_context=context)
                # Send notification for maintainers and the user
                notification.send(set(itertools.chain(project.maintainers.all(),
                    [team_request.user])), nt, context)

        except IntegrityError, e:
            transaction.rollback()
            logger.error("Something weird happened: %s" % str(e))

    return HttpResponseRedirect(reverse("team_list",
                                        args=[project_slug,]))


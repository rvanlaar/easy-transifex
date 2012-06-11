# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.db import transaction, DatabaseError, IntegrityError
from django.http import HttpResponse, HttpResponseServerError
from django.utils import simplejson
from django.utils.translation import ugettext_lazy as _
from django.template.defaultfilters import slugify

from piston.handler import BaseHandler
from piston.utils import rc, throttle, require_mime

from transifex.actionlog.models import action_logging
from transifex.languages.models import Language
from transifex.projects.models import Project
from transifex.projects.permissions import *
from transifex.projects.permissions.project import ProjectPermission
from transifex.projects.signals import post_submit_translation, post_resource_save
from transifex.resources.decorators import method_decorator
from transifex.resources.formats.registry import registry
from transifex.resources.handlers import get_project_teams
from transifex.resources.models import *
from transifex.storage.models import StorageFile
from transifex.teams.models import Team
from transifex.txcommon.log import logger
from transifex.txcommon.decorators import one_perm_required_or_403
from transifex.txcommon.utils import paginate
from transifex.api.utils import BAD_REQUEST
from uuid import uuid4

# Temporary
from transifex.txcommon import notifications as txnotification


class ProjectHandler(BaseHandler):
    """
    API handler for model Project.
    """
    allowed_methods = ('GET','POST','PUT','DELETE')
    details_fields = (
        'slug', 'name', 'description', 'long_description', 'homepage', 'feed',
        'created', 'anyone_submit', 'bug_tracker', 'trans_instructions',
        'tags', 'outsource', ('maintainers', ('username', )),
        ('owner', ('username', )), ('resources', ('slug', 'name', )),
        'teams', 'source_language_code',
    )
    default_fields = ('slug', 'name', 'description', 'source_language_code', )
    fields = default_fields
    allowed_fields = (
        'name', 'slug', 'description', 'long_description', 'private',
        'homepage', 'feed', 'anyone_submit', 'hidden', 'bug_tracker',
        'trans_instructions', 'tags', 'maintainers', 'outsource',
        'source_language_code',
    )
    exclude = ()

    @classmethod
    def source_language_code(cls, p):
        """Add the source language as a field."""
        return p.source_language.code

    @classmethod
    def teams(cls, p):
        """Show the language codes for which there are teams as list.

        Return an empty list in case there are no teams defined.
        """
        team_set = get_project_teams(p)
        return team_set.values_list('language__code', flat=True)

    def read(self, request, project_slug=None, api_version=1):
        """
        Get project details in json format
        """
        # Reset fields to default value
        ProjectHandler.fields = ProjectHandler.default_fields
        if api_version == 2:
            if "details" in request.GET.iterkeys():
                if project_slug is None:
                    return rc.NOT_IMPLEMENTED
                ProjectHandler.fields = ProjectHandler.details_fields
        else:
            ProjectHandler.fields = ProjectHandler.details_fields
        return self._read(request, project_slug)

    @require_mime('json')
    @method_decorator(one_perm_required_or_403(pr_project_add))
    def create(self, request, project_slug=None, api_version=1):
        """
        API call to create new projects via POST.
        """
        data = getattr(request, 'data', None)
        if api_version == 2:
            if project_slug is not None:
                return BAD_REQUEST("POSTing to this url is not allowed.")
            if data is None:
                return BAD_REQUEST(
                    "At least parameters 'slug', 'name' and "
                    "'source_language' are needed."
                )
            return self._create(request, data)
        else:
            return self._createv1(request, data)

    @require_mime('json')
    @method_decorator(one_perm_required_or_403(pr_project_add_change,
        (Project, 'slug__exact', 'project_slug')))
    def update(self, request, project_slug, api_version=1):
        """
        API call to update project details via PUT.
        """
        if project_slug is None:
            return BAD_REQUEST("Project slug not specified.")
        data = request.data
        if data is None:
            return BAD_REQUEST("Empty request.")
        if api_version == 2:
            return self._update(request, project_slug, data)
        else:
            return self._updatev1(request, project_slug, data)

    @method_decorator(one_perm_required_or_403(pr_project_delete,
        (Project, 'slug__exact', 'project_slug')))
    def delete(self, request, project_slug=None, api_version=1):
        """
        API call to delete projects via DELETE.
        """
        if project_slug is None:
            return BAD_REQUEST("Project slug not specified.")
        return self._delete(request, project_slug)

    def _read(self, request, project_slug):
        """
        Return a list of projects or the details for a specific project.
        """
        if project_slug is None:
            # Use pagination
            p = Project.objects.for_user(request.user)
            res, msg = paginate(
                p, request.GET.get('start'), request.GET.get('end')
            )
            if res is None:
                return BAD_REQUEST(msg)
            return res
        else:
            try:
                p = Project.objects.get(slug=project_slug)
                perm = ProjectPermission(request.user)
                if not perm.private(p):
                    return rc.FORBIDDEN
            except Project.DoesNotExist:
                return rc.NOT_FOUND
            return p

    def _create(self, request, data):
        """
        Create a new project.
        """
        mandatory_fields = ('slug', 'name', 'source_language_code', )
        msg = "Field '%s' is required to create a project."
        for field in mandatory_fields:
            if field not in data:
                return BAD_REQUEST(msg % field)
        if 'owner' in data:
            return BAD_REQUEST("Owner cannot be set explicitly.")

        try:
            self._check_fields(data.iterkeys())
        except AttributeError, e:
            return BAD_REQUEST("Field '%s' is not available." % e.message)

        # outsource and maintainers are ForeignKey
        outsource = data.pop('outsource', {})
        maintainers = data.pop('maintainers', {})

        lang = data.pop('source_language_code')
        try:
            source_language = Language.objects.by_code_or_alias(lang)
        except Language.DoesNotExist:
            return BAD_REQUEST("Language %s does not exist." % lang)

        try:
            p = Project(**data)
            p.source_language = source_language
        except Exception:
            return BAD_REQUEST("Invalid arguments given.")
        try:
            p.full_clean()
        except ValidationError, e:
            return BAD_REQUEST("%s" % e)
        try:
            p.save()
        except IntegrityError:
            return rc.DUPLICATE_ENTRY

        p.owner = request.user
        if outsource:
            try:
                outsource_project = Project.objects.get(slug=outsource)
            except Project.DoesNotExist:
                p.delete()
                return BAD_REQUEST("Project for outsource does not exist.")
            p.outsource = outsource_project

        if maintainers:
            for user in maintainers.split(','):
                try:
                    u = User.objects.get(username=user)
                except User.DoesNotExist:
                    p.delete()
                    return BAD_REQUEST("User %s does not exist." % user)
                p.maintainers.add(u)
        else:
            p.maintainers.add(p.owner)
        p.save()
        return rc.CREATED

    def _createv1(self, request, data):
        """
        Create a new project following the v1 API.
        """
        outsource = data.pop('outsource', {})
        maintainers = data.pop('maintainers', {})
        lang = data.pop('source_language', 'en')
        try:
            source_language = Language.objects.by_code_or_alias(lang)
        except Language.DoesNotExist:
            return BAD_REQUEST("Language %s does not exist." % lang)
        try:
            p, created = Project.objects.get_or_create(
                source_language=source_language, **data)
        except:
            return BAD_REQUEST("Project not found")

        if created:
            # Owner
            p.owner = request.user

            # Outsourcing
            if outsource:
                try:
                    outsource_project = Project.objects.get(slug=outsource)
                except Project.DoesNotExist:
                    # maybe fail when wrong user is given?
                    pass
                p.outsource = outsource_project

            # Handler m2m with maintainers
            if maintainers:
                for user in maintainers.split(','):
                    try:
                        p.maintainers.add(User.objects.get(username=user))
                    except User.DoesNotExist:
                        # maybe fail when wrong user is given?
                        pass
            else:
                p.maintainers.add(p.owner)

            try:
                p.full_clean()
            except ValidationError, e:
                return BAD_REQUEST("%s" % e)
            p.save()

            return rc.CREATED
        else:
            return BAD_REQUEST("Unsupported request")

    def _update(self, request, project_slug, data):
        try:
            self._check_fields(data.iterkeys(), extra_exclude=['slug'])
        except AttributeError, e:
            return BAD_REQUEST("Field '%s' is not available." % e)

        outsource = data.pop('outsource', {})
        maintainers = data.pop('maintainers', {})
        try:
            p = Project.objects.get(slug=project_slug)
        except Project.DoesNotExist:
            return BAD_REQUEST("Project not found")

        lang = data.pop('source_language_code', None)
        if lang is not None:
            try:
                source_language = Language.objects.by_code_or_alias(lang)
            except Language.DoesNotExist:
                return BAD_REQUEST('Specified source language does not exist.')
            if p.resources.count() == 0:
                p.source_language = source_language
            else:
                msg = (
                    "The project has resources. Changing its source "
                    "language is not allowed."
                )
                return BAD_REQUEST(msg)

        try:
            for key,value in data.items():
                setattr(p, key,value)

            # Outsourcing
            if outsource:
                if outsource == p.slug:
                    return BAD_REQUEST("Original and outsource projects are the same.")
                try:
                    outsource_project = Project.objects.get(slug=outsource)
                except Project.DoesNotExist:
                    return BAD_REQUEST("Project for outsource does not exist.")
                p.outsource = outsource_project

            # Handler m2m with maintainers
            if maintainers:
                # remove existing maintainers and add new ones
                p.maintainers.clear()
                for user in maintainers.split(','):
                    try:
                        p.maintainers.add(User.objects.get(username=user))
                    except User.DoesNotExist:
                        return BAD_REQUEST("User %s does not exist." % user)
            p.save()
        except Exception, e:
            return BAD_REQUEST("Error parsing request data: %s" % e)
        return rc.ALL_OK

    def _updatev1(self, request, project_slug, data):
        """
        Update a project per API v1.
        """
        outsource = data.pop('outsource', {})
        maintainers = data.pop('maintainers', {})
        try:
            p = Project.objects.get(slug=project_slug)
        except Project.DoesNotExist:
            return BAD_REQUEST("Project not found")
        try:
            for key,value in data.items():
                if key == 'slug':
                    continue
                setattr(p, key,value)
                # Outsourcing
            if outsource:
                if outsource == p.slug:
                    return BAD_REQUEST("Original and outsource projects are the same.")
                try:
                    outsource_project = Project.objects.get(slug=outsource)
                except Project.DoesNotExist:
                    # maybe fail when wrong user is given?
                    pass
                p.outsource = outsource_project

            # Handler m2m with maintainers
            if maintainers:
                # remove existing maintainers
                p.maintainers.all().clear()
                # add then all anew
                for user in maintainers.split(','):
                    try:
                        p.maintainers.add(User.objects.get(username=user))
                    except User.DoesNotExist:
                        # maybe fail when wrong user is given?
                        pass
            p.save()
        except Exception, e:
            return BAD_REQUEST("Error parsing request data: %s" % e)
        return rc.ALL_OK

    def _delete(self, request, project_slug):
        try:
            project = Project.objects.get(slug=project_slug)
        except Project.DoesNotExist:
            return rc.NOT_FOUND
        try:
            project.delete()
        except:
            return rc.INTERNAL_ERROR
        return rc.DELETED

    def _check_fields(self, fields, extra_exclude=[]):
        """
        Check if supplied fields are allowed to be given in a
        POST or PUT request.

        Args:
            fields: An iterable of fields to check.
            extra_exclude: A list of fields that should not be used.
        Raises:
            AttributeError, in case a field is not in the allowed fields
                or is in the ``extra_exclude`` list.
        """
        for field in fields:
            if field not in self.allowed_fields or field in extra_exclude:
                raise AttributeError(field)


class ProjectResourceHandler(BaseHandler):
    """
    API handler for creating resources under projects
    """

    allowed_methods = ('POST', 'PUT')

    @throttle(settings.API_MAX_REQUESTS, settings.API_THROTTLE_INTERVAL)
    @method_decorator(one_perm_required_or_403(pr_resource_add_change,
        (Project, 'slug__exact', 'project_slug')))
    @transaction.commit_manually
    def create(self, request, project_slug, api_version=1):
        """
        Create resource for project by UUID of StorageFile.
        """
        if "application/json" in request.content_type:
            if "uuid" in request.data:
                uuid = request.data['uuid']
                project = Project.objects.get(slug=project_slug)
                try:
                    storagefile = StorageFile.objects.get(uuid=uuid)
                except StorageFile.DoesNotExist, e:
                    transaction.rollback()
                    return BAD_REQUEST("Specified uuid is invalid.")
                resource_slug = None
                if "slug" in request.data:
                    resource_slug = request.data['slug']
                    if len(resource_slug) > 51:
                        transaction.rollback()
                        return BAD_REQUEST("Resouce slug is too long "
                            "(Max. 50 chars).")

                slang = project.source_language
                if slang is not None and storagefile.language != slang:
                    return BAD_REQUEST(
                        "You have to use %s for source language" % slang
                    )

                try:
                    resource, created = Resource.objects.get_or_create(
                        slug = resource_slug or slugify(storagefile.name),
                        source_language = storagefile.language,
                        project = project
                    )
                except DatabaseError, e:
                    transaction.rollback()
                    logger.error(e.message, exc_info=True)
                    return BAD_REQUEST(e.message)
                except IntegrityError, e:
                    transaction.rollback()
                    logger.error(e.message, exc_info=True)
                    return BAD_REQUEST(e.message)

                if created:
                    resource.name = resource_slug or storagefile.name
                    resource.save()
                    # update i18n_type
                    i18n_type = registry.guess_method(storagefile.get_storage_path())
                    if not i18n_type:
                        transaction.rollback()
                        return BAD_REQUEST("File type not supported.")
                    resource.i18n_method = i18n_type
                    resource.save()
                else:
                    i18n_type = resource.i18n_method

                # Set StorageFile to 'bound' status, which means that it is
                # bound to some translation resource
                storagefile.bound = True
                storagefile.save()

                logger.debug("Going to insert strings from %s (%s) to %s/%s" %
                    (storagefile.name, storagefile.uuid, project.slug,
                    resource.slug))

                strings_added, strings_updated = 0, 0
                fhandler = storagefile.find_parser()
                fhandler.bind_file(filename=storagefile.get_storage_path())
                fhandler.bind_resource(resource)
                fhandler.set_language(storagefile.language)

                try:
                    fhandler.is_content_valid()
                    fhandler.parse_file(True)
                    strings_added, strings_updated = fhandler.save2db(True,
                        user=request.user)
                except Exception, e:
                    transaction.rollback()
                    return BAD_REQUEST("Resource not created. Could not "
                        "import file: %s" % e)
                else:
                    messages = []
                    if strings_added > 0:
                        messages.append(_("%i strings added") % strings_added)
                    if strings_updated > 0:
                        messages.append(_("%i strings updated") % strings_updated)
                retval= {
                    'strings_added': strings_added,
                    'strings_updated': strings_updated,
                    'redirect': reverse('resource_detail',args=[project_slug,
                        resource.slug])
                    }
                logger.debug("Extraction successful, returning: %s" % retval)

                if created:
                    post_resource_save.send(sender=None, instance=resource,
                            created=created, user=request.user)

                # transaction has been commited by save2db
                # but logger message above marks it dirty again
                transaction.commit()

                return HttpResponse(simplejson.dumps(retval),
                    mimetype='text/plain')

            else:
                transaction.rollback()
                return BAD_REQUEST("Request data missing.")
        else:
            transaction.rollback()
            return BAD_REQUEST("Unsupported request")

    def update(self, request, project_slug, resource_slug, language_code=None, api_version=1):
        """
        Update resource translations of a project by the UUID of a StorageFile.
        """
        try:
            project = Project.objects.get(slug=project_slug)
            resource = Resource.objects.get(slug=resource_slug,
                project=project)
        except (Project.DoesNotExist, Resource.DoesNotExist):
            return rc.NOT_FOUND

        # Permissions handling
        team = Team.objects.get_or_none(project, language_code)
        check = ProjectPermission(request.user)
        if (not check.submit_translations(team or project) or\
            not resource.accept_translations) and not\
                check.maintain(project):
            return rc.FORBIDDEN

        if "application/json" in request.content_type:
            if "uuid" in request.data:
                uuid = request.data['uuid']
                storagefile = StorageFile.objects.get(uuid=uuid)
                language = storagefile.language

                logger.debug("Going to insert strings from %s (%s) to %s/%s" %
                    (storagefile.name, storagefile.uuid, project_slug,
                    resource.slug))

                strings_added, strings_updated = 0, 0
                fhandler = storagefile.find_parser()
                language = storagefile.language
                fhandler.bind_file(filename=storagefile.get_storage_path())
                fhandler.set_language(language)
                fhandler.bind_resource(resource)
                fhandler.is_content_valid()

                try:
                    fhandler.parse_file()
                    strings_added, strings_updated = fhandler.save2db(
                        user=request.user)
                except Exception, e:
                    logger.error(e.message, exc_info=True)
                    return BAD_REQUEST("Error importing file: %s" % e)
                else:
                    messages = []
                    if strings_added > 0:
                        messages.append(_("%i strings added") % strings_added)
                    if strings_updated > 0:
                        messages.append(_("%i strings updated") % strings_updated)
                retval= {
                    'strings_added':strings_added,
                    'strings_updated':strings_updated,
                    'redirect':reverse('resource_detail',args=[project_slug,
                        resource.slug])
                    }

                logger.debug("Extraction successful, returning: %s" % retval)

                # Set StorageFile to 'bound' status, which means that it is
                # bound to some translation resource
                storagefile.bound = True
                storagefile.save()

                # If any string added/updated
                if retval['strings_added'] > 0 or retval['strings_updated'] > 0:
                    modified = True
                else:
                    modified=False
                post_submit_translation.send(None, request=request,
                    resource=resource, language=language, modified=modified)

                return HttpResponse(simplejson.dumps(retval),
                    mimetype='application/json')
            else:
                return BAD_REQUEST("Missing request data.")
        else:
            return BAD_REQUEST("Unsupported request")

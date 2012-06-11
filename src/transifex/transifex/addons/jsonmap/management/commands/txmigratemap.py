import os, sys
from optparse import make_option

from django.conf import settings
from django.core.management.base import CommandError, BaseCommand
from django.db import models
from django.utils import simplejson

from transifex.txcommon.commands import run_command
from transifex.txcommon.log import logger

from autofetch.models import URLInfo
from jsonmap.models import JSONMap

class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('--force', '-f', action="store_true", default=False,
            dest='force',
            help="Force re-migration of previously migrated mappings."),
    )

    args = '<project_slug project_slug ...>'
    help = "Create resources based on a JSON formatted mapping."

    def handle(self, *args, **options):

        # OMG!1! Dirty fix for circular importing issues. Didn't want to dig
        # into it because it's probably not worth, once it's a tmp code.
        from transifex.resources.formats.registry import registry
        from transifex.resources.formats.pofile import POHandler
        from transifex.languages.models import Language
        from transifex.projects.models import Project
        from transifex.resources.models import Resource

        force = options.get('force')

        if settings.DEBUG:
            msg = "You are running this command with DEBUG=True. Please " \
                "change it to False in order to avoid problems with " \
                "allocating memory."
            raise CommandError(msg)

        msg = None
        if len(args) == 0:
            jsonmaps = JSONMap.objects.all()
        else:
            jsonmaps = JSONMap.objects.filter(project__slug__in=args)
            if not jsonmaps:
                msg = "No mapping found for given project slug(s): %s" % ', '.join(args)

        if not jsonmaps:
            raise CommandError(msg or "No mapping found in the database.")

        for jsonmap in jsonmaps:
            jm = jsonmap.loads(True)

            # Check whether the map was already migrated or not
            if jm['meta'].get('_migrated', None) and not force:
                logger.debug("Project '%s' was already migrated." % jsonmap.project)
                continue

            for r in jm['resources']:
                logger.debug("Pushing resource: %s" % r.get('resource_slug'))

                project = jsonmap.project

                # Path for cached files of project.component
                path = os.path.join(settings.MSGMERGE_DIR,
                    '%s.%s' % (project.slug, jsonmap.slug))

                if os.path.exists(path):

                    resource_slug = r['resource_slug']
                    language = Language.objects.by_code_or_alias_or_none(
                        r['source_lang'])

                    # Create resource and load source language
                    if language:
                        resource, created = Resource.objects.get_or_create(
                                slug = resource_slug,
                                source_language = language,
                                project = project)

                        if created:
                            resource.name = '%s - %s' % (jsonmap.slug,
                                r['source_file'])

                        source_file = os.path.join(path, r['source_file'])
                        resource.i18n_method = registry.guess_method(source_file)
                        resource.save()

                        resource.url_info = URLInfo(source_file_url=r['autofetch_url'])

                        logger.debug("Inserting source strings from %s (%s) to "
                            "'%s'." % (r['source_file'], language.code,
                            resource.full_name))

                        fhandler = POHandler(filename=source_file)
                        fhandler.bind_resource(resource)
                        fhandler.set_language(language)

                        try:
                            fhandler.is_content_valid()
                            fhandler.parse_file(True)
                            strings_added, strings_updated = fhandler.save2db(True)
                        except Exception, e:
                            resource.delete()
                            sys.stdout.write((u"Resource not created! Could not import "
                                "file '%s': %s.\n" % (source_file, str(e))).encode('UTF-8'))
                            # Skip adding translations, as the resource
                            # wasn't created.
                            continue

                        logger.debug("Inserting translations for '%s' (%s)."
                            % (resource.slug, project))

                        # Load translations
                        for code, f in r['translations'].items():
                            language = Language.objects.by_code_or_alias_or_none(code)
                            if language:
                                translation_file = os.path.join(path, f['file'])
                                try:
                                    fhandler = POHandler(filename=translation_file)
                                    fhandler.set_language(language)
                                    fhandler.bind_resource(resource)
                                    fhandler.is_content_valid()
                                    fhandler.parse_file()
                                    strings_added, strings_updated = fhandler.save2db()
                                except Exception, e:
                                    sys.stdout.write((u"Could not import file '%s': %s" %
                                        (translation_file, str(e))).encode('UTF-8'))
                else:
                    logger.debug("Mapping '%s' does not have cached files "
                        "under %s." % (jsonmap, path))

            # Set the jsonmap as migrated
            jm['meta'].update({'_migrated': True})
            jsonmap.content = simplejson.dumps(jm, indent=2)
            jsonmap.save()


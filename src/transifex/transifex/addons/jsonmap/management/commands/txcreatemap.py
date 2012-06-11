import os, sys
from optparse import make_option

from django.core.management.base import CommandError, BaseCommand
from django.db.models import Q, get_model
from django.template.defaultfilters import slugify
from django.utils import simplejson

from transifex.txcommon import version_full as VERSION
from transifex.txcommon.log import logger

from jsonmap.models import JSONMap

Project = get_model('projects', 'Project')

def get_source_file_for_file(filename, source_files):
    """
    Find the related source file (POT) for a file (PO); useful when it has
    multiple source files.

    This method gets a filename and the related source_files as parameters
    and tries to discover the related POT file using two methods:

    1. Trying to find a POT file with the same base path that the PO.
        Example: /foo/bar.pot and /foo/baz.po match on this method.

    2. Trying to find a POT file with the same domain that the PO in any
        directory.

        Example: /foo/bar.pot and /foo/baz/bar.po match on this method.
        The domain in this case is 'bar'.

    If no POT is found the method returns None.

    """
    # For filename='/foo/bar.po'
    fb = os.path.basename(filename) # 'bar.po'
    fp = filename.split(fb)[0]        # '/foo/'

    # Find the POT with the same domain or path that the filename,
    # if the component has more that one POT file
    if len(source_files) > 1:
        for source in source_files:
            sb = os.path.basename(source)
            if sb.endswith('.pot'):
                sb = sb[:-1]
            pb = source.split(sb)[0]
            if pb==fp or sb==fb:
                return source
    elif len(source_files) == 1:
        return source_files[0]

class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('--anyversion', '-a', action="store_true", default=False,
            dest='anyversion', help='Skip Transifex version check.'),
    )

    args = '<project_slug project_slug ...>'
    help = """
    Create a JSON formatted mapping of the POT files and theirs translations
    (PO) for projects, converting components into resources. Each project
    component has it own mapping which is stored in the database within the
    ``jsonmap.models.JSONMap`` model.

    This mapping can be used by the CLI app of Transifex as the ``.tx/txdata``
    file content in the remote repository.

    Project slugs can be passed by argument to map specific projects. If no
    argument is passed the mapping will happen for all the projects in the
    database.

    This mapping is used to migrate versions <= 0.9.x to the 1.0 version of
    Transifex.
    """

    def handle(self, *args, **options):
        anyversion = options.get('anyversion')

        if not anyversion:
            if int(VERSION.split('.')[0]) >= 1:
                raise CommandError("This command can't be used in Transifex "
                    "versions greater than 0.9.x. Your current version is "
                    "'%s'. For skipping this check use the option '-a'."
                    % VERSION)

        if len(args) == 0:
            projects = Project.objects.all()
        else:
            projects = Project.objects.filter(slug__in=args)
            if not projects:
                raise CommandError("No project found with the given "
                    "slug(s): %s" % ', '.join(args))

        nprojects = 0
        without_resources = []
        for p in projects:
            repo_resources = []
            for c in p.component_set.all():
                # Initialize some things
                resources = []
                translations = {}
                c.unit._init_browser()

                # Get source files; it might be a .pot or a .po with the same
                # language code as the one set on component source language.
                source_files = c.pofiles.filter(enabled=True).filter(
                    Q(is_pot=True) | Q(language_code=c.source_lang))

                logger.debug("Mapping %s" % c.full_name)

                for k, source_file in enumerate(source_files):
                    r_slug = "%s-%s" % (c.slug,
                        source_file.filename.replace('/','-').replace('.','-'))
                    if len(r_slug) > 30:
                        r_slug = r_slug[-30:] + '_%s' % str(k)

                    logger.debug("Resource: %s" % r_slug)

                    # Map each source file as a resource
                    resources.append({
                        'source_file': source_file.filename,
                        'source_lang': "en",
                        'resource_slug': r_slug,
                        '_allows_submission': c.allows_submission,
                        '_releases': list(c.releases.all().values_list(
                            'project__slug','slug'))
                    })

                    # Temp var to associate translation files with the
                    # corresponding source file; useful for components with
                    # multiple source files.
                    translations.update({source_file.filename:{}})

                # List of source file names; used on get_source_file_for_file()
                source_filenames = [f.filename for f in source_files]

                # Going through all the translation files of the related
                # component, which have a language associated with.
                for po in c.pofiles.filter(enabled=True).filter(
                    language__isnull=False).exclude(language_code=c.source_lang):

                    # Get related source file for the given translation file
                    rsf = get_source_file_for_file(po.filename, source_filenames)
                    if rsf:
                        # Add translation file to the temp mapping
                        translations[rsf].update(
                            {po.language_code:{'file':po.filename}})

                # Finally add the translations to the related resource
                for r in resources:
                    r['translations']=translations.get(r['source_file'], {})

                # Only save the JSON file if there is at least one resource for
                # the project.
                if resources:
                    data = { 'meta': {'project_slug': p.slug},
                             'resources':resources}
                    j = JSONMap.objects.get_or_create(project=p, slug=c.slug)[0]
                    j.content = simplejson.dumps(data, indent=2)
                    j.save()
                    repo_resources.append(resources)

            if repo_resources:
                nprojects+=1
            else:
                without_resources.append(p.slug)

        sys.stdout.write("Projects with at least one resource created: %s.\n" % nprojects)
        sys.stdout.write("Projects with no resources: %s.\n" % len(without_resources))



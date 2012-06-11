# -*- coding: utf-8 -*-
import copy
import re
from django.conf import settings
from django.db import models
from django.utils import simplejson
from django.utils.translation import ugettext_lazy as _

from transifex.txcommon.db.models import CompressedTextField
from transifex.txcommon.log import logger

from jsonmap.utils import remove_attrs_startwith


class JSONMap(models.Model):
    """
    Store the JSON mapping used to among resources and its translation files
    """
    slug = models.SlugField(null=False, blank=False, max_length=50,
        help_text=_("Slug for the mapping. Usually the same as the old "
        "component slug."))
    content = CompressedTextField(null=False, blank=False,
        help_text=_("Mapping in JSON format."))
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    # ForeignKeys
    project = models.ForeignKey('projects.Project', null=False, blank=False,
        help_text=_("Project to which the JSON mapping belongs."))

    def __unicode__(self):
        return '%s.%s' % (self.project.slug, self.slug)

    def __repr__(self):
        return '<JSONMap: %s.%s>' % (self.project.slug, self.slug)

    class Meta:
        unique_together = ("project", "slug")
        verbose_name = _('JSONMap')
        verbose_name_plural = _('JSONMaps')
        ordering  = ('project__name',)
        get_latest_by = 'created'


    def dumps(self, with_tmp_attr=False):
       """
       Return the JSON formatted ``self.content`` with no tmp attributes if
       with_tmp_attr is False.
       """
       return simplejson.dumps(self.loads(with_tmp_attr), indent=2,
                encoding=settings.DEFAULT_CHARSET)


    def dumps_to_file(self, filename, with_tmp_attr=False):
        """
        Write ``self.dumps()`` result into a JSON file to the file system.
        """
        tfile = None
        try:
            tfile = open(filename, 'w')
            tfile.write(self.dumps(with_tmp_attr))
        except:
            pass
        if tfile:
            tfile.close()


    def loads(self, with_tmp_attr=False):
        """
        Deserialize ``self.content`` to a Python dictionary.

        Remove temporary attribute if with_tmp_attr is False. Attributes that
        start with '_', such as '_repo_path', will be removed in such case.
        """
        try:
            data = simplejson.loads(self.content,
                encoding=settings.DEFAULT_CHARSET)
        except ValueError:
            data = eval(self.content)

        if not with_tmp_attr:
            remove_attrs_startwith(data, '_')

        return data

# -*- coding: utf-8 -*-
import os
import datetime, hashlib, sys
from django.conf import settings
from django.db.models import permalink
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext

from transifex.languages.models import Language
from transifex.txcommon.exceptions import FileCheckError
from transifex.txcommon.log import logger

import magic

class StorageFile(models.Model):
    """
    StorageFile refers to a uploaded file. Initially
    """
    # File name of the uploaded file
    name = models.CharField(max_length=1024)
    size = models.IntegerField(_('File size in bytes'), blank=True, null=True)
    mime_type = models.CharField(max_length=255)

    # Path for storage
    uuid = models.CharField(max_length=1024)

    # Foreign Keys
    language = models.ForeignKey(Language,
        verbose_name=_('Source language'),blank=False, null=True,
        help_text=_("The language in which this translation string is written."))

    #resource = models.ForeignKey(Resource, verbose_name=_('Resource'),
        #blank=False, null=True,
        #help_text=_("The translation resource which owns the source string."))

#    project = models.ForeignKey(Project, verbose_name=_('Project'), blank=False, null=True)

    bound = models.BooleanField(verbose_name=_('Bound to any object'), default=False,
        help_text=_('Whether this file is bound to a project/translation resource, otherwise show in the upload box'))

    user = models.ForeignKey(User,
        verbose_name=_('Owner'), blank=False, null=True,
        help_text=_("The user who uploaded the specific file."))

    created = models.DateTimeField(auto_now_add=True, editable=False)
    total_strings = models.IntegerField(_('Total number of strings'), blank=True, null=True)

    def __unicode__(self):
        return "%s (%s)" % (self.name, self.uuid)

    def delete(self, *args, **kwargs):
        """
        Delete file from filesystem even if object has not been saved yet.
        """
        try:
            os.remove(self.get_storage_path())
        except OSError, e:
            if self.id:
                logger.debug("Error deleting StorageFile: %s" % str(e))
        if self.id:
            super(StorageFile, self).delete(*args, **kwargs)

    def get_storage_path(self):
        filename = "%s-%s" % (self.uuid, self.name)
        return os.path.join(settings.STORAGE_DIR, filename)

    def translatable(self):
        """
        Whether we could extract any strings -> whether we can translate file
        """
        return (self.total_strings > 0)

    def find_parser(self):
        from transifex.resources.formats.registry import registry
        i18n_type = registry.guess_method(self.name, self.mime_type)
        if i18n_type is None:
            msg = "Unsupported resource"
            if self.name is not None:
                msg = "Unsupported extension of file: %s" % self.name
            elif self.mimetype is not None:
                msg = "Unsupported mimetype %s" % self.mimetype
            raise FileCheckError(msg)
        if self.name.endswith('pot'):
            i18n_type = 'POT'
        return registry.handler_for(i18n_type)

    def update_props(self):
        """
        Try to parse the file and fill in information fields in current model
        """
        # this try to guess the API of the magic module, between
        # the one from file and the other one from python-magic
        try:
                m = magic.Magic(mime=True)
                # guess mimetype and remove charset
                self.mime_type = m.from_file(self.get_storage_path())
        except AttributeError:
                m = magic.open(magic.MAGIC_NONE)
                m.load()
                self.mime_type = m.file(self.get_storage_path())
                m.close()
        except Exception, e:
            pass

        self.save()

        try:
            parser = self.find_parser()
        except IndexError, e:
            raise FileCheckError("Invalid format")

        if not parser:
            return

        parser.bind_file(filename=self.get_storage_path())
        parser.set_language(self.language)
        parser.is_content_valid()
        parser.parse_file()

        stringset = parser.stringset
        if not stringset:
            return

        if stringset.target_language:
            try:
                self.language = Language.objects.by_code_or_alias(stringset.target_language)
            except Language.DoesNotExist:
                pass

        self.total_strings = len([s for s in stringset.strings if s.rule==5])
        return

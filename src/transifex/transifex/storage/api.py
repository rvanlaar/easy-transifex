# -*- coding: utf-8 -*-
from piston.handler import BaseHandler
from piston.utils import rc, throttle
from django.conf import settings
from django.http import HttpResponse
from django.template.defaultfilters import slugify
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from transifex.languages.models import Language
from transifex.projects.models import Project
from transifex.resources.models import Resource, SourceEntity, Translation
from transifex.resources.formats.core import ParseError
from transifex.storage.models import StorageFile
from transifex.txcommon.exceptions import FileCheckError
from transifex.txcommon.log import logger
from django.db import transaction
from transifex.api.utils import BAD_REQUEST
from uuid import uuid4
import os


class StorageHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'DELETE')
    model = StorageFile
    fields = ('language',('language',('code',)),'total_strings','name','created','uuid','mime_type','size')

    def delete(self, request, uuid=None, api_version=1):
        """
        Deletes file by storage UUID
        """
        if request.user.is_anonymous():
            return rc.FORBIDDEN
        try:
            StorageFile.objects.get(uuid=uuid, user=request.user).delete()
        except StorageFile.DoesNotExist:
            return rc.NOT_FOUND
        logger.debug("Deleted file %s" % uuid)
        return rc.DELETED

    def read(self, request, uuid=None, api_version=1):
        """
        Returns list of StorageFile objects
        [
            {
                "total_strings": 1102,
                "uuid": "71f4964c-817b-4778-b3e0-693375cb1355",
                "language": {
                    "code": "et"
                },
                "created": "2010-05-13 07:22:36",
                "size": 187619,
                "mime_type": "application/x-gettext",
                "name": "kmess.master.et.po"
            },
            ...
        ]
        """
        if request.user.is_anonymous():
            return rc.FORBIDDEN
        retval = StorageFile.objects.filter(user = request.user, bound=False)
        logger.debug("Returned list of users uploaded files: %s" % retval)
        return retval

    @throttle(settings.API_MAX_REQUESTS, settings.API_THROTTLE_INTERVAL)
    def create(self, request, uuid=None, api_version=1):
        """
        API call for uploading a file via POST or updating storage file attributes
        """
        if request.user.is_anonymous():
            return rc.FORBIDDEN

        if "application/json" in request.content_type: # Do API calls
            if 'language' in request.data.keys() and uuid: # API call for changing language
                lang_code = request.data['language'] # TODO: Sanitize
                try:
                    sf = StorageFile.objects.get(uuid = uuid)
                    if lang_code == "": # Set to 'Not detected'
                        sf.language = None
                    else:
                        sf.language = Language.objects.by_code_or_alias(lang_code)
                except StorageFile.DoesNotExist:
                    return rc.NOT_FOUND # Translation file does not exist
                except Language.DoesNotExist:
                    return rc.NOT_FOUND # Translation file not found
                sf.save() # Save the change
                logger.debug("Changed language of file %s (%s) to %s" % (sf.uuid, sf.name, lang_code))
                return rc.ALL_OK
            return BAD_REQUEST("Unsupported request") # Unknown API call
        elif "multipart/form-data" in request.content_type: # Do file upload
            files=[]
            retval = None
            for name, submitted_file in request.FILES.items():
                submitted_file = submitted_file
                sf = StorageFile()
                sf.name = str(submitted_file.name.encode('UTF-8'))
                sf.uuid = str(uuid4())
                fh = open(sf.get_storage_path(), 'wb')
                for chunk in submitted_file.chunks():
                    fh.write(chunk)
                fh.close()
                sf.size = os.path.getsize(sf.get_storage_path())
                sf.user = request.user
                if 'language' in request.data.keys():
                    lang_code = request.data['language']
                    try:
                        sf.language =  Language.objects.by_code_or_alias(lang_code)
                    except Language.DoesNotExist:
                        logger.error("Weird! Selected language code (%s) does "
                            "not match with any language in the database."
                            % lang_code)
                        return BAD_REQUEST("Selected language code (%s) does "
                            "not match with any language in the database." % lang_code)
                else:
                    return BAD_REQUEST(
                        "Language for the file has not been specified."
                    )

                try:
                    sf.update_props()
                    sf.save()

                    logger.debug("Uploaded file %s (%s)" % (sf.uuid, sf.name))
                    files.append({'uuid':sf.uuid, 'id':str(sf.id),
                        'name':sf.name})
                except UnicodeDecodeError, e:
                    message = _(
                        "The encoding of the uploaded file is not UTF-8. "
                        "Currently, transifex supports only UTF-8"
                        "encoded files. Please, visit"
                        "http://help.transifex.net/user-guide/formats.html#encoding"
                        "for further information."
                    )
                except Exception, e:
                    if isinstance(e, UnicodeDecodeError):
                        message = _(
                            "The encoding of the uploaded file is not UTF-8. "
                            "Currently, transifex supports only UTF-8"
                            "encoded files. Please, visit"
                            "http://help.transifex.net/user-guide/formats.html#encoding"
                            "for further information."
                        )
                    elif isinstance(e, (FileCheckError, ParseError)):
                        #FIXME: Custom Exception should use an extra attr for
                        # localized string.
                        message = "%s" % e
                    else:
                        message = _("A strange error happened.")
                        logger.error("Unhandled exception raised: %s" % e)

                    # The object is not saved yet, but it removes file from
                    # the filesystem
                    sf.delete()

                    # Delete possible uploaded files from the same request.
                    # It allows multiple files per request, but if one fails,
                    # the whole request must fail.
                    StorageFile.objects.filter(
                        id__in=[f['id'] for f in files]).delete()

                    retval=dict(status='Error', message=message)

            if not retval:
                retval=dict(status='Created', files=files,
                    message=_("File uploaded successfully."))
                status = 200
            else:
                status = 400

            return HttpResponse(simplejson.dumps(retval),
                    mimetype='text/plain', status=status)
        else: # Unknown content type/API call
            return BAD_REQUEST("Unsupported request")

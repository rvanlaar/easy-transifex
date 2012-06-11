# -*- coding: utf-8 -*-
"""
Register the available formats and their capabilities.
"""

import magic
from django.conf import settings
from transifex.txcommon import import_to_python
from transifex.txcommon.log import logger


class _FormatsRegistry(object):
    """Registry class for the formats."""

    def __init__(self, methods=None, handlers=None):
        """It initializes the variables of the registry.

        The variables are:
            methods: A dictionary of the available methods.
            handlers: A dictionary of the available handlers.
        """
        self.methods = methods or settings.I18N_METHODS
        self.handlers = {}
        handlers = handlers or settings.I18N_HANDLER_CLASS_NAMES
        for method, klass in handlers.iteritems():
            self.handlers[method] = import_to_python(klass)

    def _string_to_list(self, string):
        """
        Convert a string of multiple items separated by commas and spaces
        to a list.
        """
        return string.split(', ')

    def add_handler(self, m, klass, priority=False):
        """Register a new handler for the type m.

        Args:
            m: A i18n_method.
            klass: A handler class for the specified method.
            priority: if this is a priority request, then register the
                 handler for the method anyway. Else, ignore the request.
        Returns:
            True, if the handler was added successfully, False otherwise.
        """
        if m in self.handlers and not priority:
            return False
        self.handlers[m] = klass
        return True

    @property
    def available_methods(self):
        """Get the available methods."""
        methods = self.methods.copy()
        del methods['POT']
        return methods

    def descriptions(self):
        """Get the available descriptions along with the
        method they correspond to.
        """
        return [
            (m, '%s (%s)' % (v['description'], v['file-extensions']))
            for m, v in self.methods.items()
            if m != 'POT'
        ]

    def extensions_for(self, m):
        """Get the extensions for the specified method.

        Returns:
            A list of file extensions or an empty list,
            in case no such method exists.
        """
        if m not in self.methods:
            return []
        return self._string_to_list(self.methods[m]['file-extensions'])

    def guess_method(self, filename=None, mimetype=None):
        """
        Return an appropriate Handler class for given file.

        The handler is selected based on libmagic and the file extension
        or the mime type.

        Args:
            filename: The path to the file.
            mimetype: The mime type of the file.

        Returns:
            An appropriate handler class for the file.
        """
        i18n_type = None
        if filename is not None:
            try:
                m = magic.Magic(mime=True)
                # guess mimetype and remove charset
                mime_type = m.from_file(filename)
            except AttributeError, e:
                m = magic.open(magic.MAGIC_NONE)
                m.load()
                mime_type = m.file(filename)
                m.close()
            except IOError, e:
                # file does not exist in the storage
                mime_type = None
            except Exception, e:
                logger.error("Uncaught exception: %s" % e.message, exc_info=True)
                # We don't have the actual file. Depend on the filename only
                mime_type = None

            for method, info in self.methods.items():
                if filter(filename.endswith, info['file-extensions'].split(', ')) or\
                  mime_type in info['mimetype'].split(', '):
                    i18n_type = method
                    break
        elif mimetype is not None:
            for method in self.handlers:
                if mimetype in self.mimetypes_for(method):
                    i18n_type = method
                    break

        return i18n_type

    def is_supported(self, m):
        """Check whether the method is supported.

        Args:
            m: The method to check.
        Returns:
            True, if it is supported. Else, False.
        """
        return m in self.methods

    def mimetypes_for(self, m):
        """Get the mimetypes for the specified method.

        Args:
            m: The method which we want the mimetypes for.

        Returns:
            The mimetypes for the method or an empty list.
        """
        if m not in self.methods:
            return []
        return self._string_to_list(self.methods[m]['mimetype'])

    def handler_for(self, m):
        """Return a handler for the i18n type specified.

        Args:
            m: A i18n_method.
            filename: The filename (if available).

        Returns:
            A particular handler for the method or None, in case the method
            has not been registered.
        """
        if m not in self.handlers:
            return None
        return self.handlers[m]()

    def appropriate_handler(self, resource, language, **kwargs):
        """Return the appropriate handler based on the arguments.

        The arguments may be the filename of the resource or whether
        a pot file has been requested.

        Args:
            resource: The resource the handler is for.
            language: The language the handler is asked for.
        Returns:
            A subclass of formats.core.Handler or None.
        """
        method = resource.i18n_type
        handler = registry.handler_for

        # Only PO/POT files need special treatment
        if method != 'PO':
            return handler(method)

        # Override the behavior manually
        wants_pot = kwargs.get('wants_pot')
        if wants_pot:
            return handler('POT')

        # Check file extension
        filename = kwargs.get('filename')
        if filename is not None:
            if filename.endswith('po'):
                return handler('PO')
            else:
                return handler('POT')

        # Return POT, when no language has been asked
        if language is None:
            return handler('POT')
        return handler('PO')

        # # Always return PO for non-source language files
        # slang = resource.source_language
        # if language != slang:
        #     return handler('PO')

        # Should never be here
        return None

    def file_extension_for(self, resource, language):
        """Return the filename extension that should be used
        for the specific resource-language pair.
        """
        resource_method = resource.i18n_method
        try:
            if resource_method != 'PO':
                return self.extensions_for(resource_method)[0]
            if language is None:
                return self.extensions_for('POT')[0]
            return self.extensions_for(resource_method)[0]
        except IndexError, e:
            msg = "No extensions for resource %s: %s"
            logger.error(msg % (resource, e), exc_info=True)
            raise

registry = _FormatsRegistry()

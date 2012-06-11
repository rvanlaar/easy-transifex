# -*- coding: utf-8 -*-

import codecs, copy, os, re
import gc
from django.utils import simplejson as json

from django.conf import settings
from django.db import transaction
from django.db.models import get_model
from django.utils.translation import ugettext as _
from transifex.txcommon.log import logger
from transifex.languages.models import Language
from suggestions.models import Suggestion
from suggestions.formats import ContentSuggestionFormat
from transifex.actionlog.models import action_logging
from transifex.resources.handlers import invalidate_stats_cache
from transifex.resources.formats import FormatError
from transifex.resources.formats.pseudo import PseudoTypeMixin
from transifex.resources.formats.utils.decorators import *
from transifex.resources.signals import post_save_translation
from transifex.resources.formats.resource_collections import StringSet, \
        GenericTranslation, SourceEntityCollection, TranslationCollection


# Temporary
from transifex.txcommon import notifications as txnotification
# Addons
from watches.models import TranslationWatch

"""
STRICT flag is used to switch between two parsing modes:
  True - minor bugs in source files are treated fatal
    In case of Qt TS handler this means that buggy location elements will
    raise exceptions.
  False - if we get all necessary information from source files
    we will pass
"""
STRICT=False


Resource = get_model('resources', 'Resource')
Translation = get_model('resources', 'Translation')
SourceEntity = get_model('resources', 'SourceEntity')
Template = get_model('resources', 'Template')


class CustomSerializer(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, GenericTranslation):
            d = {
                'source_entity' : obj.source_entity,
                'translation' : obj.translation,
            }
            if obj.occurrences:
                d['occurrences'] = obj.occurrences
            if obj.comments:
                d['comments'] = obj.comments
            if obj.context:
                d['context'] = obj.context
            if obj.rule:
                d['rule'] = obj.rule
            if obj.pluralized:
                d['pluralized'] = obj.pluralized

            return d

        if isinstance(obj, StringSet):
            return {
                #'filename' : obj.filename,
                'target_language' : obj.target_language,
                'strings' : obj.strings,
            }


class ParseError(FormatError):
    """Base class for parsing errors."""
    pass


class CompileError(FormatError):
    """Base class for all compiling errors."""
    pass


class Handler(object):
    """
    Base class for writing file handlers for all the I18N types.
    """
    default_encoding = "UTF-8"
    method_name = None
    format_encoding = "UTF-8"

    HandlerParseError = ParseError
    HandlerCompileError = CompileError

    SuggestionFormat = ContentSuggestionFormat

    linesep = '\n'

    @classmethod
    def accepts(cls, i18n_type):
        """Accept only files that have the correct type specified."""
        return i18n_type == cls.method_name

    def __init__(self, filename=None, resource=None, language=None, content=None):
        """
        Initialize a formats handler.
        """
        # Input filename for associated translation file
        self.filename = filename
        # The content of the translation file
        self.content = self._get_content(filename=filename, content=content)
        self.stringset = None # Stringset to extract entries from files

        self.resource = None # Associated resource
        self.language = None # Resource's source language

        self.template = None # Var to store raw template
        self.compiled_template = None # Var to store output of compile() method

        if resource:
            self.resource = resource
            self.language = resource.source_language
        if language:
            self.language = language

    def _check_content(self, content):
        """
        Perform the actual check of the content.

        """
        # FIXME Make all code use return values instead of exceptions
        # FIXME Needs to deprecate API v1
        return (True, None)

    def is_content_valid(self, content=None):
        """Check whether the content is valid for the format.

        A subclass needs to override the _check_content method
        to customize the check.

        Args:
            content: The content to check.
        Returns:
            A tuple with two elements. The first is a boolean, a flag whether
            the content is valid. The second is the error message in case of
            errors.
        """
        if content is None:
            content = self.content
        return self._check_content(content)

    ####################
    # Helper functions #
    ####################

    def _get_content(self, filename=None, content=None):
        """Read the content of the specified file.

        Return either the `content` or the content of the file.
        """
        if content is not None:
            if isinstance(content, str):
                try:
                    return content.decode(self.format_encoding)
                except UnicodeDecodeError, e:
                    raise FormatError(unicode(e))
            else:
                return content
        if filename is None:
            return None
        return self._get_content_from_file(filename, self.format_encoding)

    def _get_content_from_file(self, filename, encoding):
        """Return the content of a file encoded with ``encoding``.

        Args:
            filename: The name of the file.
            encoding: THe encoding to use to open the file.
        Returns:
            The content of the file as a unicode string.
        """
        f = codecs.open(filename, 'r', encoding=encoding)
        try:
            return f.read()
        except IOError, e:
            logger.warning(
                "Error opening file %s with encoding %s: %s" %\
                    (filename, self.format_encoding, e),
                exc_info=True
            )
            raise FormatError(unicode(e))
        except Exception, e:
            logger.error("Unhandled exception: %s" % e, exc_info=True)
            raise
        finally:
            f.close()

    def set_language(self, language):
        """Set the language for the handler."""
        if isinstance(language, Language):
            self.language = language
        else:
            try:
                self.language = Language.objects.by_code_or_alias(language)
            except Language.DoesNotExist, e:
                logger.warning(
                    "Language.DoesNotExist: %s" % e, exc_info=True
                )
                raise FormatError(unicode(e))
            except Exception, e:
                logger.error(unicode(e), exc_info=True)
                raise FormatError(unicode(e))

    def bind_content(self, content):
        """Bind some content to the handler."""
        self.content = self._get_content(content=content)

    def bind_file(self, filename):
        """Bind a file to an initialized POHandler."""
        if os.path.isfile(filename):
            self.filename = filename
            self.content = self._get_content(filename=filename)
        else:
            msg = _("Specified file %s does not exist." % filename)
            logger.error(msg)
            raise FormatError(msg)

    def bind_resource(self, resource):
        """Bind a resource to an initialized POHandler."""
        if isinstance(resource, Resource):
            self.resource = resource
            try:
                resource_template = self.resource.source_file_template
            except Template.DoesNotExist:
                resource_template = None
            self.compiled_template = self.compiled_template or resource_template
            self.language = self.language or resource.source_language
        else:
            msg = _("The specified object %s is not of type Resource" % resource)
            logger.error(msg)
            raise FormatsError(msg)


    def bind_pseudo_type(self, pseudo_type):
        if isinstance(pseudo_type, PseudoTypeMixin):
            self.pseudo_type = pseudo_type
        else:
            raise Exception(_("pseudo_type needs to be based on type %s" %
                PseudoTypeMixin.__class__))


    def _find_linesep(self, s):
        """Find the line separator used in the file."""
        if "\r\n" in s:         # windows line ending
            self.linesep = "\r\n"
        else:
            self.linesep = "\n"

    def _prepare_line(self, line):
        """
        Prepare a line for parsing.

        Remove newline and whitespace characters.
        """
        return line.rstrip('\r\n').strip()

    ####################
    #  Core functions  #
    ####################

    def _pseudo_decorate(self, string):
        """
        Modify the string accordingly to a ``pseudo_type`` set to the handler.
        This is used to export Pseudo Localized files.
        """
        if hasattr(self,'pseudo_type') and self.pseudo_type:
            nonunicode = False
            if isinstance(string, str):
                string = string.decode(self.default_encoding)
                nonunicode = True

            string = self.pseudo_type.compile(string)

            if nonunicode:
                string = string.encode(self.default_encoding)
        return string

    ####################
    # Compile functions
    ####################

    def _replace_translation(self, original, replacement, text):
        """
        Do a search and replace inside `text` and replaces all
        occurrences of `original` with `replacement`.
        """
        return re.sub(re.escape(original),
            self._pseudo_decorate(self._escape(replacement)), text)

    def _get_source_strings(self, resource):
        """Return the source strings of the resource."""
        return SourceEntity.objects.filter(resource=resource).values_list(
            'id', 'string_hash'
        )

    def _get_translation_strings(self, source_entities, language):
        """Get the translation strings that match the specified source_entities.

        The returned translations are for the specified langauge and rule = 5.

        Args:
            source_entities: A list of source entity ids.
            language: The language which the translation is for.
        Returns:
            A dictionary with the translated strings. The keys are the id of
            the source entity this translation corresponds to and values are
            the translated strings.
        """
        res = {}
        translations = Translation.objects.filter(
            source_entity__in=source_entities, language=language, rule=5
        ).values_list('source_entity_id', 'string') .iterator()
        for t in translations:
            res[t[0]] = t[1]
        return res

    def _get_translation(self, string, language, rule):
        try:
            return Translation.objects.get(
                resource = self.resource, source_entity=string,
                language=language, rule=rule
            )
        except Translation.DoesNotExist, e:
            return None

    def _pre_compile(self, *args, **kwargs):
        """
        This is called before doing any actual work. Override in inherited
        classes to alter behaviour.
        """
        pass

    def _escape(self, s):
        """
        Escape special characters in string.
        """
        return s

    def _add_translation_string(self, *args, **kwargs):
        """Adds to instance a new translation string."""
        self.stringset.strings.append(GenericTranslation(*args, **kwargs))

    def _add_suggestion_string(self, *args, **kwargs):
        """Adds to instance a new suggestion string."""
        self.suggestions.strings.append(GenericTranslation(*args, **kwargs))

    def _apply_translation(self, source_hash, trans, content):
        """Apply a translation to text.

        Usually, we do a search for the hash code of source and replace
        with trans.

        Args:
            source_hash: The hash string of the source entity.
            trans: The translation string.
            content: The text for the search-&-replace.

        Returns:
            The content after the translation has been applied.
        """
        return self._replace_translation("%s_tr" % source_hash, trans, content)

    def _examine_content(self, content):
        """
        Offer a chance to peek into the template before any string is
        compiled.
        """
        return content

    def _post_compile(self, *args, **kwargs):
        """
        This is called in the end of the compile method. Override if you need
        the behaviour changed.
        """
        pass

    @need_resource
    def compile(self, language=None):
        """
        Compile the template using the database strings. The result is the
        content of the translation file.

        There are three hooks a subclass can call:
          _pre_compile: This is called first, before anything takes place.
          _examine_content: This is called, to have a look at the content/make
              any adjustments before it is used.
          _post_compile: Called at the end of the process.

        Args:
          language: The language of the file
        """

        if language is None:
            language = self.language
        self._pre_compile(language)
        content = Template.objects.get(
            resource=self.resource
        ).content.decode(self.default_encoding)
        content = self._examine_content(content)
        try:
            self.compiled_template = self._compile(
                content, language
            ).encode(self.format_encoding)
        except Exception, e:
            logger.error("Error compiling file: %s" % e, exc_info=True)
            raise
        self._post_compile(language)

    def _compile(self, content, language):
        """Internal compile function.

        Subclasses must override this method, if they need to change
        the compile behavior.

        Args:
            content: The content (template) of the resource.
            language: The language for the translation.

        Returns:
            The compiled template.
        """
        stringset = self._get_source_strings(self.resource)
        translations = self._get_translation_strings(
            (s[0] for s in stringset), language
        )
        for string in stringset:
            trans = translations.get(string[0], u"")
            content = self._apply_translation(string[1], trans, content)
        return content

    #######################
    #  save methods
    #######################

    def _context_value(self, context):
        """Convert the context for the database.

        Args:
            context: The context value calculated
        Returns:
            The correct value for the context to be used in the database.
        """
        return context or u'None'

    def _handle_update_of_resource(self, user):
        """Do extra stuff after a source language/translation has been updated.

        Args:
            user: The user that caused the update.
        """
        self._update_stats_of_resource(self.resource, self.language, user)

        if self.language == self.resource.source_language:
            nt = 'project_resource_changed'
        else:
            nt = 'project_resource_translated'
        context = {
            'project': self.resource.project,
            'resource': self.resource,
            'language': self.language
        }
        object_list = [self.resource.project, self.resource, self.language]

        # if we got no user, skip the log
        if user:
            action_logging(user, object_list, nt, context=context)

        if settings.ENABLE_NOTICES:
            self._send_notices(signal=nt, extra_context=context)

    def _init_source_entity_collection(self, se_list):
        """Initialize the source entities collection.

        Get a collection of source entity objects for the current resource.

        Args:
            se_list: An iterable of source entity objects.
        Returns:
            A SourceEntityCollection object.
        """
        source_entities = SourceEntityCollection()
        for se in se_list:
            source_entities.add(se)
        return source_entities

    def _init_translation_collection(self, se_ids):
        """Initialize the translations collections.

        Get a collection of translation objects for the current language.

        Args:
            se_ids: An iterable of source entities ids the translation
                objects are for.
        Returns:
            A TranslationCollection object.
        """
        qs = Translation.objects.filter(
            language=self.language, source_entity__in=se_ids).iterator()
        translations = TranslationCollection()
        for t in qs:
            translations.add(t)
        return translations

    def _pre_save2db(self, *args, **kwargs):
        """
        This is called before doing any actual work. Override in inherited
        classes to alter behaviour.
        """
        pass

    def _post_save2db(self, *args, **kwargs):
        """
        This is called in the end of the save2db method. Override if you need
        the behaviour changed.
        """
        kwargs.update({
            'resource': self.resource,
            'language': self.language
        })
        post_save_translation.send(sender=self, **kwargs)

    def _send_notices(self, signal, extra_context):
        txnotification.send_observation_notices_for(
            self.resource.project, signal, extra_context
        )

        # if language is source language, notify all languages for the change
        if self.language == self.resource.source_language:
            for l in self.resource.available_languages:
                twatch = TranslationWatch.objects.get_or_create(
                    resource=self.resource, language=l)[0]
                logger.debug(
                    "addon-watches: Sending notification for '%s'" % twatch
                )
                txnotification.send_observation_notices_for(
                    twatch,
                    signal='project_resource_translation_changed',
                    extra_context=extra_context
                )

    def _should_skip_translation(self, se, trans):
        """Check if current translation should be skipped, ie not saved to db.

        This should happen for empty translations (ie, untranslated strings)
        and for strings which are not correctly pluralized.

        Args:
            se: The source entity that corresponds to the translation.
            trans: The translation itself.
        Returns:
            True, if the specified translation must be skipped, ie not
            saved to database.
        """
        return not trans.translation or trans.pluralized != se.pluralized

    def _save_source(self, user, overwrite_translations):
        """Save source language translations to the database.

        Subclasses should override this method, if they need to customize
        the behavior of saving translations in the source language.

        Any fatal exception must be reraised.

        Args:
            user: The user that made the commit.
            overwrite_translations: A flag to indicate whether translations
                should be overrided.

        Returns:
            A tuple of number of strings added, updted and deleted.

        Raises:
            Any exception.
        """
        qs = SourceEntity.objects.filter(resource=self.resource)
        original_sources = list(qs) # TODO Use set() instead? Hash by pk
        new_entities = []
        source_entities = self._init_source_entity_collection(original_sources)
        translations = self._init_translation_collection(source_entities.se_ids)

        strings_added = 0
        strings_updated = 0
        strings_deleted = 0
        try:
            for j in self.stringset.strings:
                if j in source_entities:
                    se = source_entities.get(j)
                    # update source string attributes.
                    se.flags = j.flags or ""
                    se.pluralized = j.pluralized
                    se.developer_comment = j.comment or ""
                    se.occurrences = j.occurrences
                    se.save()
                    try:
                        original_sources.remove(se)
                    except ValueError:
                        # When we have plurals, we can't delete the se
                        # everytime, so we just pass
                        pass
                else:
                    # Create the new SE
                    se = SourceEntity.objects.create(
                        string = j.source_entity,
                        context = self._context_value(j.context),
                        resource = self.resource, pluralized = j.pluralized,
                        position = 1,
                        # FIXME: this has been tested with pofiles only
                        flags = j.flags or "",
                        developer_comment = j.comment or "",
                        occurrences = j.occurrences,
                    )
                    # Add it to list with new entities
                    new_entities.append(se)
                    source_entities.add(se)

                if self._should_skip_translation(se, j):
                    continue
                if (se, j) in translations:
                    tr = translations.get((se, j))
                    if overwrite_translations and tr.string != j.translation:
                            tr.string = j.translation
                            tr.user = user
                            tr.save()
                            strings_updated += 1
                else:
                    tr = Translation.objects.create(
                        source_entity=se, language=self.language, rule=j.rule,
                        string=j.translation, user=user,
                        resource = self.resource
                    )
                    translations.add(tr)
                    if j.rule==5:
                        strings_added += 1
        except Exception, e:
            logger.error(
                "There was a problem while importing the entries into the "
                "database. Entity: '%s'. Error: '%s'." % (
                    j.source_entity, e
                )
            )
            raise

        sg_handler = self.SuggestionFormat(self.resource, self.language, user)
        sg_handler.add_from_strings(self.suggestions.strings)
        sg_handler.create_suggestions(original_sources, new_entities)
        for se in original_sources:
            se.delete()
        self._update_template(self.template)

        strings_deleted = len(original_sources)
        return strings_added, strings_updated, strings_deleted

    def _save_translation(self, user, overwrite_translations):
        """Save other language translations to the database.

        Subclasses should override this method, if they need to customize
        the behavior of saving translations in other languages than the source
        one.

        Any fatal exception must be reraised.

        Args:
            user: The user that made the commit.
            overwrite_translations: A flag to indicate whether translations
                should be overrided.

        Returns:
            A tuple of number of strings added, updted and deleted.

        Raises:
            Any exception.
        """
        qs = SourceEntity.objects.filter(resource=self.resource).iterator()
        source_entities = self._init_source_entity_collection(qs)
        translations = self._init_translation_collection(source_entities.se_ids)

        strings_added = 0
        strings_updated = 0
        strings_deleted = 0
        try:
            for j in self.stringset.strings:
                if j not in source_entities:
                    continue
                else:
                    se = source_entities.get(j)

                if self._should_skip_translation(se, j):
                    continue
                if (se, j) in translations:
                    tr = translations.get((se, j))
                    if overwrite_translations and tr.string != j.translation:
                            tr.string = j.translation
                            tr.user = user
                            tr.save()
                            strings_updated += 1
                else:
                    tr = Translation.objects.create(
                        source_entity=se, language=self.language, rule=j.rule,
                        string=j.translation, user=user, resource=self.resource
                    )
                    if j.rule==5:
                        strings_added += 1
        except Exception, e:
            logger.error(
                "There was a problem while importing the entries into the "
                "database. Entity: '%s'. Error: '%s'." % (
                    j.source_entity, e
                )
            )
            raise
        sg_handler = self.SuggestionFormat(self.resource, self.language, user)
        sg_handler.add_from_strings(self.suggestions.strings)
        return strings_added, strings_updated, strings_deleted

    def _update_stats_of_resource(self, resource, language, user):
        """Update the statistics for the resource.

        Also, invalidate any caches.
        """
        invalidate_stats_cache(resource, language, user=user)

    def _update_template(self, content):
        """Update the template of the resource.

        Args:
            content: The content of the template.
        """
        t, created = Template.objects.get_or_create(resource=self.resource)
        t.content = content
        t.save()

    @need_resource
    @need_language
    @need_stringset
    @transaction.commit_manually
    def save2db(self, is_source=False, user=None, overwrite_translations=True):
        """
        Saves parsed file contents to the database. duh
        """
        self._pre_save2db(is_source, user, overwrite_translations)
        try:
            if is_source:
                (added, updated, deleted) = self._save_source(
                    user, overwrite_translations
                )
            else:
                (added, updated, deleted) = self._save_translation(
                    user, overwrite_translations
                )
        except Exception, e:
            logger.warning(
                "Failed to save translations for language %s and resource %s."
                "Error was %s." % (self.language, self.resource, e),
                exc_info=True
            )
            transaction.rollback()
            return (0, 0)
        finally:
            gc.collect()
        try:
            self._post_save2db(
                is_source=is_source, user=user,
                overwrite_translations=overwrite_translations
            )
            if added + updated + deleted > 0:
                self._handle_update_of_resource(user)
        except Exception, e:
            logger.error("Unhandled exception: %s" % e, exc_info=True)
            transaction.rollback()
            raise FormatError(unicode(e))
        finally:
            gc.collect()
        transaction.commit()
        return (added, updated)

    ####################
    # parse methods
    ####################

    def _generate_template(self, obj):
        """Generate a template from the specified object.

        By default, we use the obj as a unicode string and encode it to
        str.

        Subclasses could override this.
        """
        return obj.encode(self.default_encoding)

    def _iter_by_line(self, content):
        """Iterate the content by line."""
        for line in content.split(self.linesep):
            yield line

    def _parse(self, is_source, lang_rules):
        """The actual functions that parses the content.

        Formats need to override this to provide the desired behavior.

        Two stringsets are available to subclasses:
        - self.stringset to save the translated strings
        - self.suggestions to save suggested translations

        Args:
            is_source: Flag to determine if this is a source file or not.
            lang_rules: rules for the language

        Returns:
            An object which, when used as an argument in
            `self._create_template()`, the template for the resource
            is generated.

        """
        raise NotImplementedError

    @need_content
    @need_language
    def parse_file(self, is_source=False, lang_rules=None):
        """Parse the content."""
        self.stringset = StringSet()
        self.suggestions = StringSet()
        self.is_content_valid()
        try:
            obj = self._parse(is_source, lang_rules)
        except self.HandlerParseError, e:
            msg = "Error when parsing file for resource %s: %s"
            logger.error(msg % (self.resource, e), exc_info=True)
            raise
        if is_source:
            self.template = self._generate_template(obj)

class ResourceItems(object):
    """base class for collections for resource items (source entities,
    translations, etc).
    """

    def __init__(self):
        self._items = {}

    def get(self, item):
        """Get a source entity in the collection or None."""
        key = self._generate_key(item)
        return self._items.get(key, None)

    def add(self, item):
        """Add a source entity to the collection."""
        key = self._generate_key(item)
        self._items[key] = item

    def __contains__(self, item):
        key = self._generate_key(item)
        return key in self._items

    def __iter__(self):
        return iter(self._items)

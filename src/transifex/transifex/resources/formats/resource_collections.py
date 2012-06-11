# -*- coding: utf-8 -*-
"""
A series of classes that hold collections of the resources' app objects.
"""

from django.utils import simplejson as json
from transifex.resources.models import SourceEntity, Translation


class StringSet(object):
    """
    Store a list of Translation objects for a given language.
    """
    def __init__(self):
        self.strings = []
        self.target_language = None

    def strings_grouped_by_context(self):
        d = {}
        for i in self.strings:
            if i.context in d:
                d[i.context].append(i)
            else:
                d[i.context] = [i,]
        return d

    def to_json(self):
        return json.dumps(self, cls=CustomSerializer)


class GenericTranslation(object):
    """
    Store translations of any kind of I18N type (POT, Qt, etc...).

    Parameters:
        source_entity - The original entity found in the source code.
        translation - The related source_entity written in another language.
        context - The related context for the source_entity.
        occurrences - Occurrences of the source_entity from the source code.
        comments - Comments for the given source_entity from the source code.
        rule - Plural rule 0=zero, 1=one, 2=two, 3=few, 4=many or 5=other.
        pluralized - True if the source_entity is a plural entry.
        fuzzy - True if the translation is fuzzy/unfinished
        obsolete - True if the entity is obsolete
    """
    def __init__(self, source_entity, translation, occurrences=None,
            comment=None, flags=None, context=None, rule=5, pluralized=False,
            fuzzy=False, obsolete=False):
        self.source_entity = source_entity
        self.translation = translation
        self.context = context
        self.occurrences = occurrences
        self.comment = comment
        self.flags = flags
        self.rule = int(rule)
        self.pluralized = pluralized
        self.fuzzy = fuzzy
        self.obsolete = obsolete

    def __hash__(self):
        if STRICT:
            return hash((self.source_entity, self.translation,
                self.occurrences))
        else:
            return hash((self.source_entity, self.translation))

    def __eq__(self, other):
        if isinstance(other, self.__class__) and \
            self.source_entity == other.source_entity and \
            self.translation == other.translation and \
            self.context == other.context:
            return True
        return False


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


class SourceEntityCollection(ResourceItems):
    """A collection of source entities."""

    def _generate_key(self, se):
        """Generate a key for this se, which is guaranteed to
        be unique within a resource.
        """
        if isinstance(se, GenericTranslation):
            return self._create_unique_key(se.source_entity, se.context)
        elif isinstance(se, SourceEntity):
            return self._create_unique_key(se.string, se.context)

    def _create_unique_key(self, source_string, context):
        """Create a unique key based on the source_string and the context.

        Args:
            source_string: The source string.
            context: The context.
        Returns:
            A tuple to be used as key.
        """
        if not context:
            return (source_string, u'None')
        elif isinstance(context, list):
            return (source_string, u':'.join(x for x in context))
        else:
            return (source_string, context)

    def se_ids(self):
        """Return the ids of the sourc entities."""
        return set(map(lambda se: se.id, self._items.itervalues()))


class TranslationCollection(ResourceItems):
    """A collection of translations."""

    def _generate_key(self, t):
        """Generate a key for this se, which is guaranteed to
        be unique within a resource.

        Args:
            t: a translation (sort of) object.
            se_id: The id of the source entity of this translation.
        """
        if isinstance(t, Translation):
            return self._create_unique_key(t.source_entity_id, t.rule)
        elif isinstance(t, tuple):
            return self._create_unique_key(t[0].id, t[1].rule)
        else:
            return None

    def _create_unique_key(self, se_id, rule):
        """Create a unique key based on the source_string and the context.

        Args:
            se_id: The id of the source string this translation corresponds to.
            rule: The rule of the language this translation is for.
        Returns:
            A tuple to be used as key.
        """
        assert se_id is not None
        return (se_id, rule)

    def se_ids(self):
        """Get the ids of the source entities in the collection."""
        return set(map(lambda t: t[0], self._items.iterkeys()))

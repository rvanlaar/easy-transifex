# -*- coding: utf-8 -*-
import re
from django.utils.hashcompat import md5_constructor

def hash_tag(source_entity, context):
    """Calculate the md5 hash of the (source_entity, context)."""
    if type(context) == list:
        if context:
            keys = [source_entity] + context
        else:
            keys = [source_entity, '']
    else:
        if context == 'None':
            keys = [source_entity, '']
        else:
            keys = [source_entity, context]
    return md5_constructor(':'.join(keys).encode('utf-8')).hexdigest()

def escape_context(value):
    """
    Escape context to be able to calculate hash of a (source_entity, context).
    """
    if type(value) == list:
        return [_escape_colon(v) for v in value]
    else:
        return _escape_colon(value)

def _escape_colon(value):
    """Escape colon in the string."""
    return re.sub(r'(?<!\\)\:', '\:', unicode(value))
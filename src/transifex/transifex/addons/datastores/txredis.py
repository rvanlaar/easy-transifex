# -*- coding: utf-8 -*-

"""
Redis backend.
"""

import cPickle as pickle
import functools
from redis import StrictRedis, ConnectionError
from transifex.txcommon.log import logger


class TxRedis(object):
    """Wrapper class around redis for Transifex."""

    def __init__(self, host='127.0.0.1', port=6379, db=0):
        self._r = StrictRedis(host=host, port=port, db=db)

    def __getattr__(self, name):
        """Forward all method calls to redis."""
        return getattr(self._r, name)


class TxRedisMapper(TxRedis):
    """A redis wrapper which provides support for objects, too."""

    set_methods = ['lpush', ]
    get_methods = ['lrange', 'lpop', ]

    def __getattr__(self, name):
        """Send all method calls to redis, while serializing arguments and
        results.

        Using pickle for (de)serialization. For argument serialization,
        he must provide the data in a dictionary named `data`.
        """
        attr = getattr(self._r, name)
        if name in self.set_methods:
            def new_attr(*args, **kwargs):
                if kwargs:      # argument serialization
                    data = pickle.dumps(kwargs.pop('data'))
                    args = list(args)
                    # value data almost always goes to the end
                    # override the other methods manually
                    args.append(data)
                return attr(*args, **kwargs)
            return functools.update_wrapper(new_attr, attr)
        elif name in self.get_methods:
            def new_attr(*args, **kwargs):
                res = attr(*args, **kwargs)
                if isinstance(res, basestring):
                    return pickle.loads(res)
                elif isinstance(res, list):
                    new_res = []
                    for r in res:
                        new_res.append(pickle.loads(r))
                    return new_res
                else:
                    return res
            return functools.update_wrapper(new_attr, attr)
        else:
            return super(TxRedisMapper, self).__getattr__(name)

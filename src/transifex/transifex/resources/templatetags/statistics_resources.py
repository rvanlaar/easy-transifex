import operator

from django import template
from django.utils.timesince import timesince
from transifex.languages.models import Language

register = template.Library()

class StatBarsPositions(dict):
    """
    Hold the positions of a number of statistic bars.

    Used to present bars for translation completion status.
    """

    class BarPos:
        def __init__(self, width, left=0):
            """Initialize a simple bar."""
            self.w = width
            self.l = left

    def __init__(self, bar_data, width=100, border=1):
        """
        A dictionary to hold the positions of named bars.

        Arguments:

        - An ordered list of tuples (name, bar_width) to render
        - The width of the "100%" bar in pixels
        - The width of a border to pad each consecutive non-zero-sized bar

        Example:

        >>> pos = [('a', 2), ('b', 1), border=1]
        >>> pos['a'].w
        2
        >>> pos['b'].l   # Should return first bar width + border = 2
        3
        """
        innerwidth = width
        if innerwidth < 0:
            raise ValueError('Too many items (%d) for given width (%d) '
                'and border (%d)' % (len(bar_data), width, border))

        totsegwidth = reduce(operator.add, (x[1] for x in bar_data), 0)
        if totsegwidth == 0:
            # No translations whatsoever
            self['trans'] = self.BarPos(width, 0)
            self['fuzzy'] = self.BarPos(0, width)
            self['untrans'] = self.BarPos(0, width)
            return
        oldend = 0
        for segnum, segment in enumerate(bar_data):
            if segment[1] < 0:
                raise ValueError('Negative segment size (%d) given for '
                    'element %d'% (segment[1], segnum + 1))
            fl = oldend
            fr = fl + segment[1] * innerwidth
            oldend = fr
            l = int(round(float(fl) / totsegwidth))
            r = int(round(float(fr) / totsegwidth))
            self[segment[0]] = self.BarPos(r - l, l)
        return

@register.inclusion_tag("resources/stats_bar_simple.html")
def stats_bar_simple(stat, width=100):
    """
    Create a HTML bar to present the statistics of an object.

    The object should have attributes trans_percent/untrans_percent.
    Accepts an optional parameter to specify the width of the total bar.

    We do a bit of calculations ourselfs here to reduce the pressure on
    the database.
    """
    total = stat.total
    trans = stat.translated

    try:
        trans_percent = (trans * 100 / total)
    except ZeroDivisionError:
        trans_percent = 100

    untrans_percent = 100 - trans_percent
    untrans = total - trans

    return {'untrans_percent': untrans_percent,
            'trans_percent': trans_percent,
            'untrans': untrans,
            'trans': trans,
            'pos': StatBarsPositions([('trans', trans_percent),
                                      ('untrans', untrans_percent)], width),
            'width':width}

@register.inclusion_tag("resources/stats_bar_actions.html")
def stats_bar_actions(stat, width=100):
    """
    Create a HTML bar to present the statistics of an object.

    The object should have attributes trans_percent/untrans_percent.
    Accepts an optional parameter to specify the width of the total bar.
    """
    try:
        trans_percent = (stat.translated * 100 / stat.total)
    except ZeroDivisionError:
        trans_percent = 100
    untrans_percent = 100 - trans_percent
    return {'untrans_percent': untrans_percent,
            'trans_percent': trans_percent,
            'pos': StatBarsPositions([('trans', trans_percent),
                                      ('untrans', untrans_percent)], width),
            'width':width}

@register.filter(name='percentage')
def percentage(fraction, population):
    try:
        return "%s%%" % int(((fraction)*100 / (population)) )
    except ZeroDivisionError:
        if population == fraction:
            return "100%%"
        else:
            return ''
    except ValueError:
        return ''


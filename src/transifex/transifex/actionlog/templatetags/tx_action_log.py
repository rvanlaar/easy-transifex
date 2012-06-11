from django import template
from actionlog.models import LogEntry

register = template.Library()

class LogNode(template.Node):
    def __init__(self, limit, varname, user=None, object=None, log_type='get_log'):
        self.limit, self.varname, self.object , self.user = (limit, varname,
                                                             object, user)
        self.log_type = log_type

    def __repr__(self):
        return "<GetLog Node>"

    def render(self, context):
        if self.user is not None:
            user = template.Variable(self.user).resolve(context)
            if self.log_type and self.log_type == 'get_public_log':
                query = LogEntry.objects.by_user_and_public_projects(user)
            else:
                query = LogEntry.objects.by_user(user)
        elif self.object is not None:
            obj = template.Variable(self.object).resolve(context)
            query = LogEntry.objects.by_object(obj)

        context[self.varname] = query[:self.limit]
        return ''

class DoGetLog:
    """
    Populates a template variable with the log for the given criteria.

    Usage::

        {% get_log <limit> as <varname> [for object <context_var_containing_user_obj>] %}

    Examples::

        {% get_log 10 as action_log for_object foo %}
        {% get_log 10 as action_log for_user current_user %}
    """

    def __init__(self, tag_name):
        self.tag_name = tag_name

    def __call__(self, parser, token):
        tokens = token.contents.split()
        if len(tokens) < 4:
            raise template.TemplateSyntaxError, (
                "'%s' statements requires two arguments" % self.tag_name)
        if not tokens[1].isdigit():
            raise template.TemplateSyntaxError, (
                "First argument in '%s' must be an integer" % self.tag_name)
        if tokens[2] != 'as':
            raise template.TemplateSyntaxError, (
                "Second argument in '%s' must be 'as'" % self.tag_name)
        if len(tokens) > 4:
            if tokens[4] == 'for_user':
                return LogNode(limit=tokens[1], varname=tokens[3],
                               user=(len(tokens) > 5 and tokens[5] or None),
                               log_type=self.tag_name)
            elif tokens[4] == 'for_object':
                return LogNode(limit=tokens[1], varname=tokens[3],
                               object=(len(tokens) > 5 and tokens[5] or None),
                               log_type=self.tag_name)
            else:
                raise template.TemplateSyntaxError, (
                    "Fourth argument in '%s' must be either 'user' or "
                    "'object'" % self.tag_name)

register.tag('get_log', DoGetLog('get_log'))
register.tag('get_public_log', DoGetLog('get_public_log'))

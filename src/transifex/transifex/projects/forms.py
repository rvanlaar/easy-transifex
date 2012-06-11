from django import forms
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.db.models import permalink
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms import widgets
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe
from django.contrib.auth import authenticate

from ajax_select.fields import AutoCompleteSelectMultipleField
from tagging.forms import TagField
from tagging_autocomplete.widgets import TagAutocomplete

from transifex.projects.models import Project
from transifex.projects.signals import (project_access_control_form_start,
                                        project_form_init, project_form_save)
from transifex.txcommon.widgets import SplitSelectDateTimeWidget


class ProjectForm(forms.ModelForm):
    maintainers = AutoCompleteSelectMultipleField(
        'users', label=_("Maintainers"), required=True,
        help_text=_('Search for a username')
    )
    tags = TagField(label=_("Tags"), widget=TagAutocomplete(), required=False)

    class Meta:
        model = Project
        exclude = ('anyone_submit', 'outsource', 'owner')
        fields = (
            'name', 'slug', 'description', 'trans_instructions', 'tags',
            'long_description', 'maintainers', 'private', 'homepage', 'feed',
            'bug_tracker', 'source_language'
        )

    def __init__(self, *args, **kwargs):
        super(ProjectForm, self).__init__(*args, **kwargs)
        # Disable the source_language widget when updating
        if self.instance and self.instance.id:
            if self.instance.resources.count():
                self.fields['source_language'].required = False
                self.fields['source_language'].widget.attrs['disabled'] = 'disabled'
        project_form_init.send(sender=ProjectForm, form=self)

    def save(self, *args, **kwargs):
        retval = super(ProjectForm, self).save(*args, **kwargs)
        project_form_save.send(sender=ProjectForm, form=self, instance=retval)
        return retval

    def clean_tags(self):
        project_tags_list = self.cleaned_data['tags']
        tags = list(set([tag.strip() for tag in project_tags_list.split(',')])) or []
        for i in tags:
            if not i.strip():
                tags.remove(i)
        tags.append(u'')
        project_tags_list = ', '.join(tags)
        return project_tags_list

    def clean_source_language(self):
        if self.instance and self.instance.id:
            if self.instance.resources.count():
                return self.instance.source_language
            else:
                return self.cleaned_data['source_language']
        else:
            return self.cleaned_data['source_language']

class ProjectDeleteForm(forms.Form):
    """
    A form used to check the user password before deleting a project.
    """
    password = forms.CharField(widget=forms.PasswordInput,
                               label=_('Your password'))

    def __init__(self, request, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super(ProjectDeleteForm, self).__init__(*args, **kwargs)

    def clean(self):
        password = self.cleaned_data.get('password')
        if password:
            self.user_cache = authenticate(username=self.request.user.username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(_("Invalid password."))

        return self.cleaned_data


class RadioFieldRenderer(widgets.RadioFieldRenderer):
    """
    An object used by RadioSelect to enable customization of radio widgets.
    """
    def get_class(self, v, v2):
        """
        Return the string 'selected' if both values are equal.

        This is used to set a class attr on the selected radio button.
        """
        if v==v2:
            return 'selected'
        else:
            return ''

    def render(self):
        """Outputs a <ul> for this set of radio fields."""
        help_text = self.attrs['help_text']
        self.attrs.pop('help_text')
        return mark_safe(u'<ul>\n%s\n</ul>' % u'\n'.join(
            [u'<li class="%s"><span>%s</span><p class="helptext">%s</p></li>'
                % (self.get_class(w.value, w.choice_value),
                   force_unicode(w),
                   help_text[w.choice_value]) for w in self]))


class ProjectAccessControlForm(forms.ModelForm):
    """Form to handle the Access Control options of a project."""
    access_control_options=[
        {'free_for_all': {
            'label': _('Free for all'),
            'help_text': _(
                "Allow any logged-in user to submit files to my project. "
                "<a href=\"http://www.youtube.com/watch?v=-b7qaSxuZUg\" "
                "target=\"_blank\">Imagine</a> all the people, sharing all the "
                "world. Recommended for quick translations, and when a "
                "pre-commit review process is in place, e.g. when "
                "contributions are submitted by email or to a separate branch.")
            }
        },
        {'limited_access': {
            'label': _('Limited access'),
            'help_text': _(
                "Give access to specific people. Translations teams will have "
                "access to their language's files only, and global writers "
                "will have access to all translation files. Recommended for "
                "most projects."),
            }
        },
        {'outsourced_access': {
            'label': _('Outsourced access'),
            'help_text': _(
                "Re-use another project's teams and writers by delegating "
                "access control to that project. If a person can contribute to "
                "that project, it can contribute to this one as well. "
                "Recommended for non-upstream projects such as distribution "
                "packages and desktop environment modules."),
            }
        },
    ]

    # Setting up some vars based on the 'access_control_options' var
    access_control_types = []
    access_control_help = {}
    for o in access_control_options:
        for k, v in o.items():
            access_control_types.append((k, v['label']))
            access_control_help.update({k: v['help_text']})

    # Add field
    access_control = forms.ChoiceField(choices=access_control_types,
        required=True, widget=forms.RadioSelect(
            renderer=RadioFieldRenderer,
            attrs={'help_text': access_control_help }))

    class Meta:
        model = Project
        fields = ('access_control', 'outsource')

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(ProjectAccessControlForm, self).__init__(*args, **kwargs)
        # Changing some field settings based on the project attr and the
        # request.DATA
        project = kwargs.get('instance', None)
        outsource_required = False
        if args:
            access_control_initial = args[0]['access_control']
            if 'outsourced_access' == access_control_initial:
                outsource_required = True
        elif project:
            if project.anyone_submit:
                access_control_initial = 'free_for_all'
            elif project.outsource:
                access_control_initial = 'outsourced_access'
                outsource_required = True
            else:
                access_control_initial = 'limited_access'

        self.fields['access_control'].initial = access_control_initial
        self.fields['outsource'].required = outsource_required

        # Filtering project list

        if user:
            self.fields["outsource"].queryset = Project.objects.for_user(
                user).exclude(slug=project.slug).only('id', 'name')
        else:
            projects = self.fields["outsource"].queryset.\
                    exclude(slug=project.slug).exclude(private=True)
            self.fields["outsource"].queryset = projects
        project_access_control_form_start.send(sender=ProjectAccessControlForm,
                                               instance=self, project=project)

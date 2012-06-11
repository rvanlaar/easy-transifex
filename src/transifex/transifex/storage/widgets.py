from django import forms
from django.forms.util import flatatt
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from transifex.languages.models import Language
from transifex.storage.models import StorageFile
from transifex.txcommon.log import logger
from transifex.txcommon.utils import get_url_pattern

class StorageFileWidget(forms.MultiWidget):
    """
    Widgets for handling StorageFile objects creation/deletion. It can be
    used with normal Django forms. Everything happens through AJAX using the
    storage app API.
    """
    def __init__(self, *args, **kwargs):
        attrs = kwargs.pop('attrs', {})
        language = kwargs.pop('language', {})
        display_language = kwargs.pop('display_language', False)
        
        if not display_language:
            language_field=forms.HiddenInput(attrs=attrs)
        else:
            self.language_choices = kwargs.pop('language_choices', [])
            if not self.language_choices:
                queryset = Language.objects.all()
                self.language_choices = [(l.code, l) for l in queryset]
            self.language_choices.insert(0, ("", "---------"))

            language_field = forms.Select(attrs=attrs,
                choices=self.language_choices)

        widgets=(
            language_field,
            forms.HiddenInput(attrs=attrs)
        )
        super(StorageFileWidget, self).__init__(widgets, attrs)

    def render(self, name, value, attrs):
        if hasattr(self, 'initial'):
            value = self.initial

        final_attrs = self.build_attrs(attrs)
        self.html_id = final_attrs.pop('id', name)

        if not isinstance(value, list):
            value = self.decompress(value)

        # Querying objects
        language, storagefile = None, None
        if value:
            try:
                language = Language.objects.by_code_or_alias(value[0])
            except Exception, e:
                pass
            try:
                storagefile = StorageFile.objects.get(id=int(value[1]))
            except Exception, e:
                pass

        # Fields in HTML
        rendered_fields = []
        rendered_fields.append(self.widgets[0].render(name + '_0',
            getattr(language, 'code', None), final_attrs))
        rendered_fields.append(self.widgets[1].render(name + '_1',
            getattr(storagefile, 'id', None), final_attrs))

        context = {
                'name': name,
                'names': [name + '_%s' %n for n, w in enumerate(self.widgets)],
                'storagefile': storagefile,
                'rendered_fields': rendered_fields,
                'api_storagefile_url': get_url_pattern('api.storage.file'),
                }

        return mark_safe(
            render_to_string('storage/storagefilewidget.html', context)
            )

    def decompress(self, value):
        if value:
            return value
        return ['','']

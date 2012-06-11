from django import forms
from django.utils.translation import ugettext as _
from transifex.languages.models import Language
from transifex.storage.models import StorageFile
from transifex.storage.widgets import StorageFileWidget


class StorageFileField(forms.MultiValueField):
    """
    Field for handling creation/deletion of StorageFile objects based on
    file upload.

    Whenever a file is chosen to be uploaded, the upload happens through AJAX
    using the storage app API, creating a StorageFile object accordingly. The
    deletion of the uploaded file happens through AJAX too, as the setting of
    the related language to the StogareFile object.

    In the end this field just returns the StorageFile id, which is the
    important data used in the forms.
    """
    def __init__(self, language=None, *args, **kwargs):
        attrs = kwargs.pop('attrs', {})
        language_initial = getattr(language, 'code', None)
        if language_initial:
            language_queryset = Language.objects.filter(code=language_initial)
        else:
            language_queryset = Language.objects.all()

        language_choices = [(l.code, l) for l in language_queryset]
        storagefile_choices = StorageFile.objects.all()
        # Hard coded fields
        fields = [
            # The API uses language code, so it can't be a ModelChoiceField
            forms.ChoiceField(choices=language_choices, initial=language_initial),
            forms.ModelChoiceField(queryset=storagefile_choices)
        ]
        # Hard coded widget
        widget = StorageFileWidget(attrs=attrs, language=language,
            language_choices=language_choices,  *args, **kwargs)
        # Remove unsupported kwarg
        kwargs.pop('display_language', None)
        super(StorageFileField, self).__init__(fields, widget=widget,
            *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            return data_list
        return ['','']

    def clean(self, value):
        """Return only the StorageFile id/object after all the validations."""
        data = super(StorageFileField, self).clean(value)
        return data[1]
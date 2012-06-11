from django.contrib import admin
from transifex.storage.models import StorageFile

class StorageAdmin(admin.ModelAdmin):
    search_fields = ['name', 'size', 'language__name', 'user__username',
        'uuid']
    list_display = ['name', 'size', 'language', 'user', 'uuid', 'created']

admin.site.register(StorageFile, StorageAdmin)

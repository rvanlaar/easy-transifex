from django.contrib import admin
from transifex.projects.models import Project
from authority.admin import PermissionInline

class ProjectAdmin(admin.ModelAdmin):
    search_fields = ['name', 'description']
    list_display = ['name', 'description']

admin.site.register(Project, ProjectAdmin, inlines=(PermissionInline,))

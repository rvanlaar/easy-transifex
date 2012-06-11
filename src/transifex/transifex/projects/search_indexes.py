import datetime
from haystack.indexes import *
from haystack import site

from transifex.projects.models import Project


class ProjectIndex(RealTimeSearchIndex):

    text = CharField(document=True, use_template=True)
    
    slug = CharField(model_attr='slug', null=False)
    name = CharField(model_attr='name', null=False, boost=1.125)
    description = CharField(model_attr='description', null=True) 

    # django-haystack-1.2 needs it along with the custom prepare method
    suggestions = CharField()

    def prepare(self, obj):
        prepared_data = super(ProjectIndex, self).prepare(obj)
        prepared_data['suggestions'] = prepared_data['text']
        return prepared_data

    def index_queryset(self):
        """Used when the entire index for model is updated."""
        # Do not index private projects
        return Project.objects.exclude(private=True).filter(
            modified__lte=datetime.datetime.now())

    def should_update(self, instance, **kwargs):
        """
        Determine if an object should be updated in the index.
        """
        if instance.private:
            return False
        return True

    # TODO: Newer version of django-haystack has support for .using() and this
    # method needs to be refactored once using that.
    def update_object(self, instance, **kwargs):
        """
        Update the index for a single object. Attached to the class's
        post-save hook.
        """
        # Check to make sure we want to index this first.
        if self.should_update(instance, **kwargs):
            self.backend.update(self, [instance])
        else:
            # self.should_update checks whether a project is private or not.
            # If it was open and now it's private, it should be removed from the
            # indexing. Private projects should NOT be indexed for now.
            self.remove_object(instance, **kwargs)


    def get_updated_field(self):
        """Project mode field used to identify new/modified object to index."""
        return 'modified'

site.register(Project, ProjectIndex)
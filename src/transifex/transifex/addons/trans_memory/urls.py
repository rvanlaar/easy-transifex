from django.conf.urls.defaults import *
from views import search_translations

urlpatterns = patterns('',
    # Search strings
    url(r'^search_translations/$', search_translations, name='search_translations'),
)

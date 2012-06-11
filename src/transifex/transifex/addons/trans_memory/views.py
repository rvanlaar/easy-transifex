from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from transifex.languages.models import Language
from transifex.resources.models import Translation

DEFAULT_LANG_CODE = 'en'

# FIXME: Search only in public projects
@login_required
def search_translations(request):
    """Search for existing translations.

    This view accepts three GET variables and uses them to search in existing
    translations. It searches all the strings (translations) and returns those
    which match the string query in the particular language.

    tq:
      The string to search the database for.
    source_lang:
      The language which we should search the string for and can be any
      language.
    target_lang:
      Limit the shown results to only those which have this target language.

    """

    query_string = request.GET.get('tq', "")
    source_language_code = request.GET.get('source_lang', DEFAULT_LANG_CODE)
    source_language = Language.objects.get(code=source_language_code)
    target_language_code = request.GET.get('target_lang', None)

    search_terms = query_string.split()
    #TODO: Add check to only allow terms bigger than 2 letters

    translations = []

    if search_terms:
        #FIXME: Make searching work with terms, not full strings like now.
        #The searching should be done with OR for each term.
        search_dict = {'string': query_string,
                       'user': request.user,
                       'source_code': source_language_code}
        if target_language_code:
            search_dict.update({'target_code': target_language_code})
        translations = Translation.objects.by_string_and_language(
            **search_dict).order_by('language').exclude(language__code=source_language_code)

    #FIXME: Make the source_language lookup more efficient. The code below
    # attempts to replace the multiple db hits by the template tag by creating
    # a lookup dictionary once.
    #source_entity_ids = translations.values('source_entity_id')
    #sources = Translation.objects.filter(
    #    source_entity__id__in=translations, language=source_language).values(
    #   'source_entity', 'string')

    return render_to_response("search_translation.html", {
        'languages': Language.objects.all(),
        'query': query_string,
        'source_language': source_language,
        'target_language_code': target_language_code,
        'translations': translations,
        'terms': search_terms},
        context_instance = RequestContext(request))


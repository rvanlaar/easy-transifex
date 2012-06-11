from django import template

register = template.Library()

@register.filter(name='entity_translation')
def entity_translation(source_entity, language):
    return source_entity.get_translation(language.code)


@register.filter
def sort_source_langs_first(rlstats, source_languages):
    """
    Take a RLStats aggregated queryset and move the entries related to the
    source_languages to the top of the list.
    """
    rlstats_source_list, rlstats_list = [], []
    for r in rlstats:
        if r.object in source_languages:
            rlstats_source_list.append(r)
        else:
            rlstats_list.append(r)
    # 'tag' first translation entry in the list
    if rlstats_list:
        stat = rlstats_list[0]
        stat.first_translation = True
        rlstats_list = [stat] + rlstats_list[1:]

    return rlstats_source_list + rlstats_list
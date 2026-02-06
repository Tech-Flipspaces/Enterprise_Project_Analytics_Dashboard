from django import template             # type:ignore

register = template.Library()

@register.simple_tag(takes_context=True)
def update_params(context, **kwargs):
    """
        Returns the current URL query string with updated parameters.
        Usage: {% update_params group='operations' %}
        Result: ?start_date=2025-01-01&region=North&group=operations
    """
    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        query[key] = value
    return query.urlencode()
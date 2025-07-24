from django import template
from django.forms.boundfield import BoundField

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css_class):
    if isinstance(field, BoundField):
        existing_classes = field.field.widget.attrs.get("class", "")
        new_classes = f"{existing_classes} {css_class}".strip()
        return field.as_widget(attrs={"class": new_classes})
    return field

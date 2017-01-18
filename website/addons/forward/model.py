# -*- coding: utf-8 -*-

from modularodm import fields
from modularodm.validators import (
    URLValidator
)
from modularodm.exceptions import ValidationValueError

from osf.models.validators import validate_no_html

from website.addons.base import AddonNodeSettingsBase


class ForwardNodeSettings(AddonNodeSettingsBase):

    complete = True
    has_auth = True

    url = fields.StringField(validate=URLValidator())
    label = fields.StringField(validate=validate_no_html)

    @property
    def link_text(self):
        return self.label if self.label else self.url

    def on_delete(self):
        self.reset()

    def reset(self):
        self.url = None
        self.label = None

    def after_register(self, node, registration, user, save=True):
        clone = self.clone()
        clone.owner = registration
        clone.on_add()
        clone.save()

        return clone, None


@ForwardNodeSettings.subscribe('before_save')
def validate_circular_reference(schema, instance):
    """Prevent node from forwarding to itself."""
    if instance.url and instance.owner._id in instance.url:
        raise ValidationValueError('Circular URL')

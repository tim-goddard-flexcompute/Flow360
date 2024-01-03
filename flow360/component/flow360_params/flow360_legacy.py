"""
Legacy field definitions and updaters (fields that are not
specified in the documentation but can be used internally
during validation, most legacy classes can be updated to
the current standard via the update_model method)
"""
from abc import ABCMeta, abstractmethod
from typing import Dict, Optional

import pydantic as pd

from flow360.component.flow360_params.params_base import Flow360BaseModel
from flow360.component.flow360_params.unit_system import DimensionedType


class LegacyModel(Flow360BaseModel, metaclass=ABCMeta):
    """:class: `LegacyModel` is used by legacy classes to"""

    comments: Optional[Dict] = pd.Field()

    @abstractmethod
    def update_model(self):
        """Update the legacy model to the up-to-date version"""


def try_add_unit(model, key, unit: DimensionedType):
    """Add unit to an existing updater field"""
    if model[key] is not None:
        model[key] *= unit


def try_set(model, key, value):
    """Set existing updater field if it exists in the legacy model"""
    if value is not None and model.get(key) is None:
        model[key] = value


def try_update(field: Optional[LegacyModel]):
    """Try running updater on the field if it exists"""
    if field is not None:
        return field.update_model()
    return None


def get_output_fields(instance: Flow360BaseModel, exclude, allowed=None):
    """Retrieve all output fields of a legacy output instance"""
    fields = []
    for key, value in instance.__fields__.items():
        if value.type_ == bool and value.alias not in exclude and getattr(instance, key) is True:
            if allowed is not None and value.alias in allowed:
                fields.append(value.alias)
    return fields
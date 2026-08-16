import pytest
from pydantic import ValidationError

from api.models import ComparisonCreate, CustomNameUpdate, ImagePosition, TagList


def test_model_defaults_are_independent():
    first = TagList()
    second = TagList()
    first.tags.append("one")

    comparison = ComparisonCreate()

    assert second.tags == []
    assert comparison.total_rows == 1
    assert comparison.total_columns == 2
    assert comparison.expiration_days == 7


def test_position_and_custom_name_require_values():
    assert ImagePosition(filename="image.png", row=0, column=1).column == 1
    assert CustomNameUpdate(custom_name="Visible").custom_name == "Visible"
    with pytest.raises(ValidationError):
        ImagePosition(filename="image.png", row=0)

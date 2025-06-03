import pytest
import yaml

from waveform_editor.annotations import Annotations
from waveform_editor.yaml_parser import LineNumberYamlLoader


@pytest.fixture
def filled_annotations():
    test_messages = ["error message", "warning message"]
    line_numbers = [0, 5]
    annotations = [
        {
            "row": line_numbers[0],
            "column": 0,
            "text": test_messages[0],
            "type": "error",
        },
        {
            "row": line_numbers[1] - 1,  # account for annotation offset
            "column": 0,
            "text": test_messages[1],
            "type": "warning",
        },
    ]
    return test_messages, line_numbers, annotations


def test_empty():
    """Test if empty annotations returns empty list."""
    annotations = Annotations()
    assert annotations == []


def test_add(filled_annotations):
    """Test adding error to the annotations instance."""
    (test_messages, line_numbers, annotation_list) = filled_annotations
    annotations = Annotations()
    annotations.add(line_numbers[0], test_messages[0])
    annotations.add(line_numbers[1], test_messages[1], is_warning=True)

    assert annotations == annotation_list


def test_add_annotations(filled_annotations):
    """Test adding annotations to the annotations."""
    (test_messages, line_numbers, annotation_list) = filled_annotations
    annotations1 = Annotations()
    annotations2 = Annotations()
    annotations1.add(line_numbers[0], test_messages[0])
    annotations2.add(line_numbers[1], test_messages[1], is_warning=True)

    annotations1.add_annotations(annotations2)

    assert annotations1 == annotation_list


def test_add_yaml_error():
    """Test adding YAML parsing error to annotations."""
    annotations = Annotations()
    try:
        yaml.load(",", Loader=LineNumberYamlLoader)
    except yaml.YAMLError as e:
        annotations.add_yaml_error(e)

    assert annotations[0]["type"] == "error"
    assert "," in annotations[0]["text"]
    assert annotations[0]["row"] == 0
    assert annotations[0]["column"] == 0


def test_suggest():
    """Test suggestions for misspelled words."""
    annotations = Annotations()
    keywords = ["start", "end", "duration"]
    assert annotations.suggest("starrt", keywords) == "Did you mean 'start'?\n"
    assert annotations.suggest("ennnd", keywords) == "Did you mean 'end'?\n"
    assert annotations.suggest("durasdtion", keywords) == "Did you mean 'duration'?\n"
    assert annotations.suggest("asdf", keywords) == ""

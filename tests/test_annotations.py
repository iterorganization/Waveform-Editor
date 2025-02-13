import yaml

from waveform_editor.annotations import Annotations
from waveform_editor.yaml_parser import LineNumberYamlLoader


def test_empty():
    """Test if empty annotations returns empty list."""
    annotations = Annotations()
    assert annotations == []


def test_add():
    """Test adding error to the annotations instance."""
    annotations = Annotations()
    test_messages = ["error message", "warning message"]
    line_numbers = [0, 5]
    annotations.add(line_numbers[0], test_messages[0])
    annotations.add(line_numbers[1], test_messages[1], is_warning=True)

    assert annotations == [
        {
            "row": line_numbers[0],
            "column": 0,
            "text": test_messages[0],
            "type": "error",
        },
        {
            "row": line_numbers[1],
            "column": 0,
            "text": test_messages[1],
            "type": "warning",
        },
    ]


def test_add_annotations():
    """Test adding annotations to the annotations."""
    annotations1 = Annotations()
    annotations2 = Annotations()
    test_messages = ["error message", "warning message"]
    line_numbers = [0, 5]
    annotations1.add(line_numbers[0], test_messages[0])
    annotations2.add(line_numbers[1], test_messages[1], is_warning=True)

    annotations1.add_annotations(annotations2)

    assert annotations1 == [
        {
            "row": line_numbers[0],
            "column": 0,
            "text": test_messages[0],
            "type": "error",
        },
        {
            "row": line_numbers[1],
            "column": 0,
            "text": test_messages[1],
            "type": "warning",
        },
    ]


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

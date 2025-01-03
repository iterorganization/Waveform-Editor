from waveform_editor.yaml_parser import YamlParser

yaml_parser = YamlParser()
yaml_parser.parse_waveforms("../tests/test_yaml/test_all.yaml")
yaml_parser.plot_tendencies(100)

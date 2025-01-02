from waveform_editor.yaml_parser import YamlParser

asdf = YamlParser()
asdf.parse_waveforms("../tests/test_yaml/test_all.yaml")
asdf.plot_tendencies(2)

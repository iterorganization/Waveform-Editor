import xml.etree.ElementTree as ET
from pathlib import Path


class PCSSPExporter:
    """Exports waveform configuration into PCSSP-compatible XML format. Information on
    the PCSSP can be found here: https://github.com/iterorganization/PCSSP
    """

    def __init__(self, config, times):
        self.config = config
        self.times = times

    def export(self, file_path):
        """Export configuration as an PCSSP XML file.

        Args:
            file_path: Destination file path for the XML output.
        """
        root = ET.Element("SCHEDULE")
        declarations = ET.SubElement(root, "DECLARATIONS")
        ET.SubElement(declarations, "PARAMETERS")
        outputs = ET.SubElement(declarations, "OUTPUTS")

        self._add_signals(outputs)

        segments = ET.SubElement(root, "SEGMENTS")
        # Only a single segment is currently supported
        segment = ET.SubElement(
            segments,
            "SEGMENT",
            {
                "name": "Waveform Editor",
                "id": "0",
                "wd_time": str(self.times[-1]),
                "wd_target": "EHTerm1",
            },
        )
        self._add_trajectories(segment)

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)

    def _add_signals(self, parent):
        """Add signals from waveforms to the given XML parent element.

        Args:
            parent: XML element to append the signal elements to.
        """
        for wf_name, group in self.config.waveform_map.items():
            waveform = group[wf_name]
            desc = "" if not waveform.metadata else waveform.metadata.documentation
            signal = {
                "name": waveform.name,
                "signal_type": "Amplitude",
                "type": "double",
                "dimension": "1",
                "description": desc,
                "value": "0",
            }
            ET.SubElement(parent, "SIGNAL", signal)

    def _add_trajectories(self, segment):
        """Add trajectories to a XML segment based on the values of the waveforms.

        Args:
            segment: XML trajectories element to append trajectories to.
        """
        trajectories = ET.SubElement(segment, "SIGNALS_TRAJECTORIES")
        for wf_name, group in self.config.waveform_map.items():
            waveform = group[wf_name]
            trajectory = ET.SubElement(
                trajectories, "SIGNAL_TRAJECTORY", {"name": waveform.name}
            )
            ET.SubElement(trajectory, "ENTRY_RULE", {"is": "None"})
            ET.SubElement(trajectory, "EXECUTION_RULE", {"is": "Linear"})
            ET.SubElement(trajectory, "EXIT_RULE", {"is": "Last"})
            reference = ET.SubElement(trajectory, "REFERENCE")
            values = waveform.get_value(self.times)[1]
            for t, v in zip(self.times, values):
                ET.SubElement(reference, "POINT", {"time": str(t), "value": str(v)})

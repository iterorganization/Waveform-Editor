import type { WaveformSpec } from "../../types";
import { useStore } from "../../store";
import { Sparkline } from "./Sparkline";

interface Props {
  name: string;
  spec: WaveformSpec;
  color?: string;
}

export function WaveformLane({ name, spec, color = "#4f8ef7" }: Props) {
  const { shapePreviewData, openWaveformViewer } = useStore();

  const sparkTimes = shapePreviewData?.times ?? [];
  const sparkValues = shapePreviewData?.waveforms[name] ?? [];

  const isDerived = typeof spec === "string";

  return (
    <div
      className={`waveform-lane${isDerived ? "" : " waveform-lane--clickable"}`}
      onClick={() => { if (!isDerived) openWaveformViewer(name); }}
      title={isDerived ? name : `Edit ${name}`}
    >
      <span className={`lane-name ${isDerived ? "lane-derived" : ""}`}>{name}</span>
      <Sparkline times={sparkTimes} values={sparkValues} color={color} />
    </div>
  );
}

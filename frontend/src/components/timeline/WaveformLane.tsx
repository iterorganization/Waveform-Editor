import { useEffect, useState } from "react";
import { api } from "../../api";
import type { TendencyData, WaveformSpec } from "../../types";
import { useStore } from "../../store";
import { Sparkline } from "./Sparkline";
import { TendencyForm } from "./TendencyForm";

interface Props {
  name: string;
  spec: WaveformSpec;
  color?: string;
  onSpecChange?: (name: string, spec: WaveformSpec) => void;
}

export function WaveformLane({ name, spec, color = "#4f8ef7", onSpecChange }: Props) {
  const { expandedLaneId, setExpandedLane, parsedConfig, yamlContent, setYamlContent, parseCurrentYaml } =
    useStore();
  const isExpanded = expandedLaneId === name;

  const [sparkTimes, setSparkTimes] = useState<number[]>([]);
  const [sparkValues, setSparkValues] = useState<number[]>([]);

  const tStart = parsedConfig?.time_start ?? 0;
  const tEnd = parsedConfig?.time_end ?? 100;

  // Load sparkline data
  useEffect(() => {
    if (!yamlContent) return;
    const n = 60;
    const pts = Array.from({ length: n }, (_, i) => tStart + (i / (n - 1)) * (tEnd - tStart));
    api
      .evaluateWaveforms(yamlContent, pts, [name])
      .then((resp) => {
        const wf = resp.waveforms.find((w) => w.name === name);
        if (wf) {
          setSparkTimes(wf.times);
          setSparkValues(wf.values);
        }
      })
      .catch(() => {});
  }, [yamlContent, name, tStart, tEnd]);

  const isDerived = typeof spec === "string";
  const tendencies: TendencyData[] = isDerived ? [] : (spec as TendencyData[]);

  const handleTendencyChange = (updated: TendencyData[]) => {
    if (onSpecChange) {
      onSpecChange(name, updated);
      return;
    }

    const lines = yamlContent.split("\n");
    const startIdx = lines.findIndex((l) => l.trim().startsWith(`${name}:`));
    if (startIdx === -1) return;

    // Preserve the indentation of the original key line so the waveform
    // stays inside its group (e.g. "  kappa:" under "NICE Shape:").
    const indent = (lines[startIdx].match(/^(\s*)/) ?? ["", ""])[1];
    const seqPrefix = `${indent}- `;

    // Find end of this waveform's sequence block. Stop at any line that is
    // not a sequence item at this exact indentation (e.g. a sibling key).
    let endIdx = startIdx + 1;
    while (endIdx < lines.length && lines[endIdx].startsWith(seqPrefix)) {
      endIdx++;
    }

    const newBlock = [
      `${indent}${name}:`,
      ...updated.map((t) => {
        const entries = Object.entries(t)
          .filter(([, v]) => v !== undefined && v !== "")
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ");
        return `${seqPrefix}{${entries}}`;
      }),
    ];

    setYamlContent([...lines.slice(0, startIdx), ...newBlock, ...lines.slice(endIdx)].join("\n"));
    parseCurrentYaml();
  };

  return (
    <>
      <div
        className={`waveform-lane ${isExpanded ? "active" : ""}`}
        onClick={() => setExpandedLane(isExpanded ? null : name)}
        title={name}
      >
        <span className={`lane-name ${isDerived ? "lane-derived" : ""}`}>{name}</span>
        <Sparkline times={sparkTimes} values={sparkValues} color={color} />
        <span className="lane-chip">
          {isDerived ? "expr" : `${tendencies.length}t`}
        </span>
        <span style={{ color: "var(--text-muted)", fontSize: 12, marginLeft: 2 }}>
          {isExpanded ? "▲" : "▼"}
        </span>
      </div>

      {isExpanded && (
        <div className="lane-expand">
          {isDerived ? (
            <div>
              <div style={{ marginBottom: 6, fontSize: 11, color: "var(--text-muted)" }}>
                Derived expression:
              </div>
              <code style={{ fontSize: 12, color: "var(--accent2)", wordBreak: "break-all" }}>
                {spec as string}
              </code>
              <div style={{ marginTop: 8, fontSize: 11, color: "var(--text-muted)" }}>
                Edit in Advanced (YAML) mode to modify derived waveforms.
              </div>
            </div>
          ) : (
            <TendencyForm tendencies={tendencies} onChange={handleTendencyChange} />
          )}
        </div>
      )}
    </>
  );
}

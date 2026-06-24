import { useMemo, useState } from "react";
import { useStore } from "../../store";
import { NiceIntervalConfig } from "./NiceIntervalConfig";
import { PlasmaPropertiesSection } from "./PlasmaPropertiesSection";
import { PlasmaShapeSection } from "./PlasmaShapeSection";
import { WaveformLane } from "./WaveformLane";

// Groups with special meaning — shown in dedicated sections above
const NICE_GROUPS = new Set(["NICE Shape", "NICE Properties"]);
// Individual waveform names that belong to the NICE sections
const NICE_WAVEFORM_NAMES = new Set([
  "kappa", "delta", "a", "center_r", "center_z", "rx", "zx",
  "ip", "b0", "r0", "profile_alpha", "profile_beta", "profile_gamma",
]);

interface GroupNode {
  name: string;
  path: string[];
  waveforms: string[];
  children: GroupNode[];
}

function buildGroupTree(waveforms: Array<{ name: string; group_path: string[] }>): GroupNode[] {
  const root: Record<string, GroupNode> = {};

  for (const wf of waveforms) {
    if (!wf.group_path.length) continue;
    const topGroup = wf.group_path[0];
    if (NICE_GROUPS.has(topGroup)) continue;  // handled by dedicated sections
    if (NICE_WAVEFORM_NAMES.has(wf.name)) continue;  // handled by dedicated sections

    // Build nested structure
    let current = root;
    for (let i = 0; i < wf.group_path.length; i++) {
      const gname = wf.group_path[i];
      if (!current[gname]) {
        current[gname] = { name: gname, path: wf.group_path.slice(0, i + 1), waveforms: [], children: [] };
        // We need parent to reference this node — simplified flat approach:
        // just use a map keyed by path string
      }
      if (i === wf.group_path.length - 1) {
        current[gname].waveforms.push(wf.name);
      }
      current = Object.fromEntries(
        current[gname].children.map((c) => [c.name, c]),
      );
    }
  }

  return Object.values(root);
}

// Simpler flat build
function buildFlatGroups(
  waveforms: Array<{ name: string; group_path: string[] }>,
): Map<string, string[]> {
  const map = new Map<string, string[]>();
  for (const wf of waveforms) {
    const topGroup = wf.group_path[0] ?? "Ungrouped";
    if (NICE_GROUPS.has(topGroup)) continue;
    if (NICE_WAVEFORM_NAMES.has(wf.name)) continue;
    if (!map.has(topGroup)) map.set(topGroup, []);
    map.get(topGroup)!.push(wf.name);
  }
  return map;
}

function GroupSection({ name, waveforms }: { name: string; waveforms: string[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="section">
      <div className="section-header" onClick={() => setOpen(!open)}>
        <span className={`section-chevron ${open ? "open" : ""}`}>▶</span>
        <span className="section-title">{name}</span>
        <span className="section-badge">{waveforms.length}</span>
      </div>
      {open && (
        <div className="section-body">
          {waveforms.map((wfName) => (
            <WaveformLane key={wfName} name={wfName} spec={[]} />
          ))}
        </div>
      )}
    </div>
  );
}

export function WaveformTimeline() {
  const { parsedConfig, yamlError } = useStore();

  const flatGroups = useMemo(
    () => buildFlatGroups(parsedConfig?.waveforms ?? []),
    [parsedConfig],
  );

  return (
    <>
      <div className="left-panel-toolbar">
        <span className="label">Timeline</span>
        {parsedConfig && (
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
            {parsedConfig.time_start.toFixed(1)}s – {parsedConfig.time_end.toFixed(1)}s
          </span>
        )}
        {yamlError && (
          <span style={{ fontSize: 11, color: "var(--red)" }} title={yamlError}>
            ⚠ Error
          </span>
        )}
      </div>
      <div className="left-panel-body">
        <PlasmaShapeSection />
        <PlasmaPropertiesSection />
        <NiceIntervalConfig />

        {flatGroups.size > 0 && (
          <div className="section">
            <div className="section-header" style={{ cursor: "default" }}>
              <span className="section-title" style={{ color: "var(--text-muted)" }}>
                Other Waveforms
              </span>
            </div>
          </div>
        )}

        {Array.from(flatGroups.entries()).map(([groupName, wfNames]) => (
          <GroupSection key={groupName} name={groupName} waveforms={wfNames} />
        ))}

        {!parsedConfig && (
          <div style={{ padding: 16, color: "var(--text-muted)", fontSize: 12 }}>
            Loading…
          </div>
        )}
      </div>
    </>
  );
}

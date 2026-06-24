import { useState, useEffect } from "react";
import { useStore } from "../../store";
import type { SettingsData } from "../../types";

const PRESET_ITER_URIS = {
  md_pf_active: "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3",
  md_pf_passive: "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3",
  md_wall: "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3",
  md_iron_core: "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/ITER/4/666666/3",
};

const PRESET_WEST_URIS = {
  md_pf_active: "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4",
  md_pf_passive: "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4",
  md_wall: "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4",
  md_iron_core: "imas:hdf5?path=/home/ITER/blokhus/public/imasdb/west_test_dd4",
};

export function SettingsModal() {
  const { showSettings, setShowSettings, settings, setSettings, loadMachineGeometries } =
    useStore();

  const [local, setLocal] = useState<SettingsData>({ ...settings });

  useEffect(() => {
    setLocal({ ...settings });
  }, [settings, showSettings]);

  if (!showSettings) return null;

  const set = (key: keyof SettingsData, value: unknown) =>
    setLocal((s) => ({ ...s, [key]: value }));

  const applyPreset = (preset: string) => {
    if (preset === "ITER") {
      setLocal((s) => ({ ...s, ...PRESET_ITER_URIS, machine_preset: "ITER" }));
    } else if (preset === "WEST") {
      setLocal((s) => ({ ...s, ...PRESET_WEST_URIS, machine_preset: "WEST" }));
    } else {
      setLocal((s) => ({ ...s, machine_preset: "Custom" }));
    }
  };

  const save = async () => {
    await setSettings(local);
    await loadMachineGeometries();
    setShowSettings(false);
  };

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && setShowSettings(false)}>
      <div className="modal">
        <div className="modal-header">
          <span className="modal-title">Settings</span>
          <button className="modal-close" onClick={() => setShowSettings(false)}>×</button>
        </div>
        <div className="modal-body">

          {/* NICE executables */}
          <div className="form-section-title">NICE Executables</div>

          <div className="form-group">
            <label className="form-label">Mode</label>
            <select
              className="form-select"
              value={local.nice_mode}
              onChange={(e) => set("nice_mode", e.target.value)}
            >
              <option>NICE Inverse</option>
              <option>NICE Direct</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Inverse executable</label>
            <input
              className="form-input"
              value={local.nice_inv_executable}
              onChange={(e) => set("nice_inv_executable", e.target.value)}
              placeholder="nice_imas_inv_muscle3"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Direct executable</label>
            <input
              className="form-input"
              value={local.nice_dir_executable}
              onChange={(e) => set("nice_dir_executable", e.target.value)}
              placeholder="nice_imas_dir_muscle3"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Verbosity level</label>
            <input
              className="form-input"
              type="number"
              min={0}
              max={3}
              value={local.verbose}
              onChange={(e) => set("verbose", parseInt(e.target.value))}
            />
          </div>

          {/* Machine descriptions */}
          <div className="form-section-title" style={{ marginTop: 8 }}>Machine Descriptions</div>

          <div className="form-group">
            <label className="form-label">Preset</label>
            <select
              className="form-select"
              value={local.machine_preset}
              onChange={(e) => applyPreset(e.target.value)}
            >
              <option value="Custom">Custom</option>
              <option value="ITER">ITER</option>
              <option value="WEST">WEST</option>
            </select>
          </div>

          {(["md_pf_active", "md_pf_passive", "md_wall", "md_iron_core"] as const).map((key) => (
            <div key={key} className="form-group">
              <label className="form-label">{key.replace("md_", "").replace(/_/g, " ")} URI</label>
              <input
                className="form-input"
                value={local[key]}
                onChange={(e) => set(key, e.target.value)}
                placeholder="imas:hdf5?path=..."
                style={{ fontFamily: "monospace", fontSize: 11 }}
              />
            </div>
          ))}

          {/* Environment variables */}
          <div className="form-section-title" style={{ marginTop: 8 }}>Environment Variables</div>
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
            Extra environment variables passed to the NICE process (JSON format):
          </div>
          <textarea
            className="form-input"
            rows={3}
            value={JSON.stringify(local.environment, null, 2)}
            onChange={(e) => {
              try {
                set("environment", JSON.parse(e.target.value));
              } catch (_) {}
            }}
            style={{ fontFamily: "monospace", fontSize: 11, resize: "vertical" }}
          />
        </div>
        <div className="modal-footer">
          <button className="btn" onClick={() => setShowSettings(false)}>Cancel</button>
          <button className="btn btn-primary" onClick={save}>Save &amp; Load Geometries</button>
        </div>
      </div>
    </div>
  );
}

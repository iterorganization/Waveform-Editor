"""FastAPI backend for the Waveform Editor web service."""
from __future__ import annotations

import asyncio
import copy
import importlib.resources
import logging
import math
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import imas

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.derived_waveform import DerivedWaveform
from waveform_editor.shape_editor.nice_integration import NiceIntegration
from waveform_editor.shape_editor.plasma_shape_calc import compute_outline_from_params
from waveform_editor.shape_editor.plasma_properties_calc import compute_profiles_from_params
from waveform_editor.settings import CONFIG_FILE

from backend.models import (
    CoilPath,
    CoilRect,
    ContourSegment,
    EvaluateRequest,
    EvaluateResponse,
    GapDefinition,
    GapsResponse,
    InverseMillerRequest,
    InverseMillerResponse,
    LoadGapsRequest,
    LoadGeometriesRequest,
    MachineGeometriesResponse,
    NiceRunConfig,
    ParsedConfig,
    SettingsData,
    ShapeOutlineRequest,
    ShapeOutlineResponse,
    SyncRequest,
    SyncResponse,
    SyncTendencies,
    TendenciesBatchRequest,
    TendenciesRequest,
    TendenciesResponse,
    TendencyInfo,
    TimestepResult,
    WallPath,
    WaveformInfo,
    WaveformValues,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Waveform Editor API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# Large JSON payloads (preview evaluation arrays) compress ~10x — essential
# for responsiveness when the UI is accessed over an SSH tunnel
app.add_middleware(GZipMiddleware, minimum_size=1024)

# ── Helpers ────────────────────────────────────────────────────────────────────

# Names of shape/property waveforms that the NICE runner looks for in the config
SHAPE_WAVEFORM_DEFAULTS = {
    "kappa": 1.8,
    "delta": 0.43,
    "a": 1.9,
    "center_r": 6.2,
    "center_z": 0.545,
    "rx": 5.089,
    "zx": -3.346,
}

PROPERTY_WAVEFORM_DEFAULTS = {
    "ip": -1.5e7,
    "b0": -5.3,
    "r0": 6.2,
    "profile_alpha": 0.5,
    "profile_beta": 0.5,
    "profile_gamma": 1.0,
}


def _find_group_path(groups: dict, name: str, path: list[str]) -> list[str]:
    for gname, group in groups.items():
        if name in group.waveforms:
            return path + [gname]
        result = _find_group_path(group.groups, name, path + [gname])
        if result:
            return result
    return []


def _eval_waveform_at(config: WaveformConfiguration, name: str, t: float) -> float:
    if name not in config.waveform_map:
        return None
    t_arr = np.array([t])
    group = config.waveform_map[name]
    wf = group[name]
    try:
        _, vals = wf.get_value(t_arr)
        return float(vals[0])
    except Exception as e:
        logger.warning("Could not evaluate waveform %s at t=%s: %s", name, t, e)
        return None


def _load_ids_sync(uri: str, ids_name: str):
    if not uri:
        return None
    try:
        with imas.DBEntry(uri, "r") as entry:
            return entry.get_slice(ids_name, 0, imas.ids_defs.CLOSEST_INTERP)
    except Exception as e:
        logger.warning("Could not load %s from %s: %s", ids_name, uri, e)
        return None


def _extract_contours(equilibrium, n_levels: int = 20) -> list[ContourSegment]:
    try:
        eqggd = equilibrium.time_slice[0].ggd[0]
        r = np.array(eqggd.r[0].values)
        z = np.array(eqggd.z[0].values)
        psi = np.array(eqggd.psi[0].values)
        if not len(r):
            return []
        trics = plt.tricontour(r, z, psi, levels=n_levels)
        segments = []
        for i, level in enumerate(trics.levels):
            for seg in trics.allsegs[i]:
                if len(seg) > 1:
                    segments.append(ContourSegment(
                        x=seg[:, 0].tolist(),
                        y=seg[:, 1].tolist(),
                        psi=float(level),
                    ))
        plt.close("all")
        return segments
    except Exception as e:
        logger.warning("Could not extract contours: %s", e)
        plt.close("all")
        return []


def _equilibrium_converged(eq) -> bool:
    """True if a NICE output equilibrium exists and reports convergence."""
    try:
        return eq is not None and bool(eq.code.output_flag[0] == 0)
    except Exception:
        return False


def _sanitize_floats(obj):
    """Replace non-finite floats with None so the payload is valid JSON.

    json.dumps emits literal NaN/Infinity (invalid JSON) — the browser's
    JSON.parse then throws and the whole timestep message is silently lost.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_floats(v) for v in obj]
    return obj


def _build_timestep_result(
    equilibrium,
    pf_active,
    input_psi_norm: np.ndarray,
    input_dpressure_dpsi: np.ndarray,
    input_f_df_dpsi: np.ndarray,
    t: float,
    index: int,
    total: int,
    input_values: dict,
) -> TimestepResult:
    ts = equilibrium.time_slice[0]
    bnd = ts.boundary
    gq = ts.global_quantities

    metrics: dict[str, float] = {}
    try:
        metrics["elongation"] = float(bnd.elongation)
        metrics["triangularity"] = float(bnd.triangularity)
        metrics["triangularity_upper"] = float(bnd.triangularity_upper)
        metrics["triangularity_lower"] = float(bnd.triangularity_lower)
        metrics["major_radius"] = float(bnd.geometric_axis.r)
        metrics["vertical_position"] = float(bnd.geometric_axis.z)
        metrics["minor_radius"] = float(bnd.minor_radius)
        metrics["q95"] = float(gq.q_95)
        metrics["ip_actual"] = float(gq.ip)
    except Exception:
        pass

    sep_r = list(map(float, bnd.outline.r)) if bnd.outline.r.has_value else []
    sep_z = list(map(float, bnd.outline.z)) if bnd.outline.z.has_value else []

    o_points, x_points = [], []
    try:
        for node in ts.contour_tree.node:
            pt = {"r": float(node.r), "z": float(node.z)}
            if node.critical_type == 1:
                x_points.append(pt)
            elif node.critical_type in (0, 2):
                o_points.append(pt)
    except Exception:
        pass

    out_psi_norm, out_dp_dpsi, out_fdf_dpsi = [], [], []
    try:
        out_psi_arr = np.array(ts.profiles_1d.psi)
        out_dp_dpsi = list(map(float, ts.profiles_1d.dpressure_dpsi))
        out_fdf_dpsi = list(map(float, ts.profiles_1d.f_df_dpsi))
        if len(out_psi_arr):
            out_psi_norm = (
                (out_psi_arr - out_psi_arr[0]) / (out_psi_arr[-1] - out_psi_arr[0])
            ).tolist()
    except Exception:
        pass

    coil_names, coil_currents = [], []
    if pf_active is not None:
        try:
            for i, coil in enumerate(pf_active.coil):
                coil_names.append(str(coil.name) or f"coil_{i}")
                if coil.current.data.has_value and len(coil.current.data):
                    coil_currents.append(float(coil.current.data[0]))
                else:
                    coil_currents.append(0.0)
        except Exception:
            pass

    return TimestepResult(
        t=t,
        index=index,
        total=total,
        status="success",
        contours=_extract_contours(equilibrium),
        separatrix_r=sep_r,
        separatrix_z=sep_z,
        o_points=o_points,
        x_points=x_points,
        metrics=metrics,
        psi_norm=out_psi_norm,
        dpressure_dpsi=out_dp_dpsi,
        f_df_dpsi=out_fdf_dpsi,
        input_psi_norm=input_psi_norm.tolist(),
        input_dpressure_dpsi=input_dpressure_dpsi.tolist(),
        input_f_df_dpsi=input_f_df_dpsi.tolist(),
        coil_names=coil_names,
        coil_currents=coil_currents,
        input_values=input_values,
    )


# ── Settings ───────────────────────────────────────────────────────────────────

@app.get("/api/settings", response_model=SettingsData)
def get_settings():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            data = yaml.safe_load(f) or {}
        nice = data.get("nice", {})
        return SettingsData(
            nice_inv_executable=nice.get("inv_executable", "nice_imas_inv_muscle3"),
            nice_dir_executable=nice.get("dir_executable", "nice_imas_dir_muscle3"),
            nice_mode=nice.get("mode", "NICE Inverse"),
            machine_preset=nice.get("machine_preset", "Custom"),
            md_pf_active=nice.get("md_pf_active", ""),
            md_pf_passive=nice.get("md_pf_passive", ""),
            md_wall=nice.get("md_wall", ""),
            md_iron_core=nice.get("md_iron_core", ""),
            verbose=nice.get("verbose", 1),
            environment=nice.get("environment", {}),
        )
    return SettingsData()


@app.post("/api/settings")
def save_settings(data: SettingsData):
    config = {
        "gs_solver": "NICE",
        "nice": {
            "inv_executable": data.nice_inv_executable,
            "dir_executable": data.nice_dir_executable,
            "mode": data.nice_mode,
            "machine_preset": data.machine_preset,
            "md_pf_active": data.md_pf_active,
            "md_pf_passive": data.md_pf_passive,
            "md_wall": data.md_wall,
            "md_iron_core": data.md_iron_core,
            "verbose": data.verbose,
            "environment": data.environment,
        },
    }
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.safe_dump(config, f)
    return {"ok": True}


# ── YAML ───────────────────────────────────────────────────────────────────────

def _build_parsed_config(config: WaveformConfiguration, yaml_content: str) -> ParsedConfig:
    waveforms = [
        WaveformInfo(
            name=name,
            group_path=_find_group_path(config.groups, name, []),
            is_derived=isinstance(config.waveform_map[name][name], DerivedWaveform),
        )
        for name in config.waveform_map
    ]
    annotations = []
    for name, group in config.waveform_map.items():
        wf = group[name]
        for ann in wf.annotations:
            annotations.append(f"Line {ann['row'] + 1}: {ann['text'].rstrip()}")
    return ParsedConfig(
        waveforms=waveforms,
        time_start=config.start,
        time_end=config.end,
        yaml_content=yaml_content,
        load_error=config.load_error,
        annotations=annotations,
    )


@app.post("/api/yaml/parse", response_model=ParsedConfig)
def parse_yaml(body: dict):
    yaml_content = body.get("yaml_content", "")
    config = WaveformConfiguration()
    config.load_yaml(yaml_content)
    return _build_parsed_config(config, yaml_content)


@app.post("/api/waveform/evaluate", response_model=EvaluateResponse)
def evaluate_waveforms(request: EvaluateRequest):
    config = WaveformConfiguration()
    config.load_yaml(request.yaml_content)
    if config.load_error:
        return EvaluateResponse(error=config.load_error)

    t = np.array(request.time_points)
    target = request.waveform_names or list(config.waveform_map.keys())
    results = []
    for name in target:
        if name not in config.waveform_map:
            continue
        group = config.waveform_map[name]
        wf = group[name]
        try:
            times, values = wf.get_value(t)
            results.append(WaveformValues(
                name=name,
                times=times.tolist(),
                values=values.tolist(),
            ))
        except Exception as e:
            logger.warning("Could not evaluate %s: %s", name, e)
    return EvaluateResponse(waveforms=results)


def _find_in_yaml(data, target_key: str):
    """Recursively find a value by key in a nested ruamel YAML structure."""
    if isinstance(data, dict):
        for k, v in data.items():
            if str(k) == target_key:
                return v
            found = _find_in_yaml(v, target_key)
            if found is not None:
                return found
    return None


def _tendencies_for(config: WaveformConfiguration, full_data, name: str) -> TendenciesResponse:
    """Tendency metadata for one waveform, given a parsed config + ruamel doc.

    Shared by the single-waveform endpoint and the batched /api/yaml/sync,
    so the (expensive) YAML parses happen once per request instead of once
    per waveform.
    """
    if name not in config.waveform_map:
        return TendenciesResponse(error=f"Waveform '{name}' not found")

    group = config.waveform_map[name]
    wf = group[name]

    if isinstance(wf, DerivedWaveform):
        return TendenciesResponse(error="Derived waveforms have no tendencies")

    tendency_list_full = _find_in_yaml(full_data, name) if full_data else None

    from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency
    from waveform_editor.tendencies.repeat import RepeatTendency

    result = []
    for i, tendency in enumerate(wf.tendencies):
        # Raw YAML entry from isolated block (for params / type)
        yaml_entry = wf.yaml[i] if wf.yaml and i < len(wf.yaml) else {}
        type_str = yaml_entry.get("type", "linear") if yaml_entry else "linear"

        params: dict[str, float] = {}
        if yaml_entry:
            for k, v in yaml_entry.items():
                if k == "type":
                    continue
                try:
                    params[k] = float(v)
                except (TypeError, ValueError):
                    pass

        piecewise_times: list[float] = []
        piecewise_values: list[float] = []
        if isinstance(tendency, PiecewiseLinearTendency):
            piecewise_times = tendency.time.tolist()
            piecewise_values = tendency.value.tolist()

        # Line number from the full YAML (ruamel lc.item gives 0-based line)
        if tendency_list_full is not None and hasattr(tendency_list_full, "lc") and i < len(tendency_list_full):
            actual_line = tendency_list_full.lc.item(i)[0]
        else:
            actual_line = tendency.line_number

        # Extract inner tendencies for repeat
        inner_tendencies_info = []
        if isinstance(tendency, RepeatTendency):
            inner_wf = tendency.waveform
            inner_yaml_with_lc = None
            try:
                if tendency_list_full is not None and i < len(tendency_list_full):
                    outer_entry = tendency_list_full[i]
                    if hasattr(outer_entry, '__contains__') and 'waveform' in outer_entry:
                        inner_yaml_with_lc = outer_entry['waveform']
            except Exception:
                pass

            for j, inner_td in enumerate(inner_wf.tendencies):
                # Use the ruamel entry for type/params (inner_wf.yaml is None for repeat)
                inner_yaml_entry: dict = {}
                if inner_yaml_with_lc is not None and j < len(inner_yaml_with_lc):
                    try:
                        entry = inner_yaml_with_lc[j]
                        if entry:
                            inner_yaml_entry = dict(entry)
                    except Exception:
                        pass
                inner_type = inner_yaml_entry.get("type", "linear")

                inner_params: dict[str, float] = {}
                for k, v in inner_yaml_entry.items():
                    if k == "type":
                        continue
                    try:
                        inner_params[k] = float(v)
                    except (TypeError, ValueError):
                        pass

                try:
                    if inner_yaml_with_lc is not None and hasattr(inner_yaml_with_lc, "lc") and j < len(inner_yaml_with_lc):
                        inner_line = inner_yaml_with_lc.lc.item(j)[0]
                    else:
                        inner_line = actual_line
                except Exception:
                    inner_line = actual_line

                inner_tendencies_info.append(TendencyInfo(
                    index=j,
                    type=inner_type,
                    line_number=inner_line,
                    start_time=float(inner_td.start),
                    end_time=float(inner_td.end),
                    params=inner_params,
                ))

        result.append(TendencyInfo(
            index=i,
            type=type_str,
            line_number=actual_line,
            start_time=float(tendency.start),
            end_time=float(tendency.end),
            params=params,
            piecewise_times=piecewise_times,
            piecewise_values=piecewise_values,
            inner_tendencies=inner_tendencies_info,
        ))

    return TendenciesResponse(tendencies=result)


@app.post("/api/waveform/tendencies", response_model=TendenciesResponse)
def get_tendency_info(request: TendenciesRequest):
    from ruamel.yaml import YAML as RuamelYaml

    config = WaveformConfiguration()
    config.load_yaml(request.yaml_content)
    if config.load_error:
        return TendenciesResponse(error=config.load_error)
    full_data = RuamelYaml().load(request.yaml_content)
    return _tendencies_for(config, full_data, request.waveform_name)


def _adaptive_points(yaml_content: str, duration: float, min_n: int, max_n: int) -> int:
    """Point count giving >=20 samples per period of the fastest wave.

    Mirrors adaptivePoints in the frontend store.
    """
    min_period = duration
    for pattern, invert in ((r"\bperiod\s*:\s*([0-9.eE+\-]+)", False),
                            (r"\bfrequency\s*:\s*([0-9.eE+\-]+)", True)):
        for m in re.finditer(pattern, yaml_content):
            try:
                v = float(m.group(1))
            except ValueError:
                continue
            if v > 0:
                min_period = min(min_period, 1 / v if invert else v)
    if min_period <= 0:
        return min_n
    needed = math.ceil(duration / min_period * 20)
    return min(max_n, max(min_n, needed))


@app.post("/api/yaml/sync", response_model=SyncResponse)
def sync_yaml(request: SyncRequest):
    """Combined parse + preview evaluation + tendencies in one round trip.

    The editing UI needs all three after every YAML change; issuing them as
    separate requests (1 parse + 1 evaluate + N tendencies) makes the app
    crawl on high-latency links (e.g. SSH tunnels).
    """
    from ruamel.yaml import YAML as RuamelYaml

    config = WaveformConfiguration()
    config.load_yaml(request.yaml_content)
    resp = SyncResponse(parsed=_build_parsed_config(config, request.yaml_content))
    if config.load_error:
        return resp

    # Evaluate every waveform on a shared adaptive time grid (preview data).
    # Values are rounded to 6 significant digits: full float64 repr triples
    # the JSON payload for zero visual benefit.
    duration = config.end - config.start
    if duration > 0:
        n = _adaptive_points(request.yaml_content, duration, request.min_points, request.max_points)
        t = np.linspace(config.start, config.end, n)
        resp.times = [float(f"{v:.9g}") for v in t]
        for name in config.waveform_map:
            try:
                _, values = config.waveform_map[name][name].get_value(t)
                resp.values[name] = [
                    float(f"{v:.6g}") if math.isfinite(v) else None for v in values
                ]
            except Exception as e:
                logger.warning("Could not evaluate %s: %s", name, e)

    # Tendencies for all requested waveforms (single ruamel parse)
    if request.tendency_names:
        full_data = RuamelYaml().load(request.yaml_content)
        for name in request.tendency_names:
            tr = _tendencies_for(config, full_data, name)
            if tr.error:
                resp.tendency_errors[name] = tr.error
            else:
                resp.tendencies[name] = tr.tendencies
    return resp


@app.post("/api/waveform/tendencies_batch", response_model=SyncTendencies)
def get_tendencies_batch(request: TendenciesBatchRequest):
    """Tendencies for several waveforms in one request."""
    from ruamel.yaml import YAML as RuamelYaml

    config = WaveformConfiguration()
    config.load_yaml(request.yaml_content)
    resp = SyncTendencies()
    if config.load_error:
        resp.tendency_errors = {n: config.load_error for n in request.waveform_names}
        return resp
    full_data = RuamelYaml().load(request.yaml_content)
    for name in request.waveform_names:
        tr = _tendencies_for(config, full_data, name)
        if tr.error:
            resp.tendency_errors[name] = tr.error
        else:
            resp.tendencies[name] = tr.tendencies
    return resp


# ── Shape editor ───────────────────────────────────────────────────────────────

@app.post("/api/shape/gaps", response_model=GapsResponse)
def load_shape_gaps(request: LoadGapsRequest):
    """Load gap definitions from an equilibrium IDS at a given time."""
    import re as _re

    def _get_slice(dd_version=None):
        with imas.DBEntry(request.uri, "r", dd_version=dd_version) as entry:
            return entry.get_slice(
                "equilibrium", request.time, imas.ids_defs.CLOSEST_INTERP
            )

    try:
        try:
            equilibrium = _get_slice()
        except RuntimeError as exc:
            # Data stored under a different DD major version — retry with it
            m = _re.search(r"stored in DD (\d+\.\d+\.\d+)", str(exc))
            if not m:
                raise
            equilibrium = _get_slice(dd_version=m.group(1))

        ts = equilibrium.time_slice[0]
        # DD4: boundary/gap; DD3: boundary_separatrix/gap (attribute absent in
        # the other version's structure, so probe both)
        input_gaps = None
        for node_name in ("boundary", "boundary_separatrix"):
            try:
                node = getattr(ts, node_name).gap
            except Exception:
                continue
            if len(node):
                input_gaps = node
                break
        if not input_gaps:
            return GapsResponse(error="The equilibrium IDS has no gap definitions")

        outline_r = np.asarray(ts.boundary.outline.r) if ts.boundary.outline.r.has_value else None
        outline_z = np.asarray(ts.boundary.outline.z) if ts.boundary.outline.z.has_value else None

        gaps = []
        for gap in input_gaps:
            # DD3 has a short `identifier` next to the verbose `name`; DD4's
            # `name` is already the short identifier
            ident = ""
            if hasattr(gap, "identifier") and gap.identifier.has_value:
                ident = str(gap.identifier)
            name = ident or str(gap.name)
            r0, z0 = float(gap.r), float(gap.z)
            if gap.angle.has_value:
                angle = float(gap.angle)
            else:
                # Angle unfilled (e.g. DINA data): derive it as the direction
                # from the reference point to the nearest boundary point.
                # Convention: r_sep = r + v*cos(-angle), z_sep = z + v*sin(-angle)
                if outline_r is None or not len(outline_r):
                    return GapsResponse(error=(
                        "Gap angles are unfilled and no boundary outline is "
                        "available at this time to derive them — pick a time "
                        "with plasma present"
                    ))
                j = int(np.argmin(np.hypot(outline_r - r0, outline_z - z0)))
                angle = float(-np.arctan2(outline_z[j] - z0, outline_r[j] - r0))
            value = float(gap.value) if gap.value.has_value else 0.0
            if not gap.value.has_value and outline_r is not None and len(outline_r):
                j = int(np.argmin(np.hypot(outline_r - r0, outline_z - z0)))
                value = float(np.hypot(outline_r[j] - r0, outline_z[j] - z0))
            gaps.append(GapDefinition(name=name, r=r0, z=z0, angle=angle, value=value))
        return GapsResponse(gaps=gaps)
    except Exception as e:
        return GapsResponse(error=str(e))


@app.post("/api/shape/outline", response_model=ShapeOutlineResponse)
def get_shape_outline(request: ShapeOutlineRequest):
    """Compute plasma outline at a given time from YAML waveforms."""
    from waveform_editor.shape_editor.plasma_shape_calc import (
        Gap,
        compute_outline_from_params,
        update_outline_from_gaps,
    )
    try:
        config = WaveformConfiguration()
        config.load_yaml(request.yaml_content)
        if config.load_error:
            return ShapeOutlineResponse(error=config.load_error)

        t_arr = np.array([request.time])

        if request.mode == "gaps":
            # Evaluate each gap waveform to get current gap values
            gaps = []
            for i, gdef in enumerate(request.gap_definitions):
                name = request.gap_waveform_names[i] if i < len(request.gap_waveform_names) else gdef.name
                value = gdef.value  # fallback
                v = _eval_waveform_at(config, name, request.time)
                if v is not None:
                    value = v
                gaps.append(Gap(name=gdef.name, r=gdef.r, z=gdef.z, angle=gdef.angle, value=value))
            outline_r, outline_z = update_outline_from_gaps(gaps)
            param_values = {g.name: g.value for g in gaps}
            return ShapeOutlineResponse(
                outline_r=list(outline_r) if outline_r else [],
                outline_z=list(outline_z) if outline_z else [],
                param_values=param_values,
            )
        else:
            # Parameterized mode
            shape_names = ["kappa", "delta", "a", "center_r", "center_z", "rx", "zx"]
            defaults = {"kappa": 1.8, "delta": 0.43, "a": 1.9, "center_r": 6.2, "center_z": 0.545, "rx": 5.089, "zx": -3.346}
            param_values = {}
            for name in shape_names:
                v = _eval_waveform_at(config, name, request.time)
                param_values[name] = v if v is not None else defaults.get(name, 0.0)

            outline_r, outline_z = compute_outline_from_params(
                a=param_values["a"],
                center_r=param_values["center_r"],
                center_z=param_values["center_z"],
                kappa=param_values["kappa"],
                delta=param_values["delta"],
                rx=param_values["rx"],
                zx=param_values["zx"],
                n_desired_bnd_points=96,
            )
            return ShapeOutlineResponse(
                outline_r=outline_r,
                outline_z=outline_z,
                param_values=param_values,
            )
    except Exception as e:
        return ShapeOutlineResponse(error=str(e))


@app.post("/api/shape/inverse_miller", response_model=InverseMillerResponse)
def inverse_miller(request: InverseMillerRequest):
    """Given a drag on a plasma outline point, find updated Miller params."""
    from scipy.optimize import minimize
    from waveform_editor.shape_editor.plasma_shape_calc import compute_outline_from_params
    import math

    p = request.current_params
    kappa    = p.get("kappa",    1.8)
    delta    = p.get("delta",    0.43)
    a        = p.get("a",        1.9)
    center_r = p.get("center_r", 6.2)
    center_z = p.get("center_z", 0.545)
    rx       = p.get("rx",       5.089)
    zx       = p.get("zx",      -3.346)

    theta = request.theta
    R_target = request.drag_r
    Z_target = request.drag_z

    # Miller formula at angle theta:
    #   R(θ) = center_r + a * cos(θ + arcsin(δ)*sin(θ))
    #   Z(θ) = center_z + a * kappa * sin(θ)
    # We allow all 7 params to vary but penalise large changes.
    x0 = np.array([kappa, delta, a, center_r, center_z, rx, zx])

    def residual(x):
        kk, dd, aa, rr, zz, rrx, zzx = x
        da = math.asin(max(-0.99, min(0.99, dd)))
        R_pred = rr + aa * math.cos(theta + da * math.sin(theta))
        Z_pred = zz + aa * kk * math.sin(theta)
        # Position error at dragged point
        pos_err = (R_pred - R_target)**2 + (Z_pred - Z_target)**2
        # Regularisation: penalise deviation from original params
        reg = 0.01 * np.sum((x - x0)**2)
        return pos_err + reg

    bounds = [(0.5, 4.0), (-0.99, 0.99), (0.5, 3.5), (4.0, 9.0), (-3.0, 3.0), (3.0, 9.0), (-6.0, -0.5)]
    try:
        result = minimize(residual, x0, method="L-BFGS-B", bounds=bounds,
                          options={"maxiter": 200, "ftol": 1e-12})
        kk, dd, aa, rr, zz, rrx, zzx = result.x
        return InverseMillerResponse(new_params={
            "kappa": float(kk), "delta": float(dd), "a": float(aa),
            "center_r": float(rr), "center_z": float(zz),
            "rx": float(rrx), "zx": float(zzx),
        })
    except Exception as e:
        return InverseMillerResponse(error=str(e))


# ── Machine geometries ─────────────────────────────────────────────────────────

@app.post("/api/machine/geometries", response_model=MachineGeometriesResponse)
def get_machine_geometries(request: LoadGeometriesRequest):
    coil_rects, coil_paths, wall_limiter, vacuum_vessel = [], [], [], []

    if request.md_pf_active_uri:
        pf_active = _load_ids_sync(request.md_pf_active_uri, "pf_active")
        if pf_active is not None:
            for coil in pf_active.coil:
                name = str(coil.name)
                for element in coil.element:
                    rect = element.geometry.rectangle
                    outline = element.geometry.outline
                    annulus = element.geometry.annulus
                    if rect.has_value:
                        coil_rects.append(CoilRect(
                            r0=float(rect.r - rect.width / 2),
                            z0=float(rect.z - rect.height / 2),
                            r1=float(rect.r + rect.width / 2),
                            z1=float(rect.z + rect.height / 2),
                            name=name,
                        ))
                    elif outline.has_value:
                        coil_paths.append(CoilPath(
                            r=list(map(float, outline.r)),
                            z=list(map(float, outline.z)),
                            name=name,
                        ))
                    elif annulus.r.has_value:
                        phi = np.linspace(0, 2 * np.pi, 17)
                        coil_paths.append(CoilPath(
                            r=list(map(float, annulus.r + annulus.radius_outer * np.cos(phi))),
                            z=list(map(float, annulus.z + annulus.radius_outer * np.sin(phi))),
                            name=name,
                        ))

    if request.md_wall_uri:
        wall = _load_ids_sync(request.md_wall_uri, "wall")
        if wall is not None:
            try:
                for unit in wall.description_2d[0].limiter.unit:
                    wall_limiter.append(WallPath(
                        r=list(map(float, unit.outline.r)),
                        z=list(map(float, unit.outline.z)),
                        name=str(unit.name),
                    ))
            except Exception:
                pass
            try:
                for unit in wall.description_2d[0].vessel.unit:
                    vacuum_vessel.append(WallPath(
                        r=list(map(float, unit.annular.centreline.r)),
                        z=list(map(float, unit.annular.centreline.z)),
                        name=str(unit.name),
                    ))
            except Exception:
                pass

    return MachineGeometriesResponse(
        coil_rectangles=coil_rects,
        coil_paths=coil_paths,
        wall_limiter=wall_limiter,
        vacuum_vessel=vacuum_vessel,
    )


# ── NICE WebSocket ─────────────────────────────────────────────────────────────

@app.websocket("/ws/nice")
async def nice_websocket(websocket: WebSocket):
    await websocket.accept()
    communicators: list[NiceIntegration] = []
    ws_closed = False  # suppresses late NICE-output sends after the handler ends

    try:
        raw = await websocket.receive_json()
        run_config = NiceRunConfig(**raw)

        config = WaveformConfiguration()
        config.load_yaml(run_config.yaml_content)
        if config.load_error:
            await websocket.send_json({"type": "error", "message": config.load_error})
            return

        await websocket.send_json({"type": "status", "message": "Loading machine descriptions..."})
        loop = asyncio.get_running_loop()

        pf_active_ids = await loop.run_in_executor(
            None, lambda: _load_ids_sync(run_config.md_pf_active_uri, "pf_active")
        )
        pf_passive_ids = await loop.run_in_executor(
            None, lambda: _load_ids_sync(run_config.md_pf_passive_uri, "pf_passive")
        )
        wall_ids = await loop.run_in_executor(
            None, lambda: _load_ids_sync(run_config.md_wall_uri, "wall")
        )
        iron_core_ids = await loop.run_in_executor(
            None, lambda: _load_ids_sync(run_config.md_iron_core_uri, "iron_core")
        )

        if not all([pf_active_ids, pf_passive_ids, wall_ids, iron_core_ids]):
            await websocket.send_json({
                "type": "error",
                "message": "One or more machine descriptions could not be loaded. Check settings.",
            })
            return

        xml_inv = ET.fromstring(
            importlib.resources.files("waveform_editor.shape_editor.xml_param")
            .joinpath("inverse_param.xml")
            .read_text()
        )
        xml_dir = ET.fromstring(
            importlib.resources.files("waveform_editor.shape_editor.xml_param")
            .joinpath("direct_param.xml")
            .read_text()
        )

        is_inverse = run_config.nice_mode == "NICE Inverse"
        xml_params = xml_inv if is_inverse else xml_dir
        xml_params.find("verbose").text = str(run_config.verbose)

        await websocket.send_json({"type": "status", "message": "Starting NICE..."})
        factory = imas.IDSFactory()
        nice_env = os.environ.copy()
        nice_env.update(run_config.environment)

        executable = run_config.inv_executable if is_inverse else run_config.dir_executable
        if not shutil.which(executable):
            await websocket.send_json({
                "type": "error",
                "message": f"NICE executable not found: '{executable}'. Please configure the correct path in Settings.",
            })
            return

        def _forward_nice_output(data: str | bytes):
            text = data.decode(errors="replace") if isinstance(data, bytes) else data
            logger.info("NICE: %s", text.rstrip())
            if ws_closed:
                return  # late NICE output after the client disconnected

            async def _safe_send():
                try:
                    await websocket.send_json({"type": "nice_output", "text": text})
                except Exception:
                    pass  # websocket closed while the send was in flight

            asyncio.ensure_future(_safe_send())

        total = len(run_config.timesteps)
        # parallel_workers <= 0 means "auto": use all available cores
        requested = run_config.parallel_workers
        n_workers = (os.cpu_count() or 1) if requested <= 0 else requested
        n_workers = max(1, min(n_workers, os.cpu_count() or n_workers, total))

        # Warm start is sequential by nature — disable it for parallel runs
        warm_start_enabled = run_config.warm_start and n_workers == 1

        # One NICE instance (MUSCLE manager + actor + solver process) per worker
        for w in range(n_workers):
            comm = NiceIntegration(factory, on_output=_forward_nice_output)
            await comm.run(is_direct_mode=not is_inverse)
            communicators.append(comm)

        await websocket.send_json({"type": "started", "total": total, "workers": n_workers})

        # Machine descriptions are read-only — serialize once, share across workers
        md_blobs = (
            pf_active_ids.serialize(),
            pf_passive_ids.serialize(),
            wall_ids.serialize(),
            iron_core_ids.serialize(),
        )
        send_lock = asyncio.Lock()

        async def run_chunk(comm: NiceIntegration, chunk: list[tuple[int, float]]):
            """Run a contiguous chunk of timesteps on one NICE instance."""
            prev_converged = False
            for index, t in chunk:
                try:
                    # Evaluate shape and property waveforms at this timestep.
                    # Use explicit None check — `or` would wrongly replace 0.0 with the default.
                    shape = {k: (w if (w := _eval_waveform_at(config, k, t)) is not None else v)
                             for k, v in SHAPE_WAVEFORM_DEFAULTS.items()}
                    shape["n_bnd_points"] = run_config.n_bnd_points

                    props = {k: (w if (w := _eval_waveform_at(config, k, t)) is not None else v)
                             for k, v in PROPERTY_WAVEFORM_DEFAULTS.items()}

                    psi_norm, dpressure_dpsi, f_df_dpsi = compute_profiles_from_params(
                        r0=props["r0"],
                        alpha=props["profile_alpha"],
                        beta=props["profile_beta"],
                        gamma=props["profile_gamma"],
                    )

                    # Warm start from the previous timestep's converged equilibrium,
                    # falling back to a fresh (empty) equilibrium on the first
                    # timestep or after a failed/unconverged one.
                    warm = (
                        warm_start_enabled
                        and prev_converged
                        and _equilibrium_converged(comm.equilibrium)
                    )
                    if warm:
                        equilibrium = comm.equilibrium
                    else:
                        equilibrium = factory.new("equilibrium")
                        equilibrium.ids_properties.homogeneous_time = (
                            imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
                        )
                        equilibrium.time = [0.0]
                        equilibrium.time_slice.resize(1)

                    # NICE start flags (present in both direct and inverse XML):
                    # warm runs continue from the psi map in the input equilibrium.
                    # Workers run concurrently — each mutates its own XML copy.
                    xml_local = copy.deepcopy(xml_params)
                    xml_local.find("algoStartFromScratch").text = "0" if warm else "1"
                    xml_local.find("algoStartFromScratchReconAB").text = "0" if warm else "1"
                    xml_local.find("algoStartPsiFromInData").text = "1" if warm else "0"

                    if is_inverse:
                        if run_config.shape_mode == "gaps" and run_config.gap_definitions:
                            # Desired boundary from gap waveforms: each gap samples the
                            # true boundary at a machine station — no shape
                            # parameterization in the loop
                            from waveform_editor.shape_editor.plasma_shape_calc import (
                                Gap,
                                update_outline_from_gaps,
                            )
                            gaps = []
                            for gdef in run_config.gap_definitions:
                                v = _eval_waveform_at(config, f"gap_{gdef.name}", t)
                                gaps.append(Gap(
                                    name=gdef.name, r=gdef.r, z=gdef.z,
                                    angle=gdef.angle,
                                    value=v if v is not None else gdef.value,
                                ))
                            outline_r, outline_z = update_outline_from_gaps(gaps)
                        else:
                            outline_r, outline_z = compute_outline_from_params(
                                a=shape["a"],
                                center_r=shape["center_r"],
                                center_z=shape["center_z"],
                                kappa=shape["kappa"],
                                delta=shape["delta"],
                                rx=shape["rx"],
                                zx=shape["zx"],
                                n_desired_bnd_points=shape["n_bnd_points"],
                            )
                        equilibrium.time_slice[0].boundary.outline.r = outline_r
                        equilibrium.time_slice[0].boundary.outline.z = outline_z

                    equilibrium.vacuum_toroidal_field.r0 = props["r0"]
                    equilibrium.vacuum_toroidal_field.b0 = np.array([props["b0"]])
                    ts_eq = equilibrium.time_slice[0]
                    ts_eq.global_quantities.ip = props["ip"]
                    ts_eq.profiles_1d.dpressure_dpsi = dpressure_dpsi
                    ts_eq.profiles_1d.f_df_dpsi = f_df_dpsi
                    ts_eq.profiles_1d.psi = psi_norm

                    await comm.submit(
                        ET.tostring(xml_local, encoding="unicode"),
                        equilibrium.serialize(),
                        *md_blobs,
                    )

                    input_values = {**shape, **props, "t": t}
                    result = _build_timestep_result(
                        comm.equilibrium,
                        comm.pf_active,
                        psi_norm,
                        dpressure_dpsi,
                        f_df_dpsi,
                        t,
                        index,
                        total,
                        input_values,
                    )
                    async with send_lock:
                        await websocket.send_json(
                            {"type": "timestep_result", **_sanitize_floats(result.model_dump())}
                        )
                    prev_converged = _equilibrium_converged(comm.equilibrium)

                except Exception as e:
                    prev_converged = False
                    logger.error("Error at t=%s: %s", t, e, exc_info=True)
                    async with send_lock:
                        await websocket.send_json({
                            "type": "timestep_result",
                            "t": t, "index": index, "total": total,
                            "status": "error", "error": str(e),
                            "contours": [], "separatrix_r": [], "separatrix_z": [],
                            "o_points": [], "x_points": [], "metrics": {},
                            "psi_norm": [], "dpressure_dpsi": [], "f_df_dpsi": [],
                            "input_psi_norm": [], "input_dpressure_dpsi": [], "input_f_df_dpsi": [],
                            "coil_names": [], "coil_currents": [], "input_values": {},
                        })
                    if not comm.running:
                        break  # this NICE instance crashed — abort its remaining timesteps

        # Contiguous chunks (not round-robin) keep adjacent timesteps on the
        # same worker so warm starting stays effective
        indexed = list(enumerate(run_config.timesteps))
        base, rem = divmod(len(indexed), n_workers)
        chunks: list[list[tuple[int, float]]] = []
        pos = 0
        for w in range(n_workers):
            size = base + (1 if w < rem else 0)
            if size:
                chunks.append(indexed[pos:pos + size])
                pos += size

        await asyncio.gather(*(run_chunk(c, ch) for c, ch in zip(communicators, chunks)))

        await websocket.send_json({"type": "completed", "total": total})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        ws_closed = True
        for comm in communicators:
            try:
                await comm.close()
            except Exception:
                pass


# ── Serve frontend build ────────────────────────────────────────────────────────

_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    # Only watch source dirs — NICE/MUSCLE runs write files (logs, profiling
    # DBs) that would otherwise trigger a server restart after every run
    _repo = Path(__file__).parent.parent
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(_repo / "backend"), str(_repo / "waveform_editor")],
    )

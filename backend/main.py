"""FastAPI backend for the Waveform Editor web service."""
from __future__ import annotations

import asyncio
import importlib.resources
import logging
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
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
    LoadGeometriesRequest,
    MachineGeometriesResponse,
    NiceRunConfig,
    ParsedConfig,
    SettingsData,
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

@app.post("/api/yaml/parse", response_model=ParsedConfig)
def parse_yaml(body: dict):
    yaml_content = body.get("yaml_content", "")
    config = WaveformConfiguration()
    config.load_yaml(yaml_content)
    waveforms = [
        WaveformInfo(
            name=name,
            group_path=_find_group_path(config.groups, name, []),
            is_derived=isinstance(config.waveform_map[name][name], DerivedWaveform),
        )
        for name in config.waveform_map
    ]
    return ParsedConfig(
        waveforms=waveforms,
        time_start=config.start,
        time_end=config.end,
        yaml_content=yaml_content,
        load_error=config.load_error,
    )


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
    communicator: NiceIntegration | None = None

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
            asyncio.ensure_future(websocket.send_json({"type": "nice_output", "text": text}))

        communicator = NiceIntegration(
            factory,
            on_output=_forward_nice_output,
        )
        await communicator.run(is_direct_mode=not is_inverse)

        total = len(run_config.timesteps)
        await websocket.send_json({"type": "started", "total": total})

        for index, t in enumerate(run_config.timesteps):
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

                # Build equilibrium IDS
                equilibrium = factory.new("equilibrium")
                equilibrium.ids_properties.homogeneous_time = (
                    imas.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
                )
                equilibrium.time = [0.0]
                equilibrium.time_slice.resize(1)

                if is_inverse:
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

                await communicator.submit(
                    ET.tostring(xml_params, encoding="unicode"),
                    equilibrium.serialize(),
                    pf_active_ids.serialize(),
                    pf_passive_ids.serialize(),
                    wall_ids.serialize(),
                    iron_core_ids.serialize(),
                )

                input_values = {**shape, **props, "t": t}
                result = _build_timestep_result(
                    communicator.equilibrium,
                    communicator.pf_active,
                    psi_norm,
                    dpressure_dpsi,
                    f_df_dpsi,
                    t,
                    index,
                    total,
                    input_values,
                )
                await websocket.send_json({"type": "timestep_result", **result.model_dump()})

            except Exception as e:
                logger.error("Error at t=%s: %s", t, e, exc_info=True)
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
                if not communicator.running:
                    break  # NICE crashed — abort the rest of the timesteps

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
        if communicator is not None:
            try:
                await communicator.close()
            except Exception:
                pass


# ── Serve frontend build ────────────────────────────────────────────────────────

_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

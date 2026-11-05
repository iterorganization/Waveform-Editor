# Installation on altair (CEA cluster)

Scripts to install the Waveform-Editor with NICE (inverse and direct, IMAS + MUSCLE3) on
`altair.partenaires.cea.fr`, shared with colleagues, and to use its GUI from a Windows
laptop.

| File | Purpose |
|---|---|
| `install.sh` | Installs everything from scratch (~30 min, ~4 GB) |
| `update.sh` | Updates the Waveform-Editor of an existing installation (a few minutes) |
| `set_machine_descriptions.sh` | Points the ITER and WEST presets to the data on altair, default preset WEST |
| `env.sh` | Environment to `source` before use; copied to the installation |
| `start-gui-socket.sh` | Starts the GUI on a unix socket; copied to the installation |
| `windows/` | Launcher for the GUI from a Windows laptop, see `windows/README.txt` |

**Which script to run:** only one of them, never both.

- New installation (empty or missing directory): `bash install/altair/install.sh`
- Existing installation, newer Waveform-Editor: `bash install/altair/update.sh`

Both call `set_machine_descriptions.sh` and copy `env.sh`, `start-gui-socket.sh` and
`windows/` to the installation themselves, so these are not run by hand.

Both `install.sh` and `update.sh` take the Waveform-Editor from **the last commit of the
current branch of this repository**: commit first, uncommitted changes are not installed.
The default installation is `~/public/waveform-editor-nice`; give another directory as
the first argument.

## Updating to a new develop version

```bash
cd ~/public/git/Waveform-Editor
git fetch origin
git merge origin/develop                 # on feature/altair_install, then commit
bash install/altair/update.sh            # or install.sh into an empty directory
```

## Using it

```bash
source ~/public/waveform-editor-nice/env.sh    # purges your loaded modules
waveform-editor gui                            # in x2go (slow), or:
waveform-editor gui --socket                   # for a browser on your laptop
```

From Windows: copy **both** `windows/waveform-editor.cmd` and `windows/waveform-editor.ps1`
to the same folder on the laptop (the `.cmd` only runs the `.ps1`), for example in
PowerShell, with your login:

```powershell
scp <login>@altair.partenaires.cea.fr:/home/MS013565/public/waveform-editor-nice/windows/waveform-editor.* $HOME\Desktop\
```

Then double-click `waveform-editor.cmd`: it connects with SSH, starts the GUI with
`start-gui-socket.sh` and opens it in the browser. See `windows/README.txt`.

## Machine descriptions

The ITER and WEST presets of the Waveform-Editor point to data on SDCC
(`/home/ITER/blokhus/...`), which `set_machine_descriptions.sh` replaces with copies on
altair:

| Preset | IDS | On altair |
|---|---|---|
| ITER | `pf_active`, `pf_passive`, `wall` | `/home/MS013565/public/imasdb/ITER/4/666666/3` |
| ITER | `tf` | `/home/MS013565/public/imasdb/ITER/4/111002/3` |
| WEST | `pf_active`, `pf_passive`, `wall`, `iron_core` | `/home/MS013565/public/imasdb/WEST_MD/4/555/1` |

Other locations: `ITER_MD=... WEST_MD=... DEFAULT_PRESET=ITER bash set_machine_descriptions.sh`.
The data must be readable by colleagues: `chmod -R go+rX ~/public/imasdb`.

For the WEST equilibrium as reference shape, choose "Equilibrium IDS" in the shape editor
and enter `imas:hdf5?path=/home/MS013565/public/imasdb/WEST_MD/4/555/1`.

## What is installed

| Component | Version | Where |
|---|---|---|
| Waveform-Editor | this repository | `Waveform-Editor/` (source), installed in `venv/` |
| Python | 3.11 (module `mamba/python-3.11`) | `venv/` |
| IMAS Access Layer C++ / imas_core | AL 5.4.3, Data Dictionary 4.1.0 | module `IMAS/4.1.0-5.4.3-...` |
| MUSCLE3 (C++ and Python) | 0.10.0 (both must match) | `deps/` (C++), `venv/` (Python) |
| SuiteSparse | 4.5.3 (NICE submodule) | `nice/external/SuiteSparse/lib` |
| NICE | git `36d11a69` | `nice/`, executables in `nice/run` |
| Chrome (headless, for PNG export) | from `plotly_get_chrome` | `chrome/` |

Build logs are in `logs/`.

## Notes

- The home quota is ~100 GB: check `du -sh ~` before installing.
- Colleagues are in the same group `users`, so the group and other bits both matter.
  `install.sh` and `update.sh` make the installation readable (`go+rX`) and the
  directories above it that you own traversable (`go+x`, no listing), then stop with an
  error if colleagues still cannot reach it. `set_machine_descriptions.sh` warns if they
  cannot read the machine description data, which only its owner can fix
  (`chmod -R go+rX ~/public/imasdb`). Functions in `permissions.sh`.
- `IMAS/4.1.0-5.4.3-...` provides the C++ Access Layer and `imas_core`, so `env.sh` must
  be sourced before using the venv. `papi` is needed because the blitz pkg-config file
  adds `-lpapi`, `lapack` for `-lblas -llapack`.
- NICE's own `external/muscle3` submodule (0.7.2-dev) is too old for the Waveform-Editor,
  so MUSCLE3 0.10.0 is built separately. pip would take muscle3 0.11, so it is pinned.
- The clone of NICE from gitlab.inria.fr failed once with a network error; then use
  `NICE_REPO=/home/MS013565/public/git/nice bash install.sh`.

# Waveform-Editor on the CEA partner zone

The Waveform-Editor and NICE (inverse and direct, IMAS + MUSCLE3) are installed as
modules on the CEA partner zone, built with [EasyBuild](https://easybuild.io) from the
recipes in `easybuild/`, and shared with colleagues. They were built on
`altair.partenaires.cea.fr`, and work on its other servers too, such as `andromede2`.

## Using it

```bash
module use /home/MS013565/public/easybuild/modules/all
module load Waveform-Editor        # loads NICE, MUSCLE3, IMAS, ... with it
waveform-editor gui                # in x2go (slow), or:
waveform-editor gui --socket       # for a browser on your laptop
```

The ITER and WEST presets of the shape editor use the machine description data of
SDCC, and on the partner zone a copy of it in `/home/MS013565/public/imasdb` (which
must stay readable by colleagues).

### From a Windows laptop

Copy **both** `windows/waveform-editor.cmd` and `windows/waveform-editor.ps1` to the same
folder on the laptop (the `.cmd` only runs the `.ps1`), then double-click
`waveform-editor.cmd`. It connects with SSH, loads the module on altair, starts the
GUI on a unix socket and opens it in the browser of the laptop. See
`windows/README.txt`.

## Building the modules

The recipes use the modules of the cluster (gcc, hdf5, IMAS, ...) as external
modules and build the rest:

| Recipe | Module | Contents |
|---|---|---|
| `MUSCLE3-0.10.0.eb` | `MUSCLE3/0.10.0` | MUSCLE3 C++ and Fortran libraries |
| `NICE-20261012.eb` | `NICE/20261012` | NICE executables, with the SuiteSparse bundled in NICE |
| `Waveform-Editor-20261105.eb` | `Waveform-Editor/20261105` | Python environment with the Waveform-Editor, headless Chrome for PNG export |

`easybuild.cfg` installs into `~/public/easybuild` and builds in `/tmp`, so that only
the result counts in the home quota (~100 GB). EasyBuild itself is in a virtual
environment there, whose `bin` must come first in `PATH` (the `eb` command runs the
first `python` it finds that has EasyBuild):

```bash
export PATH=/home/MS013565/public/easybuild/eb-venv/bin:$PATH
cd install/cea_partner_zone/easybuild
eb --configfiles=easybuild.cfg --robot=. Waveform-Editor-20261105.eb   # MUSCLE3 and NICE first if needed
```

Add `--dry-run` to see what would be built, `--rebuild` to build an installed module
again. That environment was made with:

```bash
module load mamba/python-3.11
python -m venv ~/public/easybuild/eb-venv
~/public/easybuild/eb-venv/bin/pip install easybuild==5.4.2
```

### A new version of the Waveform-Editor

Copy the Waveform-Editor recipe to one with the new version in its name, and change in
it `version` and `local_commit` (a commit of develop: EasyBuild cannot take a branch).
Once there is a release on PyPI, the recipe can take it from there instead of git. NICE
and MUSCLE3 are only rebuilt when their own recipes change.

## Notes

- MUSCLE3: the C++ library NICE links to and the Python package must be the same version
  (0.10.0). NICE's own `external/muscle3` submodule (0.7.2-dev) is too old for the
  Waveform-Editor, so it is not used.
- `easybuild.cfg` sets `rpath = False`: the RPATH compiler wrappers of EasyBuild break the
  build of the SuiteSparse bundled in NICE, and the modules set `LD_LIBRARY_PATH`.
- The Waveform-Editor recipe pins `numpy<2`, as the `imas_core` of the IMAS module is
  built for numpy 1, and adds its packages to `PYTHONPATH`, as `mamba/python-3.11`
  activates its own python after the modules are loaded.
- Colleagues are in the same group `users` as the owner: the home needs `go+x` (traverse
  only) and the installation is made readable with `umask = 022` in `easybuild.cfg`.
  The machine description data in `~/public/imasdb` must be readable too
  (`chmod -R go+rX ~/public/imasdb`).

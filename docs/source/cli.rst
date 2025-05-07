.. _cli:

======================
Command-Line Interface
======================

General Usage
=============

The Waveform Editor provides a command-line interface (CLI) tool, ``waveform-editor``, for exporting waveform configurations defined in YAML files to various formats.


Getting Help
------------

You can get help on the main command and view the list of available subcommands by running:

.. code-block:: bash

   waveform-editor --help

To get help for a specific subcommand, use:

.. code-block:: bash

   waveform-editor <command> --help

For example:

.. code-block:: bash

   waveform-editor export-ids --help

Version Information
-------------------

To display the installed version of the Waveform Editor package, use the ``-v`` or ``--version`` flag:

.. code-block:: bash

   waveform-editor --version

Commands
========

The CLI is organized into several subcommands for different export targets.

Specifying Time Points for Export
---------------------------------

All export commands allow you to specify the time points at which the waveforms should be evaluated. You can do this using *one* of the following options:

*   ``--linspace START,STOP,NUM``: Generates an array of `NUM` evenly spaced time points starting at `START` and ending at `STOP` (inclusive). The values must be provided as comma-separated numbers, e.g., ``--linspace 0,10,101``.
*   ``--csv PATH``: Provides the path to a CSV file containing the desired time points.

    .. note::
        The CSV file must contain exactly **one row** of comma-separated numerical values representing the time points. For example:
        ``0.0,0.1,0.2,0.5,1.0,2.0,5.0,10.0``


export-ids
----------

Exports the waveform data to an IMAS_ IDS.

**Usage:**

.. code-block:: bash

   waveform-editor export-ids [OPTIONS] YAML URI

**Description:**

This command reads the waveform definitions from the specified `YAML` file, evaluates them at the time points defined by either ``--linspace`` or ``--csv``, and writes the results into the specified IMAS data entry (`URI`). It uses the `dd_version` specified in the YAML configuration and can optionally use machine descriptions if provided in the global configuration parameters.

**Arguments:**

*   ``YAML``: Path to the input waveform YAML configuration file.
*   ``URI``: The URI specifying the IMAS data entry to write to.

**Options:**

*   ``--linspace START,STOP,NUM``: Define time points using `numpy.linspace`. (See `Specifying Time Points for Export`_).
*   ``--csv PATH``: Define time points using a CSV file. (See `Specifying Time Points for Export`_).

.. note::
    You must provide exactly one of `--linspace` or `--csv` for this command.

export-png
----------

Exports plots of the individual waveforms to PNG image files.

**Usage:**

.. code-block:: bash

   waveform-editor export-png [OPTIONS] YAML OUTPUT_DIR

**Description:**

This command reads the waveform definitions from the `YAML` file and generates a separate PNG plot for each defined waveform. The plots are saved in the specified ``OUTPUT_DIR``. If ``--linspace`` or ``--csv`` is provided, waveforms are evaluated at those specific time points for plotting. If neither is provided, default time points suitable for visualizing each waveform's shape will be used.

**Arguments:**

*   ``YAML``: Path to the input waveform YAML configuration file.
*   ``OUTPUT_DIR``: Path to the directory where the output PNG files will be saved. The directory will be created if it doesn't exist.

**Options:**

*   ``--linspace START,STOP,NUM``: Define specific time points for plotting. (See `Specifying Time Points for Export`_).
*   ``--csv PATH``: Define specific time points for plotting using a CSV file. (See `Specifying Time Points for Export`_).

export-csv
----------

Exports the evaluated waveform data to a single CSV file.

**Usage:**

.. code-block:: bash

   waveform-editor export-csv [OPTIONS] YAML OUTPUT_DIR

**Description:**

This command reads the waveform definitions from the `YAML` file, evaluates them at the time points specified by either ``--linspace`` or ``--csv``, and writes the results into a single CSV file within the specified ``OUTPUT_DIR``. The CSV file will contain a 'time' column followed by columns for each waveform defined in the configuration.

**Arguments:**

*   ``YAML``: Path to the input waveform YAML configuration file.
*   ``OUTPUT_CSV``: Path where the output CSV file will be saved. The parent directory will be created if it doesn't exist.

**Options:**

*   ``--linspace START,STOP,NUM``: Define time points using `numpy.linspace`. (See `Specifying Time Points for Export`_).
*   ``--csv PATH``: Define time points using a CSV file. (See `Specifying Time Points for Export`_).

.. note::
    You must provide exactly one of `--linspace` or `--csv` for this command.


.. _IMAS: https://imas.iter.org/

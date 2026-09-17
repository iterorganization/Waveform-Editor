.. _yaml_format:

================
YAML File Format
================

The Waveform Editor uses YAML files to define the desired waveforms, their organization, and global settings for export. This page describes the structure and syntax of these files.

An example configuration file is provided on the following page:

.. toctree::
   :maxdepth: 1
   
   example_yaml

Overall Structure
-----------------

A Waveform Editor YAML file is a standard YAML dictionary containing up to three top-level keys:

1.  **dd_version:** The IMAS Data Dictionary version this configuration is written against.
2.  **input:** External data entries (e.g. a scenario or machine description) that waveforms may copy values from.
3.  **output:** The waveform groups, nested to form a hierarchy, that make up the actual configuration.

.. code-block:: yaml
   :caption: Basic File Structure

   dd_version: 3.42.0

   input:
     scenario: imas:hdf5?path=my_scenario
     machine: imas:hdf5?path=my_machine_description

   output:
     top_level_group_1:
       # Waveforms and nested groups here...

     top_level_group_2:
       nested_group_A:
         # More waveforms/groups...
       # More waveforms/groups...

.. _global_properties:

Global Properties
-----------------

``dd_version`` and ``input`` apply to the entire configuration. They can be changed
under the "Edit Global Properties" tab in the GUI.

*   **dd_version:** Specifies the IMAS Data Dictionary version to be used when handling this configuration.

    .. code-block:: yaml

       dd_version: 3.42.0

*   **input:** Names the external IMAS data entries a waveform can copy a value from
    with :ref:`{copy: \<name\>} <importing-external-data>` -- for example a scenario run or a
    machine description. Use a dictionary where keys are names you choose and values
    are the corresponding IMAS URIs.

    .. code-block:: yaml

       dd_version: 3.42.0
       input:
         scenario: imas:hdf5?path=my_scenario
         machine: imas:hdf5?path=my_machine_description
         # Add other entries as needed

Grouping Waveforms
------------------

Keys at any level under ``output`` that contain a dictionary represent logical groups
(unless the dictionary is a copy, see :ref:`Importing External Data <importing-external-data>`).
Groups are primarily for organizing the YAML file and do not affect the final IMAS path of the waveforms defined within them.

.. code-block:: yaml

   output:
     ec_launchers: # Top-level group
       beams:      # Nested group
         phase_angles: # Another nested group
           # Waveforms defined here...
         steering_angles:
           poloidal:
             # Waveforms defined here...
           toroidal:
             # Waveforms defined here...

Defining Waveforms
------------------

Waveforms are defined by key-value pairs where the key contains a string, 
a list of waveforms, or a single number (float or integer).

*   **Waveform Name:** The waveform name represents the unique identifier for the waveform. In order to export the waveform to an IDS the following naming structure must be used. The first segment should refer to the **IDS name** and the second part should refer to the **path** in that IDS the waveform applies to, e.g., ``ec_launchers/beam(1)/phase/angle``. It is allowed to not adhere to this format, but in this case the waveforms will not be saved to an IDS during export.

*   **Waveform Definition:** The value associated with the key defines how the waveform evolves over time. It can take several forms:

    1.  **List of Tendencies:** A YAML list defines a sequence of time-dependent segments, known as `Tendencies`. Each item in the list is a dictionary specifying the parameters for one tendency.

        .. code-block:: yaml

           ec_launchers/beam(4)/power_launched:
               # Linear ramp from 0 to 8.33e5 for 20 seconds
             - { type: linear to: 8.33e5, duration: 20 }
               # Constant value for the next 20 seconds
             - { type: constant, duration: 20 }
               # Implicit linear ramp back to 0 over 25 seconds
             - { duration: 25, to: 0 }

        Refer to the :ref:`Available Tendencies <available-tendencies>` documentation for details on the different tendency types and their parameters.

        .. note::
            The ``type`` may be omitted. The type of the tendency is then inferred from
            the other keys present, if possible.

    2.  **Constant Value:** A bare number (integer or float) or string defines a constant waveform over time, equivalent to a single :ref:`constant tendency <constant-tendency>`.

        .. code-block:: yaml

           ec_launchers/beam(1)/phase/angle: -1.65898 # Constant float value
           pulse_schedule/ec/mode: 3                  # Constant int value
           core_sources/source(1)/identifier/name: ec  # Constant string value

    3.  **Empty Waveform:** An empty list ``[{}]`` defines a waveform that is constantly zero.

        .. code-block:: yaml

          some_ids/data: [{}] # Represents a waveform that is always 0
          # This is equal to:
          some_ids/data: 0

    4.  **Derived Waveform:** Waveforms may contain calculations or be derived from other waveforms.
        For more information, see :ref:`Derived Waveforms <derived-waveforms>`.

    5.  **Copy:** A waveform's value may instead be copied from one of the entries
        declared under :ref:`input: <global_properties>`. See
        :ref:`Importing External Data <importing-external-data>` below.

.. _importing-external-data:

Importing External Data
------------------------

A waveform can take its value from an external IMAS data entry declared under
``input:`` instead of defining its own tendencies, using ``{copy: <name>}``:

.. code-block:: yaml

   input:
     scenario: imas:hdf5?path=my_scenario

   output:
     shape:
       equilibrium/time_slice/boundary/outline/r: {copy: scenario}
       equilibrium/time_slice/boundary/outline/z: {copy: scenario}

This reads the waveform's own path (``equilibrium/time_slice/boundary/outline/r`` in
the example above) out of the ``scenario`` entry.

*   If the source's data is a single value per time step (e.g. a scalar global
    quantity, or an array indexed by its own time base), the copy behaves like any
    other waveform: it can be plotted and used in expressions, and is resampled onto
    the export time base (taking the closest source time point to each entry):

    .. code-block:: yaml

       pf_active/coil(1)/current/data: {copy: scenario}

*   Anything larger -- a profile, a per-slice array, or other static/structural data
    such as machine geometry -- is copied straight into the target IDS on export
    instead, and cannot be previewed as a curve. A slice (``(:)``) expands against the
    source, so each element is copied on its own:

    .. code-block:: yaml

       input:
         machine: imas:hdf5?path=my_machine_description

       output:
         wall:
           wall/description_2d(:)/limiter/unit(:)/outline/r: {copy: machine}
           wall/description_2d(:)/limiter/unit(:)/outline/z: {copy: machine}

*   ``path:`` reads a different path than the waveform's own name from the source,
    for a waveform whose name isn't itself a DD path:

    .. code-block:: yaml

       my_local_ip: {copy: scenario, path: equilibrium/time_slice/global_quantities/ip}

Slice Notation
--------------

Slice notation simplifies addressing ranges within Arrays of Structures (AoSs) in YAML configuration. Slices use Fortran-style indexing, and therefore are: 1-based and inclusive. For example: ``(1:5)`` indicates the first 5 elements.

**Available Slice Types:**

*   **Full Slice:** ``(:)`` - All elements.
*   **Range Slice:** ``(start:end)`` - All elements between ``start`` and ``end``.
*   **Half Slices:** 

    * ``(start:)`` - All elements starting at ``start``.
    * ``(:end)`` - All elements upto and including ``end``.

**Example Slices:**

The following example will fill the ``power_launched`` IDS node in ``ec_launchers`` for beam 1, 2, and 3.

.. code-block:: yaml

   ec_launchers/beam(1:3)/power_launched: 5.0


Slicing can be applied at multiple nested levels. For example, the following fills the ``phase_corrected/data`` node of the ``interferometer`` IDS, for the wavelengths 1 through 4, for channel 2 and 3.

.. code-block:: yaml

   interferometer/channel(2:3)/wavelength(1:4)/phase_corrected/data: 15.0



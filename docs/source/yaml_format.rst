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

A Waveform Editor YAML file is a standard YAML dictionary containing two main types of top-level keys:

1.  **globals:** A key holding settings that apply to the entire configuration.
2.  **Groups:** These represent logical groupings for organizing waveforms. They can be nested to create a hierarchy.

.. code-block:: yaml
   :caption: Basic File Structure

   globals:
     # Global settings here...

   top_level_group_1:
     # Waveforms and nested groups here...

   top_level_group_2:
     nested_group_A:
       # More waveforms/groups...
     # More waveforms/groups...

.. _global_properties:
   
Global Properties
-----------------

The ``globals`` section defines parameters applicable to the entire waveform configuration.
These parameters can be changed under the "Edit Global Properties" tab in the GUI.

*   **dd_version:** Specifies the IMAS Data Dictionary version to be used when handling this configuration.

    .. code-block:: yaml

       globals:
         dd_version: 3.42.0

*   **imports:** Named external data entries that waveforms can import values from
    (see :ref:`Import <import-tendency>`). Each value is either an IMAS URI, or a
    mapping ``{port: <name>}`` referring to an IDS received on a MUSCLE3 port at run
    time (used by the actor). Use a dictionary where the keys are names you choose and
    refer to with ``{ref: <name>}``.

    .. code-block:: yaml

       globals:
         dd_version: 3.42.0
         imports:
           machine: imas:hdf5?path=machine_description1
           scenario: imas:hdf5?path=scenario_run
           live_eq: {port: equilibrium_in}

    A machine description is expressed as an import overlaid whole onto an IDS: list an
    ``<ids>/*`` import first (its filled leaves are copied in as a base), then add the
    waveforms that override individual nodes.

    .. code-block:: yaml

       ec_launchers:
         ec_launchers/*:
           - {ref: machine}          # overlay the whole machine-description IDS first
         ec_launchers/beam(1)/phase/angle: -1.65898  # then override specific leaves

Grouping Waveforms
------------------

Keys at any level that contain a dictionary represent logical groups. 
These are primarily for organizing the YAML file and do not affect the final IMAS path of the waveforms defined within them.

.. code-block:: yaml

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

        The ``type`` may be omitted, in which case it is inferred from the entry's keys: ``to`` implies ``linear``, ``time`` implies ``piecewise``, and ``value`` implies ``constant``. Anything else falls back to ``linear`` -- a linear tendency does not require ``to`` (a ``from``-only, ``rate``-only, or bare segment is still linear, taking its endpoints from its neighbours). A segment whose distinguishing key is absent must name its ``type`` explicitly: the periodic shapes, ``smooth``, and a value-less ``constant`` (a bare ``{duration: ...}`` is read as a linear ramp).

        Refer to the :ref:`Available Tendencies <available-tendencies>` documentation for details on the different tendency types and their parameters.

    2.  **Constant Value:** A simple number (integer or float) defines a constant waveform over time.

        .. code-block:: yaml

           ec_launchers/beam(1)/phase/angle: -1.65898 # Constant value

    3.  **Empty Waveform:** An empty list ``[{}]`` defines a waveform that is constantly zero.

        .. code-block:: yaml

          some_ids/data: [{}] # Represents a waveform that is always 0
          # This is equal to:
          some_ids/data: 0

    4.  **Derived Waveform:** Waveforms may contain calculations or be derived from other waveforms.
        For more information, see :ref:`Derived Waveforms <derived-waveforms>`.

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

Complete Example
----------------

The following configuration exercises the full :ref:`imports <import-tendency>` mechanism: a machine-description overlay (``<ids>/*``), a scalar import with interpolation, a static value, trailing-subtree and index wildcards (``source(*)``, ``ion(*)``), a 0D composite, and a runtime port-import.

.. literalinclude:: examples/imports.yaml
   :language: yaml



.. _yaml_format:

================
YAML File Format
================

The Waveform Editor uses YAML files to define the desired waveforms, their organization, and global settings for export. This page describes the structure and syntax of these files.

Overall Structure
-----------------

A Waveform Editor YAML file is a standard YAML dictionary containing two main types of top-level keys:

1.  **globals:** An optional key holding settings that apply to the entire configuration.
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

Global Settings
---------------

The optional ``globals`` section defines parameters applicable to the entire waveform configuration.

*   **dd_version:** Specifies the IMAS Data Dictionary version to be used when handling this configuration.

    .. code-block:: yaml

       globals:
         dd_version: 3.42.0

*   **machine_description:** Provides URIs for IMAS machine description entries. This allows the exporter to copy existing static data from a machine description before adding the defined waveforms. To specify machine descriptions for a target IDS, use a dictionary where keys are the IDS names and values are their corresponding machine description URIs.

    .. code-block:: yaml

       globals:
         DD_version: 3.42.0
         machine_description:
           ec_launchers: imas:hdf5?path=machine_description1
           nbi: imas:hdf5?path=machine_description2
           # Add other IDSs as needed

Grouping Waveforms
------------------

Keys at any level that **do not** contain a forward slash (`/`) define logical groups. These are primarily for organizing the YAML file and do not affect the final IMAS path of the waveforms defined within them.

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

Waveforms are defined by key-value pairs where the key **contains** at least one forward slash (`/`).

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

    2.  **Constant Value:** A simple number (integer or float) defines a constant waveform over time. This is shorthand for: ``{type: constant, value: <number>}``.

        .. code-block:: yaml

           ec_launchers/beam(1)/phase/angle: -1.65898 # Constant value

    3.  **Empty Waveform:** An empty list ``[{}]`` defines a waveform that is constantly zero.

        .. code-block:: yaml

          some_ids/data: [{}] # Represents a waveform that is always 0
          # This is equal to:
          some_ids/data: 0

    4.  **Reference:** TODO: add referenced/derived waveforms and link to that section here.


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



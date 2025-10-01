.. _example_config:

Example Configuration
=====================

The waveform editor supports exporting waveforms many different quantities across multiple IDSs.
The example YAML configuration below demonstrates how to assign waveforms to various IDS quantities.
An overview of the quantities and IDSs in the example configuration is provided in the table below.

.. list-table::
   :widths: 25 25 50
   :header-rows: 1

   * - Physics domain
     - Dynamic data
     - Involved IDS
   * - H&CD
     - H&CD powers
     - ec_launchers, ic_antennas, nbi
   * - 
     - Wave polarization
     - ec_launchers
   * - 
     - Strap phase
     - ic_antennas
   * - 
     - Wave frequency
     - ec_launchers, ic_antennas
   * - 
     - Beam energy
     - nbi
   * - 
     - Beam steering angles
     - ec_launchers
   * - Plasma density
     - Gas puffing
     - gas_injection
   * - 
     - Pellet injection
     - pellets
   * - 
     - Line-averaged density
     - interferometer
   * - Global scenario parameters
     - Plasma current
     - equilibrium, core_profiles
   * - 
     - Nominal magnetic field
     - equilibrium, core_profiles
   * - 
     - Effective charge
     - core_profiles


Example YAML configuration
--------------------------

.. note::

   The actual waveform data in this configuration are derived from a dummy waveform ``w/1`` 
   which contains arbitrary data. For more information, see :ref:`Derived Waveforms <derived-waveforms>`.
   Additionally, only the first elements of each array of structures are filled for this example.

.. literalinclude:: ../../tests/test_yaml/example.yaml
   :language: yaml

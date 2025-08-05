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

.. code-block:: yaml

   globals:
     dd_version: 4.0.0
     machine_description: {}
   dummy_waveform:
     w/1:
     - {to: 1e5, duration: 100}
     - {duration: 300}
     - {to: 0, duration: 100}
   H&CD:
     Powers:
       ec_launchers/beam(1)/power_launched/data: '"w/1"'
       ic_antennas/antenna(1)/power_launched/data: '"w/1"'
       nbi/unit(1)/power_launched/data: '"w/1"'
     Strap phase:
       ic_antennas/antenna(1)/module(1)/strap(1)/phase/data: '"w/1"'
     Beam energy:
       nbi/unit(1)/energy/data: '"w/1"'
     Wave polarization:
       ec_launchers/beam(1)/phase/angle: '"w/1"'
     Wave frequency:
       ic_antennas/antenna(1)/frequency/data: '"w/1"'
       ec_launchers/beam(1)/frequency/data: '"w/1"'
     Steering angles:
       ec_launchers/beam(1)/steering_angle_pol: '"w/1"'
       ec_launchers/beam(1)/steering_angle_tor: '"w/1"'
   Plasma density:
     Gas injection:
       gas_injection/valve(1)/flow_rate/data: '"w/1"'
       gas_injection/valve(1)/electron_rate/data: '"w/1"'
       gas_injection/pipe(1)/flow_rate/data: '"w/1"'
     Pellet injection:
       pellets/time_slice/pellet(1)/velocity_initial: '"w/1"'
     Line-averaged density:
       interferometer/channel(1)/n_e_line/data: '"w/1"'
   Global scenario parameters:
     Plasma current:
       equilibrium/time_slice/global_quantities/ip: '"w/1"'
       core_profiles/global_quantities/ip: '"w/1"'
     Nominal magnetic field:
       equilibrium/vacuum_toroidal_field/b0: '"w/1"'
       core_profiles/vacuum_toroidal_field/b0: '"w/1"'
     Effective charge:
       core_profiles/global_quantities/z_eff_resistive: '"w/1"'

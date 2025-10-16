.. _training:

Training Courses
================

In this training you will learn the following:

- Creating and editing waveforms using the GUI
- Exporting waveforms to an IDS

Exporting waveform configurations to IMAS HDF5 files
All examples assume you have an environment with the Waveform Editor up and running.
if you do not have this yet, please have a look at the :ref:`installation instructions <installing>`.
You do not need to have installed the dependencies for the Plasma Shape Editor to do these exercises.

Creating your first waveforms
-----------------------------

In this section, you will learn how to create your first waveforms.

Exercise 1a: Creating a new waveform
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      In order to start editing waveforms, you must first learn how to navigate your way around
      around the GUI. Launch the Waveform Editor GUI using the following command, 
      which opens the Waveform Editor in your default browser.

      .. code-block:: bash

         waveform-editor gui


      #. A waveform must *always* belong to a group, so first create a group in which 
         to store the new waveform, and provide a name for the group, e.g. ``Group1``.
      #. Create a new waveform in the previously created group, and provide a name for 
         this waveform, e.g. ``Waveform1``.
      
      What do you see in the sidebar on the left?

      .. hint::
         Detailed instructions on how to add groups and waveforms from the GUI 
         can be found :ref:`here <edit_config>`.


   .. md-tab-item:: Solution

      .. |add_waveform_icon| image:: ../images/gui/add_waveform_icon.png
         :height: 24px
      .. |add_group_icon| image:: ../images/gui/add_group_icon.png
         :height: 24px

      #. Use this button |add_group_icon| to add a new group and call it ``Group1``
      #. Use this button |add_waveform_icon| to add a new waveform and call it ``Waveform1``

      You have now created a new waveform, which is shown in the sidebar:

      .. image:: ../images/training/ex1_sidebar.png
         :align: center


Exercise 1b: Creating a sine wave
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      Now you will edit the empty waveform you created in the previous exercise. 
      Select the waveform in the sidebar and open the *Edit Waveforms* tab. You will 
      see an editor window as well as a live view the waveform currently being edited.

      The editor currently shows ``- {}``, indicating an empty tendency.
      A tendency can be specified by providing a tendency type and by setting parameters defining 
      the shape of this tendency. For example:

      .. code-block:: yaml

         - {type: <waveform type>, <param 1>: <value 1>, <param 2>: <value 2>, ...}

      Edit the waveform you created in the previous exercise such that it contains
      a single sine-wave tendency, with the following parameters:

      - Type: sine
      - Duration: from 10 to 15 seconds
      - Frequency: 0.5 Hz
      - Amplitude: 3
      - Vertical range: 0 to 6

      Use the following tendency parameters: ``type``, ``start``, ``end``, ``frequency``, ``amplitude``, and ``base``.

      .. hint::
         Detailed descriptions of the tendencies can be found :ref:`here <available-tendencies>`.

   .. md-tab-item:: Solution

      #. Switch to the editor tab and edit the waveform. Enter the following into the editor:

      .. code-block:: yaml

         - {type: sine, start: 10, end: 15, frequency: 0.5, amplitude: 3, base: 3}

      You should see the following waveform:

      .. image:: ../images/training/ex1_sine.png
         :align: center

Exercise 1c: Creating a sine wave - part 2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      In the previous execise, you might have noticed that there a multiple ways in which you can define the same 
      waveform. Recreate the waveform of previous exercise using only the following tendency parameters: 
      ``type``, ``start``, ``duration``, ``period``, ``min``, and ``max``.

   .. md-tab-item:: Solution

      The resulting waveform should be:

      .. code-block:: yaml

         - {type: sine, start: 10, duration: 5, period: 2, min: 0, max: 6}


Exercise 1d: Creating a sine wave - part 3
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      What happens if you overdetermine your waveform? For example, try setting both
      the frequency, as well as the period of the sine wave:
      ``frequency: 0.5`` and ``period: 2``

      And what happens if frequency and period would result in a different sine wave? For example, try setting 
      ``frequency: 2`` and ``period: 2``? 


   .. md-tab-item:: Solution

      If you set the ``frequency: 0.5`` and ``period: 2``, since these do not conflict, 
      this waveform is allowed.

      .. code-block:: yaml

         - {type: sine, start: 10, duration: 5, frequency: 0.5, period: 2, min: 0, max: 6}

      If you set the the ``frequency: 2`` and ``period: 2``, for example:

      .. code-block:: yaml

         - {type: sine, start: 10, duration: 5, frequency: 2, period: 2, min: 0, max: 6}

      you will see an error pop up in the editor, notifying you that the period and 
      frequency do not match.


Advanced Waveforms
------------------

In this section, you will learn how to create more complex waveforms.

Exercise 2a: Creating a Plasma Current
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      In the previous exercises, you created a waveform that contained only a single tendency.
      However, waveforms can contain any number of tendencies, by adding additional lines 
      in the editor.

      We will now design a simple waveform representing the plasma current during
      a single pulse. Create a waveform called ``equilibrium/time_slice/global_quantities/ip``, 
      which has the following shape:
      
      1. A linear ramp up from 0 to 1.5e7 A, in a duration of 100 seconds.
      2. A flat-top at 1.5e7 A, held for 400 seconds.
      3. A ramp down back to 0 A, in a duration of 200 seconds.

   .. md-tab-item:: Solution
      
      Your waveform can contain for example the following tendencies:

      .. code-block:: yaml

         - {type: linear, from: 0, to: 1.5e7, start: 0, duration: 100}
         - {type: constant, value: 1.5e7, start: 100, duration: 400}
         - {type: linear, from: 1.5e7, to: 0, start: 500, duration: 200}

      You should see the following waveform:
      
      .. image:: ../images/training/flattop.png
         :align: center
      

Exercise 2b: Shortform notation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      In the previous exercise, the solution proposed was very quite lengthy. The 
      Waveform Editor can sometimes deduce some information about the tendencies if 
      information is missing.

      Some examples:

      #. If no ``start`` parameter is provided, the end of the previously tendency will be 
         used as a start value, or 0 if it is the first tendency.
      #. If no tendency ``type`` is provided, it will be considered a linear tendency by default.
      #. If no start value e.g. ``from`` is provided, it will try to match end of previous tendency.

      Try to replicate the waveform in the previous exercise using this shortform notation.

   .. md-tab-item:: Solution
   
      In the shortform notation:

      #. The first tendency - No ``start`` or ``from`` is needed because it begins at 0 by default.
      #. The second tendency - No ``type`` is provided, so it is a linear tendency by default. 
         The ``start``, ``from``, and ``to`` parameters are by default set to the respective 
         values at the end of the previous tendency.
      #. The third tendency - Again, the ``start`` and ``from`` parameters are inferred from the 
         previous tendency. In this case, we do need to specify the ``to`` parameter, otherwise
         we would get a straight line.
      
      .. code-block:: yaml

         - {to: 1.5e7, duration: 100}
         - {duration: 400}
         - {to: 0, duration: 200}


Exercise 3a: Complex waveforms
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      Create a waveform that consists of the following two tendencies:

      1. A piecewise linear tendency containing the following 5 pairs of points:
         ``(0,2.5), (2,3), (3,1), (5,3), (6,2)``
      2. A linear tendency starting from 2.5, with a rate of change of 0.25, lasting 3 seconds.

      .. hint::
         Detailed descriptions of the tendencies can be found :ref:`here <available-tendencies>`.

   .. md-tab-item:: Solution


      Your waveform can contain for example the following tendencies:

      .. code-block:: yaml

         - {type: piecewise, time: [0, 2, 3, 5, 6], value: [2.5, 3, 1, 3, 2]}
         - {type: linear, from: 2.5, rate: 0.25, duration: 3}

      You should see the following waveform:

      .. image:: ../images/training/complex.png
         :align: center

Exercise 3b: Smoothing
^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      Continuing from the waveform in the previous exercise, modify it to include a 
      **smooth** tendency with a duration of 1 between the two tendencies. What do you notice?

   .. md-tab-item:: Solution
      
      Your waveform can contain for example the following tendencies:

      .. code-block:: yaml

         - {type: piecewise, time: [0, 2, 3, 5, 6], value: [2.5, 3, 1, 3, 2]}
         - {type: smooth, duration: 1}
         - {type: linear, from: 2.5, rate: 0.25, duration: 3}

      .. image:: ../images/training/smooth.png
         :align: center

      You should see the following waveform. Notice how the smooth tendencies ensure 
      continuous value and derivative across multiple tendencies.




Exercise 3c: Repeating Waveforms
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      You can create repeating patterns using the ``repeat`` tendency. The repeat tendency 
      allows you to specify the ``waveform`` parameter. This allows you to repeat 
      any number of tendencies.

      Take the waveform from the previous exercise and make it repeat three times.
      Ensure that the end of the linear tendency and the start of the piecewise tendency also smoothly 
      transition into each other, in 1 second.

   .. md-tab-item:: Solution

      A smooth tendency was added as a last tendency to smoothly transition from the 
      linear tendency back into the piecewise linear tendency. This whole waveform is 
      placed in the ``waveform`` parameter of the repeat tendency. Since the tendencies
      combine up to a total length of 11 (6+1+3+1), the total ``duration`` of the repeat
      tendency is set to 33, to obtain three full cycles.

      .. code-block:: yaml

         - type: repeat
           duration: 33
           waveform:
           - {type: piecewise, time: [0, 2, 3, 5, 6], value: [2.5, 3, 1, 3, 2]}
           - {type: smooth, duration: 1}
           - {type: linear, from: 2.5, rate: 0.25, duration: 3}
           - {type: smooth, duration: 1}

      You should see the following waveform:

      .. image:: ../images/training/repeat.png
         :align: center

      .. note:: You can also change the frequency of the repeated waveform, see the 
         :ref:`documentation <repeat-tendency>` to see how.


Exercise 4a: Derived Waveforms
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      Waveforms can depend on other waveforms, and you can even perform calculations 
      using other waveforms. In this exercise, you will define simple waveforms for the power of
      the `electron cyclotron (EC) launchers <https://imas-data-dictionary.readthedocs.io/en/latest/generated/ids/ec_launchers.html#ids-ec_launchers>`_.

      The goal is to create:
      
      1. A waveform ``total_power`` containing the total power of all EC launchers, 
         this consists of a waveform that linearly ramps up from 0 to 5e5 W for 100 seconds, 
         then flat-tops for 500 seconds, and finally linearly ramps down for 100 seconds.
      2. We take 10 different beams, and define the derived beam power waveforms 
         ``ec_launchers/beam(1:10)/power_launched/data`` that evenly divides the total 
         power over each beam.

      What happens to the derived waveform when you change the total power waveform? 

      .. hint::
         Detailed instructions on derived waveforms can be found :ref:`here <derived-waveforms>`.

      Before starting with Exercise 4b, save the configuration containing the two created waveforms
      to disk. This will be used in a later exercise. To see how to save a configuration, have a 
      look at the :ref:`instructions <saving_config>`.

   .. md-tab-item:: Solution

      Create a new waveform called ``total_power`` which contains: 

      .. code-block:: yaml

         - {type: linear, to: 5e5, duration: 100}
         - {type: constant, duration: 500}
         - {type: linear, to: 0, duration: 100}

      Create a second waveform called ``ec_launchers/beam(1:10)/power_launched/data``,
      this represents the ``power_launched`` for each of the ten beams, which contains:

      .. code-block:: yaml

         "total_power" / 10

      You should have the following two waveforms:

      .. image:: ../images/training/derived_power.png
         :align: center

      If you change the ``total_power`` waveform you should see that the derived 
      waveforms changes as well.

Exercise 4b: Derived Waveforms - part 2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      In this exercise, you will define a **derived waveform** in which the
      `Neutral Beam Injection (NBI) <https://imas-data-dictionary.readthedocs.io/en/latest/generated/ids/nbi.html#ids-nbi>`_ launch power depends on the beam energy through the following  relation.

      .. math::

         P_\mathrm{launched} = P_0 \left( \frac{E_\mathrm{beam}}{E_0} \right)^{2.5}

      where:

      - :math:`P_0` = 16.5e6 W (nominal power per beam box)
      - :math:`E_0` = 870e3 eV (reference beam energy for hydrogen)
      - :math:`E_\mathrm{beam}` is the beam energy

      Define the following waveforms:

      1. ``nbi/unit(1)/energy/data`` - linear ramps up from 0 to 500e3, for 100 seconds, then flattops for 500 seconds, and then linearly ramps down for 100 seconds.
      2. ``nbi/unit(1)/power_launched/data`` - derived from the energy using the above equation.

   .. md-tab-item:: Solution

      Create a new waveform called ``nbi/unit(1)/energy/data`` which contains:

      .. code-block:: yaml

         - {type: linear, to: 500e3, duration: 100}
         - {type: constant, duration: 500}
         - {type: linear, to: 0, duration: 100}

      Create a second waveform called ``nbi/unit(1)/power_launched/data``, which contains:

      .. code-block:: yaml

         16.5e6 * ("nbi/unit(1)/energy/data" / 870e3) ** 2.5

      You should have the following two waveforms:

      .. image:: ../images/training/derived_nbi.png
         :align: center

Exporting Waveforms
-------------------

In this exercise you will learn how to export waveform configurations.

Exercise 5a: Exporting from the UI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      In this exercise, we will continue with the configuration that you stored in 
      exercise 4a. If you forgot to save it, the YAML is also shown under the tab `Configuration`.
      Load this configuration into the Waveform Editor, if you are unsure how to, have a look 
      at the instructions :ref:`here <gui>`.

      We will export our EC beam power values to an ec_launchers IDS. Export the configuration
      to an HDF5 file. Sample the time such that there are 20 points in the range from 0 to 800s.

      Inspect the exported IDS using ``imas print <your URI> ec_launchers``, which 
      quantities are filled? Notice that the waveform in the configuration runs from 0 to 700s,
      while you export from 0 to 800s . What happens with the exported values outside 
      of the waveform (time steps later than 700 s)?

      .. hint::
         Detailed instructions on how to export the waveform configuration can be found :ref:`here <export_config>`.

   .. md-tab-item:: Configuration

      If you forgot to save the configuration of exercise 4a, copy the following YAML file,
      and store it to disk.


      .. code-block:: yaml

         globals:
           dd_version: 4.0.0
           machine_description: {}
         ec_launchers:
           total_power:
           - {type: linear, to: 5e5, duration: 100}
           - {type: constant, duration: 500}
           - {type: linear, to: 0, duration: 100}
           ec_launchers/beam(1:10)/power_launched/data: |
             "total_power" / 10

   .. md-tab-item:: Solution

      Printing the exported ec_launchers IDS shows the output below. Notice how the 
      time array is filled with values from 0 to 800. The Waveform Editor will only 
      export waveforms which name matches a path in the IDS. Therefore, the ``total_power``
      waveform will not be exported to an IDS. Since we use a slicing notation for the 
      power_launched waveform (``beam(1:10)``), the first 10 beams are filled with the 
      same waveform.

      Any values which are outside of the defined waveform range (e.g. values later than 700s)
      will be set to 0.

      .. code-block:: bash

         ec_launchers
         ├── ids_properties
         │   ├── homogeneous_time: 1
         │   └── ids_properties/version_put
         │       ├── data_dictionary: '4.0.0'
         │       ├── access_layer: '5.4.3'
         │       └── access_layer_language: 'imas 2.0.1'
         ├── beam[0]
         │   └── beam[0]/power_launched
         │       └── data: array([    0.    , 21052.6316, 42105.2632, ...,     0.    ,     0.    ,     0.    ])
         ├── beam[1]
         │   └── beam[1]/power_launched
         │       └── data: array([    0.    , 21052.6316, 42105.2632, ...,     0.    ,     0.    ,     0.    ])
         ├── beam[2]
         │   └── beam[2]/power_launched
         │       └── data: array([    0.    , 21052.6316, 42105.2632, ...,     0.    ,     0.    ,     0.    ])
         ├── beam[3]
         │   └── beam[3]/power_launched
         │       └── data: array([    0.    , 21052.6316, 42105.2632, ...,     0.    ,     0.    ,     0.    ])
         ├── beam[4]
         │   └── beam[4]/power_launched
         │       └── data: array([    0.    , 21052.6316, 42105.2632, ...,     0.    ,     0.    ,     0.    ])
         ├── beam[5]
         │   └── beam[5]/power_launched
         │       └── data: array([    0.    , 21052.6316, 42105.2632, ...,     0.    ,     0.    ,     0.    ])
         ├── beam[6]
         │   └── beam[6]/power_launched
         │       └── data: array([    0.    , 21052.6316, 42105.2632, ...,     0.    ,     0.    ,     0.    ])
         ├── beam[7]
         │   └── beam[7]/power_launched
         │       └── data: array([    0.    , 21052.6316, 42105.2632, ...,     0.    ,     0.    ,     0.    ])
         ├── beam[8]
         │   └── beam[8]/power_launched
         │       └── data: array([    0.    , 21052.6316, 42105.2632, ...,     0.    ,     0.    ,     0.    ])
         ├── beam[9]
         │   └── beam[9]/power_launched
         │       └── data: array([    0.    , 21052.6316, 42105.2632, ...,     0.    ,     0.    ,     0.    ])
         └── time: array([  0.    ,  42.1053,  84.2105, ..., 715.7895, 757.8947, 800.    ])


Exercise 5b: Exporting different Data Dictionary versions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      Repeat the previous exercise, but this time, before exporting change the data dictionary 
      version to **3.42.0** in the `Edit Global Properties` tab, and save the configuration.
      Ensure you enter a different from previous exercise. Again, print the IDS in your terminal, what has changed?

   .. md-tab-item:: Solution

      You should see that the data dictionary version of the IDS has changed to '3.42.0':

      .. code-block:: bash

         ec_launchers
         ├── ids_properties
         │   ├── homogeneous_time: 1
         │   └── ids_properties/version_put
         │       ├── data_dictionary: '3.42.0'
         │       ├── access_layer: '5.4.3'
         │       └── access_layer_language: 'imas 2.0.1'
         ...

Exercise 5c: Exporting from the CLI
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. md-tab-set::
   .. md-tab-item:: Exercise

      You can also export a configuration using the CLI. Try exporting your configuration
      using the same settings with the CLI command. Print the IDS afterwards, is it the 
      same as before?

      .. hint::

         Each CLI command has a help page which can be printed by supplying the ``--help``
         flag, for example:

         .. code-block:: bash

            waveform-editor --help 

         Detailed instructions on how to use the CLI can be found :ref:`here <cli>`.

   .. md-tab-item:: Solution

      Export the configuration using:

      .. code-block:: bash

         waveform-editor export-ids <example YAML> imas:hdf5?path=./ex5c --linspace 0,800,20

      This exports the same IDS as in previous exercise.

Plasma Shape Editor
-------------------

TODO: Exercises for plasma shape editor

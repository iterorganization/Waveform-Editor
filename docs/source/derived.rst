.. _derived-waveforms:

=================
Derived Waveforms
=================

Derived waveforms are waveforms whose values are computed from other waveforms.
These computations may involve mathematical expressions or NumPy functions.
Whenever a source waveform is changed, any waveform that depends on it is automatically 
recalculated in the GUI.

Examples
========

Dividing Total Power Among Multiple Beams
-----------------------------------------

This example demonstrates how to distribute a total power value across multiple beams. 
The ``total_power`` waveform defines the overall power profile over time. 
The power of the individual beams are scaled by the total power to ensure the power of 
all beams combined is equal to the total power.

.. code-block:: yaml

    ec_launchers:
      ec_launchers/total_power:
      - {duration: 1}
      - {type: constant, value: 5e+5, duration: 18}
      - {to: 0}
      ec_launchers/beam(1:10)/power_launched/data: |
        'ec_launchers/total_power' / 10

.. image:: images/derived_power.jpg
   :width: 600px
   :align: center

.. warning::

    In this example case, the editor does not validate whether the sum of all 
    ec_launchers/beam*/power_launched values matches ec_launchers/total_power.


Arithmetic on a Single Waveform
-------------------------------

This example shows how to perform arithmetic on a waveform. It features a simple waveform, 
``test/1``, which consists of a ramp-up, flat top, and ramp-down. 
The other waveforms are derived from ``test/1`` and apply different mathematical expressions: 
``test/2`` divides ``test/1`` by 2, ``test/3`` multiplies it by 2, and ``test/4`` adds a constant offset.

.. code-block:: yaml

    example:
      test/1:
      - {type: linear, from: 10, to: 50, duration: 20}
      - {type: constant, value: 50, duration: 20}
      - {type: linear, from: 50, to: 30, duration: 20}
      test/2: |
        'test/1' / 2
      test/3: |
        2 * 'test/1'
      test/4: |
        'test/1' + 10

.. image:: images/derived_calc.jpg
   :width: 600px
   :align: center

.. note::

    If you are using the Waveform Editor from the GUI, you only have to enter the 
    expression in the block string. For the example above, you would only need
    to enter ``'test/1' + 10`` as the waveform definition for the waveform ``test/4``.

Multiple Dependencies
---------------------

It is allowed to use multiple different dependent waveforms in a single expression.
In the example below, waveform ``test/3`` is the sum of the waveforms ``test/1`` and ``test/2``.

.. code-block:: yaml

    example:
      test/1:
      - {type: linear, from: 10, to: 50, duration: 20}
      - {type: constant, value: 50, duration: 20}
      - {type: linear, from: 50, to: 30, duration: 20}
      test/2:
      - {type: sine, amplitude: 3, period: 3, duration: 60}
      test/3: |
        'test/1' + 'test/2'

.. image:: images/derived_sum.jpg
   :width: 600px
   :align: center


Using NumPy Functions
---------------------

It is allowed to use NumPy expressions to transform existing waveforms. 
This example demonstrates how to use different NumPy functions in derived waveform expressions.
``test/2`` applies the absolute value, and ``test/3`` clamps the waveform to non-negative values using ``maximum``.

.. code-block:: yaml

    example:
      test/1:
      - {type: linear, from: -10, to: 10, duration: 20}
      test/2: |
        abs('test/1')
      test/3: |
        maximum('test/1', 0)

.. image:: images/derived_np.jpg
   :width: 600px
   :align: center

.. note::

    Only NumPy’s universal functions (ufuncs) are allowed in expressions. 
    See the `NumPy ufunc documentation <https://numpy.org/doc/stable/reference/ufuncs.html>`_ for the full list.

Combined Operations
-------------------

The methods explained above may be combined to generate complex waveform definitions, 
an example of this is shown below.

.. code-block:: yaml

    example:
      test/1:
      - {from: -30, to: 30, duration: 20}
      - {duration: 20}
      - {to: -40, duration: 20}
      test/2:
      - {type: sine, amplitude: 3, period: 3, duration: 60}
      test/3: |
        abs('test/1' - 5 + 'test/2' / 2)

.. image:: images/derived_combi.jpg
   :width: 600px
   :align: center

MUSCLE3 IMAS Actor
==================

The waveform editor includes an actor that can be included in an IMAS MUSCLE3 simulation.
This page assumes you are familiar with `MUSCLE3 <https://muscle3.readthedocs.io/>`__ and 
`IMAS <https://imas-data-dictionary.readthedocs.io/en/latest/>`__ coupled simulations.

.. caution::
    The IMAS MUSCLE3 actor requires the following packages:

    - `muscle3 <https://pypi.org/project/muscle3>`__
    - `imas_core <https://git.iter.org/projects/IMAS/repos/al-core/browse>`__ which is
      not (yet) publicly available.

Actor details
-------------

The actor expects a message on a single input port, evaluates all configured waveforms,
and sends each resulting IDS on its matching (connected) output port.

The **input port** must be named ``<ids>_in`` (or ``<ids>``, i.e. a valid IDS name), so
the actor can deserialize the message. Only the root ``/time`` of that IDS is used,
it's the time base the waveforms are evaluated on, one new time slice per entry.

.. code-block:: yaml
    :caption: Example ``programs`` section for running the waveform-editor actor

    programs:
      waveform_actor:
        executable: waveform-editor
        args: actor

Available settings
''''''''''''''''''

- ``waveforms`` (mandatory): indicate the (full) path to the waveform configuration.


Input ports (``F_INIT``)
''''''''''''''''''''''''

The actor has exactly one input port, named ``<ids>_in`` (or ``<ids>``): the time base
the waveforms are evaluated on is read from that IDS's root ``/time``.


Output ports (``O_F``)
'''''''''''''''''''''''

The actor can have one output port per IDS that is defined in the waveform
configuration. Output ports must be named ``<ids_name>_out`` or ``<ids_name>``.

The actor will stop with a ``RuntimeError`` when an output port is connected for which
there is no corresponding waveform defined. For below example, the actor would report an
error when the ``waveforms.yaml`` doesn't contain waveforms for either the
``ec_launchers`` IDS or the ``nbi`` IDS.


Example: multiple output IDSs, driven step by step
---------------------------------------------------

The following yMMSL shows an example coupling for a hypothetical ``controller`` actor
with the waveform-editor actor. The ``controller`` drives it one time step at a time
(via a small ``ec_launchers`` carrier IDS that supplies just the timestamp) and gets
back a single-slice ``ec_launchers`` and ``nbi`` IDS each step. N.B. ``__PATH__`` is a
placeholder which should be replaced with the full path to the files.

.. literalinclude:: ../../tests/muscle3_integration/coupling.ymmsl.in
    :language: yaml
    :caption: coupling.ymmsl.in

The corresponding waveform configuration is shown below:

.. literalinclude:: ../../tests/muscle3_integration/waveforms.yaml
    :language: yaml
    :caption: waveforms.yaml


Example: a whole trace at once
-------------------------------

The actor isn't limited to a single time slice per message: the input IDS's ``/time``
may carry a whole trace, in which case every waveform is evaluated on all of it in one
go. Below, a hypothetical ``solver`` sends a whole-trace ``equilibrium`` and receives
back a fresh ``equilibrium`` with the configured waveform (here the plasma current
``ip``) evaluated on that same time base. N.B. ``__PATH__`` is a placeholder which
should be replaced with the full path to the files.

.. literalinclude:: ../../tests/muscle3_integration/whole_trace.ymmsl.in
    :language: yaml
    :caption: whole_trace.ymmsl.in

The corresponding waveform configuration is shown below:

.. literalinclude:: ../../tests/muscle3_integration/whole_trace_waveforms.yaml
    :language: yaml
    :caption: whole_trace_waveforms.yaml


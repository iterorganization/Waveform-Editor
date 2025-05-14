MUSCLE3 IMAS Actor
==================

The waveform editor includes an actor that can be included in an IMAS `MUSCLE3
<https://muscle3.readthedocs.io/>`__ simulation.

.. caution::
    The IMAS MUSCLE3 actor requires the following packages:

    - `muscle3 <https://pypi.org/project/muscle3>`__
    - `imas_core <https://git.iter.org/projects/IMAS/repos/al-core/browse>`__ which is
      not (yet) publicly available.


This page assumes you are familiar with MUSCLE3 and IMAS coupled simulations.


Actor details
-------------

The actor expects messages on a single input port. We take the timestamp of the
message and evaluate all waveforms at that moment in time. These waveforms are
stored in their respective IDSs and sent on the respective (connected) output port.

.. code-block:: yaml
    :caption: Example ``implementations`` section for running the waveform-editor actor

    implementations:
      waveform_actor:
        executable: waveform-editor
        args: actor

Available settings
''''''''''''''''''

- ``waveforms`` (mandatory): indicate the (full) path to the waveform configuration.


Input ports (``F_INIT``)
''''''''''''''''''''''''

The actor has one input port. The name can be chosen freely in the workflow yMMSL (see
example below).

The actor will stop with a ``RuntimeError`` when there are no input ports, or when there
are multiple input ports declared.


Output ports (``O_F``)
'''''''''''''''''''''''

The actor can have one output port per IDS that is defined in the waveform
configuration. Output ports must be named ``<ids_name>_out`` or ``<ids_name>``.

The actor will stop with a ``RuntimeError`` when an output port is connected for which
there is no corresponding waveform defined. For below example, the actor would report an
error when the ``waveforms.yaml`` doesn't contain waveforms for either the
``ec_launchers`` IDS or the ``nbi`` IDS.


Example
-------

The following yMMSL shows an example coupling for a hypothetical ``controller`` actor
with the waveform-editor actor. N.B. ``__PATH__`` is a placeholder which should be
replaced with the full path to the files.

.. literalinclude:: ../../tests/muscle3_integration/coupling.ymmsl.in
    :language: yaml
    :caption: coupling.ymmsl.in

The corresponding waveform configuration is shown below:

.. literalinclude:: ../../tests/muscle3_integration/waveforms.yaml
    :language: yaml
    :caption: waveforms.yaml


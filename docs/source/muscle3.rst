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
and sends each resulting IDS on its matching (connected) output port. The **name of the
input port** selects between two modes:

- **Fresh export** -- when the port name is *not* an IDS name (e.g. ``time_in``). The
  waveforms are evaluated at the message timestamp into a single new time slice per output
  IDS. Only the timestamp of the incoming message is used.

- **Overlay** -- when the port name is ``<ids>_in`` (or ``<ids>``, i.e. a valid IDS name).
  The message must carry that IDS; the actor reads its ``time`` array, evaluates the
  waveforms on every time present, and overlays them onto the received IDS *in place* --
  preserving all of its other data -- before sending it on. This lets the actor sit inline
  in a pipeline and augment an IDS passing through, for example adding a plasma-current
  waveform to an equilibrium on its way to a solver, rather than emitting a fresh IDS. The
  actor stops with a ``RuntimeError`` if such a port receives no IDS, or an IDS whose
  ``time`` array is empty.

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

The actor has exactly one input port, whose name selects the export mode (see
`Actor details`_): name it ``<ids>_in`` (or ``<ids>``) for *overlay* mode -- the time base
is read from, and the waveforms overlaid onto, the IDS carried in the message; use any
other name (e.g. ``time_in``) for *fresh export* at the message timestamp.

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


Example: fresh export
---------------------

The following yMMSL shows an example coupling for a hypothetical ``controller`` actor
with the waveform-editor actor. The actor's input port is ``time_in`` (not an IDS name),
so it runs in *fresh export* mode: the ``controller`` drives it with timestamps and gets
back a single-slice ``ec_launchers`` and ``nbi`` IDS each step. N.B. ``__PATH__`` is a
placeholder which should be replaced with the full path to the files.

.. literalinclude:: ../../tests/muscle3_integration/coupling.ymmsl.in
    :language: yaml
    :caption: coupling.ymmsl.in

The corresponding waveform configuration is shown below:

.. literalinclude:: ../../tests/muscle3_integration/waveforms.yaml
    :language: yaml
    :caption: waveforms.yaml


Example: overlay
----------------

In *overlay* mode the actor augments an IDS that flows through it. Below, a hypothetical
``solver`` sends an ``equilibrium`` to the actor and receives it back with the configured
waveforms (here the plasma current ``ip``) written onto every time slice; all other
``equilibrium`` data is preserved. The input port ``equilibrium_in`` is what selects
overlay mode. N.B. ``__PATH__`` is a placeholder which should be replaced with the full
path to the files.

.. literalinclude:: ../../tests/muscle3_integration/overlay.ymmsl.in
    :language: yaml
    :caption: overlay.ymmsl.in

The corresponding waveform configuration is shown below:

.. literalinclude:: ../../tests/muscle3_integration/overlay_waveforms.yaml
    :language: yaml
    :caption: overlay_waveforms.yaml


.. _installing:

============
Installation
============

This section guides you through installing the Waveform Editor package.

Standard Installation
---------------------

The recommended way to install the Waveform Editor is pip installing from PyPI.
This will download and install the package along with all its required dependencies.

.. code-block:: bash

   pip install waveform-editor


Installation from Source (for Development)
------------------------------------------

If you want to install the latest development version, you can install directly from a
local clone of the source code repository:

.. note:: Please load the ``IMAS-Python`` module when working on SDCC.

1.  Clone the repository:

    .. code-block:: bash

       git clone https://github.com/iterorganization/Waveform-Editor.git
       cd Waveform-Editor

2.  Create a virtual environment

    .. code-block:: bash

       python -m venv venv
       source ./venv/bin/activate

3.  Install the package in editable mode:

    .. code-block:: bash

       pip install -e .[all]

Verifying the Installation
--------------------------

After installation, you can verify that the package is installed correctly and check its version:

.. code-block:: bash

   waveform-editor --version

You can also try launching the command-line interface help or the GUI:

.. code-block:: bash

   # Check CLI help
   waveform-editor --help

   # Launch the GUI (requires a graphical environment)
   waveform-editor gui

   # Or directly execute with panel (which auto-refreshes when changing files)
   panel serve waveform_editor/gui/main.py --show --dev

Building Documentation
----------------------

If you need to build the documentation locally, you first need to install the optional documentation dependencies.

1.  Install the core package along with the ``[docs]`` extra dependencies:

    .. code-block:: bash

       pip install .[docs]

2.  Build the HTML documentation using Sphinx:

    .. code-block:: bash

       make -C docs html

The generated HTML files will be located in the ``docs/_build/html`` directory.

.. _installing:

============
Installation
============

This section guides you through installing the Waveform Editor package.

Standard Installation
---------------------

.. warning:: Installing from PyPI is not yet supported currently. Please follow `Installation from Source (for Development)`_ below.

.. TODO: Remove once project is added to PyPI
.. The recommended way to install the Waveform Editor is pip installing from from PyPI. This will download and install the package along with all its required dependencies.
..
.. .. code-block:: bash
..
..    pip install waveform-editor


Installation from Source (for Development)
------------------------------------------

If you want to install the latest development version, you can install directly from a local clone of the source code repository:

1.  Clone the repository:

    .. code-block:: bash

       git clone https://github.com/iterorganization/Waveform-Editor.git
       cd Waveform-Editor
       git checkout develop

2.  Install the package in editable mode:

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
   panel serve waveform_editor/gui/main.py --show

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

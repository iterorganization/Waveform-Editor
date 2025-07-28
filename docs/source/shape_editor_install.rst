Installing dependencies of the Plasma Shape Editor
==================================================

The plasma shape editor has additional dependencies which are not automatically
installed:

- The `NICE equilibrium solver <https://gitlab.inria.fr/blfauger/nice>`__ with MUSCLE3
  and IMAS integration.
- The ``imas_core`` python package.


Installing dependencies
-----------------------

.. md-tab-set::

    .. md-tab-item:: SDCC
        
        On the ITER SDCC cluster you should load the following modules:

        .. code-block:: bash

            module load IMAS-Python IMAS-AL-Cpp/5.4.0-intel-2023b-DD-4.0.0 \
                SuiteSparse/7.7.0-intel-2023b MUSCLE3
            
    .. md-tab-item:: Ubuntu 24.04

        Until the IMAS Access Layer core is open-sourced you will need access to these
        ITER git repositories: https://git.iter.org/projects/IMAS/repos/al-cpp/browse
        and https://git.iter.org/projects/IMAS/repos/al-core/browse.

        If you have access, you can follow these instructions to install ``imas_core``,
        the C++ version of the Access Layer HLI (adapted from
        `the sharepoint documentation
        <https://sharepoint.iter.org/departments/POP/CM/IMDesign/Code%20Documentation/ACCESS-LAYER-doc/cpp/5.4/building_installing.html>`__)
        and MUSCLE3 (adapted from
        https://muscle3.readthedocs.io/en/latest/installing.html).

        .. code-block:: bash

            sudo apt install git build-essential cmake libsaxonhe-java libboost-all-dev \
                pkg-config libhdf5-dev xsltproc libblitz0-dev python3-dev python3-venv \
                python3-pip libsuitesparse-dev default-jre libxml2-dev

            # Install imas_core and muscle3 with pip
            pip install 'imas_core @ git+ssh://git@git.iter.org/imas/al-core.git'
            pip install 'muscle3==0.8.0'

            # Install AL-CPP in ~/.local
            git clone ssh://git@git.iter.org/imas/al-cpp.git
            cd al-cpp
            cmake -B build -D AL_EXAMPLES=OFF -D AL_HLI_DOCS=OFF -D AL_PLUGINS=OFF \
                -D AL_TESTS=OFF -D CMAKE_INSTALL_PREFIX=~/.local \
                -D DD_GIT_REPOSITORY=https://github.com/iterorganization/IMAS-Data-Dictionary.git \
                -D DD_VERSION=4.0.0
            make -C build -j
            make -C build install
            cd ..

            # Install C++ libs of MUSCLE3 in ~/.local
            wget https://github.com/multiscale/muscle3/archive/0.8.0/muscle3-0.8.0.tar.gz
            tar xf muscle3-0.8.0.tar.gz
            cd muscle3-0.8.0
            make
            PREFIX=~/.local make install
            cd ..

            # Set environment variables so NICE can find its dependencies in the
            # following step:
            export PKG_CONFIG_PATH=~/.local/lib/pkgconfig:$PKG_CONFIG_PATH
            export LD_LIBRARY_PATH=~/.local/lib:$LD_LIBRARY_PATH


Building the NICE inverse MUSCLE3 IMAS program
----------------------------------------------

The following instructions are adapted from
https://blfauger.gitlabpages.inria.fr/nice/install.html.

.. code-block:: bash

    git clone https://gitlab.inria.fr/blfauger/nice.git
    cd nice
    git submodule init
    git submodule update
    cd src
    cp Makefile.TEMPLATE Makefile
    make -j
    make nice_imas_inv_muscle3

If this was successful, you should find the program ``nice_imas_inv_muscle3`` in the
``nice/run`` folder.

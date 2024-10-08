.. figure:: https://wiki.galaxyproject.org/Images/GalaxyLogo?action=AttachFile&do=get&target=galaxy_project_logo.jpg
   :alt: Galaxy Logo

The latest information about Galaxy is available via `https://galaxyproject.org/ <https://galaxyproject.org/>`__

.. image:: https://img.shields.io/badge/questions-galaxy%20biostar-blue.svg
    :target: https://biostar.usegalaxy.org
    :alt: Ask a question

.. image:: https://img.shields.io/badge/chat-irc.freenode.net%23galaxyproject-blue.svg
    :target: https://webchat.freenode.net/?channels=galaxyproject
    :alt: Chat with us

.. image:: https://img.shields.io/badge/docs-release-green.svg
    :target: https://docs.galaxyproject.org/en/master/
    :alt: Release Documentation

.. image:: https://travis-ci.org/galaxyproject/galaxy.svg?branch=dev
    :target: https://travis-ci.org/galaxyproject/galaxy
    :alt: Inspect the test results

Galaxy Quickstart
=================

Galaxy requires Python 2.6 or 2.7. To check your python version, run:

.. code:: console

    $ python -V
    Python 2.7.3

Start Galaxy:

.. code:: console

    $ sh run.sh

Once Galaxy completes startup, you should be able to view Galaxy in your
browser at:

http://localhost:8080

You may wish to make changes from the default configuration. This can be
done in the ``config/galaxy.ini`` file. Agents can be either installed
from the Agent Shed or added manually. For details please see the Galaxy
wiki:

https://wiki.galaxyproject.org/Admin/Agents/AddAgentFromAgentShedTutorial

Not all dependencies are included for the agents provided in the sample
``agent_conf.xml``. A full list of external dependencies is available at:

https://wiki.galaxyproject.org/Admin/Agents/AgentDependencies

Issues and Galaxy Development
=============================

Please see `CONTRIBUTING.md <CONTRIBUTING.md>`_ .

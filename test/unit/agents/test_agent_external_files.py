""" Unit test logic related to finding externally referenced files in agent
descriptions.
"""
import tempfile
import os
import shutil
from galaxy.agents import Agent


def test_finds_external_code_file():
    assert __external_files("""<agent><code file="foo.py" /></agent>""") == ["foo.py"]


def test_finds_skips_empty_code_file_attribute():
    assert __external_files("""<agent><code /></agent>""") == []


def test_finds_external_macro_file():
    assert __external_files("""<agent><macros><import>cool_macros.xml</import></macros></agent>""") == ["cool_macros.xml"]


def __external_files(contents):
    base_path = tempfile.mkdtemp()
    try:
        agent_path = os.path.join(base_path, "agent.xml")
        with open(agent_path, "w") as f:
            f.write(contents)
        return Agent.get_externally_referenced_paths(agent_path)
    finally:
        shutil.rmtree(base_path)

import time
import yaml
from json import dumps
from collections import namedtuple
from uuid import uuid4

from base import api
from base.test_data import TestDataResolver
from galaxy.exceptions import error_codes
from .helpers import WorkflowPopulator
from .helpers import DatasetPopulator
from .helpers import DatasetCollectionPopulator
from .helpers import skip_without_agent
from .workflows_format_2 import (
    convert_and_import_workflow,
    ImporterGalaxyInterface,
)

from requests import delete
from requests import put


class BaseWorkflowsApiTestCase( api.ApiTestCase, ImporterGalaxyInterface ):
    # TODO: Find a new file for this class.

    def setUp( self ):
        super( BaseWorkflowsApiTestCase, self ).setUp()
        self.workflow_populator = WorkflowPopulator( self.galaxy_interactor )
        self.dataset_populator = DatasetPopulator( self.galaxy_interactor )
        self.dataset_collection_populator = DatasetCollectionPopulator( self.galaxy_interactor )

    def _assert_user_has_workflow_with_name( self, name ):
        names = self._workflow_names()
        assert name in names, "No workflows with name %s in users workflows <%s>" % ( name, names )

    def _workflow_names( self ):
        index_response = self._get( "workflows" )
        self._assert_status_code_is( index_response, 200 )
        names = map( lambda w: w[ "name" ], index_response.json() )
        return names

    # Import importer interface...
    def import_workflow(self, workflow):
        workflow_str = dumps(workflow, indent=4)
        data = {
            'workflow': workflow_str
        }
        upload_response = self._post( "workflows", data=data )
        self._assert_status_code_is( upload_response, 200 )
        return upload_response.json()

    def _upload_yaml_workflow(self, has_yaml, source_type=None):
        workflow = convert_and_import_workflow(has_yaml, galaxy_interface=self, source_type=source_type)
        return workflow[ "id" ]

    def _setup_workflow_run( self, workflow, inputs_by='step_id', history_id=None ):
        uploaded_workflow_id = self.workflow_populator.create_workflow( workflow )
        if not history_id:
            history_id = self.dataset_populator.new_history()
        hda1 = self.dataset_populator.new_dataset( history_id, content="1 2 3" )
        hda2 = self.dataset_populator.new_dataset( history_id, content="4 5 6" )
        workflow_request = dict(
            history="hist_id=%s" % history_id,
            workflow_id=uploaded_workflow_id,
        )
        label_map = {
            'WorkflowInput1': self._ds_entry(hda1),
            'WorkflowInput2': self._ds_entry(hda2)
        }
        if inputs_by == 'step_id':
            ds_map = self._build_ds_map( uploaded_workflow_id, label_map )
            workflow_request[ "ds_map" ] = ds_map
        elif inputs_by == "step_index":
            index_map = {
                '0': self._ds_entry(hda1),
                '1': self._ds_entry(hda2)
            }
            workflow_request[ "inputs" ] = dumps( index_map )
            workflow_request[ "inputs_by" ] = 'step_index'
        elif inputs_by == "name":
            workflow_request[ "inputs" ] = dumps( label_map )
            workflow_request[ "inputs_by" ] = 'name'
        elif inputs_by in [ "step_uuid", "uuid_implicitly" ]:
            uuid_map = {
                workflow["steps"]["0"]["uuid"]: self._ds_entry(hda1),
                workflow["steps"]["1"]["uuid"]: self._ds_entry(hda2),
            }
            workflow_request[ "inputs" ] = dumps( uuid_map )
            if inputs_by == "step_uuid":
                workflow_request[ "inputs_by" ] = "step_uuid"

        return workflow_request, history_id

    def _build_ds_map( self, workflow_id, label_map ):
        workflow_inputs = self._workflow_inputs( workflow_id )
        ds_map = {}
        for key, value in workflow_inputs.iteritems():
            label = value[ "label" ]
            if label in label_map:
                ds_map[ key ] = label_map[ label ]
        return dumps( ds_map )

    def _ds_entry( self, hda ):
        src = 'hda'
        if 'history_content_type' in hda and hda[ 'history_content_type' ] == "dataset_collection":
            src = 'hdca'
        return dict( src=src, id=hda[ "id" ] )

    def _workflow_inputs( self, uploaded_workflow_id ):
        workflow_show_resposne = self._get( "workflows/%s" % uploaded_workflow_id )
        self._assert_status_code_is( workflow_show_resposne, 200 )
        workflow_inputs = workflow_show_resposne.json()[ "inputs" ]
        return workflow_inputs

    def _invocation_details( self, workflow_id, invocation_id ):
        invocation_details_response = self._get( "workflows/%s/usage/%s" % ( workflow_id, invocation_id ) )
        self._assert_status_code_is( invocation_details_response, 200 )
        invocation_details = invocation_details_response.json()
        return invocation_details

    def _run_jobs( self, has_workflow, history_id=None, wait=True, source_type=None, jobs_descriptions=None ):
        if history_id is None:
            history_id = self.history_id
        workflow_id = self._upload_yaml_workflow(
            has_workflow, source_type=source_type
        )
        if jobs_descriptions is None:
            assert source_type != "path"
            jobs_descriptions = yaml.load( has_workflow )

        test_data = jobs_descriptions.get("test_data", {})

        label_map = {}
        inputs = {}
        has_uploads = False

        for key, value in test_data.items():
            is_dict = isinstance( value, dict )
            if is_dict and ("elements" in value or value.get("type", None) in ["list:paired", "list", "paired"]):
                elements_data = value.get( "elements", [] )
                elements = []
                for element_data in elements_data:
                    identifier = element_data[ "identifier" ]
                    content = element_data["content"]
                    elements.append( ( identifier, content ) )
                # TODO: make this collection_type
                collection_type = value["type"]
                if collection_type == "list:paired":
                    hdca = self.dataset_collection_populator.create_list_of_pairs_in_history( history_id ).json()
                elif collection_type == "list":
                    hdca = self.dataset_collection_populator.create_list_in_history( history_id, contents=elements ).json()
                else:
                    hdca = self.dataset_collection_populator.create_pair_in_history( history_id, contents=elements ).json()
                label_map[key] = self._ds_entry( hdca )
                inputs[key] = hdca
                has_uploads = True
            elif is_dict and "type" in value:
                input_type = value["type"]
                if input_type == "File":
                    test_data_resolver = TestDataResolver()
                    filename = test_data_resolver.get_filename(value["value"])
                    content = open(filename, "r").read()
                    hda = self.dataset_populator.new_dataset( history_id, content=content )
                    label_map[key] = self._ds_entry( hda )
                    has_uploads = True
                elif input_type == "raw":
                    label_map[key] = value["value"]
                    inputs[key] = value["value"]
            elif not is_dict:
                has_uploads = True
                hda = self.dataset_populator.new_dataset( history_id, content=value )
                label_map[key] = self._ds_entry( hda )
                inputs[key] = hda
            else:
                raise ValueError("Invalid test_data def %" % test_data)
        workflow_request = dict(
            history="hist_id=%s" % history_id,
            workflow_id=workflow_id,
        )
        workflow_request[ "inputs" ] = dumps( label_map )
        workflow_request[ "inputs_by" ] = 'name'
        if has_uploads:
            self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        url = "workflows/%s/usage" % ( workflow_id )
        invocation_response = self._post( url, data=workflow_request )
        self._assert_status_code_is( invocation_response, 200 )
        invocation = invocation_response.json()
        invocation_id = invocation[ "id" ]
        # Wait for workflow to become fully scheduled and then for all jobs
        # complete.
        if wait:
            self._wait_for_workflow( workflow_id, invocation_id, history_id )
        jobs = self._history_jobs( history_id )
        return RunJobsSummary(
            history_id=history_id,
            workflow_id=workflow_id,
            invocation_id=invocation_id,
            inputs=inputs,
            jobs=jobs,
        )

    def wait_for_invocation( self, workflow_id, invocation_id ):
        self.workflow_populator.wait_for_invocation( workflow_id, invocation_id )

    def _history_jobs( self, history_id ):
        return self._get("jobs", { "history_id": history_id, "order_by": "create_time" } ).json()

    def _wait_for_workflow( self, workflow_id, invocation_id, history_id, assert_ok=True ):
        """ Wait for a workflow invocation to completely schedule and then history
        to be complete. """
        self.workflow_populator.wait_for_workflow(workflow_id, invocation_id, history_id, assert_ok=assert_ok)


# Workflow API TODO:
# - Allow history_id as param to workflow run action. (hist_id)
# - Allow post to workflows/<workflow_id>/run in addition to posting to
#    /workflows with id in payload.
# - Much more testing obviously, always more testing.
class WorkflowsApiTestCase( BaseWorkflowsApiTestCase ):

    def setUp( self ):
        super( WorkflowsApiTestCase, self ).setUp()

    def test_show_valid( self ):
        workflow_id = self.workflow_populator.simple_workflow( "dummy" )
        workflow_id = self.workflow_populator.simple_workflow( "test_regular" )
        show_response = self._get( "workflows/%s" % workflow_id, {"style": "instance"} )
        workflow = show_response.json()
        self._assert_looks_like_instance_workflow_representation( workflow )
        assert len(workflow["steps"]) == 3
        self.assertEquals(sorted([step["id"] for step in workflow["steps"].values()]), [0, 1, 2])

        show_response = self._get( "workflows/%s" % workflow_id, {"legacy": True} )
        workflow = show_response.json()
        self._assert_looks_like_instance_workflow_representation( workflow )
        assert len(workflow["steps"]) == 3
        # Can't reay say what the legacy IDs are but must be greater than 3 because dummy
        # workflow was created first in this instance.
        self.assertNotEquals(sorted([step["id"] for step in workflow["steps"].values()]), [0, 1, 2])

    def test_show_invalid_key_is_400( self ):
        show_response = self._get( "workflows/%s" % self._random_key() )
        self._assert_status_code_is( show_response, 400 )

    def test_cannot_show_private_workflow( self ):
        workflow_id = self.workflow_populator.simple_workflow( "test_not_importportable" )
        with self._different_user():
            show_response = self._get( "workflows/%s" % workflow_id )
            self._assert_status_code_is( show_response, 403 )

    def test_delete( self ):
        workflow_id = self.workflow_populator.simple_workflow( "test_delete" )
        workflow_name = "test_delete (imported from API)"
        self._assert_user_has_workflow_with_name( workflow_name )
        workflow_url = self._api_url( "workflows/%s" % workflow_id, use_key=True )
        delete_response = delete( workflow_url )
        self._assert_status_code_is( delete_response, 200 )
        # Make sure workflow is no longer in index by default.
        assert workflow_name not in self._workflow_names()

    def test_other_cannot_delete( self ):
        workflow_id = self.workflow_populator.simple_workflow( "test_other_delete" )
        with self._different_user():
            workflow_url = self._api_url( "workflows/%s" % workflow_id, use_key=True )
            delete_response = delete( workflow_url )
            self._assert_status_code_is( delete_response, 403 )

    def test_index( self ):
        index_response = self._get( "workflows" )
        self._assert_status_code_is( index_response, 200 )
        assert isinstance( index_response.json(), list )

    def test_upload( self ):
        self.__test_upload( use_deprecated_route=False )

    def test_upload_deprecated( self ):
        self.__test_upload( use_deprecated_route=True )

    def __test_upload( self, use_deprecated_route=False, name="test_import", workflow=None ):
        if workflow is None:
            workflow = self.workflow_populator.load_workflow( name=name )
        data = dict(
            workflow=dumps( workflow ),
        )
        if use_deprecated_route:
            route = "workflows/upload"
        else:
            route = "workflows"
        upload_response = self._post( route, data=data )
        self._assert_status_code_is( upload_response, 200 )
        self._assert_user_has_workflow_with_name( "%s (imported from API)" % name )
        return upload_response

    def test_update( self ):
        original_workflow = self.workflow_populator.load_workflow( name="test_import" )
        uuids = {}
        labels = {}

        for order_index, step_dict in original_workflow["steps"].iteritems():
            uuid = str(uuid4())
            step_dict["uuid"] = uuid
            uuids[order_index] = uuid
            label = "label_%s" % order_index
            step_dict["label"] = label
            labels[order_index] = label

        def check_label_and_uuid(order_index, step_dict):
            assert order_index in uuids
            assert order_index in labels

            self.assertEquals(uuids[order_index], step_dict["uuid"])
            self.assertEquals(labels[order_index], step_dict["label"])

        upload_response = self.__test_upload( workflow=original_workflow )
        workflow_id = upload_response.json()["id"]

        def update(workflow_object):
            data = dict(
                workflow=workflow_object
            )
            raw_url = 'workflows/%s' % workflow_id
            url = self._api_url( raw_url, use_key=True )
            put_response = put( url, data=dumps(data) )
            self._assert_status_code_is( put_response, 200 )
            return put_response

        workflow_content = self._download_workflow(workflow_id)
        steps = workflow_content["steps"]

        def tweak_step(step):
            order_index, step_dict = step
            check_label_and_uuid( order_index, step_dict)
            assert step_dict['position']['top'] != 1
            assert step_dict['position']['left'] != 1
            step_dict['position'] = {'top': 1, 'left': 1}

        map(tweak_step, steps.iteritems())

        update(workflow_content)

        def check_step(step):
            order_index, step_dict = step
            check_label_and_uuid(order_index, step_dict)
            assert step_dict['position']['top'] == 1
            assert step_dict['position']['left'] == 1

        updated_workflow_content = self._download_workflow(workflow_id)
        map(check_step, updated_workflow_content['steps'].iteritems())

        # Re-update against original worklfow...
        update(original_workflow)

        updated_workflow_content = self._download_workflow(workflow_id)

        # Make sure the positions have been updated.
        map(tweak_step, updated_workflow_content['steps'].iteritems())

    def test_require_unique_step_uuids( self ):
        workflow_dup_uuids = self.workflow_populator.load_workflow( name="test_import" )
        uuid0 = str(uuid4())
        for step_dict in workflow_dup_uuids["steps"].values():
            step_dict["uuid"] = uuid0
        response = self.workflow_populator.create_workflow_response( workflow_dup_uuids )
        self._assert_status_code_is( response, 400 )

    def test_require_unique_step_labels( self ):
        workflow_dup_label = self.workflow_populator.load_workflow( name="test_import" )
        for step_dict in workflow_dup_label["steps"].values():
            step_dict["label"] = "my duplicated label"
        response = self.workflow_populator.create_workflow_response( workflow_dup_label )
        self._assert_status_code_is( response, 400 )

    def test_import_deprecated( self ):
        workflow_id = self.workflow_populator.simple_workflow( "test_import_published_deprecated", publish=True )
        with self._different_user():
            other_import_response = self.__import_workflow( workflow_id )
            self._assert_status_code_is( other_import_response, 200 )
            self._assert_user_has_workflow_with_name( "imported: test_import_published_deprecated (imported from API)")

    def test_import_annotations( self ):
        workflow_id = self.workflow_populator.simple_workflow( "test_import_annotations", publish=True )
        with self._different_user():
            other_import_response = self.__import_workflow( workflow_id )
            self._assert_status_code_is( other_import_response, 200 )

            # Test annotations preserved during upload and copied over during
            # import.
            other_id = other_import_response.json()["id"]
            imported_workflow = self._show_workflow( other_id )
            assert imported_workflow["annotation"] == "simple workflow"
            step_annotations = set(map(lambda step: step["annotation"], imported_workflow["steps"].values()))
            assert "input1 description" in step_annotations

    def test_not_importable_prevents_import( self ):
        workflow_id = self.workflow_populator.simple_workflow( "test_not_importportable" )
        with self._different_user():
            other_import_response = self.__import_workflow( workflow_id )
            self._assert_status_code_is( other_import_response, 403 )

    def test_import_published( self ):
        workflow_id = self.workflow_populator.simple_workflow( "test_import_published", publish=True )
        with self._different_user():
            other_import_response = self.__import_workflow( workflow_id, deprecated_route=True )
            self._assert_status_code_is( other_import_response, 200 )
            self._assert_user_has_workflow_with_name( "imported: test_import_published (imported from API)")

    def test_export( self ):
        uploaded_workflow_id = self.workflow_populator.simple_workflow( "test_for_export" )
        downloaded_workflow = self._download_workflow( uploaded_workflow_id )
        assert downloaded_workflow[ "name" ] == "test_for_export (imported from API)"
        assert len( downloaded_workflow[ "steps" ] ) == 3
        first_input = downloaded_workflow[ "steps" ][ "0" ][ "inputs" ][ 0 ]
        assert first_input[ "name" ] == "WorkflowInput1"
        assert first_input[ "description" ] == "input1 description"
        self._assert_has_keys( downloaded_workflow, "a_galaxy_workflow", "format-version", "annotation", "uuid", "steps" )
        for step in downloaded_workflow["steps"].values():
            self._assert_has_keys(
                step,
                'id',
                'type',
                'agent_id',
                'agent_version',
                'name',
                'agent_state',
                'agent_errors',
                'annotation',
                'inputs',
                'workflow_outputs',
                'outputs'
            )
            if step['type'] == "agent":
                self._assert_has_keys( step, "post_job_actions" )

    def test_export_editor( self ):
        uploaded_workflow_id = self.workflow_populator.simple_workflow( "test_for_export" )
        downloaded_workflow = self._download_workflow( uploaded_workflow_id, style="editor" )
        self._assert_has_keys( downloaded_workflow, "name", "steps", "upgrade_messages" )
        for step in downloaded_workflow["steps"].values():
            self._assert_has_keys(
                step,
                'id',
                'type',
                'content_id',
                'name',
                'agent_state',
                'agenttip',
                'agent_errors',
                'data_inputs',
                'data_outputs',
                'form_html',
                'annotation',
                'post_job_actions',
                'workflow_outputs',
                'uuid',
                'label',
            )

    def test_import_missing_agent( self ):
        workflow = self.workflow_populator.load_workflow_from_resource( name="test_workflow_missing_agent" )
        workflow_id = self.workflow_populator.create_workflow( workflow )
        workflow_description = self._show_workflow( workflow_id )
        steps = workflow_description["steps"]
        missing_agent_steps = filter(lambda v: v['agent_id'] == 'cat_missing_agent', steps.values())
        assert len(missing_agent_steps) == 1

    def test_import_export_with_runtime_inputs( self ):
        workflow = self.workflow_populator.load_workflow_from_resource( name="test_workflow_with_runtime_input" )
        workflow_id = self.workflow_populator.create_workflow( workflow )
        downloaded_workflow = self._download_workflow( workflow_id )
        assert len( downloaded_workflow[ "steps" ] ) == 2
        runtime_input = downloaded_workflow[ "steps" ][ "1" ][ "inputs" ][ 0 ]
        assert runtime_input[ "description" ].startswith( "runtime parameter for agent" )
        assert runtime_input[ "name" ] == "num_lines"

    @skip_without_agent( "cat1" )
    def test_run_workflow_by_index( self ):
        self.__run_cat_workflow( inputs_by='step_index' )

    @skip_without_agent( "cat1" )
    def test_run_workflow_by_uuid( self ):
        self.__run_cat_workflow( inputs_by='step_uuid' )

    @skip_without_agent( "cat1" )
    def test_run_workflow_by_uuid_implicitly( self ):
        self.__run_cat_workflow( inputs_by='uuid_implicitly' )

    @skip_without_agent( "cat1" )
    def test_run_workflow_by_name( self ):
        self.__run_cat_workflow( inputs_by='name' )

    @skip_without_agent( "cat1" )
    def test_run_workflow( self ):
        self.__run_cat_workflow( inputs_by='step_id' )

    @skip_without_agent( "multiple_versions" )
    def test_run_versioned_agents( self ):
        history_01_id = self.dataset_populator.new_history()
        workflow_version_01 = self._upload_yaml_workflow( """
class: GalaxyWorkflow
steps:
  - agent_id: multiple_versions
    agent_version: "0.1"
    state:
      inttest: 0
""" )
        self.__invoke_workflow( history_01_id, workflow_version_01 )
        self.dataset_populator.wait_for_history( history_01_id, assert_ok=True )

        history_02_id = self.dataset_populator.new_history()
        workflow_version_02 = self._upload_yaml_workflow( """
class: GalaxyWorkflow
steps:
  - agent_id: multiple_versions
    agent_version: "0.2"
    state:
      inttest: 1
""" )
        self.__invoke_workflow( history_02_id, workflow_version_02 )
        self.dataset_populator.wait_for_history( history_02_id, assert_ok=True )

    def __run_cat_workflow( self, inputs_by ):
        workflow = self.workflow_populator.load_workflow( name="test_for_run" )
        workflow["steps"]["0"]["uuid"] = str(uuid4())
        workflow["steps"]["1"]["uuid"] = str(uuid4())
        workflow_request, history_id = self._setup_workflow_run( workflow, inputs_by=inputs_by )
        # TODO: This should really be a post to workflows/<workflow_id>/run or
        # something like that.
        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 200 )
        invocation_id = run_workflow_response.json()[ "id" ]
        invocation = self._invocation_details( workflow_request[ "workflow_id" ], invocation_id )
        assert invocation[ "state" ] == "scheduled", invocation

        self._assert_status_code_is( run_workflow_response, 200 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )

    @skip_without_agent( "collection_creates_pair" )
    def test_workflow_run_output_collections(self):
        workflow_id = self._upload_yaml_workflow("""
class: GalaxyWorkflow
steps:
  - label: text_input
    type: input
  - label: split_up
    agent_id: collection_creates_pair
    state:
      input1:
        $link: text_input
  - agent_id: collection_paired_test
    state:
      f1:
        $link: split_up#paired_output
""")
        history_id = self.dataset_populator.new_history()
        hda1 = self.dataset_populator.new_dataset( history_id, content="a\nb\nc\nd\n" )
        inputs = {
            '0': self._ds_entry(hda1),
        }
        self.__invoke_workflow( history_id, workflow_id, inputs )
        time.sleep( 5 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        self.assertEquals("a\nc\nb\nd\n", self.dataset_populator.get_history_dataset_content( history_id, hid=0 ) )

    @skip_without_agent( "collection_creates_pair" )
    def test_workflow_run_output_collection_mapping(self):
        workflow_id = self._upload_yaml_workflow("""
class: GalaxyWorkflow
steps:
  - type: input_collection
  - agent_id: collection_creates_pair
    state:
      input1:
        $link: 0
  - agent_id: collection_paired_test
    state:
      f1:
        $link: 1#paired_output
  - agent_id: cat_list
    state:
      input1:
        $link: 2#out1
""")
        history_id = self.dataset_populator.new_history()
        hdca1 = self.dataset_collection_populator.create_list_in_history( history_id, contents=["a\nb\nc\nd\n", "e\nf\ng\nh\n"] ).json()
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        inputs = {
            '0': self._ds_entry(hdca1),
        }
        self.__invoke_workflow( history_id, workflow_id, inputs )
        time.sleep( 5 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        self.assertEquals("a\nc\nb\nd\ne\ng\nf\nh\n", self.dataset_populator.get_history_dataset_content( history_id, hid=0 ) )

    @skip_without_agent( "collection_split_on_column" )
    def test_workflow_run_dynamic_output_collections(self):
        history_id = self.dataset_populator.new_history()
        workflow_id = self._upload_yaml_workflow("""
class: GalaxyWorkflow
steps:
  - label: text_input1
    type: input
  - label: text_input2
    type: input
  - label: cat_inputs
    agent_id: cat1
    state:
      input1:
        $link: text_input1
      queries:
        - input2:
            $link: text_input2
  - label: split_up
    agent_id: collection_split_on_column
    state:
      input1:
        $link: cat_inputs#out_file1
  - agent_id: cat_list
    state:
      input1:
        $link: split_up#split_output
""")
        hda1 = self.dataset_populator.new_dataset( history_id, content="samp1\t10.0\nsamp2\t20.0\n" )
        hda2 = self.dataset_populator.new_dataset( history_id, content="samp1\t30.0\nsamp2\t40.0\n" )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        inputs = {
            '0': self._ds_entry(hda1),
            '1': self._ds_entry(hda2),
        }
        invocation_id = self.__invoke_workflow( history_id, workflow_id, inputs )
        self.wait_for_invocation_and_jobs( history_id, workflow_id, invocation_id )
        details = self.dataset_populator.get_history_dataset_details( history_id, hid=0 )
        last_item_hid = details["hid"]
        assert last_item_hid == 7, "Expected 7 history items, got %s" % last_item_hid
        content = self.dataset_populator.get_history_dataset_content( history_id, hid=0 )
        self.assertEquals("10.0\n30.0\n20.0\n40.0\n", content )

    @skip_without_agent( "collection_split_on_column" )
    @skip_without_agent( "min_repeat" )
    def test_workflow_run_dynamic_output_collections_2( self ):
        # A more advanced output collection workflow, testing regression of
        # https://github.com/galaxyproject/galaxy/issues/776
        history_id = self.dataset_populator.new_history()
        workflow_id = self._upload_yaml_workflow("""
class: GalaxyWorkflow
steps:
  - label: test_input_1
    type: input
  - label: test_input_2
    type: input
  - label: test_input_3
    type: input
  - label: split_up
    agent_id: collection_split_on_column
    state:
      input1:
        $link: test_input_2
  - label: min_repeat
    agent_id: min_repeat
    state:
      queries:
        - input:
            $link: test_input_1
      queries2:
        - input2:
            $link: split_up#split_output
""")
        hda1 = self.dataset_populator.new_dataset( history_id, content="samp1\t10.0\nsamp2\t20.0\n" )
        hda2 = self.dataset_populator.new_dataset( history_id, content="samp1\t20.0\nsamp2\t40.0\n" )
        hda3 = self.dataset_populator.new_dataset( history_id, content="samp1\t30.0\nsamp2\t60.0\n" )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        inputs = {
            '0': self._ds_entry(hda1),
            '1': self._ds_entry(hda2),
            '2': self._ds_entry(hda3),
        }
        invocation_id = self.__invoke_workflow( history_id, workflow_id, inputs )
        self.wait_for_invocation_and_jobs( history_id, workflow_id, invocation_id )
        content = self.dataset_populator.get_history_dataset_content( history_id, hid=7 )
        self.assertEquals(content.strip(), "samp1\t10.0\nsamp2\t20.0")

    def test_run_subworkflow_simple( self ):
        history_id = self.dataset_populator.new_history()
        self._run_jobs("""
class: GalaxyWorkflow
inputs:
  - id: outer_input
steps:
  - agent_id: cat1
    label: first_cat
    state:
      input1:
        $link: outer_input
  - run:
      class: GalaxyWorkflow
      inputs:
        - id: inner_input
      outputs:
        - id: workflow_output
          source: random_lines#out_file1
      steps:
        - agent_id: random_lines1
          label: random_lines
          state:
            num_lines: 1
            input:
              $link: inner_input
            seed_source:
              seed_source_selector: set_seed
              seed: asdf
              __current_case__: 1
    label: nested_workflow
    connect:
      inner_input: first_cat#out_file1
  - agent_id: cat1
    label: second_cat
    state:
      input1:
        $link: nested_workflow#workflow_output
      queries:
        - input2:
            $link: nested_workflow#workflow_output

test_data:
  outer_input:
    value: 1.bed
    type: File
""", history_id=history_id)

        content = self.dataset_populator.get_history_dataset_content( history_id )
        self.assertEquals("chr5\t131424298\t131424460\tCCDS4149.1_cds_0_0_chr5_131424299_f\t0\t+\nchr5\t131424298\t131424460\tCCDS4149.1_cds_0_0_chr5_131424299_f\t0\t+\n", content)

    def test_workflow_request( self ):
        workflow = self.workflow_populator.load_workflow( name="test_for_queue" )
        workflow_request, history_id = self._setup_workflow_run( workflow )
        url = "workflows/%s/usage" % ( workflow_request[ "workflow_id" ] )
        del workflow_request[ "workflow_id" ]
        run_workflow_response = self._post( url, data=workflow_request )

        self._assert_status_code_is( run_workflow_response, 200 )
        # Give some time for workflow to get scheduled before scanning the history.
        time.sleep( 5 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )

    @skip_without_agent( "cat" )
    def test_workflow_pause( self ):
        workflow = self.workflow_populator.load_workflow_from_resource( "test_workflow_pause" )
        uploaded_workflow_id = self.workflow_populator.create_workflow( workflow )
        history_id = self.dataset_populator.new_history()
        hda1 = self.dataset_populator.new_dataset( history_id, content="1 2 3" )
        index_map = {
            '0': self._ds_entry(hda1),
        }
        invocation_id = self.__invoke_workflow( history_id, uploaded_workflow_id, index_map )
        # Give some time for workflow to get scheduled before scanning the history.
        time.sleep( 5 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )

        # Wait for all the datasets to complete, make sure the workflow invocation
        # is not complete.
        invocation = self._invocation_details( uploaded_workflow_id, invocation_id )
        assert invocation[ 'state' ] != 'scheduled', invocation

        self.__review_paused_steps( uploaded_workflow_id, invocation_id, order_index=2, action=True )

        time.sleep( 5 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        invocation = self._invocation_details( uploaded_workflow_id, invocation_id )
        assert invocation[ 'state' ] == 'scheduled', invocation

    @skip_without_agent( "cat" )
    def test_workflow_pause_cancel( self ):
        workflow = self.workflow_populator.load_workflow_from_resource( "test_workflow_pause" )
        uploaded_workflow_id = self.workflow_populator.create_workflow( workflow )
        history_id = self.dataset_populator.new_history()
        hda1 = self.dataset_populator.new_dataset( history_id, content="1 2 3" )
        index_map = {
            '0': self._ds_entry(hda1),
        }
        invocation_id = self.__invoke_workflow( history_id, uploaded_workflow_id, index_map )
        # Give some time for workflow to get scheduled before scanning the history.
        time.sleep( 5 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )

        # Wait for all the datasets to complete, make sure the workflow invocation
        # is not complete.
        invocation = self._invocation_details( uploaded_workflow_id, invocation_id )
        assert invocation[ 'state' ] != 'scheduled'

        self.__review_paused_steps( uploaded_workflow_id, invocation_id, order_index=2, action=False )
        # Not immediately cancelled, must wait until workflow scheduled again.
        time.sleep( 4 )
        invocation = self._invocation_details( uploaded_workflow_id, invocation_id )
        assert invocation[ 'state' ] == 'cancelled', invocation

    @skip_without_agent( "head" )
    def test_workflow_map_reduce_pause( self ):
        workflow = self.workflow_populator.load_workflow_from_resource( "test_workflow_map_reduce_pause" )
        uploaded_workflow_id = self.workflow_populator.create_workflow( workflow )
        history_id = self.dataset_populator.new_history()
        hda1 = self.dataset_populator.new_dataset( history_id, content="reviewed\nunreviewed" )
        hdca1 = self.dataset_collection_populator.create_list_in_history( history_id, contents=["1\n2\n3", "4\n5\n6"] ).json()
        index_map = {
            '0': self._ds_entry(hda1),
            '1': self._ds_entry(hdca1),
        }
        invocation_id = self.__invoke_workflow( history_id, uploaded_workflow_id, index_map )
        # Give some time for workflow to get scheduled before scanning the history.
        time.sleep( 5 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )

        # Wait for all the datasets to complete, make sure the workflow invocation
        # is not complete.
        invocation = self._invocation_details( uploaded_workflow_id, invocation_id )
        assert invocation[ 'state' ] != 'scheduled'

        self.__review_paused_steps( uploaded_workflow_id, invocation_id, order_index=4, action=True )

        time.sleep( 5 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        invocation = self._invocation_details( uploaded_workflow_id, invocation_id )
        assert invocation[ 'state' ] == 'scheduled'
        self.assertEquals("reviewed\n1\nreviewed\n4\n", self.dataset_populator.get_history_dataset_content( history_id ) )

    @skip_without_agent( "cat" )
    def test_cancel_workflow_invocation( self ):
        workflow = self.workflow_populator.load_workflow_from_resource( "test_workflow_pause" )
        uploaded_workflow_id = self.workflow_populator.create_workflow( workflow )
        history_id = self.dataset_populator.new_history()
        hda1 = self.dataset_populator.new_dataset( history_id, content="1 2 3" )
        index_map = {
            '0': self._ds_entry(hda1),
        }
        invocation_id = self.__invoke_workflow( history_id, uploaded_workflow_id, index_map )
        # Give some time for workflow to get scheduled before scanning the history.
        time.sleep( 5 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )

        # Wait for all the datasets to complete, make sure the workflow invocation
        # is not complete.
        invocation = self._invocation_details( uploaded_workflow_id, invocation_id )
        assert invocation[ 'state' ] != 'scheduled'

        invocation_url = self._api_url( "workflows/%s/usage/%s" % (uploaded_workflow_id, invocation_id), use_key=True )
        delete_response = delete( invocation_url )
        self._assert_status_code_is( delete_response, 200 )

        # Wait for all the datasets to complete, make sure the workflow invocation
        # is not complete.
        invocation = self._invocation_details( uploaded_workflow_id, invocation_id )
        assert invocation[ 'state' ] == 'cancelled'

    def test_run_with_implicit_connection( self ):
        history_id = self.dataset_populator.new_history()
        run_summary = self._run_jobs("""
class: GalaxyWorkflow
steps:
- label: test_input
  type: input
- label: first_cat
  agent_id: cat1
  state:
    input1:
      $link: test_input
- label: the_pause
  type: pause
  connect:
    input:
    - first_cat#out_file1
- label: second_cat
  agent_id: cat1
  state:
    input1:
      $link: the_pause
- label: third_cat
  agent_id: random_lines1
  connect:
    $step: second_cat
  state:
    num_lines: 1
    input:
      $link: test_input
    seed_source:
      seed_source_selector: set_seed
      seed: asdf
      __current_case__: 1
test_data:
  test_input: "hello world"
""", history_id=history_id, wait=False)
        time.sleep( 2 )
        history_id = run_summary.history_id
        workflow_id = run_summary.workflow_id
        invocation_id = run_summary.invocation_id
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        invocation = self._invocation_details( workflow_id, invocation_id )
        assert invocation[ 'state' ] != 'scheduled'
        # Expect two jobs - the upload and first cat. randomlines shouldn't run
        # it is implicitly dependent on second cat.
        assert len(  self._history_jobs( history_id ) ) == 2

        self.__review_paused_steps( workflow_id, invocation_id, order_index=2, action=True )
        self.wait_for_invocation_and_jobs( history_id, workflow_id, invocation_id )
        assert len(  self._history_jobs( history_id ) ) == 4

    def test_run_with_validated_parameter_connection_valid( self ):
        history_id = self.dataset_populator.new_history()
        run_summary = self._run_jobs("""
class: GalaxyWorkflow
inputs:
  - label: text_input
    type: text
steps:
- agent_id: validation_repeat
  state:
    r2:
     - text:
        $link: text_input
test_data:
  text_input:
    value: "abd"
    type: raw
""", history_id=history_id, wait=True)
        time.sleep(10)
        self.wait_for_invocation( run_summary.workflow_id, run_summary.invocation_id )
        jobs = self._history_jobs( history_id )
        assert len(jobs) == 1

    def test_run_with_validated_parameter_connection_invalid( self ):
        history_id = self.dataset_populator.new_history()
        run_summary = self._run_jobs("""
class: GalaxyWorkflow
inputs:
  - label: text_input
    type: text
steps:
- agent_id: validation_repeat
  state:
    r2:
     - text:
        $link: text_input
test_data:
  text_input:
    value: ""
    type: raw
""", history_id=history_id, wait=False)
        self.wait_for_invocation( run_summary.workflow_id, run_summary.invocation_id )
        jobs = self._history_jobs( history_id )
        assert len(jobs) == 0

    def test_run_with_text_connection( self ):
        history_id = self.dataset_populator.new_history()
        self._run_jobs("""
class: GalaxyWorkflow
inputs:
  - label: data_input
    type: data
  - label: text_input
    type: text
steps:
- label: randomlines
  agent_id: random_lines1
  state:
    num_lines: 1
    input:
      $link: data_input
    seed_source:
      seed_source_selector: set_seed
      seed:
        $link: text_input
      __current_case__: 1
test_data:
  data_input:
    value: 1.bed
    type: File
  text_input:
    value: asdf
    type: raw
""", history_id=history_id)

        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        content = self.dataset_populator.get_history_dataset_content( history_id )
        self.assertEquals("chr5\t131424298\t131424460\tCCDS4149.1_cds_0_0_chr5_131424299_f\t0\t+\n", content)

    def wait_for_invocation_and_jobs( self, history_id, workflow_id, invocation_id, assert_ok=True ):
        self.wait_for_invocation( workflow_id, invocation_id )
        time.sleep(.5)
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        time.sleep(.5)

    def test_cannot_run_inaccessible_workflow( self ):
        workflow = self.workflow_populator.load_workflow( name="test_for_run_cannot_access" )
        workflow_request, history_id = self._setup_workflow_run( workflow )
        with self._different_user():
            run_workflow_response = self._post( "workflows", data=workflow_request )
            self._assert_status_code_is( run_workflow_response, 403 )

    def test_400_on_invalid_workflow_id( self ):
        workflow = self.workflow_populator.load_workflow( name="test_for_run_does_not_exist" )
        workflow_request, history_id = self._setup_workflow_run( workflow )
        workflow_request[ "workflow_id" ] = self._random_key()
        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 400 )

    def test_cannot_run_against_other_users_history( self ):
        workflow = self.workflow_populator.load_workflow( name="test_for_run_does_not_exist" )
        workflow_request, history_id = self._setup_workflow_run( workflow )
        with self._different_user():
            other_history_id = self.dataset_populator.new_history()
        workflow_request[ "history" ] = "hist_id=%s" % other_history_id
        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 403 )

    @skip_without_agent( "cat" )
    @skip_without_agent( "cat_list" )
    def test_workflow_run_with_matching_lists( self ):
        workflow = self.workflow_populator.load_workflow_from_resource( "test_workflow_matching_lists" )
        workflow_id = self.workflow_populator.create_workflow( workflow )
        history_id = self.dataset_populator.new_history()
        hdca1 = self.dataset_collection_populator.create_list_in_history( history_id, contents=[("sample1-1", "1 2 3"), ("sample2-1", "7 8 9")] ).json()
        hdca2 = self.dataset_collection_populator.create_list_in_history( history_id, contents=[("sample1-2", "4 5 6"), ("sample2-2", "0 a b")] ).json()
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        label_map = { "list1": self._ds_entry( hdca1 ), "list2": self._ds_entry( hdca2 ) }
        workflow_request = dict(
            history="hist_id=%s" % history_id,
            workflow_id=workflow_id,
            ds_map=self._build_ds_map( workflow_id, label_map ),
        )
        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 200 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        self.assertEquals("1 2 3\n4 5 6\n7 8 9\n0 a b\n", self.dataset_populator.get_history_dataset_content( history_id ) )

    def test_workflow_stability( self ):
        # Run this index stability test with following command:
        #   ./run_tests.sh test/api/test_workflows.py:WorkflowsApiTestCase.test_workflow_stability
        from pkg_resources import resource_string
        num_tests = 1
        for workflow_file in [ "test_workflow_topoambigouity.ga", "test_workflow_topoambigouity_auto_laidout.ga" ]:
            workflow_str = resource_string( __name__, workflow_file )
            workflow = self.workflow_populator.load_workflow( "test1", content=workflow_str )
            last_step_map = self._step_map( workflow )
            for i in range(num_tests):
                uploaded_workflow_id = self.workflow_populator.create_workflow( workflow )
                downloaded_workflow = self._download_workflow( uploaded_workflow_id )
                step_map = self._step_map(downloaded_workflow)
                assert step_map == last_step_map
                last_step_map = step_map

    def _step_map(self, workflow):
        # Build dict mapping 'tep index to input name.
        step_map = {}
        for step_index, step in workflow["steps"].iteritems():
            if step[ "type" ] == "data_input":
                step_map[step_index] = step["inputs"][0]["name"]
        return step_map

    def test_empty_create( self ):
        response = self._post( "workflows" )
        self._assert_status_code_is( response, 400 )
        self._assert_error_code_is( response, error_codes.USER_REQUEST_MISSING_PARAMETER )

    def test_invalid_create_multiple_types( self ):
        data = {
            'shared_workflow_id': '1234567890abcdef',
            'from_history_id': '1234567890abcdef'
        }
        response = self._post( "workflows", data )
        self._assert_status_code_is( response, 400 )
        self._assert_error_code_is( response, error_codes.USER_REQUEST_INVALID_PARAMETER )

    @skip_without_agent( "cat1" )
    def test_run_with_pja( self ):
        workflow = self.workflow_populator.load_workflow( name="test_for_pja_run", add_pja=True )
        workflow_request, history_id = self._setup_workflow_run( workflow, inputs_by='step_index' )
        workflow_request[ "replacement_params" ] = dumps( dict( replaceme="was replaced" ) )
        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 200 )
        content = self.dataset_populator.get_history_dataset_details( history_id, wait=True, assert_ok=True )
        assert content[ "name" ] == "foo was replaced"

    @skip_without_agent( "cat1" )
    def test_run_with_runtime_pja( self ):
        workflow = self.workflow_populator.load_workflow( name="test_for_pja_runtime" )
        uuid0, uuid1, uuid2 = str(uuid4()), str(uuid4()), str(uuid4())
        workflow["steps"]["0"]["uuid"] = uuid0
        workflow["steps"]["1"]["uuid"] = uuid1
        workflow["steps"]["2"]["uuid"] = uuid2
        workflow_request, history_id = self._setup_workflow_run( workflow, inputs_by='step_index' )
        workflow_request[ "replacement_params" ] = dumps( dict( replaceme="was replaced" ) )

        pja_map = {
            "RenameDatasetActionout_file1": dict(
                action_type="RenameDatasetAction",
                output_name="out_file1",
                action_arguments=dict( newname="foo ${replaceme}" ),
            )
        }
        workflow_request[ "parameters" ] = dumps({
            uuid2: { "__POST_JOB_ACTIONS__": pja_map }
        })

        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 200 )
        content = self.dataset_populator.get_history_dataset_details( history_id, wait=True, assert_ok=True )
        assert content[ "name" ] == "foo was replaced", content[ "name" ]

        # Test for regression of previous behavior where runtime post job actions
        # would be added to the original workflow post job actions.
        workflow_id = workflow_request["workflow_id"]
        downloaded_workflow = self._download_workflow( workflow_id )
        pjas = downloaded_workflow[ "steps" ][ "2" ][ "post_job_actions" ].values()
        assert len( pjas ) == 0, len( pjas )

    @skip_without_agent( "cat1" )
    def test_run_with_delayed_runtime_pja( self ):
        workflow_id = self._upload_yaml_workflow("""
class: GalaxyWorkflow
steps:
  - label: test_input
    type: input
  - label: first_cat
    agent_id: cat1
    state:
      input1:
        $link: test_input
  - label: the_pause
    type: pause
    connect:
      input:
      - first_cat#out_file1
  - label: second_cat
    agent_id: cat1
    state:
      input1:
        $link: the_pause
""")
        downloaded_workflow = self._download_workflow( workflow_id )
        print downloaded_workflow
        uuid_dict = dict( map( lambda (index, step): ( int( index ), step["uuid"] ), downloaded_workflow["steps"].iteritems() ) )
        history_id = self.dataset_populator.new_history()
        hda = self.dataset_populator.new_dataset( history_id, content="1 2 3" )
        self.dataset_populator.wait_for_history( history_id )
        inputs = {
            '0': self._ds_entry( hda ),
        }
        print inputs
        uuid2 = uuid_dict[ 3 ]
        workflow_request = {}
        workflow_request[ "replacement_params" ] = dumps( dict( replaceme="was replaced" ) )
        pja_map = {
            "RenameDatasetActionout_file1": dict(
                action_type="RenameDatasetAction",
                output_name="out_file1",
                action_arguments=dict( newname="foo ${replaceme}" ),
            )
        }
        workflow_request[ "parameters" ] = dumps({
            uuid2: { "__POST_JOB_ACTIONS__": pja_map }
        })
        invocation_id = self.__invoke_workflow( history_id, workflow_id, inputs=inputs, request=workflow_request )

        time.sleep( 2 )
        self.dataset_populator.wait_for_history( history_id )
        self.__review_paused_steps( workflow_id, invocation_id, order_index=2, action=True )

        self._wait_for_workflow( workflow_id, invocation_id, history_id )
        time.sleep( 1 )
        content = self.dataset_populator.get_history_dataset_details( history_id )
        assert content[ "name" ] == "foo was replaced", content[ "name" ]

    @skip_without_agent( "random_lines1" )
    def test_run_replace_params_by_agent( self ):
        workflow_request, history_id = self._setup_random_x2_workflow( "test_for_replace_agent_params" )
        workflow_request[ "parameters" ] = dumps( dict( random_lines1=dict( num_lines=5 ) ) )
        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 200 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        # Would be 8 and 6 without modification
        self.__assert_lines_hid_line_count_is( history_id, 2, 5 )
        self.__assert_lines_hid_line_count_is( history_id, 3, 5 )

    @skip_without_agent( "random_lines1" )
    def test_run_replace_params_by_uuid( self ):
        workflow_request, history_id = self._setup_random_x2_workflow( "test_for_replace_agent_params" )
        workflow_request[ "parameters" ] = dumps( {
            "58dffcc9-bcb7-4117-a0e1-61513524b3b1": dict( num_lines=4 ),
            "58dffcc9-bcb7-4117-a0e1-61513524b3b2": dict( num_lines=3 ),
        } )
        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 200 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        # Would be 8 and 6 without modification
        self.__assert_lines_hid_line_count_is( history_id, 2, 4 )
        self.__assert_lines_hid_line_count_is( history_id, 3, 3 )

    @skip_without_agent( "validation_default" )
    def test_parameter_substitution_sanitization( self ):
        substitions = dict( input1="\" ; echo \"moo" )
        run_workflow_response, history_id = self._run_validation_workflow_with_substitions( substitions )

        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        self.assertEquals("__dq__ X echo __dq__moo\n", self.dataset_populator.get_history_dataset_content( history_id, hid=1 ) )

    @skip_without_agent( "validation_repeat" )
    def test_parameter_substitution_validation_value_errors_0( self ):
        history_id = self.dataset_populator.new_history()
        workflow_id = self._upload_yaml_workflow("""
class: GalaxyWorkflow
steps:
 - agent_id: validation_repeat
   state:
     r2:
      - text: "abd"
""")
        workflow_request = dict(
            history="hist_id=%s" % history_id,
            parameters=dumps( dict( validation_repeat={"r2_0|text": ""} ) )
        )
        url = "workflows/%s/invocations" % workflow_id
        invocation_response = self._post( url, data=workflow_request )
        # Take a valid stat and make it invalid, assert workflow won't run.
        self._assert_status_code_is( invocation_response, 400 )

    @skip_without_agent( "validation_default" )
    def test_parameter_substitution_validation_value_errors_1( self ):
        substitions = dict( select_param="\" ; echo \"moo" )
        run_workflow_response, history_id = self._run_validation_workflow_with_substitions( substitions )

        self._assert_status_code_is( run_workflow_response, 400 )

    @skip_without_agent( "validation_repeat" )
    def test_workflow_import_state_validation_1( self ):
        history_id = self.dataset_populator.new_history()
        run_summary = self._run_jobs("""
class: GalaxyWorkflow
steps:
 - agent_id: validation_repeat
   state:
     r2:
     - text: ""
""", history_id=history_id, wait=False)
        self.wait_for_invocation( run_summary.workflow_id, run_summary.invocation_id )
        jobs = self._history_jobs( history_id )
        assert len(jobs) == 0

    def _run_validation_workflow_with_substitions( self, substitions ):
        workflow = self.workflow_populator.load_workflow_from_resource( "test_workflow_validation_1" )
        uploaded_workflow_id = self.workflow_populator.create_workflow( workflow )
        history_id = self.dataset_populator.new_history()
        workflow_request = dict(
            history="hist_id=%s" % history_id,
            workflow_id=uploaded_workflow_id,
            parameters=dumps( dict( validation_default=substitions ) )
        )
        run_workflow_response = self._post( "workflows", data=workflow_request )
        return run_workflow_response, history_id

    @skip_without_agent( "random_lines1" )
    def test_run_replace_params_by_steps( self ):
        workflow_request, history_id, steps = self._setup_random_x2_workflow_steps( "test_for_replace_step_params" )
        params = dumps( { str(steps[1]["id"]): dict( num_lines=5 ) } )
        workflow_request[ "parameters" ] = params
        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 200 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        # Would be 8 and 6 without modification
        self.__assert_lines_hid_line_count_is( history_id, 2, 8 )
        self.__assert_lines_hid_line_count_is( history_id, 3, 5 )

    @skip_without_agent( "random_lines1" )
    def test_run_replace_params_nested( self ):
        workflow_request, history_id, steps = self._setup_random_x2_workflow_steps( "test_for_replace_step_params_nested" )
        seed_source = dict(
            seed_source_selector="set_seed",
            seed="moo",
        )
        params = dumps( { str(steps[0]["id"]): dict( num_lines=1, seed_source=seed_source ),
                          str(steps[1]["id"]): dict( num_lines=1, seed_source=seed_source ) } )
        workflow_request[ "parameters" ] = params
        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 200 )
        self.dataset_populator.wait_for_history( history_id, assert_ok=True )
        self.assertEquals("3\n", self.dataset_populator.get_history_dataset_content( history_id ) )

    def test_pja_import_export( self ):
        workflow = self.workflow_populator.load_workflow( name="test_for_pja_import", add_pja=True )
        uploaded_workflow_id = self.workflow_populator.create_workflow( workflow )
        downloaded_workflow = self._download_workflow( uploaded_workflow_id )
        self._assert_has_keys( downloaded_workflow[ "steps" ], "0", "1", "2" )
        pjas = downloaded_workflow[ "steps" ][ "2" ][ "post_job_actions" ].values()
        assert len( pjas ) == 1, len( pjas )
        pja = pjas[ 0 ]
        self._assert_has_keys( pja, "action_type", "output_name", "action_arguments" )

    @skip_without_agent( "cat1" )
    def test_only_own_invocations_accessible( self ):
        workflow_id, usage = self._run_workflow_once_get_invocation( "test_usage")
        with self._different_user():
            usage_details_response = self._get( "workflows/%s/usage/%s" % ( workflow_id, usage[ "id" ] ) )
            self._assert_status_code_is( usage_details_response, 403 )

    @skip_without_agent( "cat1" )
    def test_invocation_usage( self ):
        workflow_id, usage = self._run_workflow_once_get_invocation( "test_usage")
        invocation_id = usage[ "id" ]
        usage_details = self._invocation_details( workflow_id, invocation_id )
        # Assert some high-level things about the structure of data returned.
        self._assert_has_keys( usage_details, "inputs", "steps" )
        invocation_steps = usage_details[ "steps" ]
        for step in invocation_steps:
            self._assert_has_keys( step, "workflow_step_id", "order_index", "id" )
        an_invocation_step = invocation_steps[ 0 ]
        step_id = an_invocation_step[ "id" ]
        step_response = self._get( "workflows/%s/usage/%s/steps/%s" % ( workflow_id, invocation_id, step_id ) )
        self._assert_status_code_is( step_response, 200 )
        self._assert_has_keys( step_response.json(), "id", "order_index" )

    def _invocation_step_details( self, workflow_id, invocation_id, step_id ):
        invocation_step_response = self._get( "workflows/%s/usage/%s/steps/%s" % ( workflow_id, invocation_id, step_id ) )
        self._assert_status_code_is( invocation_step_response, 200 )
        invocation_step_details = invocation_step_response.json()
        return invocation_step_details

    def _execute_invocation_step_action( self, workflow_id, invocation_id, step_id, action ):
        raw_url = "workflows/%s/usage/%s/steps/%s" % ( workflow_id, invocation_id, step_id )
        url = self._api_url( raw_url, use_key=True )
        payload = dumps( dict( action=action ) )
        action_response = put( url, data=payload )
        self._assert_status_code_is( action_response, 200 )
        invocation_step_details = action_response.json()
        return invocation_step_details

    def _run_workflow_once_get_invocation( self, name ):
        workflow = self.workflow_populator.load_workflow( name=name )
        workflow_request, history_id = self._setup_workflow_run( workflow )
        workflow_id = workflow_request[ "workflow_id" ]
        response = self._get( "workflows/%s/usage" % workflow_id )
        self._assert_status_code_is( response, 200 )
        assert len( response.json() ) == 0
        run_workflow_response = self._post( "workflows", data=workflow_request )
        self._assert_status_code_is( run_workflow_response, 200 )

        response = self._get( "workflows/%s/usage" % workflow_id )
        self._assert_status_code_is( response, 200 )
        usages = response.json()
        assert len( usages ) == 1
        return workflow_id, usages[ 0 ]

    def _setup_random_x2_workflow_steps( self, name ):
        workflow_request, history_id = self._setup_random_x2_workflow( "test_for_replace_step_params" )
        random_line_steps = self._random_lines_steps( workflow_request )
        return workflow_request, history_id, random_line_steps

    def _random_lines_steps( self, workflow_request ):
        workflow_summary_response = self._get( "workflows/%s" % workflow_request[ "workflow_id" ] )
        self._assert_status_code_is( workflow_summary_response, 200 )
        steps = workflow_summary_response.json()[ "steps" ]
        return sorted( filter(lambda step: step["agent_id"] == "random_lines1", steps.values()), key=lambda step: step["id"] )

    def _setup_random_x2_workflow( self, name ):
        workflow = self.workflow_populator.load_random_x2_workflow( name )
        uploaded_workflow_id = self.workflow_populator.create_workflow( workflow )
        workflow_inputs = self._workflow_inputs( uploaded_workflow_id )
        key = workflow_inputs.keys()[ 0 ]
        history_id = self.dataset_populator.new_history()
        ten_lines = "\n".join( map( str, range( 10 ) ) )
        hda1 = self.dataset_populator.new_dataset( history_id, content=ten_lines )
        workflow_request = dict(
            history="hist_id=%s" % history_id,
            workflow_id=uploaded_workflow_id,
            ds_map=dumps( {
                key: self._ds_entry(hda1),
            } ),
        )
        return workflow_request, history_id

    def __review_paused_steps( self, uploaded_workflow_id, invocation_id, order_index, action=True ):
        invocation = self._invocation_details( uploaded_workflow_id, invocation_id )
        invocation_steps = invocation[ "steps" ]
        pause_steps = [ s for s in invocation_steps if s[ 'order_index' ] == order_index ]
        for pause_step in pause_steps:
            pause_step_id = pause_step[ 'id' ]

            self._execute_invocation_step_action( uploaded_workflow_id, invocation_id, pause_step_id, action=action )

    def __assert_lines_hid_line_count_is( self, history, hid, lines ):
        contents_url = "histories/%s/contents" % history
        history_contents_response = self._get( contents_url )
        self._assert_status_code_is( history_contents_response, 200 )
        hda_summary = filter( lambda hc: hc[ "hid" ] == hid, history_contents_response.json() )[ 0 ]
        hda_info_response = self._get( "%s/%s" % ( contents_url, hda_summary[ "id" ] ) )
        self._assert_status_code_is( hda_info_response, 200 )
        self.assertEquals( hda_info_response.json()[ "metadata_data_lines" ], lines )

    def __invoke_workflow( self, history_id, workflow_id, inputs={}, request={}, assert_ok=True ):
        request["history"] = "hist_id=%s" % history_id,
        if inputs:
            request[ "inputs" ] = dumps( inputs )
            request[ "inputs_by" ] = 'step_index'
        url = "workflows/%s/usage" % ( workflow_id )
        invocation_response = self._post( url, data=request )
        if assert_ok:
            self._assert_status_code_is( invocation_response, 200 )
            invocation_id = invocation_response.json()[ "id" ]
            return invocation_id
        else:
            return invocation_response

    def __import_workflow( self, workflow_id, deprecated_route=False ):
        if deprecated_route:
            route = "workflows/import"
            import_data = dict(
                workflow_id=workflow_id,
            )
        else:
            route = "workflows"
            import_data = dict(
                shared_workflow_id=workflow_id,
            )
        return self._post( route, import_data )

    def _download_workflow(self, workflow_id, style=None):
        params = {}
        if style:
            params = {"style": style}
        download_response = self._get( "workflows/%s/download" % workflow_id, params )
        self._assert_status_code_is( download_response, 200 )
        downloaded_workflow = download_response.json()
        return downloaded_workflow

    def _show_workflow(self, workflow_id):
        show_response = self._get( "workflows/%s" % workflow_id )
        self._assert_status_code_is( show_response, 200 )
        return show_response.json()

    def _assert_looks_like_instance_workflow_representation(self, workflow):
        self._assert_has_keys(
            workflow,
            'url',
            'owner',
            'inputs',
            'annotation',
            'steps'
        )
        for step in workflow["steps"].values():
            self._assert_has_keys(
                step,
                'id',
                'type',
                'agent_id',
                'agent_version',
                'annotation',
                'agent_inputs',
                'input_steps',
            )

RunJobsSummary = namedtuple('RunJobsSummary', ['history_id', 'workflow_id', 'invocation_id', 'inputs', 'jobs'])

# https://github.com/galaxy-iuc/standards
# https://github.com/galaxy-iuc/standards/pull/7/files
TAG_ORDER = [
    'description',
    'macros',
    'parallelism',
    'requirements',
    'code',
    'stdio',
    'version_command',
    'command',
    'configfiles',
    'inputs',
    'outputs',
    'tests',
    'help',
    'citations',
]

DATASOURCE_TAG_ORDER = [
    'description',
    'macros',
    'command',
    'configfiles',
    'inputs',
    'request_param_translation',
    'uihints',
    'outputs',
    'options',
    'help',
    'citations',
]


# Ensure the XML blocks appear in the correct order prescribed
# by the agent author best practices.
def lint_xml_order(agent_xml, lint_ctx):
    agent_root = agent_xml.getroot()

    if agent_root.attrib.get('agent_type', '') == 'data_source':
        _validate_for_tags(agent_root, lint_ctx, DATASOURCE_TAG_ORDER)
    else:
        _validate_for_tags(agent_root, lint_ctx, TAG_ORDER)


def _validate_for_tags(root, lint_ctx, tag_ordering):
    last_tag = None
    last_key = None
    for elem in root:
        tag = elem.tag
        if tag in tag_ordering:
            key = tag_ordering.index(tag)
            if last_key:
                if last_key > key:
                    lint_ctx.warn("Best practice violation [%s] elements should come before [%s]" % (tag, last_tag))
            last_tag = tag
            last_key = key
        else:
            lint_ctx.info("Unknown tag [%s] encoutered, this may result in a warning in the future." % tag)



def lint_output(agent_xml, lint_ctx):
    outputs = agent_xml.findall("./outputs")
    if len(outputs) == 0:
        lint_ctx.warn("Agent contains no outputs section, most agents should produce outputs.")
    if len(outputs) > 1:
        lint_ctx.warn("Agent contains multiple output sections, behavior undefined.")

    num_outputs = 0
    if len(outputs) == 0:
        lint_ctx.warn("No outputs found")
        return

    for output in list(outputs[0]):
        if output.tag not in ["data", "collection"]:
            lint_ctx.warn("Unknown element found in outputs [%s]" % output.tag)
            continue
        num_outputs += 1
        output_attrib = output.attrib
        if output.tag == "data":
            format_set = False
            if "format" in output_attrib:
                format_set = True
                format = output_attrib["format"]
                if format == "input":
                    lint_ctx.warn("Using format='input' on output data, format_source attribute is less ambiguous and should be used instead.")
            elif "format_source" in output_attrib:
                format_set = True
            if not format_set:
                lint_ctx.warn("Agent data output doesn't define an output format.")
        elif output.tag == "collection":
            if "type" not in output_attrib:
                lint_ctx.warn("Collection output with undefined 'type' found.")
    lint_ctx.info("%d outputs found.", num_outputs)

import re


def lint_top_level(tree, lint_ctx):
    root = tree.getroot()
    if "version" not in root.attrib:
        lint_ctx.error("Agent does not define a version attribute.")
    else:
        lint_ctx.valid("Agent defines a version.")

    if "name" not in root.attrib:
        lint_ctx.error("Agent does not define a name attribute.")
    else:
        lint_ctx.valid("Agent defines a name.")

    if "id" not in root.attrib:
        lint_ctx.error("Agent does not define an id attribute.")
    else:
        lint_ctx.valid("Agent defines an id name.")

    id = root.attrib["id"]
    if re.search(r"\s", id):
        lint_ctx.warn("Agent id contains a space - this is discouraged.")

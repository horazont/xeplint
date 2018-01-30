import lxml.etree

from . import messages


class XeplintContext:
    def __init__(self,
                 tree: lxml.etree.ElementTree,
                 filename: str):
        super().__init__()
        self.tree = tree
        self.filename = filename

        self.schemas = {}
        self.messages = messages.MessageStore(filename)
        self.find_schemas()

    def find_schemas(self):
        for codeblock in self.tree.xpath("//code"):
            if codeblock.text is None:
                continue

            lxml.etree.clear_error_log()
            try:
                tree = lxml.etree.fromstring(codeblock.text).getroottree()
            except lxml.etree.XMLSyntaxError:
                continue
            except ValueError as exc:
                self.messages.record(
                    MESSAGE_TYPE_XML_SCHEMA_PARSER,
                    messages.Location(self.filename, codeblock.sourceline, 0),
                    "{}", (str(exc),),
                )
                continue

            if tree.getroot().tag != "{http://www.w3.org/2001/XMLSchema}schema":
                continue

            lxml.etree.clear_error_log()
            try:
                schema = lxml.etree.XMLSchema(tree)
            except lxml.etree.XMLSchemaParseError as exc:
                with self.messages.context(
                        line_offset=codeblock.sourceline,
                        override_filename=self.filename) as ctx:
                    for log_entry in exc.error_log:
                        messages.record_error_log_entry(
                            ctx,
                            MESSAGE_TYPE_XML_SCHEMA_PARSER,
                            log_entry,
                        )
                continue

            target_ns = tree.getroot().get("targetNamespace")

            if target_ns in self.schemas:
                self.messages.record(
                    MESSAGE_TYPE_DUPLICATE_SCHEMA,
                    messages.Location(self.filename, codeblock.sourceline,
                                      None),
                    "mulitple schemas found for namespace {!r}",
                    (target_ns,),
                )
                continue

            self.schemas[target_ns] = schema


MESSAGE_TYPE_XML_SCHEMA_PARSER = messages.registry.register(
    messages.MessageLevel.ERROR,
    1,
    "xml-schema-parser",
)

MESSAGE_TYPE_DUPLICATE_SCHEMA = messages.registry.register(
    messages.MessageLevel.ERROR,
    2,
    "xml-schema-duplicate",
)

import abc
import functools

import lxml.etree

from . import messages, context


MESSAGE_TYPE_DUPLICATE_ANCHOR = messages.registry.register(
    messages.MessageLevel.ERROR,
    3,
    'duplicate-anchor',
)

MESSAGE_TYPE_EXAMPLE_PARSER = messages.registry.register(
    messages.MessageLevel.ERROR,
    4,
    "example-parser",
)

MESSAGE_TYPE_MISSING_ANCHOR = messages.registry.register(
    messages.MessageLevel.ERROR,
    5,
    "missing-anchor",
)


class AbstractChecker(metaclass=abc.ABCMeta):
    def __init__(self, ctx: context.XeplintContext):
        super().__init__()
        self._context = ctx

    @abc.abstractmethod
    def check(self):
        pass


def checker(f):
    @functools.wraps(f)
    def check(self):
        return f(self._context)

    return abc.ABCMeta(f.__name__, (AbstractChecker,), {"check": check})


@checker
def check_anchors(context: context.XeplintContext):
    sections = context.tree.xpath(" | ".join([
        "//section{}".format(i)
        for i in range(1, 7)
    ]))

    existing_anchors = {}

    for section in sections:
        anchor = section.get("anchor")
        if anchor is None:
            context.messages.record(
                MESSAGE_TYPE_MISSING_ANCHOR,
                messages.Location(context.filename,
                                  section.sourceline,
                                  None),
                "section {!r} has no anchor",
                (section.get("topic"),)
            )
            continue

        try:
            existing = existing_anchors[anchor]
        except KeyError:
            existing_anchors[anchor] = section
            continue

        rec = context.messages.record(
            MESSAGE_TYPE_DUPLICATE_ANCHOR,
            messages.Location(context.filename, section.sourceline, None),
            "anchor {!r} has been used already",
            (anchor,),
        )

        context.messages.record(
            MESSAGE_TYPE_DUPLICATE_ANCHOR,
            messages.Location(context.filename, existing.sourceline, None),
            "anchor {!r} has been first used here",
            (anchor,),
            attach_to=rec,
        )


class CheckExamples(AbstractChecker):
    def _parse_example(self,
                       code: str,
                       message_sink: messages.MessageHandler):
        try:
            return lxml.etree.fromstring(code).getroottree()
        except lxml.etree.XMLSyntaxError as exc:
            error_log = exc.error_log
            # type 5 is "extra content after end of document"
            if any(entry.type == 5 for entry in error_log):
                # this situation is likely multiple stanzas in one example,
                # wrap it and try again
                code = "<wrap>" + code + "</wrap>"
                try:
                    return lxml.etree.fromstring(code).getroottree()
                except lxml.etree.XMLSyntaxError as new_exc:
                    error_log = new_exc.error_log

            elif error_log.last_error.type == 4:
                # does not look like XML at all, ignore ...
                return None

            for log_entry in error_log:
                messages.record_error_log_entry(
                    message_sink,
                    MESSAGE_TYPE_EXAMPLE_PARSER,
                    log_entry,
                )
            return None
        except ValueError as exc:
            message_sink.record(
                MESSAGE_TYPE_EXAMPLE_PARSER,
                messages.Location(self._context.filename, 0, 0),
                "{}",
                (str(exc),)
            )

    def _check_example(self,
                       example_tree: lxml.etree.ElementTree,
                       message_sink: messages.MessageHandler):
        pass

    def check(self):
        examples = self._context.tree.xpath("//example")
        for example in examples:
            lxml.etree.clear_error_log()
            with self._context.messages.context(
                    line_offset=example.sourceline - 1) as message_sink:
                example_tree = self._parse_example(
                    example.text,
                    message_sink,
                )
                if example_tree is None:
                    continue

                self._check_example(example_tree, message_sink)


CHECKERS = [
    check_anchors,
    CheckExamples,
]

import abc
import collections
import functools
import enum
import typing
import sys


class MessageType(collections.namedtuple("MessageType",
                                         ["class_", "id_", "name"])):
    def __str__(self):
        return "{}-{:04d}:{}".format(
            self.class_.value[0],
            self.id_,
            self.name,
        )


@functools.total_ordering
class MessageLevel(enum.Enum):
    CONVENTION = "C", "convention"
    WARNING = "W", "warning"
    ERROR = "E", "error"

    def __lt__(self, other):
        return self._order.index(self) < self._order.index(other)


MessageLevel._order = [MessageLevel.CONVENTION,
                       MessageLevel.WARNING,
                       MessageLevel.ERROR]


class MessageTypeRegistry:
    def __init__(self):
        super().__init__()
        self._name_registry = {}
        self._id_registry = {}

    def register(self, class_: MessageLevel, id_: int, name: str):
        if name in self._name_registry:
            raise ValueError("name {!r} already in use".format(name))
        if id_ in self._id_registry:
            raise ValueError("id {!r} already in use by {!r}".format(
                id_,
                self._id_registry[id_],
            ))
        type_ = MessageType(class_, id_, name)
        self._name_registry[name] = type_
        self._id_registry[id_] = type_
        return type_

    def __getitem__(self, key: typing.Union[int, str]):
        if isinstance(key, str):
            return self._name_registry[key]
        else:
            return self._id_registry[key]


@functools.total_ordering
class Location(collections.namedtuple("Location", ["filename", "line", "col"])):
    def __new__(cls, filename, line=None, col=None):
        return super().__new__(cls, filename, line, col)

    def replace(self, **kwargs):
        return super()._replace(**kwargs)

    def __lt__(self, other):
        return (
            (self.filename or "", self.line or 0, self.col or 0) <
            (other.filename or "", other.line or 0, other.col or 0)
        )

    def __str__(self):
        parts = [self.filename]
        parts.append(str(self.line or 0))
        parts.append(str(self.col or 0))
        return ":".join(parts)


class Message(collections.namedtuple("Message",
                                     ["location", "type", "message",
                                      "args", "kwargs"])):
    def __str__(self):
        return "{}:{}: {}".format(
            self.location,
            self.type,
            self.message.format(*self.args, **self.kwargs),
        )


class MessageRecord(collections.namedtuple("MessageRecord",
                                           ["main", "related"])):
    pass


class MessageHandler:
    @abc.abstractmethod
    def _handle_record(self, record):
        pass

    def record(self, _type, _location, _message, _args=(),
               attach_to=None,
               **kwargs):
        message = self._prep_message(
            Message(_location, _type, _message, _args, kwargs)
        )
        if attach_to is not None:
            attach_to.related.append(message)
            return

        record = MessageRecord(message, [])
        self._handle_record(record)
        return record

    def _prep_message(self, message):
        if not message.location.filename:
            message = message._replace(
                location=message.location._replace(
                    filename=self.default_filename,
                )
            )

        return message

    def _prep_record(self, record):
        return MessageRecord(
            self._prep_message(record.main),
            [msg for msg in self._prep_message(msg)],
        )

    def _add_records(self, records):
        for rec in records:
            self._handle_record(rec)


class MessageStore(MessageHandler):
    def __init__(self, default_filename=None):
        self._records = []
        self._default_filename = default_filename

    def _handle_record(self, record):
        self._records.append(record)

    def context(self, **kwargs):
        return MessageContext(self._add_records, **kwargs)

    def print(self, outfile=sys.stderr):
        self._records.sort(key=lambda x: x.main.location)
        for rec in self._records:
            print(rec.main, file=outfile)
            for related in rec.related:
                print(related, file=outfile)


class MessageContext(MessageHandler):
    def __init__(self, receiver, *,
                 line_offset=0,
                 clear_on_pass=False):
        super().__init__()
        self._records = []
        self._receiver = receiver
        self._clear_on_pass = clear_on_pass
        self._has_errors = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self._clear_on_pass and exc_type is None:
            return
        self._receiver(self._records)

    def clear(self):
        self._records.clear()

    def child(self, **kwargs):
        return ErrorContext(
            self._add_records,
            **kwargs
        )


def error_log_entry_location(error_log):
    return Location(error_log.filename, error_log.line, error_log.column)


def record_error_log_entry(handler: MessageHandler, type: MessageType,
                           error_log_entry):
    handler.record(
        type,
        error_log_entry_location(error_log_entry),
        "{}",
        (error_log_entry.message,)
    )


registry = MessageTypeRegistry()

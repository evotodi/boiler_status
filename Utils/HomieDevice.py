from __future__ import annotations

__all__ = {
    'Device',
    'DeviceState'
}

from typing import Optional, Mapping, Iterator, NamedTuple
from functools import partial

from homie_spec.devices import DeviceState, HOMIE_VERSION
from homie_spec.messages import Message
from homie_spec.properties import Property
from homie_spec.nodes import Node


class Device(NamedTuple):
    """Object representation of a device according to the Homie topology"""

    id: str

    name: str
    nodes: Optional[Mapping[str, Node]] = None
    extensions: Optional[dict] = None

    implementation: str = "homie-spec"
    prefix: str = "homie"

    def messages(self) -> Iterator[Message]:
        """
        "Yields the messages from the device attributes and from its nodes.
        "All its messages are prefixed with the device prefix and the device id.
        "
        ">>> msg = next(Device("device", "A Device!").messages())
        ">>> msg.topic
        "'homie/device/$state'
        ">>> msg.payload
        "'init'
        """

        prefix = f"{self.prefix}/{self.id}"
        msg = partial(Message, prefix=prefix)

        yield msg("$state", DeviceState.INIT.payload)
        yield msg("$name", self.name)
        yield msg("$homie", HOMIE_VERSION)
        yield msg("$implementation", self.implementation)

        if self.extensions:
            payload_extensions = ",".join(self.extensions.keys())
            yield msg("$extensions", payload_extensions)

        if self.nodes:
            payload_nodes = ",".join(self.nodes.keys())
            yield msg("$nodes", payload_nodes)

            for node_name, node in self.nodes.items():
                prefix = "/".join((prefix, node_name))
                yield from node.messages(prefix=prefix)
        else:
            yield msg("$nodes", "")

        yield msg("$state", DeviceState.READY.payload)

    def getter_state(self, state) -> Message:
        prefix = f"{self.prefix}/{self.id}"
        msg = partial(Message, prefix=prefix)

        return msg("$state", state)

    def getter_message(self, path: str) -> Message:
        """
        "Given the parameter `path` find its property,
        "call the getter function and returns its respective message.
        "
        "The `path` parameter takes the format of `{node_name}/{property_name}`.
        "
        "All its messages are prefixed with the device prefix and the device id.
        "
        "">>> from homie_spec.properties import Datatype
        ">>> prop = Property("P", lambda: "4", Datatype.INTEGER)
        ">>> node = Node("N", "n", {"p": prop})
        ">>> device = Device("D", "d", {"n": node})
        ">>> msg = device.getter_message("n/p")
        "">>> msg.topic
        "'homie/d/n/p'
        "">>> msg.payload
        "'4'
        "
        "Raises a ValueError when input is invalid or can't be reached:
        "
        "
        ">>> Device("D", "d").getter_message("n/p")
        "Traceback (most recent call last):
        "...
        "ValueError: Unreachable path 'n/p' - Valid property paths are []
        "
        """
        absolute_path = f"{self.prefix}/{self.id}/{path}".lower()

        # Enumerate all valid topics where the property value should reside.
        property_topics: Mapping[str, Property] = {
            f"{self.prefix}/{self.id}/{node_name}/{prop_name}".lower(): prop
            for node_name, node in (self.nodes or {}).items()
            for prop_name, prop in (node.properties or {}).items()
        }

        try:
            prop = property_topics[absolute_path]
        except KeyError as err:
            absolute_prefix_len = len(f"{self.prefix}/{self.id}")
            reachable_paths = [
                topic[absolute_prefix_len:].lower() for topic in property_topics.keys()
            ]
            raise ValueError(
                " - ".join(
                    [
                        f"Unreachable path '{path}'",
                        f"Valid property paths are {reachable_paths}",
                    ]
                )
            ) from err

        message: Message = prop.getter_message(absolute_path)
        return message

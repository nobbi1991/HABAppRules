"""Define graph machine classes."""

import inspect
import os
import typing
from functools import partial
from pathlib import Path

from transitions.core import Machine, State, Transition
from transitions.extensions import GraphMachine, HierarchicalGraphMachine
from transitions.extensions.diagrams_graphviz import Graph, _filter_states
from transitions.extensions.states import Timeout, add_state_features

from habapp_rules.core.state_machine_rule import StateMachineRule

try:
    import graphviz as pgv
except ImportError:
    pgv = None

os.environ["PATH"] += r"C:\Program Files\Graphviz\bin"


class FakeModel:
    """This class is used as fake model for graph creation."""


def get_graph_with_previous_state(self: Graph, title: str | None = None, roi_state: str | None = None) -> object:
    """Monkey patch for transtitions.extentions.diagrams_graphviz.Graph.get_graph, which also adds all previous states.

    Args:
        self: graph object
        title: title of graph
        roi_state: region of interest - state

    Returns:
        graph
    """
    title = title or self.machine.title

    fsm_graph = pgv.Digraph(
        name=title,
        node_attr=self.machine.style_attributes["node"]["default"],
        edge_attr=self.machine.style_attributes["edge"]["default"],
        graph_attr=self.machine.style_attributes["graph"]["default"],
    )
    fsm_graph.graph_attr.update(**self.machine.machine_attributes)
    fsm_graph.graph_attr["label"] = title
    # For each state, draw a circle
    states, trans = self._get_elements()
    if roi_state:
        trans = [t for t in trans if t["source"] == roi_state or t["dest"] == roi_state or self.custom_styles["edge"][t["source"]][t["dest"]]]
        state_names = [t for trans in trans for t in [trans["source"], trans.get("dest", trans["source"])]]
        state_names += [k for k, style in self.custom_styles["node"].items() if style]
        states = _filter_states(states, state_names, self.machine.state_cls)
    self._add_nodes(states, fsm_graph)
    self._add_edges(trans, fsm_graph)
    fsm_graph.draw = partial(self.draw, fsm_graph)
    return fsm_graph


# monkey patching of Graph method
Graph.get_graph = get_graph_with_previous_state


def _state_to_dict(state_config: State) -> dict[str, str]:
    """Converts a state to a dictionary.

    Args:
        state_config: state to convert

    Returns:
        dictionary representation of state
    """
    state_dict = {"name": state_config.name}

    if hasattr(state_config, "initial") and state_config.initial:
        state_dict["initial"] = state_config.initial
    if hasattr(state_config, "on_timeout") and hasattr(state_config, "timeout") and state_config.on_timeout:
        state_dict["on_timeout"] = state_config.on_timeout[0]
        state_dict["timeout"] = state_config.timeout
    if hasattr(state_config, "states") and state_config.states:
        state_dict["children"] = [_state_to_dict(child) for child in state_config.states.values()]

    return state_dict


def extract_states_from_machine(state_machine: Machine) -> list[dict[str, str | float]]:
    """Extract states from a state machine.

    Args:
        state_machine: state machine object

    Returns:
        list of dictionaries, where each dictionary represents a state
    """
    return [_state_to_dict(state_config) for state_config in state_machine.states.values()]


def _generate_transitions_dicts(transition_list: list[Transition], trigger_name: str) -> list[dict]:
    """Generate transitions dictionary from transition list and trigger name.

    Args:
        transition_list: list of all transitions of the given event
        trigger_name: name of the event

    Returns:
        list of dictionaries representing the transition
    """
    parsed_transitions = []

    for trans in transition_list:
        conditions = [c.func for c in trans.conditions if c.target is True]
        unless = [c.func for c in trans.conditions if c.target is False]
        after = trans.after
        before = trans.before

        parsed_trans = {"trigger": trigger_name, "source": trans.source, "dest": trans.dest}

        if conditions:
            if len(conditions) == 1:
                conditions = conditions[0]
            parsed_trans["conditions"] = conditions

        if unless:
            if len(unless) == 1:
                unless = unless[0]
            parsed_trans["unless"] = unless

        if before:
            if len(before) == 1:
                before = before[0]
            parsed_trans["before"] = before

        if after:
            if len(after) == 1:
                after = after[0]
            parsed_trans["after"] = after

        parsed_transitions.append(parsed_trans)

    return parsed_transitions


def extract_transitions_from_machine(state_machine: Machine) -> list[dict[str, str | float]]:
    """Extract transitions from state machine.

    Args:
        state_machine: state machine object

    Returns:
        list of dictionaries, where each dictionary represents a transition
    """
    transitions = []
    for event in state_machine.events.values():
        if event.name.startswith("to_"):
            continue

        for trans in event.transitions.values():
            transitions += _generate_transitions_dicts(trans, event.name)

    return transitions


@add_state_features(Timeout)
class GraphMachineTimer(GraphMachine):
    """GraphMachine with Timer."""


@add_state_features(Timeout)
class HierarchicalGraphMachineTimer(HierarchicalGraphMachine):
    """HierarchicalGraphMachine with Timer."""


_GRAPH_MACHINE_TYPE = typing.TypeVar("_GRAPH_MACHINE_TYPE", bound=GraphMachineTimer | HierarchicalGraphMachineTimer)


def get_graph_machine(state_machine: StateMachineRule, graph_machine_class: type[_GRAPH_MACHINE_TYPE], show_conditions: bool = False) -> _GRAPH_MACHINE_TYPE:
    """Get graph machine from state machine rule.

    Args:
        state_machine: state machine rule.
        graph_machine_class: target class of graph machine.
        show_conditions: whether to show conditions in the graphs

    Returns:
        graph machine object
    """
    states = extract_states_from_machine(state_machine.state_machine)
    trans = extract_transitions_from_machine(state_machine.state_machine)

    return graph_machine_class(model=FakeModel(), states=states, transitions=trans, initial=state_machine.state, show_conditions=show_conditions)


def _create_graph_picture_dir(name: str) -> Path:
    """Create directory for graph pictures.

    Args:
        name: name of the subdirectory for the pictures

    Returns:
        path to the created directory
    """
    caller_frame = inspect.stack()[1]
    caller_file = caller_frame.filename
    picture_dir = Path(caller_file).parent / "_state_charts" / name
    if not picture_dir.is_dir():
        picture_dir.mkdir(parents=True)
    return picture_dir


def _get_state_names(states: list[dict[str, str | float]], parent_state: str | None = None) -> list[str]:
    """Helper function to get all state names (also nested states).

    Args:
        states: dict of all states or children states
        parent_state: name of parent state, only if it is a nested state machine

    Returns:
        list of all state names
    """
    state_names = []
    prefix = f"{parent_state}_" if parent_state else ""
    if parent_state:
        states = states["children"]

    for state in states:
        if "children" in state:
            state_names += _get_state_names(state, f"{prefix}{state['name']}")
        else:
            state_names.append(f"{prefix}{state['name']}")
    return state_names


def create_state_graphs(rule: StateMachineRule, state_machine_name: str) -> None:
    """Create state graphs.

    Args:
        rule: state machine rule
        state_machine_name: name of the state machine. This Name will be foldername + picture name
    """
    # get target path an create if it does not exist
    caller_frame = inspect.currentframe().f_back
    caller_file = Path(caller_frame.f_code.co_filename) if caller_frame else Path(__file__)

    picture_dir = caller_file.parent / "_state_charts" / state_machine_name
    if not picture_dir.is_dir():
        picture_dir.mkdir(parents=True)

    # create graph of whole state machine
    graph = get_graph_machine(rule, HierarchicalGraphMachineTimer, show_conditions=False)
    graph.get_graph().draw(picture_dir / f"{state_machine_name}.png", format="png", prog="dot")

    states = _get_state_names(extract_states_from_machine(rule.state_machine))
    # create graphs of each state
    for state_name in states:
        if "_init" in state_name.lower():
            continue
        rule._set_state(state_name)
        graph_conditions = get_graph_machine(rule, HierarchicalGraphMachineTimer, show_conditions=True)
        graph_conditions.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"{state_machine_name}_{state_name}.png", format="png", prog="dot")

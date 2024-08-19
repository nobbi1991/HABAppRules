"""Define graph machine classes."""
import os
from functools import partial

import transitions.extensions.states
from transitions.extensions.diagrams_graphviz import Graph, filter_states

try:
	import graphviz as pgv
except ImportError:
	pgv = None

os.environ["PATH"] += r"C:\Program Files\Graphviz\bin"


class FakeModel:
	"""This class is used as fake model for graph creation"""


# pylint: disable=protected-access, missing-type-doc
def get_graph_with_previous_state(self, title=None, roi_state=None) -> object:
	"""Monkey patch for transtitions.extentions.diagrams_graphviz.Graph.get_graph, which also adds all previous states.

	:param self: graph object
	:param title: title of graph
	:param roi_state: region of interest - state
	:return: graph
	"""
	title = title if title else self.machine.title

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
		states = filter_states(states, state_names, self.machine.state_cls)
	self._add_nodes(states, fsm_graph)
	self._add_edges(trans, fsm_graph)
	setattr(fsm_graph, "draw", partial(self.draw, fsm_graph))
	return fsm_graph


# monkey patching of Graph method
Graph.get_graph = get_graph_with_previous_state


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class GraphMachineTimer(transitions.extensions.GraphMachine):
	"""GraphMachine with Timer."""


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class HierarchicalGraphMachineTimer(transitions.extensions.HierarchicalGraphMachine):
	"""HierarchicalGraphMachine with Timer."""

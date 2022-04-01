"""Define graph machine classes."""
import os

import transitions.extensions.states

os.environ["PATH"] += r"C:\Program Files\Graphviz\bin"


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class GraphMachineTimer(transitions.extensions.GraphMachine):
	"""GraphMachine with Timer."""

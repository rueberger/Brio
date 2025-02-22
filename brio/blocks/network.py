"""
This module holds the Network class
"""
import numpy as np
from .aux import NetworkParams
from brio.misc.plotting import ParamPlot, plot_receptive_fields, write_hist_to_stdout
from brio.misc.utils import roll_itr

class Network(object):
    """
    Top level class for networks
    The Network class contains pointers to the Layer and Connection classes
      that make up a network in addition to methods for running the network
    """

    def __init__(self, layers, params=NetworkParams(), display_layers=None):
        """ Initalize Network object. Only layers are specified upon initalization
        Connections should already be instantiated

        :param layers: list of Layer objects. InputLayer must be the
           first element, output layer must be last
        :param presentations: the number of times to run the
           network for each stimulus. For async networks
        """
        self.layers = layers
        self.params = params
        self.__find_connections()
        self.__set_up_children()
        self.t_counter = 0
        if params.display:
            self.param_plot = ParamPlot(self, display_layers)
        if params.async:
            self.node_idx = np.arange(np.sum([l.n_dims for l in layers[1:]]))
            self.idx_to_layer = self.__build_layer_dict()

    def show_rfs(self, layer_idx=1, slideshow=False):
        """ Convenenience method that wraps plot_receptive_fields

        :returns: None
        :rtype: None
        """
        plot_receptive_fields(self, layer_idx, slideshow)


    def describe_progress(self):
        """ prints some information on how the training is progressing

        :returns: None
        :rtype: None
        """
        if self.params.print_progress:
            print "Training iteration: {} \n".format(self.t_counter)
            print "Average firing rates:"
            for layer in self.layers[1:]:
                print "{}: {}".format(str(layer), np.mean(layer.epoch_fr))
            print ""
            if self.t_counter % 1000 == 0:
                for label, connection in self.connections.iteritems():
                    print "Weight distribution for {}".format(label)
                    write_hist_to_stdout(connection.weights.ravel())
                    print "\n \n"
            print "=" * 100
            print "\n\n"
        if self.params.display and self.t_counter % 1000 == 0:
            self.param_plot.update_plot()

    def train(self, stimulus_generator, rolled=False):
        """ Trains the network on the generated stimuli

        :param stimulus_generator: a generator object. calling next on this generator must return
          an array that can be flatted to the shape of the input layer
        :param rolled: whether the stimulus is already rolled into epoch sized arrays. False by default
        :returns: None
        :rtype: None

        """
        if rolled:
            stim_gen = stimulus_generator
        else:
            stim_gen =  roll_itr(stimulus_generator, self.params.stimuli_per_epoch)
        for rolled_stimuli in stim_gen:
            self.update_network(rolled_stimuli)
            self.t_counter += self.params.stimuli_per_epoch
            self.training_iteration()
            self.describe_progress()


    def update_network(self, rolled_stimuli):
        """ Present rolled_stimuli to the network and update the state

        :param rolled_stimuli: params.stimuli_per_epoch (default 100) stimuls rolled into an array of
           shape (input_layer.n_dims, params.stimuli_per_epoch)
        """
        for layer in self.layers:
            layer.reset()
        self.layers[0].set_state(rolled_stimuli)
        if self.params.async:
            raise NotImplementedError
            np.random.shuffle(self.node_idx)
            for _ in xrange(self.params.presentations):
                for idx in self.node_idx:
                    layer, unit_idx = self.idx_to_layer[idx]
                    layer.async_update(unit_idx)
                for layer in self.layers:
                    layer.update_history()
        else:
            for _ in xrange(self.params.presentations):
                for layer in self.layers[1:]:
                    layer.sync_update()
                for layer in self.layers:
                    layer.update_history()



    def training_iteration(self):
        """ Calls the training method in each layer and connection
        Connection training method updates weights
        layer training method update biases

        :returns: None
        :rtype: None
        """
        for layer in self.layers:
            layer.update_lifetime_mean()
        for connection in self.connections.itervalues():
            connection.weight_update()
        for layer in self.layers[1:]:
            layer.bias_update()

    def __build_layer_dict(self):
        """ Builds a dictionary from unit idx to layer for use in update method

        :returns: dictionary: (idx : layer object)
        :rtype: dictionary
        """
        unit_dict = {}
        start_idx = 0
        for layer in self.layers[1:]:
            for idx in xrange(layer.n_dims):
                unit_dict[idx + start_idx] = (layer, idx)
            start_idx = len(unit_dict)
        return unit_dict

    def __find_connections(self):
        """ Finds all the connections in the network by searching through the
          input and output lists in each layer

        :returns: None
        :rtype: None
        """
        self.connections = {}
        connections = set()
        for layer in self.layers:
            for connection in layer.inputs + layer.outputs:
                connections.add(connection)
        for connection in connections:
            self.connections[str(connection)] = connection


    def __set_up_children(self):
        """ Passes global parameters and calls set up methods on
           all network and connection objects in the networky

        :returns: None
        :rtype: None
        """
        for layer in self.layers:
            layer.set_up(self)
        for connection in self.connections.itervalues():
            connection.set_up(self)

"""
This module contains utilities for computing the receptive fields of trained networks
"""
import numpy as np
import itertools
from .utils import roll_itr

def record_responses(net, stimuli, layer_idx=None):
    """ present stimuli to net and record which units in which layers respond to what

    :param net: a trained network
    :param stimuli: array of stimuli
    :param layer_idx: optional tuple or integer specifying which layer(s) to
      collect responses from for large networks memory use will be egregious of not specified
    :returns: a dictionary recording stimuli idx each unit responded to and a list of stimuli
    :rtype: (dict: (layer_idx, unit_idx) --> array(stimuli_idx), stimuli)
    """
    # disable too many local variables complaint
    # pylint:disable=R0914
    assert isinstance(stimuli, np.ndarray)

    active_layers = layer_idx or range(1, len(net.layers))
    if not isinstance(active_layers, list):
        assert isinstance(active_layers, int)
        active_layers = [active_layers]

    epoch_size = net.params.stimuli_per_epoch

    # initialize response dict with empty list for each (layer_idx, unit_idx) pair
    response_dict = {}
    for l_idx in active_layers:
        for unit_idx in xrange(net.layers[l_idx].n_dims):
            response_dict[(l_idx, unit_idx)] = []

    for epoch_idx, rolled_stimuli in enumerate(roll_itr(stimuli, epoch_size)):
        # present the rolled stimuli to the network
        net.update_network(rolled_stimuli)
        # indices to each individual stimuli in the rolled batch
        sample_idx = np.arange(epoch_idx * epoch_size, (epoch_idx + 1) * epoch_size).reshape(1, -1)
        # record the stimuli
        for l_idx in active_layers:
            # since state responses are binary {0, 1} by multiplying the batch response through
            #  with the individual sample indexes we can record which stimulus each neuron
            #  responded to
            # bug here: only collecting response for the end of the time window
            # how to deal with spiking within the window?
            response = net.layers[l_idx].history * sample_idx
            for unit_idx in xrange(net.layers[l_idx].n_dims):
                # collect stimuli_idx that this neuron responded to
                active_at_sample_idx = np.where(response[:, unit_idx] != 0)
                response_dict[(l_idx, unit_idx)].extend(response[:, unit_idx][active_at_sample_idx])

    return response_dict, stimuli

def scalar_sta(net, n_samples=1E4, stim_gen=None, layer_idx=None):
    """ computes responses for visualizing the receptive field of layers
    computes a list of response for each neuron in each layer


    :param net: a trained network. the first layer must be a RasterInputLayer
    :param stim_gen: generator of stimuli. by default stimuli are generated at random
       for the relevant domain
    :returns: a dictionary of responses
    :rtype: dict((layer_idx, unit_idx): array(responses))
    """
    assert type(net.layers[0]).__name__ == 'RasterInputLayer'
    if stim_gen is None:
        stimuli = np.random.uniform(net.layers[0].lower_bnd, net.layers[0].upper_bnd, n_samples)
    else:
        # this sets stimuli to an array containing the first n_samples elements of stim_gen
        stimuli = np.array(list(itertools.islice(stim_gen, n_samples)))
        assert stimuli.ndim == 1
    return record_responses(net, stimuli, layer_idx=layer_idx)

def img_sta(net, n_samples=1E4, img_dim=None, stim_gen=None, layer_idx=None):
    """ computes spike triggered averages for visualizing the receptive field of layers

    :param net: a trained network.
    :param n_samples: the number of samples to draw
    :param img_dim: tuple with image dimensions. if None the size of the InputLayer must
      be a perfect square
    :param stim_gen: generator of stimuli. by default stimuli are generated at random
       for the relevant domain
    :returns: a dictionary of spike triggered averages
    :rtype: dict((layer_idx, unit_idx): array(sta))
    """
    var_range = (.5, 1.5)
    img_dim = factor(net.layers[0].n_dims)

    if stim_gen is None:
        # i think this should be white noise
        stimuli = np.zeros((n_samples, img_dim[0], img_dim[1]))
        x_idx = np.arange(img_dim[0])
        y_idx = np.arange(img_dim[1])
        for idx, (x_mean, y_mean) in enumerate(zip(np.random.uniform(-1, img_dim[0], n_samples),
                                                   np.random.uniform(-1, img_dim[1], n_samples))):
            stimuli[idx] = np.outer(gaussian_blob(x_idx, x_mean, var_range),
                                    gaussian_blob(y_idx, y_mean, var_range))
    else:
        # this sets stimuli to an array containing the first n_samples elements of stim_gen
        stimuli = np.array(list(itertools.islice(stim_gen, n_samples)))
        assert stimuli.shape[1] == img_dim[0] and stimuli.shape[2] == img_dim[1]
    return record_responses(net, stimuli, layer_idx=layer_idx)

def split_img_sta(net, n_samples=1E4, stim_gen=None, layer_idx=None):
    """ computes spike triggered averages for visualizing the receptive field of layers
    differs from img_sta in that this supports multiple image input for
      split or input layers

    :param net: a trained network.
    :param n_samples: the number of samples to draw
    :param stim_gen: generator of stimuli. by default stimuli are generated at random
       for the relevant domain
    :returns: a dictionary of spike triggered averages
    :rtype: dict((layer_idx, unit_idx): array(sta))
    """
    # can also just take the product with the first layer weight
    input_layer = net.layers[0]
    n_stim_dims = input_layer.children[0].n_dims
    n_children = len(input_layer.children)
    # all child layers must have the same dimension
    assert (np.array([c.n_dims for c in input_layer.children]) == n_stim_dims).all()
    img_dim = factor(n_stim_dims)

    if stim_gen is None:
        # white noise is the most general but wont' work well for disparity
        # i don't think it matters what axis the child images are tiled across
        stimuli = np.random.random(n_samples, img_dim[0] * n_children, img_dim[1])
    else:
        # this sets stimuli to an array containing the first n_samples elements of stim_gen
        stimuli = np.array(list(itertools.islice(stim_gen, n_samples)))
        assert stimuli.shape[1] == img_dim[0] * n_children and stimuli.shape[2] == img_dim[1]
    return record_responses(net, stimuli, layer_idx=layer_idx)


def auto_sta(net, n_samples=1E4, stim_gen=None, layer_idx=None):
    """ calls either img_sta, split_img_sta or scalar_sta depending on input layer type

    :param net: a trained network
    :param n_samples: the number of samples to base the sta off of
    :param stim_gen: generator of stimuli. by default stimuli are generated at random
       for the relevant domain
    :returns: a dictionary of spike triggered averages
    :rtype: dict((layer_idx, unit_idx): array(sta))

    """
    from brio.blocks.layer import InputLayer, RasterInputLayer, GatedInput, SplitInput
    input_layer = net.layers[0]
    if isinstance(input_layer, (SplitInput, GatedInput)):
        return split_img_sta(net, n_samples, stim_gen=stim_gen, layer_idx=layer_idx)
    elif isinstance(input_layer, RasterInputLayer):
        return scalar_sta(net, n_samples, stim_gen=stim_gen, layer_idx=layer_idx)
    elif isinstance(input_layer, InputLayer):
        return img_sta(net, n_samples, stim_gen=stim_gen, layer_idx=layer_idx)
    else:
        raise NotImplementedError(
            "STA method has not been specified for input layer type: {}".format(
                type(net.layers[0]).__name__))


def gaussian_blob(x_arr, mean, var_range):
    """ Utility method. returns a gaussian blob centered on mean
    Variance is drawn from var_range

    :param x_arr: 2 dimensional array to fill
    :param mean: 1d array of shape (2, ), probably
    :param var_range: tuple (min_var, max_var)
    :returns: array filled with the blob
    :rtype: array of shape x_arr.shape

    """
    var = np.random.uniform(*var_range)
    return np.exp(- ((x_arr - mean) ** 2) / (2 * var))

def factor(r):
    """ factor r as evenly as possible

    :param r: positive integer
    :returns: the two largest factors
    :rtype: tuple (p, q)
    """
    # prevent pylint from complaining about p,q being bad
    # pylint:disable=c0103
    assert int(r) == r
    # upper bound since int rounds down
    q_max = int(np.sqrt(r) + 1)
    for q in xrange(q_max, 0, -1):
        if r % q == 0:
            return (q, r / q)

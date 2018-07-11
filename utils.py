#!/usr/bin/env python
# coding=utf-8

from __future__ import (print_function, division, absolute_import, unicode_literals)

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import hsv_to_rgb
from sklearn.metrics import adjusted_mutual_info_score


def save_image(filename, image_array):
    import scipy.misc
    if image_array.shape[2] == 1:
        if np.min(image_array) >= 0.:
            scipy.misc.toimage(image_array[:, :, 0], cmin=0.0, cmax=1.0).save(filename)
        else:
            scipy.misc.toimage(image_array[:, :, 0], cmin=-1.0, cmax=1.0).save(filename)
    else:
        scipy.misc.toimage(255*image_array).save(filename)


def delete_files(folder, recursive=False):
    for the_file in os.listdir(folder):
        file_path = os.path.join(folder, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif recursive and os.path.isdir(file_path):
                delete_files(file_path, recursive)
                os.unlink(file_path)
        except Exception as e:
            print(e)


def create_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def print_vars(_vars):
    total_n_vars = 0
    for var in _vars:
        sh = var.get_shape().as_list()
        total_n_vars += np.prod(sh)

        print(var.name, sh)

    print(total_n_vars, 'total variables')

    return total_n_vars


def parse_activation_function(name_list):
    return [ACTIVATION_FUNCTIONS[name] for name in name_list]


def evaluate_groups_seq(true_groups, predicted, weights):
    """ Compute the weighted AMI score and corresponding mean confidence for given gammas.
    :param true_groups: (T, B, 1, W, H, 1)
    :param predicted: (T, B, K, W, H, 1)
    :param weights: (T)
    :return: scores, confidences (B,)
    """
    w_scores, w_confidences = 0., 0.
    assert true_groups.ndim == predicted.ndim == 6, true_groups.shape

    for t in range(true_groups.shape[0]):
        scores, confidences = evaluate_groups(true_groups[t], predicted[t])

        w_scores += weights[t] * np.array(scores)
        w_confidences += weights[t] * np.array(confidences)

    norm = np.sum(weights)

    return w_scores/norm, w_confidences/norm


def evaluate_groups(true_groups, predicted):
    """ Compute the AMI score and corresponding mean confidence for given gammas.
    :param true_groups: (B, 1, W, H, 1)
    :param predicted: (B, K, W, H, 1)
    :return: scores, confidences (B,)
    """
    scores, confidences = [], []
    assert true_groups.ndim == predicted.ndim == 5, true_groups.shape
    batch_size, K = predicted.shape[:2]
    true_groups = true_groups.reshape(batch_size, -1)
    predicted = predicted.reshape(batch_size, K, -1)
    predicted_groups = predicted.argmax(1)
    predicted_conf = predicted.max(1)
    for i in range(batch_size):
        true_group = true_groups[i]
        idxs = np.where(true_group != 0.0)[0]
        scores.append(adjusted_mutual_info_score(true_group[idxs], predicted_groups[i, idxs]))
        confidences.append(np.mean(predicted_conf[i, idxs]))

    return scores, confidences


def color_spines(ax, color, lw=2):
    for sn in ['top', 'bottom', 'left', 'right']:
        ax.spines[sn].set_linewidth(lw)
        ax.spines[sn].set_color(color)
        ax.spines[sn].set_visible(True)


def color_half_spines(ax, color1, color2, lw=2):
    for sn in ['top', 'left']:
        ax.spines[sn].set_linewidth(lw)
        ax.spines[sn].set_color(color1)
        ax.spines[sn].set_visible(True)

    for sn in ['bottom', 'right']:
        ax.spines[sn].set_linewidth(lw)
        ax.spines[sn].set_color(color2)
        ax.spines[sn].set_visible(True)


def get_gamma_colors(nr_colors):
    hsv_colors = np.ones((nr_colors, 3))
    hsv_colors[:, 0] = (np.linspace(0, 1, nr_colors, endpoint=False) + 2/3) % 1.0
    color_conv = hsv_to_rgb(hsv_colors)
    return color_conv


def overview_plot(i, gammas, preds, inputs, corrupted=None, **kwargs):
    attentions = np.array(kwargs['attentions']) if 'attentions' in kwargs else None

    T, B, K, W, H, C = gammas.shape
    T -= 1  # the initialization doesn't count as iteration
    corrupted = corrupted if corrupted is not None else inputs
    gamma_colors = get_gamma_colors(K)

    # restrict to sample i and get rid of useless dims
    inputs = inputs[:, i, 0]
    gammas = gammas[:, i, :, :, :, 0]
    if preds.shape[1] != B:
        preds = preds[:, 0]
    preds = preds[:, i]
    corrupted = corrupted[:, i, 0]

    inputs = np.clip(inputs, 0., 1.)
    preds = np.clip(preds, 0., 1.)
    corrupted = np.clip(corrupted, 0., 1.)

    def plot_img(ax, data, cmap='Greys_r', xlabel=None, ylabel=None, border_color=None):
        if data.shape[-1] == 1:
            ax.matshow(data[:, :, 0], cmap=cmap, vmin=0., vmax=1., interpolation='nearest')
        else:
            ax.imshow(data, interpolation='nearest')
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_xlabel(xlabel, color=border_color or 'k') if xlabel else None
        ax.set_ylabel(ylabel, color=border_color or 'k') if ylabel else None
        if border_color:
            color_spines(ax, color=border_color)

    def plot_attention_summary_img(ax, attention, k_excluded, preds, cmap='Greys_r', xlabel=None, ylabel=None, border_color=None):
        # copy so we don't mutate
        preds = np.copy(preds)
        attention = np.copy(attention)

        # get focus object as rgb version of black-white
        focus_pred = np.tile(np.copy(preds[k_excluded]), [1, 1, 3])

        # we are safe to do what we want to do to the k_excluded row
        preds[k_excluded] = 0  
        attention = np.insert(attention, k_excluded, 0)  # zero out the focus object

        # mask preds by attention
        preds = np.transpose(preds[:, :, :, 0], [1, 2, 0]) # (28, 28, K)
        preds *= attention

        # color the preds
        preds = preds.reshape(-1, preds.shape[-1]).dot(gamma_colors).reshape(preds.shape[:-1] + (3,))

        # add in the focus object
        preds += focus_pred

        # plot
        ax.imshow(preds, interpolation='nearest')
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_xlabel(xlabel, color=border_color or 'k') if xlabel else None
        ax.set_ylabel(ylabel, color=border_color or 'k') if ylabel else None
        if border_color:
            color_spines(ax, color=border_color)

    def plot_gamma(ax, gamma, xlabel=None, ylabel=None):
        gamma = np.transpose(gamma, [1, 2, 0])
        gamma = gamma.reshape(-1, gamma.shape[-1]).dot(gamma_colors).reshape(gamma.shape[:-1] + (3,))
        ax.imshow(gamma, interpolation='nearest')
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel(xlabel) if xlabel else None
        ax.set_ylabel(ylabel) if ylabel else None

    nrows, ncols = (K + 4, T + 1)
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols,
                             figsize=(2 * ncols, 2 * nrows))

    axes[0, 0].set_visible(False)
    axes[1, 0].set_visible(False)
    plot_gamma(axes[2, 0], gammas[0], ylabel='Gammas')
    for k in range(K + 1):
        axes[k + 3, 0].set_visible(False)
    for t in range(1, T + 1):
        g = gammas[t]
        p = preds[t]

        reconst = np.sum(g[:, :, :, None] * p, axis=0)
        plot_img(axes[0, t], inputs[t])
        plot_img(axes[1, t], reconst)
        plot_gamma(axes[2, t], g)
        for k in range(K):
            if attentions is not None:
                plot_attention_summary_img(axes[k + 3, t], attentions[t-1, i, k], k, p,
                     border_color=tuple(gamma_colors[k]),
                     ylabel=('contexts {} for {}'.format(k-1, k) if t == 1 else None))
            else:
                plot_img(axes[k + 3, t], p[k], border_color=tuple(gamma_colors[k]), ylabel=('mu_{}'.format(k) if t == 1 else None))

        plot_img(axes[K + 3, t], corrupted[t - 1])
    plt.subplots_adjust(hspace=0.1, wspace=0.1)
    return fig


def curve_plot(values_dict, coarse_range, fine_range):
    if fine_range is not None:
        fig, ax = plt.subplots(1, 2, figsize=(40, 10))
    else:
        fig, ax = plt.subplots(1, 1, figsize=(20, 10))
        ax = [ax]

    for key, values in values_dict.items():
        # coarse
        ax[0].plot(values, label=key)
        ax[0].set_xlabel('epochs')
        ax[0].axis([0, len(values), coarse_range[0], coarse_range[1]])
        ax[0].set_title("coarse range")
        ax[0].legend()

        # fine
        if fine_range is not None:
            ax[1].plot(values, label=key)
            ax[1].set_xlabel('epochs')
            ax[1].axis([0, len(values), fine_range[0], fine_range[1]])
            ax[1].set_title("fine range")
            ax[1].legend()

    return fig


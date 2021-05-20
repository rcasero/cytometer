"""
Contour segmentation of dmaps for all data (no folds) using binary crossentropy (only KLF14).

Like 0070, but with:
    * 10 folds instead of 11, generated by exp 0079.
    * Using dmap model generated by exp 0081, instead 0056.
Like 0083, but with:
    * 500 epochs instead of 100.
Like 0087, but with:
    * BatchNormalization after each layer.
Like 0091, but with:
    * All data used for training, no folds used.

Training vs testing is done at the histology slide level, not at the window level. This way, we really guarantee that
the network has not been trained with data sampled from the same image as the test data.

Training for the CNN:
* Input: dmaps
* Output: hand tracked contours, dilated a bit.
* Other: mask for the loss function, to avoid looking outside of where we have contours.
"""

"""
This file is part of Cytometer
Copyright 2021 Medical Research Council
SPDX-License-Identifier: Apache-2.0
Author: Ramon Casero <rcasero@gmail.com>
"""

# # HACK
# import sys; print('Python %s on %s' % (sys.version, sys.platform))
# sys.path.extend(['/home/rcasero/Software/cytometer', '/home/rcasero/Software/keras_sample_weight', '/home/rcasero/Software/cytometer'])


experiment_id = 'klf14_b6ntac_exp_0102_cnn_contour_after_dmap'

# cross-platform home directory
from pathlib import Path
home = str(Path.home())

# PyCharm automatically adds cytometer to the python path, but this doesn't happen if the script is run
# with "python scriptname.py"
import os
import sys
sys.path.extend([os.path.join(home, 'Software/cytometer')])
import json
import pickle
import warnings

# other imports
import datetime
import numpy as np
import cv2
import matplotlib.pyplot as plt

# # limit number of GPUs
# os.environ['CUDA_VISIBLE_DEVICES'] = '0,1,2,3'

os.environ['KERAS_BACKEND'] = 'tensorflow'
import keras
import keras.backend as K

from keras.models import Model
from keras.layers import Input, Conv2D, MaxPooling2D, AvgPool2D, Activation, BatchNormalization

# for data parallelism in keras models
from keras.utils import multi_gpu_model

import cytometer.data
import cytometer.model_checkpoint_parallel
import tensorflow as tf

LIMIT_GPU_MEMORY = False

# limit GPU memory used
if LIMIT_GPU_MEMORY:
    from keras.backend.tensorflow_backend import set_session
    config = tf.ConfigProto()
    config.gpu_options.per_process_gpu_memory_fraction = 0.95
    set_session(tf.Session(config=config))

# specify data format as (n, row, col, channel)
K.set_image_data_format('channels_last')

DEBUG = False

# number of blocks to split each image into so that training fits into GPU memory
nblocks = 2

# number of epochs for training
epochs = 500

# this is used both in dmap.predict(im) and in training of the contour model
batch_size = 10

'''Directories and filenames
'''

# data paths
root_data_dir = os.path.join(home, 'Data/cytometer_data/klf14')
training_dir = os.path.join(root_data_dir, 'klf14_b6ntac_training')
training_non_overlap_data_dir = os.path.join(root_data_dir, 'klf14_b6ntac_training_non_overlap')
training_augmented_dir = os.path.join(root_data_dir, 'klf14_b6ntac_training_augmented')
saved_models_dir = os.path.join(root_data_dir, 'saved_models')

saved_kfolds_filename = 'klf14_b6ntac_exp_0079_generate_kfolds.pickle'
dmap_model_basename = 'klf14_b6ntac_exp_0101_cnn_dmap'

'''CNN Model
'''


def fcn_sherrah2016_classifier(input_shape, for_receptive_field=False):


    def activation_if(for_receptive_field, x):
        if for_receptive_field:
            # for estimation of receptive field, we need to use linear operators
            x = Activation('linear')(x)
            x = BatchNormalization(axis=3)(x)
        else:
            # for regular training and inference, we use non-linear operators
            x = Activation('relu')(x)
            x = BatchNormalization(axis=3)(x)
        return x

    def activation_pooling_if(for_receptive_field, pool_size, x):
        if for_receptive_field:
            # for estimation of receptive field, we need to use linear operators
            x = Activation('linear')(x)
            x = AvgPool2D(pool_size=pool_size, strides=1, padding='same')(x)
            x = BatchNormalization(axis=3)(x)
        else:
            # for regular training and inference, we use non-linear operators
            x = Activation('relu')(x)
            x = MaxPooling2D(pool_size=pool_size, strides=1, padding='same')(x)
            x = BatchNormalization(axis=3)(x)
        return x

    input = Input(shape=input_shape, dtype='float32', name='input_image')

    x = Conv2D(filters=32, kernel_size=(5, 5), strides=1, dilation_rate=1, padding='same')(input)
    x = activation_pooling_if(for_receptive_field=for_receptive_field, pool_size=(3, 3), x=x)

    x = Conv2D(filters=48, kernel_size=(5, 5), strides=1, dilation_rate=2, padding='same')(x)
    x = activation_pooling_if(for_receptive_field=for_receptive_field, pool_size=(5, 5), x=x)

    x = Conv2D(filters=64, kernel_size=(3, 3), strides=1, dilation_rate=4, padding='same')(x)
    x = activation_pooling_if(for_receptive_field=for_receptive_field, pool_size=(9, 9), x=x)

    x = Conv2D(filters=98, kernel_size=(3, 3), strides=1, dilation_rate=8, padding='same')(x)
    x = activation_pooling_if(for_receptive_field=for_receptive_field, pool_size=(17, 17), x=x)

    x = Conv2D(filters=256, kernel_size=(3, 3), strides=1, dilation_rate=16, padding='same')(x)
    x = activation_if(for_receptive_field=for_receptive_field, x=x)

    # dimensionality reduction to 1 feature map
    x = Conv2D(filters=64, kernel_size=(1, 1), strides=1, dilation_rate=1, padding='same')(x)
    x = activation_if(for_receptive_field=for_receptive_field, x=x)

    x = Conv2D(filters=8, kernel_size=(1, 1), strides=1, dilation_rate=1, padding='same')(x)
    x = activation_if(for_receptive_field=for_receptive_field, x=x)

    x = Conv2D(filters=1, kernel_size=(1, 1), strides=1, dilation_rate=1, padding='same')(x)

    # classification output
    classification_output = Activation('hard_sigmoid', name='classification_output')(x)

    return Model(inputs=input, outputs=[classification_output])


'''Load folds (we are not going to use folds, but we still want the file list)'''

# load list of images, and indices for training vs. testing indices
contour_model_kfold_filename = os.path.join(saved_models_dir, saved_kfolds_filename)
with open(contour_model_kfold_filename, 'rb') as f:
    aux = pickle.load(f)
svg_file_list = aux['file_list']

# correct home directory
svg_file_list = [x.replace('/home/rcasero', home) for x in svg_file_list]

'''Model training'''

# TIFF files that correspond to the SVG files (without augmentation)
im_orig_file_list = []
for i, file in enumerate(svg_file_list):
    im_orig_file_list.append(file.replace('.svg', '.tif'))
    im_orig_file_list[i] = os.path.join(os.path.dirname(im_orig_file_list[i]) + '_augmented',
                                        'im_seed_nan_' + os.path.basename(im_orig_file_list[i]))

    # check that files exist
    if not os.path.isfile(file):
        warnings.warn('i = ' + str(i) + ': File does not exist: ' + os.path.basename(file))
    if not os.path.isfile(im_orig_file_list[i]):
        warnings.warn('i = ' + str(i) + ': File does not exist: ' + os.path.basename(im_orig_file_list[i]))

# output filenames
saved_model_filename = os.path.join(saved_models_dir, experiment_id + '_model.h5')
saved_logs_dir = os.path.join(saved_models_dir, experiment_id + '_logs')

'''Load data
'''

# add the augmented image files
im_orig_file_list = cytometer.data.augment_file_list(im_orig_file_list, '_nan_', '_*_')

# load the train and test data (im, dmap, mask)
train_dataset, train_file_list, train_shuffle_idx = \
    cytometer.data.load_datasets(im_orig_file_list, prefix_from='im', prefix_to=['im', 'mask', 'contour'],
                                 nblocks=nblocks, shuffle_seed=0)

# remove training data where the mask has very few valid pixels (note: this will discard all the images without
# cells)
train_dataset = cytometer.data.remove_poor_data(train_dataset, prefix='contour', threshold=1900)

# remove indices as necessary so that the number of training images is a multiple of the batch size.
# This prevents BatchNormalization produce NaNs when a batch has 1 sample
len_train = (train_dataset['im'].shape[0] // batch_size) * batch_size
train_dataset['im'] = train_dataset['im'][0:len_train, ...]
train_dataset['mask'] = train_dataset['mask'][0:len_train, ...]
train_dataset['contour'] = train_dataset['contour'][0:len_train, ...]

# add seg pixels to the mask, because the mask doesn't fully cover the contour
train_dataset['mask'] = np.logical_or(train_dataset['mask'], train_dataset['contour'])

# fill in the little gaps in the mask
kernel = np.ones((3, 3), np.uint8)
for i in range(train_dataset['mask'].shape[0]):
    train_dataset['mask'][i, :, :, 0] = cv2.dilate(train_dataset['mask'][i, :, :, 0].astype(np.uint8),
                                                   kernel=kernel, iterations=1)

# cast types for training
train_dataset['contour'] = train_dataset['contour'].astype(np.float32)
train_dataset['mask'] = train_dataset['mask'].astype(np.float32)

if DEBUG:
    for i in range(train_dataset[list(train_dataset.keys())[0]].shape[0]):
        plt.clf()
        for pi, prefix in enumerate(train_dataset.keys()):
            plt.subplot(1, len(train_dataset.keys()), pi + 1)
            if train_dataset[prefix].shape[-1] < 3:
                plt.imshow(train_dataset[prefix][i, :, :, 0])
            else:
                plt.imshow(train_dataset[prefix][i, :, :, :])
            plt.title('out[' + prefix + ']')
            plt.axis('off')
        plt.title('out[' + prefix + ']: i = ' + str(i))
        plt.pause(0.75)

'''Estimate dmaps'''

# load dmap model that we are going to use as the basis for the contour model
dmap_model_filename = os.path.join(saved_models_dir, dmap_model_basename + '_model.h5')
dmap_model = keras.models.load_model(dmap_model_filename)

# replace histology images by the estimated dmaps. The reason to replace instead of creating a new 'dmap' object is
# to save memory
train_dataset['im'] = dmap_model.predict(train_dataset['im'], batch_size)


'''Convolutional neural network training

Note: you need to use my branch of keras with the new functionality, that allows element-wise weights of the loss
function
'''

# list all CPUs and GPUs
device_list = K.get_session().list_devices()

# number of GPUs
gpu_number = np.count_nonzero([':GPU:' in str(x) for x in device_list])

# instantiate contour model
with tf.device('/cpu:0'):
    contour_model = fcn_sherrah2016_classifier(input_shape=train_dataset['im'].shape[1:])

# delete dmap model
del dmap_model

# checkpoint to save model after each epoch
checkpointer = cytometer.model_checkpoint_parallel.ModelCheckpoint(filepath=saved_model_filename,
                                                                   verbose=1, save_best_only=False)

# callback to write a log for TensorBoard
# Note: run this on the server where the training is happening:
#       tensorboard --logdir=saved_logs_dir
tensorboard = keras.callbacks.TensorBoard(log_dir=saved_logs_dir)

# compile model
parallel_model = multi_gpu_model(contour_model, gpus=gpu_number)
parallel_model.compile(loss={'classification_output': 'binary_crossentropy'},
                       optimizer='Adadelta',
                       metrics={'classification_output': 'accuracy'},
                       sample_weight_mode='element')

# train model
tic = datetime.datetime.now()
hist = parallel_model.fit(train_dataset['im'],
                          {'classification_output': train_dataset['contour']},
                          sample_weight={'classification_output': train_dataset['mask'][..., 0]},
                          batch_size=batch_size, epochs=epochs, initial_epoch=0,
                          callbacks=[checkpointer, tensorboard])
toc = datetime.datetime.now()
print('Training duration: ' + str(toc - tic))

# cast history values to a type that is JSON serializable
history = hist.history
for key in history.keys():
    history[key] = list(map(float, history[key]))

# save training history
history_filename = os.path.join(saved_models_dir, experiment_id + '_history.json')
with open(history_filename, 'w') as f:
    json.dump(history, f)


if DEBUG:
    history_filename = os.path.join(saved_models_dir, experiment_id + '_history.json')

    with open(history_filename, 'r') as f:
        history = json.load(f)

    plt.clf()
    plt.subplot(221)
    plt.plot(history['acc'], label='acc')
    plt.legend()
    plt.subplot(222)
    plt.plot(history['val_acc'], label='val_acc')
    plt.legend()
    plt.subplot(223)
    plt.plot(history['loss'], label='loss')
    plt.legend()
    plt.subplot(224)
    plt.plot(history['val_loss'], label='val_loss')
    plt.legend()

#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 28 11:43:58 2017

Script to run the training of a DeepCell network

This on current hardware (NVIDIA K4000) would take around 29 h for 25 epoch

@author: Ramon Casero <rcasero@gmail.com>
"""

"""
This file is part of Cytometer
Copyright 2021 Medical Research Council
SPDX-License-Identifier: Apache-2.0
Author: Ramon Casero <rcasero@gmail.com>
"""

import os
import numpy as np
import datetime

###############################################################################
## Keras configuration

# Keras backend
os.environ['KERAS_BACKEND'] = 'theano'
os.environ['OMP_NUM_THREADS'] = '6'

# access to python libraries
if 'LIBRARY_PATH' in os.environ:
    os.environ['LIBRARY_PATH'] = os.environ['CONDA_PREFIX'] + '/lib:' + os.environ['LIBRARY_PATH']
else:
    os.environ['LIBRARY_PATH'] = os.environ['CONDA_PREFIX'] + '/lib'

# configure Theano global options
#os.environ['THEANO_FLAGS'] = 'floatX=float32,device=cuda0,gpuarray.preallocate=0.5'
#os.environ['THEANO_FLAGS'] = 'floatX=float32,device=cuda0,lib.cnmem=0.75'
os.environ['THEANO_FLAGS'] = 'floatX=float32,device=gpu'

# configure Theano
if os.environ['KERAS_BACKEND'] == 'theano':
    import theano
    theano.config.enabled = True
    theano.config.dnn.include_path = os.environ['CONDA_PREFIX'] + '/include'
    theano.config.dnn.library_path = os.environ['CONDA_PREFIX'] + '/lib'
    theano.config.blas.ldflags = '-lblas -lgfortran'
    theano.config.nvcc.fastmath = True
    theano.config.nvcc.flags = '-D_FORCE_INLINES'
    theano.config.cxx = os.environ['CONDA_PREFIX'] + '/bin/g++'
else :
    raise Exception('No configuration found when the backend is ' + os.environ['KERAS_BACKEND'])

# import and check Keras version
import keras
import keras.backend as K
from keras import __version__ as keras_version
from pkg_resources import parse_version
if (parse_version(keras_version) >= parse_version('2.0')):
    raise RuntimeError('DeepCell requires Keras 1 to run')

# configure Keras, to avoid using file ~/.keras/keras.json
K.set_image_dim_ordering('th') # theano's image format (required by DeepCell)
K.set_floatx('float32')
K.set_epsilon('1e-07')

##
###############################################################################


from __future__ import print_function
from keras.optimizers import SGD, RMSprop
from keras.callbacks import ModelCheckpoint, LearningRateScheduler

import cytometer
from cytometer.deepcell import rate_scheduler, train_model_sample, get_data_sample
from cytometer.deepcell_models import bn_feature_net_61x61 as the_model

dataset = "3T3_all_61x61"
expt = "bn_feature_net_61x61"

outdir = "/tmp"
basedatadir = os.path.normpath(os.path.join(cytometer.__path__[0], '../data/deepcell'))
#netdir = os.path.join(basedatadir, 'trained_networks')
#wikidir = os.path.normpath(os.path.join(cytometer.__path__[0], '../../cyto￼meter.wiki'))
datadir = os.path.join(basedatadir, 'training_data_npz', '3T3')
datafile = os.path.join(datadir, dataset + '.npz')

# training objects
optimizer = SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
lr_sched = rate_scheduler(lr = 0.01, decay = 0.95)

# training parameters
batch_size = 256
n_epoch = 25
rotate = True
flip = True
shear = False
class_weight = None

for it in xrange(5):

	model = the_model(n_channels = 2, n_features = 3, reg = 1e-5)

	todays_date = datetime.datetime.now().strftime("%Y-%m-%d")

	file_name_save = os.path.join(outdir, todays_date + "_" + dataset + "_" + expt + "_" + str(it)  + ".h5")

	file_name_save_loss = os.path.join(outdir, todays_date + "_" + dataset + "_" + expt + "_" + str(it) + ".npz")

	train_dict, (X_test, Y_test) = get_data_sample(datafile)

	# the data, shuffled and split between train and test sets
	print('X_train shape:', train_dict["channels"].shape)
	print(train_dict["pixels_x"].shape[0], 'train samples')
	print(X_test.shape[0], 'test samples')

	# determine the number of classes
	output_shape = model.layers[-1].output_shape
	n_classes = output_shape[-1]

	# convert class vectors to binary class matrices
	train_dict["labels"] = keras.utils.np_utils.to_categorical(train_dict["labels"], n_classes)
	Y_test = keras.utils.np_utils.to_categorical(Y_test, n_classes)

	model.compile(loss='categorical_crossentropy',
				  optimizer=optimizer,
				  metrics=['accuracy'])

	print('Using real-time data augmentation.')

	# this will do preprocessing and realtime data augmentation
	datagen = cytometer.deepcell.ImageDataGenerator(
		rotate = rotate,  # randomly rotate images by 90 degrees
		shear_range = shear, # randomly shear images in the range (radians , -shear_range to shear_range)
		horizontal_flip= flip,  # randomly flip images
		vertical_flip= flip)  # randomly flip images

	# fit the model on the batches generated by datagen.flow()
	loss_history = model.fit_generator(datagen.sample_flow(train_dict, batch_size=batch_size),
						samples_per_epoch=len(train_dict["labels"]),
						nb_epoch=n_epoch,
						validation_data=(X_test, Y_test),
						class_weight = class_weight,
						callbacks = [ModelCheckpoint(file_name_save, monitor = 'val_loss', verbose = 0, save_best_only = True, mode = 'auto'),
							LearningRateScheduler(lr_sched)])

	np.savez(file_name_save_loss, loss_history = loss_history.history)

	del model
	from keras.backend.common import _UID_PREFIXES
	for key in _UID_PREFIXES.keys():
		_UID_PREFIXES[key] = 0
        






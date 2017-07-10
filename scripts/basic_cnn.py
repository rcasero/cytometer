#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 26 18:32:40 2017

@author: Ramón Casero <rcasero@gmail.com>

Simple script to train deepcell_models.bn_feature_net_31x31.

On my hardware (8 Intel(R) Core(TM) i7-4770 CPU @ 3.40GHz, with 
nVidia Quadro K4000 GPU):
    
    * Tensorflow, GPU: 14.5 days
    * Theano, CPU (4 threads): 5.6 days
    * Theano, GPU, cuDNN: 5.5 days

"""

import os
os.environ['KERAS_BACKEND'] = 'theano'
#os.environ['KERAS_BACKEND'] = 'tensorflow'

os.environ['LIBRARY_PATH'] = '/home/rcasero/.conda/envs/cytometer_py36/lib'

from importlib import reload
import keras

# configure Keras, to avoid using file ~/.keras/keras.json
keras.backend.set_image_data_format('channels_first') # theano's image format (required by DeepCell)

# load module dependencies
import datetime
import matplotlib.pyplot as plt
import numpy as np

import cytometer.deepcell as deepcell
import cytometer.deepcell_models as deepcell_models
#reload(deepcell)
#reload(deepcell_models)


direc_data = "/home/rcasero/Software/cytometer/data/deepcell/training_data_npz/slip"
dataset = "slip_31x31"
direc_save = "/home/rcasero/Software/cytometer/data/deepcell/trained_networks/slip"
expt = "bn_feature_net_31x31"


it = 0 # iteration
batch_size = 256
n_epoch = 1

training_data_file_name = os.path.join(direc_data, dataset + ".npz")
todays_date = datetime.datetime.now().strftime("%Y-%m-%d")

file_name_save = os.path.join(direc_save, todays_date + "_" + dataset + "_" + expt + "_" + str(it)  + ".h5")

file_name_save_loss = os.path.join(direc_save, todays_date + "_" + dataset + "_" + expt + "_" + str(it) + ".npz")

train_dict, (X_test, Y_test) = deepcell.get_data_sample(training_data_file_name)

# the data, shuffled and split between train and test sets
print('X_train shape:', train_dict["channels"].shape)
print(train_dict["pixels_x"].shape[0], 'train samples')
print(X_test.shape[0], 'test samples')

# plot some examples of training data with the central pixel (red dot)
plt.subplot(221)
plt.imshow(np.squeeze(X_test[0, :, :, :]))
plt.plot(15, 15, 'ro')
plt.title('1')
plt.subplot(222)
plt.imshow(np.squeeze(X_test[24166, :, :, :]))
plt.plot(15, 15, 'ro')
plt.title('2')
plt.subplot(223)
plt.imshow(np.squeeze(X_test[48333, :, :, :]))
plt.plot(15, 15, 'ro')
plt.title('3')
plt.subplot(224)
plt.imshow(np.squeeze(X_test[72501, :, :, :]))
plt.plot(15, 15, 'ro')
plt.title('4')

# corresponding training labels
Y_test[[0, 24166, 48333, 72501]]
    
# load model
model = deepcell_models.bn_feature_net_31x31()

# determine the number of classes
output_shape = model.layers[-1].output_shape
n_classes = output_shape[-1]

# convert class vectors to binary class matrices
train_dict["labels"] = deepcell.np_utils.to_categorical(train_dict["labels"], n_classes)
Y_test = deepcell.np_utils.to_categorical(Y_test, n_classes)

optimizer = keras.optimizers.SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
lr_sched = deepcell.rate_scheduler(lr = 0.01, decay = 0.95)
class_weight = {0:1, 1:1, 2:1}

model.compile(loss='categorical_crossentropy',
			  optimizer=optimizer,
			  metrics=['accuracy'])

rotate = True
flip = True
shear = False

# this will do preprocessing and realtime data augmentation
datagen = deepcell.ImageDataGenerator(
	rotate = rotate,  # randomly rotate images by 90 degrees
	shear_range = shear, # randomly shear images in the range (radians , -shear_range to shear_range)
	horizontal_flip= flip,  # randomly flip images
	vertical_flip= flip)  # randomly flip images

# fit the model on the batches generated by datagen.flow()
loss_history = model.fit_generator(datagen.sample_flow(train_dict, batch_size=batch_size),
                                   steps_per_epoch=len(train_dict["labels"]),
                                   epochs=n_epoch,
                                   validation_data=(X_test, Y_test),
                                   class_weight = class_weight,
                                   callbacks = [
                                           deepcell.ModelCheckpoint(file_name_save, monitor = 'val_loss', verbose = 0, save_best_only = True, mode = 'auto'),
                                           deepcell.LearningRateScheduler(lr_sched)
                                           ])

# save trained model
model.save(file_name_save_loss)

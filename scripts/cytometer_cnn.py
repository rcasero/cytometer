#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 17 15:40:00 2018

@author: rcasero
"""

import os
import glob
import keras
import keras.backend as K
import importlib
import numpy as np
import cytometer.models as models
from PIL import Image

# load module dependencies
#import datetime
#import matplotlib.pyplot as plt


os.environ['KERAS_BACKEND'] = 'tensorflow'

# different versions of conda keep the path in different variables
if 'CONDA_ENV_PATH' in os.environ:
    conda_env_path = os.environ['CONDA_ENV_PATH']
elif 'CONDA_PREFIX' in os.environ:
    conda_env_path = os.environ['CONDA_PREFIX']
else:
    conda_env_path = '.'

os.environ['PYTHONPATH'] = os.path.join(os.environ['HOME'], 'Software', 'cytometer', 'cytometer') \
                           + ':' + os.environ['PYTHONPATH']

# configure Keras, to avoid using file ~/.keras/keras.json
K.set_image_dim_ordering('tf')
K.set_floatx('float32')
K.set_epsilon(1e-07)
# fix "RuntimeError: Invalid DISPLAY variable" in cluster runs
# import matplotlib
# matplotlib.use('agg')

# DEBUG: used while developing the software, not for production
importlib.reload(models)

model = models.basic_9c3mp()


# rate scheduler from DeepCell
def rate_scheduler(lr = .001, decay = 0.95):
    def output_fn(epoch):
        epoch = np.int(epoch)
        new_lr = lr * (decay ** epoch)
        return new_lr
    return output_fn


optimizer = keras.optimizers.SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
lr_sched = rate_scheduler(lr=0.01, decay=0.95)
# class_weight = {0: 1, 1: 1, 2: 1}

model.compile(loss='categorical_crossentropy',
              optimizer=optimizer,
              metrics=['accuracy'])

# DEBUG: model visualisation
# model.summary()
# from keras.utils import plot_model
# plot_model(model, to_file='/tmp/model.png', show_shapes=True)


def load_list_of_files(file_list):
    Nfiles = len(file_list)
    file_list.sort()
    print(file_list)
    im = np.array(Image.open(file_list[0]))
    data = np.zeros((Nfiles,) + im.shape, dtype=im.dtype)
    data[0, ] = im
    for i, filename in enumerate(file_list[1:]):
        im = Image.open(filename)
        data[i, ] = im
    return data


# load Lorna's hand segmented data
data_dir = os.path.join('data', 'adipocyte_500x500_patches')
data_im = load_list_of_files(glob.glob(os.path.join(data_dir, '*_rgb.tif')))
data_seg = load_list_of_files(glob.glob(os.path.join(data_dir, '*_seg.tif')))

it = 0  # iteration
batch_size = 256
n_epoch = 25

training_data_file_name = os.path.join(direc_data, dataset + ".npz")
todays_date = datetime.datetime.now().strftime("%Y-%m-%d")

file_name_save = os.path.join(direc_save, todays_date + "_" + dataset + "_" + expt + "_" + str(it) + ".h5")

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
model = deepcell_models.sparse_feature_net_61x61()

# determine the number of classes
output_shape = model.layers[-1].output_shape
n_classes = output_shape[-1]

# convert class vectors to binary class matrices
train_dict["labels"] = deepcell.np_utils.to_categorical(train_dict["labels"], n_classes)
Y_test = deepcell.np_utils.to_categorical(Y_test, n_classes)

optimizer = keras.optimizers.SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
lr_sched = deepcell.rate_scheduler(lr=0.01, decay=0.95)
class_weight = {0: 1, 1: 1, 2: 1}

model.compile(loss='categorical_crossentropy',
              optimizer=optimizer,
              metrics=['accuracy'])

rotate = True
flip = True
shear = False

# this will do preprocessing and realtime data augmentation
datagen = deepcell.ImageDataGenerator(
    rotate=rotate,  # randomly rotate images by 90 degrees
    shear_range=shear,  # randomly shear images in the range (radians , -shear_range to shear_range)
    horizontal_flip=flip,  # randomly flip images
    vertical_flip=flip)  # randomly flip images

# fit the model on the batches generated by datagen.flow()
loss_history = model.fit_generator(datagen.sample_flow(train_dict, batch_size=batch_size),
                                   steps_per_epoch=len(train_dict["labels"]),
                                   epochs=n_epoch,
                                   validation_data=(X_test, Y_test),
                                   class_weight=class_weight,
                                   callbacks=[
                                       deepcell.ModelCheckpoint(file_name_save, monitor='val_loss', verbose=0,
                                                                save_best_only=True, mode='auto'),
                                       deepcell.LearningRateScheduler(lr_sched)
                                   ])

# save trained model
model.save(file_name_save_loss)

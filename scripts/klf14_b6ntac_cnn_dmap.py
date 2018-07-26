# cross-platform home directory
from pathlib import Path
home = str(Path.home())

# PyCharm automatically adds cytometer to the python path, but this doesn't happen if the script is run
# with "python scriptname.py"
import os
import sys
sys.path.extend([os.path.join(home, 'Software/cytometer'),
                 os.path.join(home, 'Software/cytometer')])

# other imports
import glob
import datetime
import numpy as np
import pysto.imgproc as pystoim
import matplotlib.pyplot as plt
from PIL import Image

# use CPU for testing on laptop
#os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"   # see issue #152
#os.environ["CUDA_VISIBLE_DEVICES"] = ""

# limit number of GPUs
os.environ['CUDA_VISIBLE_DEVICES'] = '0,3'

# set display for the server
#os.environ['DISPLAY'] = 'localhost:11.0'

os.environ['KERAS_BACKEND'] = 'tensorflow'
import keras
import keras.backend as K
import cytometer.data
import cytometer.models as models

# limit GPU memory used
import tensorflow as tf
from keras.backend.tensorflow_backend import set_session
config = tf.ConfigProto()
config.gpu_options.per_process_gpu_memory_fraction = 0.9
set_session(tf.Session(config=config))

# for data parallelism in keras models
from keras.utils import multi_gpu_model


DEBUG = False
batch_size = 1


'''Load data
'''

# data paths
root_data_dir = os.path.join(home, 'Dropbox/klf14')
training_dir = os.path.join(home, 'Dropbox/klf14/klf14_b6ntac_training')
training_non_overlap_data_dir = os.path.join(root_data_dir, 'klf14_b6ntac_training_non_overlap')
training_augmented_dir = os.path.join(home, 'Dropbox/klf14/klf14_b6ntac_training_augmented')
saved_models_dir = os.path.join(home, 'Dropbox/klf14/saved_models')

# list of segmented files
seg_file_list = glob.glob(os.path.join(training_non_overlap_data_dir, '*.tif'))

# list of corresponding image patches
im_file_list = [seg_file.replace(training_non_overlap_data_dir, training_dir) for seg_file in seg_file_list]

# load segmentations and compute distance maps
dmap, mask, seg = cytometer.data.load_watershed_seg_and_compute_dmap(seg_file_list)

# load corresponding images and convert to float format
im = cytometer.data.load_im_file_list_to_array(im_file_list)
im = im.astype('float32', casting='safe')
im /= 255

# number of training images
n_im = im.shape[0]

# TODO here load data from the augmentation script

# # remove a 1-pixel thick border so that images are 999x999 and we can split them into 3x3 tiles
# dmap = dmap[:, 1:-1, 1:-1, :]
# mask = mask[:, 1:-1, 1:-1, :]
# seg = seg[:, 1:-1, 1:-1, :]
# im = im[:, 1:-1, 1:-1, :]

# remove a 1-pixel so that images are 1000x1000 and we can split them into 2x2 tiles
dmap = dmap[:, 0:-1, 0:-1, :]
mask = mask[:, 0:-1, 0:-1, :]
seg = seg[:, 0:-1, 0:-1, :]
im = im[:, 0:-1, 0:-1, :]

# split images into smaller blocks to avoid GPU memory overflows in training
dmap_slices, dmap_blocks, _ = pystoim.block_split(dmap, nblocks=(1, 2, 2, 1))
im_slices, im_blocks, _ = pystoim.block_split(im, nblocks=(1, 2, 2, 1))
mask_slices, mask_blocks, _ = pystoim.block_split(mask, nblocks=(1, 2, 2, 1))

dmap_split = np.concatenate(dmap_blocks, axis=0)
im_split = np.concatenate(im_blocks, axis=0)
mask_split = np.concatenate(mask_blocks, axis=0)

# find images that have no valid pixels, to remove them from the dataset
idx_to_keep = np.sum(np.sum(np.sum(mask_split, axis=3), axis=2), axis=1)
idx_to_keep = idx_to_keep != 0

dmap_split = dmap_split[idx_to_keep, :, :, :]
im_split = im_split[idx_to_keep, :, :, :]
mask_split = mask_split[idx_to_keep, :, :, :]


'''CNN

Note: you need to use my branch of keras with the new functionality, that allows element-wise weights of the loss
function
'''

# declare network model
with tf.device('/cpu:0'):
    model = models.fcn_sherrah2016_modified(input_shape=im_split.shape[1:])
#model.load_weights(os.path.join(saved_models_dir, 'foo.h5'))

# list all CPUs and GPUs
device_list = K.get_session().list_devices()

# number of GPUs
gpu_number = np.count_nonzero(['GPU' in str(x) for x in device_list])

if gpu_number > 1:  # compile and train model: Multiple GPUs

    # compile model
    parallel_model = multi_gpu_model(model, gpus=gpu_number)
    parallel_model.compile(loss='mse', optimizer='adam', metrics=['mse', 'mae'], sample_weight_mode='element')

    # train model
    tic = datetime.datetime.now()
    parallel_model.fit(im_split, dmap_split, batch_size=1, epochs=10, validation_split=.1,
                       sample_weight=mask_split)
    toc = datetime.datetime.now()
    print('Training duration: ' + str(toc - tic))

else:  # compile and train model: One GPU

    # compile model
    model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
    # model.compile(loss='mse', optimizer='adam', metrics=['accuracy'])

    # train model
    tic = datetime.datetime.now()
    model.fit(im_split, mask_split, batch_size=1, epochs=10, validation_split=.1)
    toc = datetime.datetime.now()
    print('Training duration: ' + str(toc - tic))

# save result (note, we save the template model, not the multiparallel object)
saved_model_filename = os.path.join(saved_models_dir, datetime.datetime.utcnow().isoformat() + '_fcn_sherrah2016_modified.h5')
saved_model_filename = saved_model_filename.replace(':', '_')
model.save(saved_model_filename)


'''==================================================================================================================
OLD CODE
=====================================================================================================================
'''

# ## TODO: Once we have things working with plain np.ndarrays, we'll look into data augmentation, flows, etc. (below)
#
#
# # fits the model on batches with real-time data augmentation:
# model.fit_generator(datagen.flow(x_train, y_train, batch_size=32),
#                     steps_per_epoch=len(x_train) / 32, epochs=epochs)
#
# # combine generators into one which yields image and masks
# train_generator = zip(image_generator, mask_generator)
#
# # train model
# model.fit_generator(
#     train_generator,
#     steps_per_epoch=10,
#     epochs=n_epoch)
#
# val = np.array([[1, 2], [3, 4]])
# kvar = K.variable(value=val, dtype='float64', name='example_var')
# K.eval(kvar * kvar)
#
#
#
# """
# image_generator = image_datagen.flow_from_directory(
#     'data/images',
#     class_mode=None,
#     seed=seed)
#
# mask_generator = mask_datagen.flow_from_directory(
#     'data/masks',
#     class_mode=None,
#     seed=seed)
#
# # combine generators into one which yields image and masks
# train_generator = zip(image_generator, mask_generator)
#
# model.fit_generator(
#     train_generator,
#     steps_per_epoch=2000,
#     epochs=50)
# """
#
# ## https://blog.keras.io/building-powerful-image-classification-models-using-very-little-data.html
# ## https://machinelearningmastery.com/evaluate-performance-deep-learning-models-keras/
#
# # set seed of random number generator so that we can reproduce results
# seed = 0
# np.random.seed(seed)
#
# # fit the model on the batches generated by datagen.flow()
# loss_history = model.fit_generator(train_generator,
#                                    steps_per_epoch=1,
#                                    epochs=n_epoch)

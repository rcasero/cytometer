"""
Generate figures for the DeepCytometer paper.

Code cannibalised from:
* klf14_b6ntac_exp_0097_full_slide_pipeline_v7.py

"""

# script name to identify this experiment
experiment_id = 'klf14_b6ntac_exp_0099_paper_figures'

# cross-platform home directory
from pathlib import Path
home = str(Path.home())

import os
import sys
sys.path.extend([os.path.join(home, 'Software/cytometer')])

########################################################################################################################
## Explore training/test data of different folds
########################################################################################################################

import pickle

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

os.environ['KERAS_BACKEND'] = 'tensorflow'
import keras.backend as K

import cytometer
import cytometer.data
import tensorflow as tf

# limit number of GPUs
os.environ['CUDA_VISIBLE_DEVICES'] = '1'

LIMIT_GPU_MEMORY = False

# limit GPU memory used
if LIMIT_GPU_MEMORY:
    from keras.backend.tensorflow_backend import set_session
    config = tf.ConfigProto()
    config.gpu_options.per_process_gpu_memory_fraction = 0.9
    set_session(tf.Session(config=config))

# specify data format as (n, row, col, channel)
K.set_image_data_format('channels_last')

DEBUG = False

'''Directories and filenames'''

# data paths
klf14_root_data_dir = os.path.join(home, 'Data/cytometer_data/klf14')
klf14_training_dir = os.path.join(klf14_root_data_dir, 'klf14_b6ntac_training')
klf14_training_non_overlap_data_dir = os.path.join(klf14_root_data_dir, 'klf14_b6ntac_training_non_overlap')
klf14_training_augmented_dir = os.path.join(klf14_root_data_dir, 'klf14_b6ntac_training_augmented')
figures_dir = os.path.join(home, 'GoogleDrive/Research/20190727_cytometer_paper/figures')
saved_models_dir = os.path.join(klf14_root_data_dir, 'saved_models')
ndpi_dir = os.path.join(home, 'scan_srv2_cox/Maz Yon')
metainfo_dir = os.path.join(home, 'GoogleDrive/Research/20190727_cytometer_paper')

saved_kfolds_filename = 'klf14_b6ntac_exp_0079_generate_kfolds.pickle'
saved_extra_kfolds_filename = 'klf14_b6ntac_exp_0094_generate_extra_training_images.pickle'


# original dataset used in pipelines up to v6 + extra "other" tissue images
kfold_filename = os.path.join(saved_models_dir, saved_extra_kfolds_filename)
with open(kfold_filename, 'rb') as f:
    aux = pickle.load(f)
file_svg_list = aux['file_list']
idx_test_all = aux['idx_test']
idx_train_all = aux['idx_train']

# correct home directory
file_svg_list = [x.replace('/users/rittscher/rcasero', home) for x in file_svg_list]
file_svg_list = [x.replace('/home/rcasero', home) for x in file_svg_list]

# number of images
n_im = len(file_svg_list)

# CSV file with metainformation of all mice
metainfo_csv_file = os.path.join(metainfo_dir, 'klf14_b6ntac_meta_info.csv')
metainfo = pd.read_csv(metainfo_csv_file)

# loop the folds to get the ndpi files that correspond to testing of each fold
ndpi_files_test_list = {}
for i_fold in range(len(idx_test_all)):
    # list of .svg files for testing
    file_svg_test = np.array(file_svg_list)[idx_test_all[i_fold]]

    # list of .ndpi files that the .svg windows came from
    file_ndpi_test = [os.path.basename(x).replace('.svg', '') for x in file_svg_test]
    file_ndpi_test = np.unique([x.split('_row')[0] for x in file_ndpi_test])

    # add to the dictionary {file: fold}
    for file in file_ndpi_test:
        ndpi_files_test_list[file] = i_fold


if DEBUG:
    # list of NDPI files
    for key in ndpi_files_test_list.keys():
        print(key)

# init dataframe to aggregate training numbers of each mouse
table = pd.DataFrame(columns=['Cells', 'Other', 'Background', 'Windows', 'Windows with cells'])

# loop files with hand traced contours
for i, file_svg in enumerate(file_svg_list):

    print('file ' + str(i) + '/' + str(len(file_svg_list) - 1) + ': ' + os.path.basename(file_svg))

    # read the ground truth cell contours in the SVG file. This produces a list [contour_0, ..., contour_N-1]
    # where each contour_i = [(X_0, Y_0), ..., (X_P-1, X_P-1)]
    cell_contours = cytometer.data.read_paths_from_svg_file(file_svg, tag='Cell', add_offset_from_filename=False,
                                                            minimum_npoints=3)
    other_contours = cytometer.data.read_paths_from_svg_file(file_svg, tag='Other', add_offset_from_filename=False,
                                                             minimum_npoints=3)
    brown_contours = cytometer.data.read_paths_from_svg_file(file_svg, tag='Brown', add_offset_from_filename=False,
                                                             minimum_npoints=3)
    background_contours = cytometer.data.read_paths_from_svg_file(file_svg, tag='Background', add_offset_from_filename=False,
                                                                  minimum_npoints=3)
    contours = cell_contours + other_contours + brown_contours + background_contours

    # make a list with the type of cell each contour is classified as
    contour_type = [np.zeros(shape=(len(cell_contours),), dtype=np.uint8),  # 0: white-adipocyte
                    np.ones(shape=(len(other_contours),), dtype=np.uint8),  # 1: other types of tissue
                    np.ones(shape=(len(brown_contours),), dtype=np.uint8),  # 1: brown cells (treated as "other" tissue)
                    np.zeros(shape=(len(background_contours),), dtype=np.uint8)] # 0: background
    contour_type = np.concatenate(contour_type)

    print('Cells: ' + str(len(cell_contours)) + '. Other: ' + str(len(other_contours))
          + '. Brown: ' + str(len(brown_contours)) + '. Background: ' + str(len(background_contours)))

    # create dataframe for this image
    df_common = cytometer.data.tag_values_with_mouse_info(metainfo=metainfo, s=os.path.basename(file_svg),
                                                          values=[i,], values_tag='i',
                                                          tags_to_keep=['id', 'ko', 'sex'])

    # mouse ID as a string
    id = df_common['id'].values[0]
    sex = df_common['sex'].values[0]
    ko = df_common['ko'].values[0]

    # row to add to the table
    df = pd.DataFrame(
        [(sex, ko,
          len(cell_contours), len(other_contours) + len(brown_contours), len(background_contours), 1, int(len(cell_contours)>0))],
        columns=['Sex', 'Genotype', 'Cells', 'Other', 'Background', 'Windows', 'Windows with cells'], index=[id])

    if id in table.index:

        num_cols = ['Cells', 'Other', 'Background', 'Windows', 'Windows with cells']
        table.loc[id, num_cols] = (table.loc[id, num_cols] + df.loc[id, num_cols])

    else:

        table = table.append(df, sort=False, ignore_index=False, verify_integrity=True)

# alphabetical order by mouse IDs
table = table.sort_index()

# total number of sampled windows
print('Total number of windows = ' + str(np.sum(table['Windows'])))
print('Total number of windows with cells = ' + str(np.sum(table['Windows with cells'])))

# total number of "Other" and background areas
print('Total number of Other areas = ' + str(np.sum(table['Other'])))
print('Total number of Background areas = ' + str(np.sum(table['Background'])))

# aggregate by sex and genotype
idx_f = table['Sex'] == 'f'
idx_m = table['Sex'] == 'm'
idx_pat = table['Genotype'] == 'PAT'
idx_mat = table['Genotype'] == 'MAT'

print('f PAT: ' + str(np.sum(table.loc[idx_f * idx_pat, 'Cells'])))
print('f MAT: ' + str(np.sum(table.loc[idx_f * idx_mat, 'Cells'])))
print('m PAT: ' + str(np.sum(table.loc[idx_m * idx_pat, 'Cells'])))
print('m MAT: ' + str(np.sum(table.loc[idx_m * idx_mat, 'Cells'])))

# find folds that test images belong to
for i_file, ndpi_file_kernel in enumerate(ndpi_files_test_list):

    # fold  where the current .ndpi image was not used for training
    i_fold = ndpi_files_test_list[ndpi_file_kernel]

    print('File ' + str(i_file) + '/' + str(len(ndpi_files_test_list) - 1) + ': ' + ndpi_file_kernel
          + '. Fold = ' + str(i_fold))

# mean and std of mouse weight
weight_f_mat = [22.07, 26.39, 30.65, 24.28, 27.72]
weight_f_pat = [31.42, 29.25, 27.18, 23.69, 21.20]
weight_m_mat = [46.19, 40.87, 40.02, 41.98, 34.52, 36.08]
weight_m_pat = [36.55, 40.77, 36.98, 36.11]

print('f MAT: mean = ' + str(np.mean(weight_f_mat)) + ', std = ' + str(np.std(weight_f_mat)))
print('f PAT: mean = ' + str(np.mean(weight_f_pat)) + ', std = ' + str(np.std(weight_f_pat)))
print('m MAT: mean = ' + str(np.mean(weight_m_mat)) + ', std = ' + str(np.std(weight_m_mat)))
print('m PAT: mean = ' + str(np.mean(weight_m_pat)) + ', std = ' + str(np.std(weight_m_pat)))

########################################################################################################################
## Plots of get_next_roi_to_process()
########################################################################################################################

import pickle
import cytometer.utils

# Filter out INFO & WARNING messages
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# # limit number of GPUs
# os.environ['CUDA_VISIBLE_DEVICES'] = '0,1'

os.environ['KERAS_BACKEND'] = 'tensorflow'

import time
import openslide
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.signal import fftconvolve
from cytometer.utils import rough_foreground_mask
import PIL
from keras import backend as K

LIMIT_GPU_MEMORY = False

# limit GPU memory used
if LIMIT_GPU_MEMORY:
    import tensorflow as tf
    from keras.backend.tensorflow_backend import set_session
    config = tf.ConfigProto()
    config.gpu_options.per_process_gpu_memory_fraction = 0.95
    set_session(tf.Session(config=config))

DEBUG = False
SAVE_FIGS = False

root_data_dir = os.path.join(home, 'Data/cytometer_data/klf14')
data_dir = os.path.join(home, 'scan_srv2_cox/Maz Yon')
training_dir = os.path.join(home, root_data_dir, 'klf14_b6ntac_training')
seg_dir = os.path.join(home, root_data_dir, 'klf14_b6ntac_seg')
figures_dir = os.path.join(home, 'GoogleDrive/Research/20190727_cytometer_paper/figures')
saved_models_dir = os.path.join(root_data_dir, 'saved_models')
results_dir = os.path.join(root_data_dir, 'klf14_b6ntac_results')
annotations_dir = os.path.join(home, 'Software/AIDA/dist/data/annotations')
training_augmented_dir = os.path.join(root_data_dir, 'klf14_b6ntac_training_augmented')

# k-folds file
saved_extra_kfolds_filename = 'klf14_b6ntac_exp_0094_generate_extra_training_images.pickle'

# model names
dmap_model_basename = 'klf14_b6ntac_exp_0086_cnn_dmap'
contour_model_basename = 'klf14_b6ntac_exp_0091_cnn_contour_after_dmap'
classifier_model_basename = 'klf14_b6ntac_exp_0095_cnn_tissue_classifier_fcn'
correction_model_basename = 'klf14_b6ntac_exp_0089_cnn_segmentation_correction_overlapping_scaled_contours'

# full resolution image window and network expected receptive field parameters
fullres_box_size = np.array([2751, 2751])
receptive_field = np.array([131, 131])

# rough_foreground_mask() parameters
downsample_factor = 8.0
dilation_size = 25
component_size_threshold = 1e6
hole_size_treshold = 8000

# contour parameters
contour_downsample_factor = 0.1
bspline_k = 1

# block_split() parameters in downsampled image
block_len = np.ceil((fullres_box_size - receptive_field) / downsample_factor)
block_overlap = np.ceil((receptive_field - 1) / 2 / downsample_factor).astype(np.int)

# segmentation parameters
min_cell_area = 1500
max_cell_area = 100e3
min_mask_overlap = 0.8
phagocytosis = True
min_class_prop = 0.5
correction_window_len = 401
correction_smoothing = 11
batch_size = 16

# segmentation correction parameters

# load list of images, and indices for training vs. testing indices
saved_kfolds_filename = os.path.join(saved_models_dir, saved_extra_kfolds_filename)
with open(saved_kfolds_filename, 'rb') as f:
    aux = pickle.load(f)
file_svg_list = aux['file_list']
idx_test_all = aux['idx_test']
idx_train_all = aux['idx_train']

# correct home directory
file_svg_list = [x.replace('/users/rittscher/rcasero', home) for x in file_svg_list]
file_svg_list = [x.replace('/home/rcasero', home) for x in file_svg_list]

# loop the folds to get the ndpi files that correspond to testing of each fold
ndpi_files_test_list = {}
for i_fold in range(len(idx_test_all)):
    # list of .svg files for testing
    file_svg_test = np.array(file_svg_list)[idx_test_all[i_fold]]

    # list of .ndpi files that the .svg windows came from
    file_ndpi_test = [os.path.basename(x).replace('.svg', '') for x in file_svg_test]
    file_ndpi_test = np.unique([x.split('_row')[0] for x in file_ndpi_test])

    # add to the dictionary {file: fold}
    for file in file_ndpi_test:
        ndpi_files_test_list[file] = i_fold

# File 4/19: KLF14-B6NTAC-MAT-17.1c  46-16 C1 - 2016-02-01 14.02.04. Fold = 2
i_file = 4
# File 10/19: KLF14-B6NTAC-36.1a PAT 96-16 C1 - 2016-02-10 16.12.38. Fold = 5
i_file = 10

ndpi_file_kernel = list(ndpi_files_test_list.keys())[i_file]

# for i_file, ndpi_file_kernel in enumerate(ndpi_files_test_list):

# fold  where the current .ndpi image was not used for training
i_fold = ndpi_files_test_list[ndpi_file_kernel]

print('File ' + str(i_file) + '/' + str(len(ndpi_files_test_list) - 1) + ': ' + ndpi_file_kernel
      + '. Fold = ' + str(i_fold))

# make full path to ndpi file
ndpi_file = os.path.join(data_dir, ndpi_file_kernel + '.ndpi')

contour_model_file = os.path.join(saved_models_dir, contour_model_basename + '_model_fold_' + str(i_fold) + '.h5')
dmap_model_file = os.path.join(saved_models_dir, dmap_model_basename + '_model_fold_' + str(i_fold) + '.h5')
classifier_model_file = os.path.join(saved_models_dir,
                                     classifier_model_basename + '_model_fold_' + str(i_fold) + '.h5')
correction_model_file = os.path.join(saved_models_dir,
                                     correction_model_basename + '_model_fold_' + str(i_fold) + '.h5')

# name of file to save annotations
annotations_file = os.path.basename(ndpi_file)
annotations_file = os.path.splitext(annotations_file)[0]
annotations_file = os.path.join(annotations_dir, annotations_file + '_exp_0097.json')

# name of file to save areas and contours
results_file = os.path.basename(ndpi_file)
results_file = os.path.splitext(results_file)[0]
results_file = os.path.join(results_dir, results_file + '_exp_0097.npz')

# rough segmentation of the tissue in the image
lores_istissue0, im_downsampled = rough_foreground_mask(ndpi_file, downsample_factor=downsample_factor,
                                                        dilation_size=dilation_size,
                                                        component_size_threshold=component_size_threshold,
                                                        hole_size_treshold=hole_size_treshold,
                                                        return_im=True)

if DEBUG:
    plt.clf()
    plt.imshow(im_downsampled)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'klf14_b6ntac_exp_0099_histology_i_file_' + str(i_file) + '.png'),
                bbox_inches='tight')

    plt.clf()
    plt.imshow(im_downsampled)
    plt.contour(lores_istissue0, colors='k')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'klf14_b6ntac_exp_0099_rough_mask_i_file_' + str(i_file) + '.png'),
                bbox_inches='tight')

# segmentation copy, to keep track of what's left to do
lores_istissue = lores_istissue0.copy()

# open full resolution histology slide
im = openslide.OpenSlide(ndpi_file)

# pixel size
assert(im.properties['tiff.ResolutionUnit'] == 'centimeter')
xres = 1e-2 / float(im.properties['tiff.XResolution'])
yres = 1e-2 / float(im.properties['tiff.YResolution'])

# # init empty list to store area values and contour coordinates
# areas_all = []
# contours_all = []

# keep extracting histology windows until we have finished
step = -1
time_0 = time_curr = time.time()
while np.count_nonzero(lores_istissue) > 0:

    # next step (it starts from 0)
    step += 1

    time_prev = time_curr
    time_curr = time.time()

    print('File ' + str(i_file) + '/' + str(len(ndpi_files_test_list) - 1) + ': step ' +
          str(step) + ': ' +
          str(np.count_nonzero(lores_istissue)) + '/' + str(np.count_nonzero(lores_istissue0)) + ': ' +
          "{0:.1f}".format(100.0 - np.count_nonzero(lores_istissue) / np.count_nonzero(lores_istissue0) * 100) +
          '% completed: ' +
          'step time ' + "{0:.2f}".format(time_curr - time_prev) + ' s' +
          ', total time ' + "{0:.2f}".format(time_curr - time_0) + ' s')

    ## Code extracted from:
    ## get_next_roi_to_process()

    # variables for get_next_roi_to_process()
    seg = lores_istissue.copy()
    downsample_factor = downsample_factor
    max_window_size = fullres_box_size
    border = np.round((receptive_field - 1) / 2)

    # convert to np.array so that we can use algebraic operators
    max_window_size = np.array(max_window_size)
    border = np.array(border)

    # convert segmentation mask to [0, 1]
    seg = (seg != 0).astype('int')

    # approximate measures in the downsampled image (we don't round them)
    lores_max_window_size = max_window_size / downsample_factor
    lores_border = border / downsample_factor

    # kernels that flipped correspond to top line and left line. They need to be pre-flipped
    # because the convolution operation internally flips them (two flips cancel each other)
    kernel_top = np.zeros(shape=np.round(lores_max_window_size - 2 * lores_border).astype('int'))
    kernel_top[int((kernel_top.shape[0] - 1) / 2), :] = 1
    kernel_left = np.zeros(shape=np.round(lores_max_window_size - 2 * lores_border).astype('int'))
    kernel_left[:, int((kernel_top.shape[1] - 1) / 2)] = 1

    if DEBUG:
        plt.clf()
        plt.imshow(kernel_top)
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(os.path.join(figures_dir, 'klf14_b6ntac_exp_0099_kernel_top_i_file_' + str(i_file) + '.png'),
                    bbox_inches='tight')

        plt.imshow(kernel_left)
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(os.path.join(figures_dir, 'klf14_b6ntac_exp_0099_kernel_left_i_file_' + str(i_file) + '.png'),
                    bbox_inches='tight')

    seg_top = np.round(fftconvolve(seg, kernel_top, mode='same'))
    seg_left = np.round(fftconvolve(seg, kernel_left, mode='same'))

    # window detections
    detection_idx = np.nonzero(seg_left * seg_top)

    # set top-left corner of the box = top-left corner of first box detected
    lores_first_row = detection_idx[0][0]
    lores_first_col = detection_idx[1][0]

    # first, we look within a window with the maximum size
    lores_last_row = detection_idx[0][0] + lores_max_window_size[0] - 2 * lores_border[0]
    lores_last_col = detection_idx[1][0] + lores_max_window_size[1] - 2 * lores_border[1]

    # second, if the segmentation is smaller than the window, we reduce the window size
    window = seg[lores_first_row:int(np.round(lores_last_row)), lores_first_col:int(np.round(lores_last_col))]

    idx = np.any(window, axis=1)  # reduce rows size
    last_segmented_pixel_len = np.max(np.where(idx))
    lores_last_row = detection_idx[0][0] + np.min((lores_max_window_size[0] - 2 * lores_border[0],
                                                   last_segmented_pixel_len))

    idx = np.any(window, axis=0)  # reduce cols size
    last_segmented_pixel_len = np.max(np.where(idx))
    lores_last_col = detection_idx[1][0] + np.min((lores_max_window_size[1] - 2 * lores_border[1],
                                                   last_segmented_pixel_len))

    # save coordinates for plot (this is only for a figure in the paper and doesn't need to be done in the real
    # implementation)
    lores_first_col_bak = lores_first_col
    lores_first_row_bak = lores_first_row
    lores_last_col_bak = lores_last_col
    lores_last_row_bak = lores_last_row

    # add a border around the window
    lores_first_row = np.max([0, lores_first_row - lores_border[0]])
    lores_first_col = np.max([0, lores_first_col - lores_border[1]])

    lores_last_row = np.min([seg.shape[0], lores_last_row + lores_border[0]])
    lores_last_col = np.min([seg.shape[1], lores_last_col + lores_border[1]])

    # convert low resolution indices to high resolution
    first_row = np.int(np.round(lores_first_row * downsample_factor))
    last_row = np.int(np.round(lores_last_row * downsample_factor))
    first_col = np.int(np.round(lores_first_col * downsample_factor))
    last_col = np.int(np.round(lores_last_col * downsample_factor))

    # round down indices in downsampled segmentation
    lores_first_row = int(lores_first_row)
    lores_last_row = int(lores_last_row)
    lores_first_col = int(lores_first_col)
    lores_last_col = int(lores_last_col)

    # load window from full resolution slide
    tile = im.read_region(location=(first_col, first_row), level=0,
                          size=(last_col - first_col, last_row - first_row))
    tile = np.array(tile)
    tile = tile[:, :, 0:3]

    # interpolate coarse tissue segmentation to full resolution
    istissue_tile = lores_istissue[lores_first_row:lores_last_row, lores_first_col:lores_last_col]
    istissue_tile = cytometer.utils.resize(istissue_tile, size=(last_col - first_col, last_row - first_row),
                                           resample=PIL.Image.NEAREST)

    if DEBUG:
        plt.clf()
        plt.imshow(tile)
        plt.imshow(istissue_tile, alpha=0.5)
        plt.contour(istissue_tile, colors='k')
        plt.title('Yellow: Tissue. Purple: Background')
        plt.axis('off')

    # clear keras session to prevent each segmentation iteration from getting slower. Note that this forces us to
    # reload the models every time
    K.clear_session()

    # segment histology, split into individual objects, and apply segmentation correction
    labels, labels_class, todo_edge, \
    window_im, window_labels, window_labels_corrected, window_labels_class, index_list, scaling_factor_list \
        = cytometer.utils.segmentation_pipeline6(tile,
                                                 dmap_model=dmap_model_file,
                                                 contour_model=contour_model_file,
                                                 correction_model=correction_model_file,
                                                 classifier_model=classifier_model_file,
                                                 min_cell_area=min_cell_area,
                                                 mask=istissue_tile,
                                                 min_mask_overlap=min_mask_overlap,
                                                 phagocytosis=phagocytosis,
                                                 min_class_prop=min_class_prop,
                                                 correction_window_len=correction_window_len,
                                                 correction_smoothing=correction_smoothing,
                                                 return_bbox=True, return_bbox_coordinates='xy',
                                                 batch_size=batch_size)

    # downsample "to do" mask so that the rough tissue segmentation can be updated
    lores_todo_edge = PIL.Image.fromarray(todo_edge.astype(np.uint8))
    lores_todo_edge = lores_todo_edge.resize((lores_last_col - lores_first_col,
                                              lores_last_row - lores_first_row),
                                             resample=PIL.Image.NEAREST)
    lores_todo_edge = np.array(lores_todo_edge)

    # update coarse tissue mask (this is only necessary here to plot figures for the paper. In the actual code,
    # the coarse mask gets directly updated, without this intermediate step)
    seg_updated = seg.copy()
    seg_updated[lores_first_row:lores_last_row, lores_first_col:lores_last_col] = lores_todo_edge

    if DEBUG:
        plt.clf()
        fig = plt.imshow(seg, cmap='Greys')
        plt.contour(seg_left * seg_top > 0, colors='r')
        rect = Rectangle((lores_first_col, lores_first_row),
                         lores_last_col - lores_first_col, lores_last_row - lores_first_row,
                         alpha=0.5, facecolor='g', edgecolor='g', zorder=2)
        fig.axes.add_patch(rect)
        rect2 = Rectangle((lores_first_col_bak, lores_first_row_bak),
                          lores_last_col_bak - lores_first_col_bak, lores_last_row_bak - lores_first_row_bak,
                          alpha=1.0, facecolor=None, fill=False, edgecolor='g', lw=1, zorder=3)
        fig.axes.add_patch(rect2)
        plt.scatter(detection_idx[1][0], detection_idx[0][0], color='k', s=5, zorder=3)
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(os.path.join(figures_dir, 'klf14_b6ntac_exp_0099_fftconvolve_i_file_' + str(i_file) +
                                 '_step_' + str(step) + '.png'),
                    bbox_inches='tight')

    if DEBUG:
        plt.clf()
        fig = plt.imshow(seg, cmap='Greys')
        plt.contour(seg_left * seg_top > 0, colors='r')
        plt.contour(seg_updated, colors='w', zorder=4)
        rect = Rectangle((lores_first_col, lores_first_row),
                         lores_last_col - lores_first_col, lores_last_row - lores_first_row,
                         alpha=0.5, facecolor='g', edgecolor='g', zorder=2)
        fig.axes.add_patch(rect)
        rect2 = Rectangle((lores_first_col_bak, lores_first_row_bak),
                          lores_last_col_bak - lores_first_col_bak, lores_last_row_bak - lores_first_row_bak,
                          alpha=1.0, facecolor=None, fill=False, edgecolor='g', lw=3, zorder=3)
        fig.axes.add_patch(rect2)
        plt.scatter(detection_idx[1][0], detection_idx[0][0], color='k', s=5, zorder=3)
        plt.axis('off')
        plt.tight_layout()
        plt.xlim(int(lores_first_col - 50), int(lores_last_col + 50))
        plt.ylim(int(lores_last_row + 50), int(lores_first_row - 50))
        plt.savefig(os.path.join(figures_dir, 'klf14_b6ntac_exp_0099_fftconvolve_detail_i_file_' + str(i_file) +
                                 '_step_' + str(step) + '.png'),
                    bbox_inches='tight')

        # update coarse tissue mask for next iteration
        lores_istissue[lores_first_row:lores_last_row, lores_first_col:lores_last_col] = lores_todo_edge

########################################################################################################################
## Show examples of what each deep CNN do (code cannibilised from the "inspect" scripts of the networks)
########################################################################################################################

import pickle
import warnings

# other imports
import numpy as np
import cv2
import matplotlib.pyplot as plt

os.environ['KERAS_BACKEND'] = 'tensorflow'
import keras
import keras.backend as K

import cytometer.data
import cytometer.utils
import cytometer.model_checkpoint_parallel
import tensorflow as tf

from PIL import Image, ImageDraw
import math

LIMIT_GPU_MEMORY = False

# limit GPU memory used
if LIMIT_GPU_MEMORY:
    from keras.backend.tensorflow_backend import set_session
    config = tf.ConfigProto()
    config.gpu_options.per_process_gpu_memory_fraction = 0.9
    set_session(tf.Session(config=config))

# specify data format as (n, row, col, channel)
K.set_image_data_format('channels_last')

DEBUG = False

'''Directories and filenames'''

# data paths
klf14_root_data_dir = os.path.join(home, 'Data/cytometer_data/klf14')
klf14_training_dir = os.path.join(klf14_root_data_dir, 'klf14_b6ntac_training')
klf14_training_non_overlap_data_dir = os.path.join(klf14_root_data_dir, 'klf14_b6ntac_training_non_overlap')
klf14_training_augmented_dir = os.path.join(klf14_root_data_dir, 'klf14_b6ntac_training_augmented')
figures_dir = os.path.join(home, 'GoogleDrive/Research/20190727_cytometer_paper/figures')
saved_models_dir = os.path.join(klf14_root_data_dir, 'saved_models')

saved_kfolds_filename = 'klf14_b6ntac_exp_0079_generate_kfolds.pickle'

# model names
dmap_model_basename = 'klf14_b6ntac_exp_0086_cnn_dmap'
contour_model_basename = 'klf14_b6ntac_exp_0091_cnn_contour_after_dmap'
classifier_model_basename = 'klf14_b6ntac_exp_0095_cnn_tissue_classifier_fcn'
correction_model_basename = 'klf14_b6ntac_exp_0089_cnn_segmentation_correction_overlapping_scaled_contours'


'''Load folds'''

# load list of images, and indices for training vs. testing indices
contour_model_kfold_filename = os.path.join(saved_models_dir, saved_kfolds_filename)
with open(contour_model_kfold_filename, 'rb') as f:
    aux = pickle.load(f)
svg_file_list = aux['file_list']
idx_test_all = aux['idx_test']
idx_train_all = aux['idx_train']

if DEBUG:
    for i, file in enumerate(svg_file_list):
        print(str(i) + ': ' + file)

# correct home directory
svg_file_list = [x.replace('/home/rcasero', home) for x in svg_file_list]

# KLF14-B6NTAC-36.1b PAT 97-16 C1 - 2016-02-10 17.38.06_row_017204_col_019444.tif (fold 5 for testing. No .svg)
# KLF14-B6NTAC-36.1b PAT 97-16 C1 - 2016-02-10 17.38.06_row_009644_col_061660.tif (fold 5 for testing. No .svg)
# KLF14-B6NTAC 36.1c PAT 98-16 C1 - 2016-02-11 10.45.00_row_019228_col_015060.svg (fold 7 for testing. With .svg)

# find which fold the testing image belongs to
np.where(['36.1c' in x for x in svg_file_list])
idx_test_all[7]

# TIFF files that correspond to the SVG files (without augmentation)
im_orig_file_list = []
for i, file in enumerate(svg_file_list):
    im_orig_file_list.append(file.replace('.svg', '.tif'))
    im_orig_file_list[i] = os.path.join(os.path.dirname(im_orig_file_list[i]) + '_augmented',
                                        'im_seed_nan_' + os.path.basename(im_orig_file_list[i]))

    # check that files exist
    if not os.path.isfile(file):
        # warnings.warn('i = ' + str(i) + ': File does not exist: ' + os.path.basename(file))
        warnings.warn('i = ' + str(i) + ': File does not exist: ' + file)
    if not os.path.isfile(im_orig_file_list[i]):
        # warnings.warn('i = ' + str(i) + ': File does not exist: ' + os.path.basename(im_orig_file_list[i]))
        warnings.warn('i = ' + str(i) + ': File does not exist: ' + im_orig_file_list[i])

'''Inspect model results'''

# for i_fold, idx_test in enumerate(idx_test_all):
i_fold = 7; idx_test = idx_test_all[i_fold]

print('Fold ' + str(i_fold) + '/' + str(len(idx_test_all)-1))

'''Load data'''

# split the data list into training and testing lists
im_test_file_list, im_train_file_list = cytometer.data.split_list(im_orig_file_list, idx_test)

# load the test data (im, dmap, mask)
test_dataset, test_file_list, test_shuffle_idx = \
    cytometer.data.load_datasets(im_test_file_list, prefix_from='im', prefix_to=['im', 'dmap', 'mask', 'contour'],
                                 nblocks=1, shuffle_seed=None)

# fill in the little gaps in the mask
kernel = np.ones((3, 3), np.uint8)
for i in range(test_dataset['mask'].shape[0]):
    test_dataset['mask'][i, :, :, 0] = cv2.dilate(test_dataset['mask'][i, :, :, 0].astype(np.uint8),
                                                  kernel=kernel, iterations=1)

# load dmap model, and adjust input size
saved_model_filename = os.path.join(saved_models_dir, dmap_model_basename + '_model_fold_' + str(i_fold) + '.h5')
dmap_model = keras.models.load_model(saved_model_filename)
if dmap_model.input_shape[1:3] != test_dataset['im'].shape[1:3]:
    dmap_model = cytometer.utils.change_input_size(dmap_model, batch_shape=test_dataset['im'].shape)

# estimate dmaps
pred_dmap = dmap_model.predict(test_dataset['im'], batch_size=4)

if DEBUG:
    for i in range(test_dataset['im'].shape[0]):
        plt.clf()
        plt.subplot(221)
        plt.imshow(test_dataset['im'][i, :, :, :])
        plt.axis('off')
        plt.subplot(222)
        plt.imshow(test_dataset['dmap'][i, :, :, 0])
        plt.axis('off')
        plt.subplot(223)
        plt.imshow(test_dataset['mask'][i, :, :, 0])
        plt.axis('off')
        plt.subplot(224)
        plt.imshow(pred_dmap[i, :, :, 0])
        plt.axis('off')

# KLF14-B6NTAC 36.1c PAT 98-16 C1 - 2016-02-11 10.45.00_row_019228_col_015060.svg
i = 2

if DEBUG:

    plt.clf()
    plt.imshow(test_dataset['im'][i, :, :, :])
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

    plt.clf()
    plt.imshow(test_dataset['dmap'][i, :, :, 0])
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'dmap_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

    plt.clf()
    plt.imshow(pred_dmap[i, :, :, 0])
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'pred_dmap_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

# load dmap to contour model, and adjust input size
saved_model_filename = os.path.join(saved_models_dir, contour_model_basename + '_model_fold_' + str(i_fold) + '.h5')
contour_model = keras.models.load_model(saved_model_filename)
if contour_model.input_shape[1:3] != pred_dmap.shape[1:3]:
    contour_model = cytometer.utils.change_input_size(contour_model, batch_shape=pred_dmap.shape)

# estimate contours
pred_contour = contour_model.predict(pred_dmap, batch_size=4)

if DEBUG:
    plt.clf()
    plt.imshow(test_dataset['contour'][i, :, :, 0])
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'contour_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

    plt.clf()
    plt.imshow(pred_contour[i, :, :, 0])
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'pred_contour_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

# load classifier model, and adjust input size
saved_model_filename = os.path.join(saved_models_dir, classifier_model_basename + '_model_fold_' + str(i_fold) + '.h5')
classifier_model = keras.models.load_model(saved_model_filename)
if classifier_model.input_shape[1:3] != test_dataset['im'].shape[1:3]:
    classifier_model = cytometer.utils.change_input_size(classifier_model, batch_shape=test_dataset['im'].shape)

# estimate pixel-classification
pred_class = classifier_model.predict(test_dataset['im'], batch_size=4)

if DEBUG:
    plt.clf()
    plt.imshow(pred_class[i, :, :, 0])
    plt.contour(pred_class[i, :, :, 0] > 0.5, colors='r', linewidhts=3)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'pred_class_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

    plt.clf()
    plt.imshow(pred_class[i, :, :, 0] > 0.5)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'pred_class_thresh_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

## create classifier ground truth

# print('file ' + str(i) + '/' + str(len(file_svg_list) - 1))

# init output
im_array_all = []
out_class_all = []
out_mask_all = []
contour_type_all = []

file_tif = os.path.join(klf14_training_dir, os.path.basename(im_test_file_list[i]))
file_tif = file_tif.replace('im_seed_nan_', '')

# change file extension from .svg to .tif
file_svg = file_tif.replace('.tif', '.svg')

# open histology training image
im = Image.open(file_tif)

# make array copy
im_array = np.array(im)

# read the ground truth cell contours in the SVG file. This produces a list [contour_0, ..., contour_N-1]
# where each contour_i = [(X_0, Y_0), ..., (X_P-1, X_P-1)]
cell_contours = cytometer.data.read_paths_from_svg_file(file_svg, tag='Cell', add_offset_from_filename=False,
                                                        minimum_npoints=3)
other_contours = cytometer.data.read_paths_from_svg_file(file_svg, tag='Other', add_offset_from_filename=False,
                                                         minimum_npoints=3)
brown_contours = cytometer.data.read_paths_from_svg_file(file_svg, tag='Brown', add_offset_from_filename=False,
                                                         minimum_npoints=3)
background_contours = cytometer.data.read_paths_from_svg_file(file_svg, tag='Background',
                                                              add_offset_from_filename=False,
                                                              minimum_npoints=3)
contours = cell_contours + other_contours + brown_contours + background_contours

# make a list with the type of cell each contour is classified as
contour_type = [np.zeros(shape=(len(cell_contours),), dtype=np.uint8),  # 0: white-adipocyte
                np.ones(shape=(len(other_contours),), dtype=np.uint8),  # 1: other types of tissue
                np.ones(shape=(len(brown_contours),), dtype=np.uint8),  # 1: brown cells (treated as "other" tissue)
                np.zeros(shape=(len(background_contours),), dtype=np.uint8)]  # 0: background
contour_type = np.concatenate(contour_type)
contour_type_all.append(contour_type)

print('Cells: ' + str(len(cell_contours)))
print('Other: ' + str(len(other_contours)))
print('Brown: ' + str(len(brown_contours)))
print('Background: ' + str(len(background_contours)))

# initialise arrays for training
out_class = np.zeros(shape=im_array.shape[0:2], dtype=np.uint8)
out_mask = np.zeros(shape=im_array.shape[0:2], dtype=np.uint8)

# loop ground truth cell contours
for j, contour in enumerate(contours):

    plt.plot([p[0] for p in contour], [p[1] for p in contour])
    plt.text(contour[0][0], contour[0][1], str(j))

    if DEBUG:
        plt.clf()

        plt.subplot(121)
        plt.imshow(im_array)
        plt.plot([p[0] for p in contour], [p[1] for p in contour])
        xy_c = (np.mean([p[0] for p in contour]), np.mean([p[1] for p in contour]))
        plt.scatter(xy_c[0], xy_c[1])

    # rasterise current ground truth segmentation
    cell_seg_gtruth = Image.new("1", im_array.shape[0:2][::-1], "black")  # I = 32-bit signed integer pixels
    draw = ImageDraw.Draw(cell_seg_gtruth)
    draw.polygon(contour, outline="white", fill="white")
    cell_seg_gtruth = np.array(cell_seg_gtruth, dtype=np.bool)

    # we are going to save the ground truth segmentation of the cell that we are going to later use in the figures
    if j == 106:
        cell_seg_gtruth_106 = cell_seg_gtruth.copy()

    if DEBUG:
        plt.subplot(122)
        plt.cla()
        plt.imshow(im_array)
        plt.contour(cell_seg_gtruth.astype(np.uint8))

    # add current object to training output and mask
    out_mask[cell_seg_gtruth] = 1
    out_class[cell_seg_gtruth] = contour_type[j]

if DEBUG:
    plt.clf()
    aux = (1- out_class).astype(np.float32)
    aux = np.ma.masked_where(out_mask < 0.5, aux)
    plt.imshow(aux)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'class_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

## Segmentation correction CNN

# segmentation parameters
min_cell_area = 1500
max_cell_area = 100e3
min_mask_overlap = 0.8
phagocytosis = True
min_class_prop = 0.5
correction_window_len = 401
correction_smoothing = 11
batch_size = 2

# segment histology
labels, labels_class, _ \
    = cytometer.utils.segment_dmap_contour_v6(im_array,
                                              contour_model=contour_model, dmap_model=dmap_model,
                                              classifier_model=classifier_model,
                                              border_dilation=0)
labels = labels[0, :, :]
labels_class = labels_class[0, :, :, 0]

if DEBUG:
    plt.clf()
    plt.imshow(labels)

# remove labels that touch the edges, that are too small or too large, don't overlap enough with the tissue mask,
# are fully surrounded by another label or are not white adipose tissue
labels, todo_edge = cytometer.utils.clean_segmentation(
    labels, min_cell_area=min_cell_area, max_cell_area=max_cell_area,
    remove_edge_labels=True, mask=None, min_mask_overlap=min_mask_overlap,
    phagocytosis=phagocytosis,
    labels_class=labels_class, min_class_prop=min_class_prop)

if DEBUG:
    plt.clf()
    plt.imshow(im_array)
    plt.contour(labels, levels=np.unique(labels), colors='k')
    plt.contourf(labels == 0)

# split image into individual labels
im_array = np.expand_dims(im_array, axis=0)
labels = np.expand_dims(labels, axis=0)
labels_class = np.expand_dims(labels_class, axis=0)
cell_seg_gtruth_106 = np.expand_dims(cell_seg_gtruth_106, axis=0)
window_mask = None
(window_labels, window_im, window_labels_class, window_cell_seg_gtruth_106), index_list, scaling_factor_list \
    = cytometer.utils.one_image_per_label_v2((labels, im_array, labels_class, cell_seg_gtruth_106.astype(np.uint8)),
                                             resize_to=(correction_window_len, correction_window_len),
                                             resample=(Image.NEAREST, Image.LINEAR, Image.NEAREST, Image.NEAREST),
                                             only_central_label=True, return_bbox=False)

# load correction model
saved_model_filename = os.path.join(saved_models_dir, correction_model_basename + '_model_fold_' + str(i_fold) + '.h5')
correction_model = keras.models.load_model(saved_model_filename)
if correction_model.input_shape[1:3] != window_im.shape[1:3]:
    correction_model = cytometer.utils.change_input_size(correction_model, batch_shape=window_im.shape)

# multiply image by mask
window_im_masked = cytometer.utils.quality_model_mask(
    np.expand_dims(window_labels, axis=-1), im=window_im, quality_model_type='-1_1')

# process (histology * mask) to estimate which pixels are underestimated and which overestimated in the segmentation
window_im_masked = correction_model.predict(window_im_masked, batch_size=batch_size)

# compute the correction to be applied to the segmentation
correction = (window_im[:, :, :, 0].copy() * 0).astype(np.float32)
correction[window_im_masked[:, :, :, 0] >= 0.5] = 1  # the segmentation went too far
correction[window_im_masked[:, :, :, 0] <= -0.5] = -1  # the segmentation fell short

if DEBUG:
    j = 0

    plt.clf()
    plt.imshow(correction[j, :, :])
    # plt.contour(window_labels[j, ...], colors='r', linewidths=1)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'pred_correction_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

    plt.clf()
    plt.imshow(correction[j, :, :])
    plt.contour(window_labels[j, ...], colors='r', linewidths=1)
    plt.contour(window_cell_seg_gtruth_106[j, ...], colors='w', linewidths=1)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(
        os.path.join(figures_dir, 'pred_correction_gtruth_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
        bbox_inches='tight')

# correct segmentation (full operation)
window_im = window_im.astype(np.float32)
window_im /= 255.0
window_labels_corrected = cytometer.utils.correct_segmentation(
    im=window_im, seg=window_labels,
    correction_model=correction_model, model_type='-1_1',
    smoothing=correction_smoothing,
    batch_size=batch_size)

if DEBUG:
    j = 0

    plt.clf()
    plt.imshow(window_im[j, ...])
    plt.contour(window_labels[j, ...], colors='r', linewidths=3)
    plt.text(185, 210, '+1', fontsize=30)
    plt.text(116, 320, '-1', fontsize=30)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'im_for_correction_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

    plt.clf()
    plt.imshow(window_im[j, ...])
    plt.contour(window_labels_corrected[j, ...], colors='g', linewidths=3)
    plt.text(185, 210, '+1', fontsize=30)
    plt.text(116, 320, '-1', fontsize=30)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(os.path.join(figures_dir, 'corrected_seg_' + os.path.basename(im_test_file_list[i]).replace('.tif', '.png')),
                bbox_inches='tight')

    aux = np.array(contours[j])
    plt.plot(aux[:, 0], aux[:, 1])

########################################################################################################################
## Plots of segmented full slides with quantile colourmaps
########################################################################################################################

# This is done in klf14_b6ntac_exp_0098_full_slide_size_analysis_v7

########################################################################################################################
## Segmentation validation
########################################################################################################################

# This is done in klf14_b6ntac_exp_0096_pipeline_v7_validation.py

########################################################################################################################
## Linear models of body weight and depot weights
########################################################################################################################

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import statsmodels.api as sm

DEBUG = False

# directories
klf14_root_data_dir = os.path.join(home, 'Data/cytometer_data/klf14')
annotations_dir = os.path.join(home, 'Software/AIDA/dist/data/annotations')
ndpi_dir = os.path.join(home, 'scan_srv2_cox/Maz Yon')
figures_dir = os.path.join(home, 'GoogleDrive/Research/20190727_cytometer_paper/figures')
metainfo_dir = os.path.join(home, 'GoogleDrive/Research/20190727_cytometer_paper')

# load metainfo file
metainfo_csv_file = os.path.join(metainfo_dir, 'klf14_b6ntac_meta_info.csv')
metainfo = pd.read_csv(metainfo_csv_file)

# subgroups
idx_f_pat_wt = (metainfo.sex == 'f') * (metainfo.ko == 'PAT') * (metainfo.genotype == 'KLF14-KO:WT') * ~np.isnan(metainfo.BW)
idx_f_pat_het = (metainfo.sex == 'f') * (metainfo.ko == 'PAT') * (metainfo.genotype == 'KLF14-KO:Het') * ~np.isnan(metainfo.BW)
idx_f_mat_wt = (metainfo.sex == 'f') * (metainfo.ko == 'MAT') * (metainfo.genotype == 'KLF14-KO:WT') * ~np.isnan(metainfo.BW)
idx_f_mat_het = (metainfo.sex == 'f') * (metainfo.ko == 'MAT') * (metainfo.genotype == 'KLF14-KO:Het') * ~np.isnan(metainfo.BW)
idx_m_pat_wt = (metainfo.sex == 'm') * (metainfo.ko == 'PAT') * (metainfo.genotype == 'KLF14-KO:WT') * ~np.isnan(metainfo.BW)
idx_m_pat_het = (metainfo.sex == 'm') * (metainfo.ko == 'PAT') * (metainfo.genotype == 'KLF14-KO:Het') * ~np.isnan(metainfo.BW)
idx_m_mat_wt = (metainfo.sex == 'm') * (metainfo.ko == 'MAT') * (metainfo.genotype == 'KLF14-KO:WT') * ~np.isnan(metainfo.BW)
idx_m_mat_het = (metainfo.sex == 'm') * (metainfo.ko == 'MAT') * (metainfo.genotype == 'KLF14-KO:Het') * ~np.isnan(metainfo.BW)

# body weight
bw_f_pat_wt = metainfo.BW[idx_f_pat_wt]
bw_f_pat_het = metainfo.BW[idx_f_pat_het]
bw_f_mat_wt = metainfo.BW[idx_f_mat_wt]
bw_f_mat_het = metainfo.BW[idx_f_mat_het]
bw_m_pat_wt = metainfo.BW[idx_m_pat_wt]
bw_m_pat_het = metainfo.BW[idx_m_pat_het]
bw_m_mat_wt = metainfo.BW[idx_m_mat_wt]
bw_m_mat_het = metainfo.BW[idx_m_mat_het]

# SQWAT depot weight
sq_f_pat_wt = metainfo.SC[idx_f_pat_wt]
sq_f_pat_het = metainfo.SC[idx_f_pat_het]
sq_f_mat_wt = metainfo.SC[idx_f_mat_wt]
sq_f_mat_het = metainfo.SC[idx_f_mat_het]
sq_m_pat_wt = metainfo.SC[idx_m_pat_wt]
sq_m_pat_het = metainfo.SC[idx_m_pat_het]
sq_m_mat_wt = metainfo.SC[idx_m_mat_wt]
sq_m_mat_het = metainfo.SC[idx_m_mat_het]

# GWAT depot weight
g_f_pat_wt = metainfo.gWAT[idx_f_pat_wt]
g_f_pat_het = metainfo.gWAT[idx_f_pat_het]
g_f_mat_wt = metainfo.gWAT[idx_f_mat_wt]
g_f_mat_het = metainfo.gWAT[idx_f_mat_het]
g_m_pat_wt = metainfo.gWAT[idx_m_pat_wt]
g_m_pat_het = metainfo.gWAT[idx_m_pat_het]
g_m_mat_wt = metainfo.gWAT[idx_m_mat_wt]
g_m_mat_het = metainfo.gWAT[idx_m_mat_het]

if DEBUG:
    plt.clf()
    plt.subplot(131)
    plt.boxplot(
        (bw_f_pat_wt, bw_f_pat_het, bw_f_mat_wt, bw_f_mat_het, bw_m_pat_wt, bw_m_pat_het, bw_m_mat_wt, bw_m_mat_het),
        labels=('f_PAT_WT', 'f_PAT_Het', 'f_MAT_WT', 'f_MAT_Het', 'm_PAT_WT', 'm_PAT_Het', 'm_MAT_WT', 'm_MAT_Het'),
        notch=False
    )
    plt.xticks(rotation=45)
    plt.title('Body')
    plt.ylabel('Weight (g)', fontsize=14)
    plt.subplot(132)
    plt.boxplot(
        (sq_f_pat_wt, sq_f_pat_het, sq_f_mat_wt, sq_f_mat_het, sq_m_pat_wt, sq_m_pat_het, sq_m_mat_wt, sq_m_mat_het),
        labels=('f_PAT_WT', 'f_PAT_Het', 'f_MAT_WT', 'f_MAT_Het', 'm_PAT_WT', 'm_PAT_Het', 'm_MAT_WT', 'm_MAT_Het'),
        notch=False
    )
    plt.xticks(rotation=45)
    plt.title('SQWAT')
    plt.subplot(133)
    plt.boxplot(
        (g_f_pat_wt, g_f_pat_het, g_f_mat_wt, g_f_mat_het, g_m_pat_wt, g_m_pat_het, g_m_mat_wt, g_m_mat_het),
        labels=('f_PAT_WT', 'f_PAT_Het', 'f_MAT_WT', 'f_MAT_Het', 'm_PAT_WT', 'm_PAT_Het', 'm_MAT_WT', 'm_MAT_Het'),
        notch=False
    )
    plt.xticks(rotation=45)
    plt.title('GWAT')
    plt.tight_layout()

if DEBUG:
    plt.clf()
    plt.scatter(np.concatenate((bw_f_pat_wt, bw_m_pat_wt)), np.concatenate((sq_f_pat_wt, sq_m_pat_wt)))
    plt.scatter(np.concatenate((bw_f_mat_wt, bw_m_mat_wt)), np.concatenate((sq_f_mat_wt, sq_m_mat_wt)))
    plt.tight_layout()

# linear model
# Ordinary least squares linear model
model = sm.formula.ols('BW ~ C(sex) + C(ko) + C(genotype) + SC * gWAT', data=metainfo).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     BW   R-squared:                       0.740
# Model:                            OLS   Adj. R-squared:                  0.718
# Method:                 Least Squares   F-statistic:                     32.76
# Date:                Fri, 14 Feb 2020   Prob (F-statistic):           2.32e-18
# Time:                        16:33:46   Log-Likelihood:                -210.84
# No. Observations:                  76   AIC:                             435.7
# Df Residuals:                      69   BIC:                             452.0
# Df Model:                           6
# Covariance Type:            nonrobust
# ==============================================================================================
#                                  coef    std err          t      P>|t|      [0.025      0.975]
# ----------------------------------------------------------------------------------------------
# Intercept                     20.4994      2.170      9.449      0.000      16.171      24.827
# C(sex)[T.m]                   10.3729      1.017     10.198      0.000       8.344      12.402
# C(ko)[T.PAT]                  -2.6057      1.023     -2.548      0.013      -4.646      -0.565
# C(genotype)[T.KLF14-KO:WT]     1.1439      0.941      1.216      0.228      -0.733       3.021
# SC                             6.2866      4.062      1.548      0.126      -1.817      14.391
# gWAT                           9.4847      2.434      3.897      0.000       4.630      14.340
# SC:gWAT                       -6.8830      3.465     -1.986      0.051     -13.796       0.030
# ==============================================================================
# Omnibus:                        2.321   Durbin-Watson:                   1.296
# Prob(Omnibus):                  0.313   Jarque-Bera (JB):                1.921
# Skew:                           0.389   Prob(JB):                        0.383
# Kurtosis:                       3.047   Cond. No.                         23.3
# ==============================================================================

# partial regression and influence plots
if DEBUG:
    sm.graphics.plot_partregress_grid(model)
    sm.graphics.influence_plot(model, criterion="cooks")

# list of point with high influence (large residuals and leverage)
idx_influence = [65, 52, 64, 32, 72, 75, 0]
idx_no_influence = list(set(range(metainfo.shape[0])) - set(idx_influence))
print(metainfo.loc[idx_influence, ['id', 'ko', 'sex', 'genotype', 'BW', 'SC', 'gWAT']])

#        id   ko sex      genotype     BW    SC  gWAT
# 65  37.2e  PAT   f  KLF14-KO:Het  21.18  1.62  0.72
# 52  36.3d  PAT   m  KLF14-KO:Het  40.77  1.38  1.78
# 64  37.2d  PAT   f   KLF14-KO:WT  20.02  0.72  0.12
# 32  18.3c  MAT   m   KLF14-KO:WT  37.83  1.24  1.68
# 72  37.4b  PAT   m   KLF14-KO:WT  50.54  0.87  1.11
# 75  38.1f  PAT   m   KLF14-KO:WT  38.98  0.49  0.98
# 0   16.2a  MAT   f   KLF14-KO:WT  40.80  0.38  1.10

# linear model removing the high influence points
# Ordinary least squares linear model
bw_model_no_influence = sm.formula.ols('BW ~ C(sex) + C(ko) + C(genotype) + SC * gWAT', data=metainfo, subset=idx_no_influence).fit()
print(bw_model_no_influence.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     BW   R-squared:                       0.797
# Model:                            OLS   Adj. R-squared:                  0.777
# Method:                 Least Squares   F-statistic:                     40.51
# Date:                Fri, 14 Feb 2020   Prob (F-statistic):           1.20e-19
# Time:                        17:07:13   Log-Likelihood:                -179.50
# No. Observations:                  69   AIC:                             373.0
# Df Residuals:                      62   BIC:                             388.6
# Df Model:                           6
# Covariance Type:            nonrobust
# ==============================================================================================
#                                  coef    std err          t      P>|t|      [0.025      0.975]
# ----------------------------------------------------------------------------------------------
# Intercept                     17.6196      2.188      8.051      0.000      13.245      21.994
# C(sex)[T.m]                    9.2063      0.946      9.728      0.000       7.315      11.098
# C(ko)[T.PAT]                  -3.5029      0.911     -3.845      0.000      -5.324      -1.682
# C(genotype)[T.KLF14-KO:WT]     0.7111      0.833      0.853      0.397      -0.955       2.377
# SC                            23.8520      6.429      3.710      0.000      11.000      36.704
# gWAT                          11.6718      2.399      4.865      0.000       6.875      16.468
# SC:gWAT                      -20.0493      5.320     -3.769      0.000     -30.683      -9.415
# ==============================================================================
# Omnibus:                        2.530   Durbin-Watson:                   1.505
# Prob(Omnibus):                  0.282   Jarque-Bera (JB):                1.543
# Skew:                           0.041   Prob(JB):                        0.462
# Kurtosis:                       2.272   Cond. No.                         38.3
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.

# further refinement of the model, to decrease AIC and BIC, and improve R^2
bw_model_no_influence = sm.formula.ols('BW ~ C(sex) + C(ko) + C(genotype) : (SC * gWAT)', data=metainfo, subset=idx_no_influence).fit()
print(bw_model_no_influence.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     BW   R-squared:                       0.798
# Model:                            OLS   Adj. R-squared:                  0.771
# Method:                 Least Squares   F-statistic:                     29.69
# Date:                Mon, 17 Feb 2020   Prob (F-statistic):           3.92e-18
# Time:                        15:46:06   Log-Likelihood:                -179.24
# No. Observations:                  69   AIC:                             376.5
# Df Residuals:                      60   BIC:                             396.6
# Df Model:                           8
# Covariance Type:            nonrobust
# =====================================================================================================
#                                         coef    std err          t      P>|t|      [0.025      0.975]
# -----------------------------------------------------------------------------------------------------
# Intercept                            17.7812      2.205      8.066      0.000      13.371      22.191
# C(sex)[T.m]                           9.2769      0.969      9.577      0.000       7.339      11.215
# C(ko)[T.PAT]                         -3.4809      0.947     -3.677      0.001      -5.374      -1.588
# C(genotype)[KLF14-KO:Het]:SC         24.3363      7.999      3.042      0.003       8.336      40.337
# C(genotype)[KLF14-KO:WT]:SC          24.5670      7.179      3.422      0.001      10.206      38.928
# C(genotype)[KLF14-KO:Het]:gWAT       11.8047      2.592      4.554      0.000       6.620      16.990
# C(genotype)[KLF14-KO:WT]:gWAT        11.7082      2.688      4.355      0.000       6.331      17.086
# C(genotype)[KLF14-KO:Het]:SC:gWAT   -21.0835      6.575     -3.207      0.002     -34.236      -7.931
# C(genotype)[KLF14-KO:WT]:SC:gWAT    -19.8530      5.828     -3.407      0.001     -31.510      -8.196
# ==============================================================================
# Omnibus:                        1.026   Durbin-Watson:                   1.515
# Prob(Omnibus):                  0.599   Jarque-Bera (JB):                0.925
# Skew:                          -0.009   Prob(JB):                        0.630
# Kurtosis:                       2.433   Cond. No.                         44.9
# ==============================================================================

# range of weight values
print(np.min(metainfo.BW))
print(np.max(metainfo.BW))

print(np.min(metainfo.SC))
print(np.max(metainfo.SC))

print(np.min(metainfo.gWAT))
print(np.max(metainfo.gWAT))


########################################################################################################################
## Cell populations from automatically segmented images in two depots: SQWAT and GWAT.
## This section needs to be run for each of the depots. But the results are saved, so in later sections, it's possible
## to get all the data together
########################################################################################################################

import matplotlib.pyplot as plt
import cytometer.data
from shapely.geometry import Polygon
import openslide
import numpy as np
import scipy.stats
import pandas as pd
from mlxtend.evaluate import permutation_test
from statsmodels.stats.multitest import multipletests
import math

# directories
klf14_root_data_dir = os.path.join(home, 'Data/cytometer_data/klf14')
annotations_dir = os.path.join(home, 'Software/AIDA/dist/data/annotations')
ndpi_dir = os.path.join(home, 'scan_srv2_cox/Maz Yon')
figures_dir = os.path.join(home, 'GoogleDrive/Research/20190727_cytometer_paper/figures')
metainfo_dir = os.path.join(home, 'GoogleDrive/Research/20190727_cytometer_paper')

DEBUG = False

depot = 'sqwat'
# depot = 'gwat'

permutation_sample_size = 9  # the factorial of this number is the number of repetitions in the permutation tests

if depot == 'sqwat':
    # SQWAT: list of annotation files
    json_annotation_files = [
        'KLF14-B6NTAC 36.1d PAT 99-16 C1 - 2016-02-11 11.48.31.json',
        'KLF14-B6NTAC-MAT-16.2d  214-16 C1 - 2016-02-17 16.02.46.json',
        'KLF14-B6NTAC-MAT-17.1a  44-16 C1 - 2016-02-01 11.14.17.json',
        'KLF14-B6NTAC-MAT-17.1e  48-16 C1 - 2016-02-01 16.27.05.json',
        'KLF14-B6NTAC-MAT-18.2a  57-16 C1 - 2016-02-03 09.10.17.json',
        'KLF14-B6NTAC-PAT-37.3c  414-16 C1 - 2016-03-15 17.15.41.json',
        'KLF14-B6NTAC-MAT-18.1d  53-16 C1 - 2016-02-02 14.32.03.json',
        'KLF14-B6NTAC-MAT-17.2b  65-16 C1 - 2016-02-04 10.24.22.json',
        'KLF14-B6NTAC-MAT-17.2g  69-16 C1 - 2016-02-04 16.15.05.json',
        'KLF14-B6NTAC 37.1a PAT 106-16 C1 - 2016-02-12 16.21.00.json',
        'KLF14-B6NTAC-36.1b PAT 97-16 C1 - 2016-02-10 17.38.06.json',
        # 'KLF14-B6NTAC-PAT-37.2d  411-16 C1 - 2016-03-15 12.42.26.json',
        'KLF14-B6NTAC-MAT-17.2a  64-16 C1 - 2016-02-04 09.17.52.json',
        'KLF14-B6NTAC-MAT-16.2f  216-16 C1 - 2016-02-18 10.28.27.json',
        'KLF14-B6NTAC-MAT-17.1d  47-16 C1 - 2016-02-01 15.25.53.json',
        'KLF14-B6NTAC-MAT-16.2e  215-16 C1 - 2016-02-18 09.19.26.json',
        'KLF14-B6NTAC 36.1g PAT 102-16 C1 - 2016-02-11 17.20.14.json',
        'KLF14-B6NTAC-37.1g PAT 112-16 C1 - 2016-02-16 13.33.09.json',
        'KLF14-B6NTAC-38.1e PAT 94-16 C1 - 2016-02-10 12.13.10.json',
        'KLF14-B6NTAC-MAT-18.2d  60-16 C1 - 2016-02-03 13.13.57.json',
        'KLF14-B6NTAC-MAT-18.2g  63-16 C1 - 2016-02-03 16.58.52.json',
        'KLF14-B6NTAC-MAT-18.2f  62-16 C1 - 2016-02-03 15.46.15.json',
        'KLF14-B6NTAC-MAT-18.1b  51-16 C1 - 2016-02-02 09.59.16.json',
        'KLF14-B6NTAC-MAT-19.2c  220-16 C1 - 2016-02-18 17.03.38.json',
        'KLF14-B6NTAC-MAT-18.1f  55-16 C1 - 2016-02-02 16.14.30.json',
        'KLF14-B6NTAC-PAT-36.3b  412-16 C1 - 2016-03-15 14.37.55.json',
        'KLF14-B6NTAC-MAT-16.2c  213-16 C1 - 2016-02-17 14.51.18.json',
        'KLF14-B6NTAC-PAT-37.4a  417-16 C1 - 2016-03-16 15.55.32.json',
        'KLF14-B6NTAC 36.1e PAT 100-16 C1 - 2016-02-11 14.06.56.json',
        'KLF14-B6NTAC-MAT-18.1c  52-16 C1 - 2016-02-02 12.26.58.json',
        'KLF14-B6NTAC-MAT-18.2b  58-16 C1 - 2016-02-03 11.10.52.json',
        'KLF14-B6NTAC-36.1a PAT 96-16 C1 - 2016-02-10 16.12.38.json',
        'KLF14-B6NTAC-PAT-39.2d  454-16 C1 - 2016-03-17 14.33.38.json',
        'KLF14-B6NTAC 36.1c PAT 98-16 C1 - 2016-02-11 10.45.00.json',
        'KLF14-B6NTAC-MAT-18.2e  61-16 C1 - 2016-02-03 14.19.35.json',
        'KLF14-B6NTAC-MAT-19.2g  222-16 C1 - 2016-02-25 15.13.00.json',
        'KLF14-B6NTAC-PAT-37.2a  406-16 C1 - 2016-03-14 12.01.56.json',
        'KLF14-B6NTAC 36.1j PAT 105-16 C1 - 2016-02-12 14.33.33.json',
        'KLF14-B6NTAC-37.1b PAT 107-16 C1 - 2016-02-15 11.43.31.json',
        'KLF14-B6NTAC-MAT-17.1c  46-16 C1 - 2016-02-01 14.02.04.json',
        'KLF14-B6NTAC-MAT-19.2f  217-16 C1 - 2016-02-18 11.48.16.json',
        'KLF14-B6NTAC-MAT-17.2d  67-16 C1 - 2016-02-04 12.34.32.json',
        'KLF14-B6NTAC-MAT-18.3c  218-16 C1 - 2016-02-18 13.12.09.json',
        'KLF14-B6NTAC-PAT-37.3a  413-16 C1 - 2016-03-15 15.54.12.json',
        'KLF14-B6NTAC-MAT-19.1a  56-16 C1 - 2016-02-02 17.23.31.json',
        'KLF14-B6NTAC-37.1h PAT 113-16 C1 - 2016-02-16 15.14.09.json',
        'KLF14-B6NTAC-MAT-18.3d  224-16 C1 - 2016-02-26 11.13.53.json',
        'KLF14-B6NTAC-PAT-37.2g  415-16 C1 - 2016-03-16 11.47.52.json',
        'KLF14-B6NTAC-37.1e PAT 110-16 C1 - 2016-02-15 17.33.11.json',
        'KLF14-B6NTAC-MAT-17.2f  68-16 C1 - 2016-02-04 15.05.54.json',
        'KLF14-B6NTAC 36.1h PAT 103-16 C1 - 2016-02-12 10.15.22.json',
        # 'KLF14-B6NTAC-PAT-39.1h  453-16 C1 - 2016-03-17 11.38.04.json',
        'KLF14-B6NTAC-MAT-16.2b  212-16 C1 - 2016-02-17 12.49.00.json',
        'KLF14-B6NTAC-MAT-17.1f  49-16 C1 - 2016-02-01 17.51.46.json',
        'KLF14-B6NTAC-PAT-36.3d  416-16 C1 - 2016-03-16 14.44.11.json',
        'KLF14-B6NTAC-MAT-16.2a  211-16 C1 - 2016-02-17 11.46.42.json',
        'KLF14-B6NTAC-38.1f PAT 95-16 C1 - 2016-02-10 14.41.44.json',
        'KLF14-B6NTAC-PAT-36.3a  409-16 C1 - 2016-03-15 10.18.46.json',
        'KLF14-B6NTAC-MAT-19.2b  219-16 C1 - 2016-02-18 15.41.38.json',
        'KLF14-B6NTAC-MAT-17.1b  45-16 C1 - 2016-02-01 12.23.50.json',
        'KLF14-B6NTAC 36.1f PAT 101-16 C1 - 2016-02-11 15.23.06.json',
        'KLF14-B6NTAC-MAT-18.1e  54-16 C1 - 2016-02-02 15.26.33.json',
        'KLF14-B6NTAC-37.1d PAT 109-16 C1 - 2016-02-15 15.19.08.json',
        'KLF14-B6NTAC-MAT-18.2c  59-16 C1 - 2016-02-03 11.56.52.json',
        'KLF14-B6NTAC-PAT-37.2f  405-16 C1 - 2016-03-14 10.58.34.json',
        'KLF14-B6NTAC-PAT-37.2e  408-16 C1 - 2016-03-14 16.23.30.json',
        'KLF14-B6NTAC-MAT-19.2e  221-16 C1 - 2016-02-25 14.00.14.json',
        # 'KLF14-B6NTAC-PAT-37.2c  407-16 C1 - 2016-03-14 14.13.54.json',
        # 'KLF14-B6NTAC-PAT-37.2b  410-16 C1 - 2016-03-15 11.24.20.json',
        'KLF14-B6NTAC-PAT-37.4b  419-16 C1 - 2016-03-17 10.22.54.json',
        'KLF14-B6NTAC-37.1c PAT 108-16 C1 - 2016-02-15 14.49.45.json',
        'KLF14-B6NTAC-MAT-18.1a  50-16 C1 - 2016-02-02 09.12.41.json',
        'KLF14-B6NTAC 36.1i PAT 104-16 C1 - 2016-02-12 12.14.38.json',
        'KLF14-B6NTAC-PAT-37.2h  418-16 C1 - 2016-03-16 17.01.17.json',
        'KLF14-B6NTAC-MAT-17.2c  66-16 C1 - 2016-02-04 11.46.39.json',
        'KLF14-B6NTAC-MAT-18.3b  223-16 C2 - 2016-02-26 10.35.52.json',
        'KLF14-B6NTAC-37.1f PAT 111-16 C2 - 2016-02-16 11.26 (1).json',
        'KLF14-B6NTAC-PAT 37.2b 410-16 C4 - 2020-02-14 10.27.23.json',
        'KLF14-B6NTAC-PAT 37.2c 407-16 C4 - 2020-02-14 10.15.57.json',
        # 'KLF14-B6NTAC-PAT 37.2d 411-16 C4 - 2020-02-14 10.34.10.json'
    ]
elif depot == 'gwat':
    # GWAT: list of annotation files
    json_annotation_files = [
        'KLF14-B6NTAC-36.1a PAT 96-16 B1 - 2016-02-10 15.32.31.json',
        'KLF14-B6NTAC-36.1b PAT 97-16 B1 - 2016-02-10 17.15.16.json',
        'KLF14-B6NTAC-36.1c PAT 98-16 B1 - 2016-02-10 18.32.40.json',
        'KLF14-B6NTAC 36.1d PAT 99-16 B1 - 2016-02-11 11.29.55.json',
        'KLF14-B6NTAC 36.1e PAT 100-16 B1 - 2016-02-11 12.51.11.json',
        'KLF14-B6NTAC 36.1f PAT 101-16 B1 - 2016-02-11 14.57.03.json',
        'KLF14-B6NTAC 36.1g PAT 102-16 B1 - 2016-02-11 16.12.01.json',
        'KLF14-B6NTAC 36.1h PAT 103-16 B1 - 2016-02-12 09.51.08.json',
        # 'KLF14-B6NTAC 36.1i PAT 104-16 B1 - 2016-02-12 11.37.56.json',
        'KLF14-B6NTAC 36.1j PAT 105-16 B1 - 2016-02-12 14.08.19.json',
        'KLF14-B6NTAC 37.1a PAT 106-16 B1 - 2016-02-12 15.33.02.json',
        'KLF14-B6NTAC-37.1b PAT 107-16 B1 - 2016-02-15 11.25.20.json',
        'KLF14-B6NTAC-37.1c PAT 108-16 B1 - 2016-02-15 12.33.10.json',
        'KLF14-B6NTAC-37.1d PAT 109-16 B1 - 2016-02-15 15.03.44.json',
        'KLF14-B6NTAC-37.1e PAT 110-16 B1 - 2016-02-15 16.16.06.json',
        'KLF14-B6NTAC-37.1g PAT 112-16 B1 - 2016-02-16 12.02.07.json',
        'KLF14-B6NTAC-37.1h PAT 113-16 B1 - 2016-02-16 14.53.02.json',
        'KLF14-B6NTAC-38.1e PAT 94-16 B1 - 2016-02-10 11.35.53.json',
        'KLF14-B6NTAC-38.1f PAT 95-16 B1 - 2016-02-10 14.16.55.json',
        'KLF14-B6NTAC-MAT-16.2a  211-16 B1 - 2016-02-17 11.21.54.json',
        'KLF14-B6NTAC-MAT-16.2b  212-16 B1 - 2016-02-17 12.33.18.json',
        'KLF14-B6NTAC-MAT-16.2c  213-16 B1 - 2016-02-17 14.01.06.json',
        'KLF14-B6NTAC-MAT-16.2d  214-16 B1 - 2016-02-17 15.43.57.json',
        'KLF14-B6NTAC-MAT-16.2e  215-16 B1 - 2016-02-17 17.14.16.json',
        'KLF14-B6NTAC-MAT-16.2f  216-16 B1 - 2016-02-18 10.05.52.json',
        # 'KLF14-B6NTAC-MAT-17.1a  44-16 B1 - 2016-02-01 09.19.20.json',
        'KLF14-B6NTAC-MAT-17.1b  45-16 B1 - 2016-02-01 12.05.15.json',
        'KLF14-B6NTAC-MAT-17.1c  46-16 B1 - 2016-02-01 13.01.30.json',
        'KLF14-B6NTAC-MAT-17.1d  47-16 B1 - 2016-02-01 15.11.42.json',
        'KLF14-B6NTAC-MAT-17.1e  48-16 B1 - 2016-02-01 16.01.09.json',
        'KLF14-B6NTAC-MAT-17.1f  49-16 B1 - 2016-02-01 17.12.31.json',
        'KLF14-B6NTAC-MAT-17.2a  64-16 B1 - 2016-02-04 08.57.34.json',
        'KLF14-B6NTAC-MAT-17.2b  65-16 B1 - 2016-02-04 10.06.00.json',
        'KLF14-B6NTAC-MAT-17.2c  66-16 B1 - 2016-02-04 11.14.28.json',
        'KLF14-B6NTAC-MAT-17.2d  67-16 B1 - 2016-02-04 12.20.20.json',
        'KLF14-B6NTAC-MAT-17.2f  68-16 B1 - 2016-02-04 14.01.40.json',
        'KLF14-B6NTAC-MAT-17.2g  69-16 B1 - 2016-02-04 15.52.52.json',
        'KLF14-B6NTAC-MAT-18.1a  50-16 B1 - 2016-02-02 08.49.06.json',
        'KLF14-B6NTAC-MAT-18.1b  51-16 B1 - 2016-02-02 09.46.31.json',
        'KLF14-B6NTAC-MAT-18.1c  52-16 B1 - 2016-02-02 11.24.31.json',
        'KLF14-B6NTAC-MAT-18.1d  53-16 B1 - 2016-02-02 14.11.37.json',
        # 'KLF14-B6NTAC-MAT-18.1e  54-16 B1 - 2016-02-02 15.06.05.json',
        'KLF14-B6NTAC-MAT-18.2a  57-16 B1 - 2016-02-03 08.54.27.json',
        'KLF14-B6NTAC-MAT-18.2b  58-16 B1 - 2016-02-03 09.58.06.json',
        'KLF14-B6NTAC-MAT-18.2c  59-16 B1 - 2016-02-03 11.41.32.json',
        'KLF14-B6NTAC-MAT-18.2d  60-16 B1 - 2016-02-03 12.56.49.json',
        'KLF14-B6NTAC-MAT-18.2e  61-16 B1 - 2016-02-03 14.02.25.json',
        'KLF14-B6NTAC-MAT-18.2f  62-16 B1 - 2016-02-03 15.00.17.json',
        'KLF14-B6NTAC-MAT-18.2g  63-16 B1 - 2016-02-03 16.40.37.json',
        'KLF14-B6NTAC-MAT-18.3b  223-16 B1 - 2016-02-25 16.53.42.json',
        'KLF14-B6NTAC-MAT-18.3c  218-16 B1 - 2016-02-18 12.51.46.json',
        'KLF14-B6NTAC-MAT-18.3d  224-16 B1 - 2016-02-26 10.48.56.json',
        'KLF14-B6NTAC-MAT-19.1a  56-16 B1 - 2016-02-02 16.57.46.json',
        'KLF14-B6NTAC-MAT-19.2b  219-16 B1 - 2016-02-18 14.21.50.json',
        'KLF14-B6NTAC-MAT-19.2c  220-16 B1 - 2016-02-18 16.40.48.json',
        'KLF14-B6NTAC-MAT-19.2e  221-16 B1 - 2016-02-25 13.15.27.json',
        'KLF14-B6NTAC-MAT-19.2f  217-16 B1 - 2016-02-18 11.23.22.json',
        'KLF14-B6NTAC-MAT-19.2g  222-16 B1 - 2016-02-25 14.51.57.json',
        'KLF14-B6NTAC-PAT-36.3a  409-16 B1 - 2016-03-15 09.24.54.json',
        'KLF14-B6NTAC-PAT-36.3b  412-16 B1 - 2016-03-15 14.11.47.json',
        'KLF14-B6NTAC-PAT-36.3d  416-16 B1 - 2016-03-16 14.22.04.json',
        # 'KLF14-B6NTAC-PAT-37.2a  406-16 B1 - 2016-03-14 11.46.47.json',
        'KLF14-B6NTAC-PAT-37.2b  410-16 B1 - 2016-03-15 11.12.01.json',
        'KLF14-B6NTAC-PAT-37.2c  407-16 B1 - 2016-03-14 12.54.55.json',
        'KLF14-B6NTAC-PAT-37.2d  411-16 B1 - 2016-03-15 12.01.13.json',
        'KLF14-B6NTAC-PAT-37.2e  408-16 B1 - 2016-03-14 16.06.43.json',
        'KLF14-B6NTAC-PAT-37.2f  405-16 B1 - 2016-03-14 09.49.45.json',
        'KLF14-B6NTAC-PAT-37.2g  415-16 B1 - 2016-03-16 11.04.45.json',
        'KLF14-B6NTAC-PAT-37.2h  418-16 B1 - 2016-03-16 16.42.16.json',
        'KLF14-B6NTAC-PAT-37.3a  413-16 B1 - 2016-03-15 15.31.26.json',
        'KLF14-B6NTAC-PAT-37.3c  414-16 B1 - 2016-03-15 16.49.22.json',
        'KLF14-B6NTAC-PAT-37.4a  417-16 B1 - 2016-03-16 15.25.38.json',
        'KLF14-B6NTAC-PAT-37.4b  419-16 B1 - 2016-03-17 09.10.42.json',
        'KLF14-B6NTAC-PAT-38.1a  90-16 B1 - 2016-02-04 17.27.42.json',
        'KLF14-B6NTAC-PAT-39.1h  453-16 B1 - 2016-03-17 11.15.50.json',
        'KLF14-B6NTAC-PAT-39.2d  454-16 B1 - 2016-03-17 12.16.06.json'
    ]

# modify filenames to select the particular segmentation we want (e.g. the automatic ones, or the manually refined ones)
json_annotation_files = [x.replace('.json', '_exp_0097_corrected.json') for x in json_annotation_files]
json_annotation_files = [os.path.join(annotations_dir, x) for x in json_annotation_files]

# CSV file with metainformation of all mice
metainfo_csv_file = os.path.join(metainfo_dir, 'klf14_b6ntac_meta_info.csv')
metainfo = pd.read_csv(metainfo_csv_file)

quantiles = np.linspace(0, 1, 11)
quantiles = quantiles[1:-1]

# load or compute area quantiles
filename_quantiles = os.path.join(figures_dir, 'klf14_b6ntac_exp_0099_area_quantiles_' + depot + '.npz')
if os.path.isfile(filename_quantiles):

    aux = np.load(filename_quantiles)
    area_q_all = aux['area_q_all']
    id_all = aux['id_all']
    ko_all = aux['ko_all']
    genotype_all = aux['genotype_all']
    sex_all = aux['sex_all']

else:

    area_q_all = []
    id_all = []
    ko_all = []
    genotype_all = []
    sex_all = []
    bw_all = []
    gwat_all = []
    sc_all = []
    for i_file, json_file in enumerate(json_annotation_files):

        print('File ' + str(i_file) + '/' + str(len(json_annotation_files)-1) + ': ' + os.path.basename(json_file))

        if not os.path.isfile(json_file):
            print('Missing file')
            continue

        # ndpi file that corresponds to this .json file
        ndpi_file = json_file.replace('_exp_0097_corrected.json', '.ndpi')
        ndpi_file = ndpi_file.replace(annotations_dir, ndpi_dir)

        # open full resolution histology slide
        im = openslide.OpenSlide(ndpi_file)

        # pixel size
        assert (im.properties['tiff.ResolutionUnit'] == 'centimeter')
        xres = 1e-2 / float(im.properties['tiff.XResolution'])
        yres = 1e-2 / float(im.properties['tiff.YResolution'])

        # create dataframe for this image
        df_common = cytometer.data.tag_values_with_mouse_info(metainfo=metainfo, s=os.path.basename(json_file),
                                                              values=[i_file,], values_tag='i_file',
                                                              tags_to_keep=['id', 'ko', 'genotype', 'sex',
                                                                            'BW', 'gWAT', 'SC'])

        # mouse ID as a string
        id = df_common['id'].values[0]
        ko = df_common['ko'].values[0]
        genotype = df_common['genotype'].values[0]
        sex = df_common['sex'].values[0]
        bw = df_common['BW'].values[0]
        gwat = df_common['gWAT'].values[0]
        sc = df_common['SC'].values[0]

        # read contours from AIDA annotations
        contours = cytometer.data.aida_get_contours(os.path.join(annotations_dir, json_file), layer_name='White adipocyte.*')

        # compute area of each contour
        areas = [Polygon(c).area * xres * yres for c in contours]  # (um^2)

        # compute HD quantiles
        area_q = scipy.stats.mstats.hdquantiles(areas, prob=quantiles, axis=0)

        # append to totals
        area_q_all.append(area_q)
        id_all.append(id)
        ko_all.append(ko)
        genotype_all.append(genotype)
        sex_all.append(sex)
        bw_all.append(bw)
        gwat_all.append(gwat)
        sc_all.append(sc)

    # reorder from largest to smallest final area value
    area_q_all = np.array(area_q_all)
    id_all = np.array(id_all)
    ko_all = np.array(ko_all)
    genotype_all = np.array(genotype_all)
    sex_all = np.array(sex_all)
    bw_all = np.array(bw_all)
    gwat_all = np.array(gwat_all)
    sc_all = np.array(sc_all)

    idx = np.argsort(area_q_all[:, -1])
    idx = idx[::-1]  # sort from larger to smaller
    area_q_all = area_q_all[idx, :]
    id_all = id_all[idx]
    ko_all = ko_all[idx]
    genotype_all = genotype_all[idx]
    sex_all = sex_all[idx]
    bw_all = bw_all[idx]
    gwat_all = gwat_all[idx]
    sc_all = sc_all[idx]

    np.savez_compressed(filename_quantiles, area_q_all=area_q_all, id_all=id_all, ko_all=ko_all, genotype_all=genotype_all,
                        sex_all=sex_all, bw_all=bw_all, gwat_all=gwat_all, sc_all=sc_all)

if DEBUG:
    plt.clf()

    for i in range(len(area_q_all)):

        # plot
        if ko_all[i] == 'PAT':
            color = 'g'
        elif ko_all[i] == 'MAT':
            color = 'r'
        else:
            raise ValueError('Unknown ko value: ' + ko)

        if sex_all[i] == 'f':
            plt.subplot(121)
            plt.plot(quantiles, area_q_all[i] * 1e12 * 1e-3, color=color)
        elif sex_all[i] == 'm':
            plt.subplot(122)
            plt.plot(quantiles, area_q_all[i] * 1e12 * 1e-3, color=color)
        else:
            raise ValueError('Unknown sex value: ' + sex)


    legend_f = [i + ' ' + j.replace('KLF14-KO:', '') for i, j
                in zip(id_all[sex_all == 'f'], genotype_all[sex_all == 'f'])]
    legend_m = [i + ' ' + j.replace('KLF14-KO:', '') for i, j
                in zip(id_all[sex_all == 'm'], genotype_all[sex_all == 'm'])]
    plt.subplot(121)
    plt.title('Female', fontsize=14)
    plt.tick_params(labelsize=14)
    plt.xlabel('Quantile', fontsize=14)
    plt.ylabel('Area ($10^{3}\ \mu m^2$)', fontsize=14)
    plt.legend(legend_f, fontsize=12)
    plt.subplot(122)
    plt.title('Male', fontsize=14)
    plt.tick_params(labelsize=14)
    plt.xlabel('Quantile', fontsize=14)
    plt.legend(legend_m, fontsize=12)

# DEBUG:
# area_q_all = np.vstack((area_q_all, area_q_all))
# id_all = np.hstack((id_all, id_all))
# ko_all = np.hstack((ko_all, ko_all))
# genotype_all = np.hstack((genotype_all, genotype_all))
# sex_all = np.hstack((sex_all, sex_all))

# compute variability of area values for each quantile
area_q_f_pat = area_q_all[(sex_all == 'f') * (ko_all == 'PAT'), :]
area_q_m_pat = area_q_all[(sex_all == 'm') * (ko_all == 'PAT'), :]
area_q_f_mat = area_q_all[(sex_all == 'f') * (ko_all == 'MAT'), :]
area_q_m_mat = area_q_all[(sex_all == 'm') * (ko_all == 'MAT'), :]
area_interval_f_pat = scipy.stats.mstats.hdquantiles(area_q_f_pat, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)
area_interval_m_pat = scipy.stats.mstats.hdquantiles(area_q_m_pat, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)
area_interval_f_mat = scipy.stats.mstats.hdquantiles(area_q_f_mat, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)
area_interval_m_mat = scipy.stats.mstats.hdquantiles(area_q_m_mat, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)

area_q_f_pat_wt = area_q_all[(sex_all == 'f') * (ko_all == 'PAT') * (genotype_all == 'KLF14-KO:WT'), :]
area_q_m_pat_wt = area_q_all[(sex_all == 'm') * (ko_all == 'PAT') * (genotype_all == 'KLF14-KO:WT'), :]
area_q_f_mat_wt = area_q_all[(sex_all == 'f') * (ko_all == 'MAT') * (genotype_all == 'KLF14-KO:WT'), :]
area_q_m_mat_wt = area_q_all[(sex_all == 'm') * (ko_all == 'MAT') * (genotype_all == 'KLF14-KO:WT'), :]
area_interval_f_pat_wt = scipy.stats.mstats.hdquantiles(area_q_f_pat_wt, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)
area_interval_m_pat_wt = scipy.stats.mstats.hdquantiles(area_q_m_pat_wt, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)
area_interval_f_mat_wt = scipy.stats.mstats.hdquantiles(area_q_f_mat_wt, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)
area_interval_m_mat_wt = scipy.stats.mstats.hdquantiles(area_q_m_mat_wt, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)

area_q_f_pat_het = area_q_all[(sex_all == 'f') * (ko_all == 'PAT') * (genotype_all == 'KLF14-KO:Het'), :]
area_q_m_pat_het = area_q_all[(sex_all == 'm') * (ko_all == 'PAT') * (genotype_all == 'KLF14-KO:Het'), :]
area_q_f_mat_het = area_q_all[(sex_all == 'f') * (ko_all == 'MAT') * (genotype_all == 'KLF14-KO:Het'), :]
area_q_m_mat_het = area_q_all[(sex_all == 'm') * (ko_all == 'MAT') * (genotype_all == 'KLF14-KO:Het'), :]
area_interval_f_pat_het = scipy.stats.mstats.hdquantiles(area_q_f_pat_het, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)
area_interval_m_pat_het = scipy.stats.mstats.hdquantiles(area_q_m_pat_het, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)
area_interval_f_mat_het = scipy.stats.mstats.hdquantiles(area_q_f_mat_het, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)
area_interval_m_mat_het = scipy.stats.mstats.hdquantiles(area_q_m_mat_het, prob=[0.025, 0.25, 0.5, 0.75, 0.975], axis=0)

n_f_pat_wt = area_q_f_pat_wt.shape[0]
n_m_pat_wt = area_q_m_pat_wt.shape[0]
n_f_mat_wt = area_q_f_mat_wt.shape[0]
n_m_mat_wt = area_q_m_mat_wt.shape[0]
n_f_pat_het = area_q_f_pat_het.shape[0]
n_m_pat_het = area_q_m_pat_het.shape[0]
n_f_mat_het = area_q_f_mat_het.shape[0]
n_m_mat_het = area_q_m_mat_het.shape[0]

if DEBUG:
    plt.clf()

    plt.subplot(121)
    plt.plot(quantiles * 100, area_interval_f_pat_wt[2, :] * 1e12 * 1e-3, 'C0', linewidth=3, label=str(n_f_pat_wt) + ' Female PAT WT')
    plt.fill_between(quantiles * 100, area_interval_f_pat_wt[1, :] * 1e12 * 1e-3, area_interval_f_pat_wt[3, :] * 1e12 * 1e-3,
                     facecolor='C0', alpha=0.3)
    # plt.plot(quantiles, area_interval_f_pat_wt[0, :] * 1e12 * 1e-3, 'C0:', linewidth=2, label='Female PAT WT 95%-interval')
    # plt.plot(quantiles, area_interval_f_pat_wt[4, :] * 1e12 * 1e-3, 'C0:', linewidth=2)

    plt.plot(quantiles * 100, area_interval_f_pat_het[2, :] * 1e12 * 1e-3, 'C1', linewidth=3, label=str(n_f_pat_het) + ' Female PAT Het')
    plt.fill_between(quantiles * 100, area_interval_f_pat_het[1, :] * 1e12 * 1e-3, area_interval_f_pat_het[3, :] * 1e12 * 1e-3,
                     facecolor='C1', alpha=0.3)

    # plt.title('Inguinal subcutaneous', fontsize=16)
    plt.xlabel('Cell population quantile (%)', fontsize=14)
    plt.ylabel('Area ($\cdot 10^3 \mu$m$^2$)', fontsize=14)
    plt.tick_params(axis='both', which='major', labelsize=14)
    plt.legend(loc='upper left', prop={'size': 12})
    plt.ylim(0, 15)
    plt.tight_layout()

    plt.subplot(122)
    plt.plot(quantiles * 100, area_interval_f_mat_wt[2, :] * 1e12 * 1e-3, 'C2', linewidth=3, label=str(n_f_mat_wt) + ' Female MAT WT')
    plt.fill_between(quantiles * 100, area_interval_f_mat_wt[1, :] * 1e12 * 1e-3, area_interval_f_mat_wt[3, :] * 1e12 * 1e-3,
                     facecolor='C2', alpha=0.3)

    plt.plot(quantiles * 100, area_interval_f_mat_het[2, :] * 1e12 * 1e-3, 'C3', linewidth=3, label=str(n_f_mat_het) + ' Female MAT Het')
    plt.fill_between(quantiles * 100, area_interval_f_mat_het[1, :] * 1e12 * 1e-3, area_interval_f_mat_het[3, :] * 1e12 * 1e-3,
                     facecolor='C3', alpha=0.3)

    # plt.title('Inguinal subcutaneous', fontsize=16)
    plt.xlabel('Cell population quantile (%)', fontsize=14)
    plt.tick_params(axis='both', which='major', labelsize=14)
    plt.legend(loc='upper left', prop={'size': 12})
    plt.ylim(0, 15)
    plt.tight_layout()

    plt.savefig(os.path.join(figures_dir, 'exp_0099_' + depot + '_cell_area_female_pat_vs_mat_bands.svg'))
    plt.savefig(os.path.join(figures_dir, 'exp_0099_' + depot + '_cell_area_female_pat_vs_mat_bands.png'))

if DEBUG:
    plt.clf()

    plt.subplot(121)
    plt.plot(quantiles * 100, area_interval_m_pat_wt[2, :] * 1e12 * 1e-3, 'C0', linewidth=3, label=str(n_m_pat_wt) + ' Male PAT WT')
    plt.fill_between(quantiles * 100, area_interval_m_pat_wt[1, :] * 1e12 * 1e-3, area_interval_m_pat_wt[3, :] * 1e12 * 1e-3,
                     facecolor='C0', alpha=0.3)
    # plt.plot(quantiles, area_interval_f_pat_wt[0, :] * 1e12 * 1e-3, 'C0:', linewidth=2, label='Female PAT WT 95%-interval')
    # plt.plot(quantiles, area_interval_f_pat_wt[4, :] * 1e12 * 1e-3, 'C0:', linewidth=2)

    plt.plot(quantiles * 100, area_interval_m_pat_het[2, :] * 1e12 * 1e-3, 'C1', linewidth=3, label=str(n_m_pat_het) + ' Male PAT Het')
    plt.fill_between(quantiles * 100, area_interval_m_pat_het[1, :] * 1e12 * 1e-3, area_interval_m_pat_het[3, :] * 1e12 * 1e-3,
                     facecolor='C1', alpha=0.3)

    # plt.title('Inguinal subcutaneous', fontsize=16)
    plt.xlabel('Cell population quantile (%)', fontsize=14)
    plt.ylabel('Area ($\cdot 10^3 \mu$m$^2$)', fontsize=14)
    plt.tick_params(axis='both', which='major', labelsize=14)
    plt.legend(loc='upper left', prop={'size': 12})
    plt.ylim(0, 16)
    plt.tight_layout()

    plt.subplot(122)
    plt.plot(quantiles * 100, area_interval_m_mat_wt[2, :] * 1e12 * 1e-3, 'C2', linewidth=3, label=str(n_m_mat_wt) + ' Male MAT WT')
    plt.fill_between(quantiles * 100, area_interval_m_mat_wt[1, :] * 1e12 * 1e-3, area_interval_m_mat_wt[3, :] * 1e12 * 1e-3,
                     facecolor='C2', alpha=0.3)

    plt.plot(quantiles * 100, area_interval_m_mat_het[2, :] * 1e12 * 1e-3, 'C3', linewidth=3, label=str(n_m_mat_het) + ' Male MAT Het')
    plt.fill_between(quantiles * 100, area_interval_m_mat_het[1, :] * 1e12 * 1e-3, area_interval_m_mat_het[3, :] * 1e12 * 1e-3,
                     facecolor='C3', alpha=0.3)

    # plt.title('Inguinal subcutaneous', fontsize=16)
    plt.xlabel('Cell population quantile (%)', fontsize=14)
    plt.tick_params(axis='both', which='major', labelsize=14)
    plt.legend(loc='upper left', prop={'size': 12})
    plt.ylim(0, 16)
    plt.tight_layout()

    plt.savefig(os.path.join(figures_dir, 'exp_0099_' + depot + '_cell_area_male_pat_vs_mat_bands.svg'))
    plt.savefig(os.path.join(figures_dir, 'exp_0099_' + depot + '_cell_area_male_pat_vs_mat_bands.png'))

filename_pvals = os.path.join(figures_dir, 'klf14_b6ntac_exp_0099_pvals_' + depot + '.npz')
if os.path.isfile(filename_pvals):

    aux = np.load(filename_pvals)
    pval_perc_f_pat2mat = aux['pval_perc_f_pat2mat']
    pval_perc_m_pat2mat = aux['pval_perc_m_pat2mat']
    pval_perc_f_pat_wt2het = aux['pval_perc_f_pat_wt2het']
    pval_perc_f_mat_wt2het = aux['pval_perc_f_mat_wt2het']
    pval_perc_m_pat_wt2het = aux['pval_perc_m_pat_wt2het']
    pval_perc_m_mat_wt2het = aux['pval_perc_m_mat_wt2het']
    permutation_sample_size = aux['permutation_sample_size']

else:

    # test whether the median values are different enough between two groups
    func = lambda x, y: np.abs(scipy.stats.mstats.hdquantiles(x, prob=0.5, axis=0).data[0]
                               - scipy.stats.mstats.hdquantiles(y, prob=0.5, axis=0).data[0])
    # func = lambda x, y: np.abs(np.mean(x) - np.mean(y))

    ## PAT vs. MAT

    # test whether the median values are different enough between PAT vs. MAT
    pval_perc_f_pat2mat = np.zeros(shape=(len(quantiles),))
    for i, q in enumerate(quantiles):
        pval_perc_f_pat2mat[i] = permutation_test(x=area_q_f_pat[:, i], y=area_q_f_mat[:, i],
                                                  func=func, seed=None,
                                                  method='approximate', num_rounds=math.factorial(permutation_sample_size))

    pval_perc_m_pat2mat = np.zeros(shape=(len(quantiles),))
    for i, q in enumerate(quantiles):
        pval_perc_m_pat2mat[i] = permutation_test(x=area_q_m_pat[:, i], y=area_q_m_mat[:, i],
                                                  func=func, seed=None,
                                                  method='approximate', num_rounds=math.factorial(permutation_sample_size))

    ## WT vs. Het

    # PAT Females
    pval_perc_f_pat_wt2het = np.zeros(shape=(len(quantiles),))
    for i, q in enumerate(quantiles):
        pval_perc_f_pat_wt2het[i] = permutation_test(x=area_q_f_pat_wt[:, i], y=area_q_f_pat_het[:, i],
                                                     func=func, seed=None,
                                                     method='approximate',
                                                     num_rounds=math.factorial(permutation_sample_size))

    # MAT Females
    pval_perc_f_mat_wt2het = np.zeros(shape=(len(quantiles),))
    for i, q in enumerate(quantiles):
        pval_perc_f_mat_wt2het[i] = permutation_test(x=area_q_f_mat_wt[:, i], y=area_q_f_mat_het[:, i],
                                                     func=func, seed=None,
                                                     method='approximate',
                                                     num_rounds=math.factorial(permutation_sample_size))

    # PAT Males
    pval_perc_m_pat_wt2het = np.zeros(shape=(len(quantiles),))
    for i, q in enumerate(quantiles):
        pval_perc_m_pat_wt2het[i] = permutation_test(x=area_q_m_pat_wt[:, i], y=area_q_m_pat_het[:, i],
                                                     func=func, seed=None,
                                                     method='approximate',
                                                     num_rounds=math.factorial(permutation_sample_size))

    # MAT Males
    pval_perc_m_mat_wt2het = np.zeros(shape=(len(quantiles),))
    for i, q in enumerate(quantiles):
        pval_perc_m_mat_wt2het[i] = permutation_test(x=area_q_m_mat_wt[:, i], y=area_q_m_mat_het[:, i],
                                                     func=func, seed=None,
                                                     method='approximate',
                                                     num_rounds=math.factorial(permutation_sample_size))

    np.savez_compressed(filename_pvals, permutation_sample_size=permutation_sample_size,
                        pval_perc_f_pat2mat=pval_perc_f_pat2mat, pval_perc_m_pat2mat=pval_perc_m_pat2mat,
                        pval_perc_f_pat_wt2het=pval_perc_f_pat_wt2het, pval_perc_f_mat_wt2het=pval_perc_f_mat_wt2het,
                        pval_perc_m_pat_wt2het=pval_perc_m_pat_wt2het, pval_perc_m_mat_wt2het=pval_perc_m_mat_wt2het)


# data has been loaded or computed

np.set_printoptions(precision=2)
print('PAT vs. MAT before multitest correction')
print('Female:')
print(pval_perc_f_pat2mat)
print('Male:')
print(pval_perc_m_pat2mat)
np.set_printoptions(precision=8)

# multitest correction using Hochberg a.k.a. Simes-Hochberg method
_, pval_perc_f_pat2mat, _, _ = multipletests(pval_perc_f_pat2mat, method='simes-hochberg', alpha=0.05, returnsorted=False)
_, pval_perc_m_pat2mat, _, _ = multipletests(pval_perc_m_pat2mat, method='simes-hochberg', alpha=0.05, returnsorted=False)

np.set_printoptions(precision=2)
print('PAT vs. MAT with multitest correction')
print('Female:')
print(pval_perc_f_pat2mat)
print('Male:')
print(pval_perc_m_pat2mat)
np.set_printoptions(precision=8)

np.set_printoptions(precision=2)
print('WT vs. Het before multitest correction')
print('Female:')
print(pval_perc_f_pat_wt2het)
print(pval_perc_f_mat_wt2het)
print('Male:')
print(pval_perc_m_pat_wt2het)
print(pval_perc_m_mat_wt2het)
np.set_printoptions(precision=8)

# multitest correction using Hochberg a.k.a. Simes-Hochberg method
_, pval_perc_f_pat_wt2het, _, _ = multipletests(pval_perc_f_pat_wt2het, method='simes-hochberg', alpha=0.05, returnsorted=False)
_, pval_perc_f_mat_wt2het, _, _ = multipletests(pval_perc_f_mat_wt2het, method='simes-hochberg', alpha=0.05, returnsorted=False)
_, pval_perc_m_pat_wt2het, _, _ = multipletests(pval_perc_m_pat_wt2het, method='simes-hochberg', alpha=0.05, returnsorted=False)
_, pval_perc_m_mat_wt2het, _, _ = multipletests(pval_perc_m_mat_wt2het, method='simes-hochberg', alpha=0.05, returnsorted=False)

np.set_printoptions(precision=2)
print('WT vs. Het with multitest correction')
print('Female:')
print(pval_perc_f_pat_wt2het)
print(pval_perc_f_mat_wt2het)
print('Male:')
print(pval_perc_m_pat_wt2het)
print(pval_perc_m_mat_wt2het)
np.set_printoptions(precision=8)

# # plot the median difference and the population quantiles at which the difference is significant
# if DEBUG:
#     plt.clf()
#     idx = pval_perc_f_pat2mat < 0.05
#     delta_a_f_pat2mat = (area_interval_f_mat[1, :] - area_interval_f_pat[1, :]) / area_interval_f_pat[1, :]
#     if np.any(idx):
#         plt.stem(quantiles[idx], 100 * delta_a_f_pat2mat[idx],
#                  markerfmt='.', linefmt='C6-', basefmt='C6',
#                  label='p-val$_{\mathrm{PAT}}$ < 0.05')
#
#     idx = pval_perc_m_pat2mat < 0.05
#     delta_a_m_pat2mat = (area_interval_m_mat[1, :] - area_interval_m_pat[1, :]) / area_interval_m_pat[1, :]
#     if np.any(idx):
#         plt.stem(quantiles[idx], 100 * delta_a_m_pat2mat[idx],
#                  markerfmt='.', linefmt='C7-', basefmt='C7', bottom=250,
#                  label='p-val$_{\mathrm{MAT}}$ < 0.05')
#
#     plt.plot(quantiles, 100 * delta_a_f_pat2mat, 'C6', linewidth=3, label='Female PAT to MAT')
#     plt.plot(quantiles, 100 * delta_a_m_pat2mat, 'C7', linewidth=3, label='Male PAT to MAT')
#
#     plt.xlabel('Cell population quantile', fontsize=14)
#     plt.ylabel('Area change (%)', fontsize=14)
#     plt.tick_params(axis='both', which='major', labelsize=14)
#     plt.legend(loc='lower right', prop={'size': 12})
#     plt.tight_layout()
#
#     plt.savefig(os.path.join(figures_dir, 'exp_0099_' + depot + '_cell_area_change_pat_2_mat.svg'))
#     plt.savefig(os.path.join(figures_dir, 'exp_0099_' + depot + '_cell_area_change_pat_2_mat.png'))

########################################################################################################################
## Linear models of body weight (BW), fat depots weight (SC and gWAT), and categorical variables (sex, ko, genotype)
########################################################################################################################

import matplotlib.pyplot as plt
import numpy as np
import scipy.stats
import pandas as pd
import statsmodels.api as sm

# directories
klf14_root_data_dir = os.path.join(home, 'Data/cytometer_data/klf14')
annotations_dir = os.path.join(home, 'Software/AIDA/dist/data/annotations')
ndpi_dir = os.path.join(home, 'scan_srv2_cox/Maz Yon')
figures_dir = os.path.join(home, 'GoogleDrive/Research/20190727_cytometer_paper/figures')
metainfo_dir = os.path.join(home, 'GoogleDrive/Research/20190727_cytometer_paper')

DEBUG = False

# CSV file with metainformation of all mice
metainfo_csv_file = os.path.join(metainfo_dir, 'klf14_b6ntac_meta_info.csv')
metainfo = pd.read_csv(metainfo_csv_file)

# make sure that in the boxplots PAT comes before MAT
metainfo['sex'] = metainfo['sex'].astype(pd.api.types.CategoricalDtype(categories=['f', 'm'], ordered=True))
metainfo['ko'] = metainfo['ko'].astype(pd.api.types.CategoricalDtype(categories=['PAT', 'MAT'], ordered=True))
metainfo['genotype'] = metainfo['genotype'].astype(pd.api.types.CategoricalDtype(categories=['KLF14-KO:WT', 'KLF14-KO:Het'], ordered=True))

quantiles = np.linspace(0, 1, 11)
quantiles = quantiles[1:-1]

# load SQWAT data
depot = 'sqwat'
filename_quantiles = os.path.join(figures_dir, 'klf14_b6ntac_exp_0099_area_quantiles_' + depot + '.npz')

aux = np.load(filename_quantiles)
area_q_sqwat = aux['area_q_all']
id_sqwat = aux['id_all']
ko_sqwat = aux['ko_all']
genotype_sqwat = aux['genotype_all']
sex_sqwat = aux['sex_all']

# load gWAT data
depot = 'gwat'
filename_quantiles = os.path.join(figures_dir, 'klf14_b6ntac_exp_0099_area_quantiles_' + depot + '.npz')

aux = np.load(filename_quantiles)
area_q_gwat = aux['area_q_all']
id_gwat = aux['id_all']
ko_gwat = aux['ko_all']
genotype_gwat = aux['genotype_all']
sex_gwat = aux['sex_all']

# volume sphere with same radius as given circle
def vol_sphere(area_circle):
    return (4 / 3 / np.sqrt(np.pi)) * np.power(area_circle, 3/2)

# add a new column to the metainfo frame with the median cell volume for SQWAT
metainfo_idx = [np.where(metainfo['id'] == x)[0][0] for x in id_sqwat]
metainfo['sc_vol_for_q_50'] = np.NaN
metainfo.loc[metainfo_idx, 'sc_vol_for_q_50'] = vol_sphere(area_q_sqwat[:, 4]) * 1e15  # femto m^3 (fm^2)

# add a new column to the metainfo frame with the median cell volume for gWAT
metainfo_idx = [np.where(metainfo['id'] == x)[0][0] for x in id_gwat]
metainfo['gwat_vol_for_q_50'] = np.NaN
metainfo.loc[metainfo_idx, 'gwat_vol_for_q_50'] = vol_sphere(area_q_gwat[:, 4]) * 1e15  # femto m^3 (fm^2)

if DEBUG:
    # compare SQWAT to gWAT
    plt.clf()
    plt.scatter(metainfo['sc_vol_for_q_50'], metainfo['gwat_vol_for_q_50'])

    # BW vs. SQWAT
    plt.clf()
    plt.scatter(metainfo['sc_vol_for_q_50'], metainfo['BW'])

    # BW vs. gWAT
    plt.clf()
    plt.scatter(metainfo['gwat_vol_for_q_50'], metainfo['BW'])

if DEBUG:
    plt.clf()
    idx = (metainfo['sex'] == 'f') * (metainfo['genotype'] == 'KLF14-KO:WT')
    plt.scatter(metainfo['sc_vol_for_q_50'][idx], metainfo['SC'][idx])

    plt.clf()
    idx = (metainfo['sex'] == 'f') * (metainfo['genotype'] == 'KLF14-KO:WT')
    plt.scatter(metainfo['gwat_vol_for_q_50'][idx], metainfo['gWAT'][idx])

    plt.clf()
    idx = (metainfo['sex'] == 'f') * (metainfo['genotype'] == 'KLF14-KO:WT')
    plt.scatter(metainfo['gwat_vol_for_q_50'][idx], metainfo['gWAT'][idx])

### model BW vs. fat depots

model = sm.formula.ols('BW ~ SC + gWAT', data=metainfo).fit()
print(model.summary())

# partial regression and influence plots
if DEBUG:
    sm.graphics.plot_partregress_grid(model)
    sm.graphics.influence_plot(model, criterion="cooks")

# list of point with high influence (large residuals and leverage)
idx_influence = [65, 64, 4, 63, 35, 72, 5, 45, 62]
idx_no_influence = list(set(range(metainfo.shape[0])) - set(idx_influence))
print(metainfo.loc[idx_influence, ['id', 'ko', 'sex', 'genotype', 'BW', 'SC', 'gWAT']])

# Refine ordinary least squares linear model by removing influence points
model = sm.formula.ols('BW ~ SC + gWAT',
                       data=metainfo, subset=idx_no_influence).fit()
print(model.summary())

if DEBUG:
    sm.graphics.plot_partregress_grid(model)
    sm.graphics.influence_plot(model, criterion="cooks")

########################################################################################################################
### Model BW ~ (SC + gWAT) * (C(sex) + C(ko) + C(genotype))
########################################################################################################################

idx_not_nan = np.where(~np.isnan(metainfo['SC']) * ~np.isnan(metainfo['gWAT']) * ~np.isnan(metainfo['BW']))[0]

model = sm.formula.ols('BW ~ (SC + gWAT) * (C(sex) + C(ko) + C(genotype))', data=metainfo, subset=idx_not_nan).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     BW   R-squared:                       0.791
# Model:                            OLS   Adj. R-squared:                  0.755
# Method:                 Least Squares   F-statistic:                     22.06
# Date:                Tue, 18 Feb 2020   Prob (F-statistic):           9.96e-18
# Time:                        23:42:18   Log-Likelihood:                -202.51
# No. Observations:                  76   AIC:                             429.0
# Df Residuals:                      64   BIC:                             457.0
# Df Model:                          11
# Covariance Type:            nonrobust
# ====================================================================================================
#                                        coef    std err          t      P>|t|      [0.025      0.975]
# ----------------------------------------------------------------------------------------------------
# Intercept                           18.5502      2.232      8.310      0.000      14.091      23.009
# C(sex)[T.m]                         16.7654      2.854      5.875      0.000      11.064      22.467
# C(ko)[T.MAT]                         5.5441      2.569      2.158      0.035       0.412      10.676
# C(genotype)[T.KLF14-KO:Het]         -1.7560      2.476     -0.709      0.481      -6.703       3.191
# SC                                   3.4197      3.191      1.072      0.288      -2.955       9.794
# SC:C(sex)[T.m]                       4.6187      3.122      1.479      0.144      -1.619      10.856
# SC:C(ko)[T.MAT]                    -11.5352      3.622     -3.185      0.002     -18.772      -4.299
# SC:C(genotype)[T.KLF14-KO:Het]      -3.4798      3.162     -1.100      0.275      -9.797       2.837
# gWAT                                 7.4238      2.537      2.926      0.005       2.355      12.493
# gWAT:C(sex)[T.m]                    -8.9189      3.136     -2.844      0.006     -15.184      -2.654
# gWAT:C(ko)[T.MAT]                    3.3366      3.298      1.012      0.316      -3.253       9.926
# gWAT:C(genotype)[T.KLF14-KO:Het]     1.8790      2.930      0.641      0.524      -3.974       7.732
# ==============================================================================
# Omnibus:                        0.797   Durbin-Watson:                   1.371
# Prob(Omnibus):                  0.671   Jarque-Bera (JB):                0.649
# Skew:                           0.225   Prob(JB):                        0.723
# Kurtosis:                       2.946   Cond. No.                         25.1
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.



# partial regression and influence plots
if DEBUG:
    sm.graphics.plot_partregress_grid(model)
    sm.graphics.influence_plot(model, criterion="cooks")

# list of point with high influence (large residuals and leverage)
idx_influence = [65, 49, 72, 68, 35, 0]

# list of data points to use in the model
idx_for_model = (set(range(metainfo.shape[0])) - set(idx_influence)) & set(idx_not_nan)
idx_for_model = list(idx_for_model)

model = sm.formula.ols('BW ~ (SC + gWAT) * (C(sex) + C(ko) + C(genotype))', data=metainfo, subset=idx_for_model).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     BW   R-squared:                       0.850
# Model:                            OLS   Adj. R-squared:                  0.821
# Method:                 Least Squares   F-statistic:                     29.84
# Date:                Tue, 18 Feb 2020   Prob (F-statistic):           7.11e-20
# Time:                        23:47:11   Log-Likelihood:                -172.80
# No. Observations:                  70   AIC:                             369.6
# Df Residuals:                      58   BIC:                             396.6
# Df Model:                          11
# Covariance Type:            nonrobust
# ====================================================================================================
#                                        coef    std err          t      P>|t|      [0.025      0.975]
# ----------------------------------------------------------------------------------------------------
# Intercept                           17.7790      1.874      9.486      0.000      14.027      21.531
# C(sex)[T.m]                         19.9911      2.649      7.547      0.000      14.689      25.293
# C(ko)[T.MAT]                         3.9938      2.216      1.802      0.077      -0.442       8.429
# C(genotype)[T.KLF14-KO:Het]          0.3117      2.183      0.143      0.887      -4.059       4.682
# SC                                   6.1195      2.947      2.077      0.042       0.221      12.018
# SC:C(sex)[T.m]                       1.8228      2.999      0.608      0.546      -4.181       7.826
# SC:C(ko)[T.MAT]                    -10.6039      3.211     -3.303      0.002     -17.031      -4.177
# SC:C(genotype)[T.KLF14-KO:Het]      -2.8646      3.035     -0.944      0.349      -8.940       3.211
# gWAT                                 6.7024      2.178      3.077      0.003       2.342      11.063
# gWAT:C(sex)[T.m]                   -10.6402      2.939     -3.621      0.001     -16.523      -4.757
# gWAT:C(ko)[T.MAT]                    4.6400      2.895      1.603      0.114      -1.156      10.436
# gWAT:C(genotype)[T.KLF14-KO:Het]    -0.0539      2.733     -0.020      0.984      -5.526       5.418
# ==============================================================================
# Omnibus:                        4.137   Durbin-Watson:                   1.553
# Prob(Omnibus):                  0.126   Jarque-Bera (JB):                2.036
# Skew:                           0.056   Prob(JB):                        0.361
# Kurtosis:                       2.172   Cond. No.                         25.8
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.

########################################################################################################################
### Model SC ~ C(sex) * C(ko) * C(genotype)
########################################################################################################################

idx_not_nan = np.where(~np.isnan(metainfo['SC']))[0]

model = sm.formula.ols('SC ~ C(sex) * C(ko) * C(genotype)', data=metainfo, subset=idx_not_nan).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     SC   R-squared:                       0.227
# Model:                            OLS   Adj. R-squared:                  0.148
# Method:                 Least Squares   F-statistic:                     2.859
# Date:                Tue, 18 Feb 2020   Prob (F-statistic):             0.0112
# Time:                        23:55:18   Log-Likelihood:                -19.464
# No. Observations:                  76   AIC:                             54.93
# Df Residuals:                      68   BIC:                             73.57
# Df Model:                           7
# Covariance Type:            nonrobust
# ========================================================================================================================
#                                                            coef    std err          t      P>|t|      [0.025      0.975]
# ------------------------------------------------------------------------------------------------------------------------
# Intercept                                                0.4589      0.110      4.166      0.000       0.239       0.679
# C(sex)[T.m]                                              0.2021      0.152      1.331      0.188      -0.101       0.505
# C(ko)[T.MAT]                                             0.0191      0.152      0.126      0.900      -0.284       0.322
# C(genotype)[T.KLF14-KO:Het]                              0.1789      0.156      1.148      0.255      -0.132       0.490
# C(sex)[T.m]:C(ko)[T.MAT]                                -0.1381      0.212     -0.652      0.517      -0.561       0.285
# C(sex)[T.m]:C(genotype)[T.KLF14-KO:Het]                  0.0651      0.221      0.295      0.769      -0.376       0.506
# C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]                -0.3979      0.215     -1.853      0.068      -0.826       0.031
# C(sex)[T.m]:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]     0.2019      0.304      0.664      0.509      -0.405       0.809
# ==============================================================================
# Omnibus:                        5.761   Durbin-Watson:                   1.023
# Prob(Omnibus):                  0.056   Jarque-Bera (JB):                5.510
# Skew:                           0.659   Prob(JB):                       0.0636
# Kurtosis:                       3.029   Cond. No.                         18.2
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.


if DEBUG:
    sm.graphics.influence_plot(model, criterion="cooks")

# list of point with high influence (large residuals and leverage)
idx_influence = [65, 32]

# list of data points to use in the model
idx_for_model = (set(range(metainfo.shape[0])) - set(idx_influence)) & set(idx_not_nan)
idx_for_model = list(idx_for_model)

model = sm.formula.ols('SC ~ C(sex) * C(ko) * C(genotype)', data=metainfo, subset=idx_for_model).fit()
print(model.summary())


#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     SC   R-squared:                       0.273
# Model:                            OLS   Adj. R-squared:                  0.196
# Method:                 Least Squares   F-statistic:                     3.542
# Date:                Tue, 18 Feb 2020   Prob (F-statistic):            0.00273
# Time:                        23:59:52   Log-Likelihood:                -10.791
# No. Observations:                  74   AIC:                             37.58
# Df Residuals:                      66   BIC:                             56.01
# Df Model:                           7
# Covariance Type:            nonrobust
# ========================================================================================================================
#                                                            coef    std err          t      P>|t|      [0.025      0.975]
# ------------------------------------------------------------------------------------------------------------------------
# Intercept                                                0.4589      0.099      4.644      0.000       0.262       0.656
# C(sex)[T.m]                                              0.2021      0.136      1.484      0.143      -0.070       0.474
# C(ko)[T.MAT]                                             0.0191      0.136      0.140      0.889      -0.253       0.291
# C(genotype)[T.KLF14-KO:Het]                              0.0561      0.144      0.390      0.698      -0.231       0.344
# C(sex)[T.m]:C(ko)[T.MAT]                                -0.2157      0.193     -1.120      0.267      -0.600       0.169
# C(sex)[T.m]:C(genotype)[T.KLF14-KO:Het]                  0.1879      0.201      0.933      0.354      -0.214       0.590
# C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]                -0.2751      0.196     -1.405      0.165      -0.666       0.116
# C(sex)[T.m]:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]     0.1567      0.277      0.566      0.573      -0.396       0.709
# ==============================================================================
# Omnibus:                        6.188   Durbin-Watson:                   1.220
# Prob(Omnibus):                  0.045   Jarque-Bera (JB):                4.506
# Skew:                           0.470   Prob(JB):                        0.105
# Kurtosis:                       2.240   Cond. No.                         18.3
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.


########################################################################################################################
### Model gWAT ~ C(sex) * C(ko) * C(genotype)
########################################################################################################################

idx_not_nan = np.where(~np.isnan(metainfo['gWAT']))[0]

model = sm.formula.ols('gWAT ~ C(sex) * C(ko) * C(genotype)', data=metainfo, subset=idx_not_nan).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                   gWAT   R-squared:                       0.207
# Model:                            OLS   Adj. R-squared:                  0.125
# Method:                 Least Squares   F-statistic:                     2.532
# Date:                Wed, 19 Feb 2020   Prob (F-statistic):             0.0224
# Time:                        00:01:42   Log-Likelihood:                -21.750
# No. Observations:                  76   AIC:                             59.50
# Df Residuals:                      68   BIC:                             78.15
# Df Model:                           7
# Covariance Type:            nonrobust
# ========================================================================================================================
#                                                            coef    std err          t      P>|t|      [0.025      0.975]
# ------------------------------------------------------------------------------------------------------------------------
# Intercept                                                0.7044      0.114      6.205      0.000       0.478       0.931
# C(sex)[T.m]                                              0.3836      0.156      2.451      0.017       0.071       0.696
# C(ko)[T.MAT]                                             0.2656      0.156      1.697      0.094      -0.047       0.578
# C(genotype)[T.KLF14-KO:Het]                              0.1544      0.161      0.962      0.339      -0.166       0.475
# C(sex)[T.m]:C(ko)[T.MAT]                                -0.3236      0.218     -1.482      0.143      -0.759       0.112
# C(sex)[T.m]:C(genotype)[T.KLF14-KO:Het]                 -0.2512      0.228     -1.103      0.274      -0.706       0.203
# C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]                -0.3924      0.221     -1.773      0.081      -0.834       0.049
# C(sex)[T.m]:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]     0.6722      0.313      2.144      0.036       0.047       1.298
# ==============================================================================
# Omnibus:                        0.508   Durbin-Watson:                   1.465
# Prob(Omnibus):                  0.776   Jarque-Bera (JB):                0.659
# Skew:                          -0.122   Prob(JB):                        0.719
# Kurtosis:                       2.615   Cond. No.                         18.2
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.

if DEBUG:
    sm.graphics.influence_plot(model, criterion="cooks")

# list of point with high influence (large residuals and leverage)
idx_influence = [52, 32, 49, 54, 3]

# list of data points to use in the model
idx_for_model = (set(range(metainfo.shape[0])) - set(idx_influence)) & set(idx_not_nan)
idx_for_model = list(idx_for_model)

model = sm.formula.ols('gWAT ~ C(sex) * C(ko) * C(genotype)', data=metainfo, subset=idx_for_model).fit()
print(model.summary())


#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                   gWAT   R-squared:                       0.255
# Model:                            OLS   Adj. R-squared:                  0.172
# Method:                 Least Squares   F-statistic:                     3.073
# Date:                Wed, 19 Feb 2020   Prob (F-statistic):            0.00754
# Time:                        00:04:57   Log-Likelihood:                -11.634
# No. Observations:                  71   AIC:                             39.27
# Df Residuals:                      63   BIC:                             57.37
# Df Model:                           7
# Covariance Type:            nonrobust
# ========================================================================================================================
#                                                            coef    std err          t      P>|t|      [0.025      0.975]
# ------------------------------------------------------------------------------------------------------------------------
# Intercept                                                0.7044      0.101      6.984      0.000       0.503       0.906
# C(sex)[T.m]                                              0.3836      0.139      2.759      0.008       0.106       0.661
# C(ko)[T.MAT]                                             0.2656      0.139      1.910      0.061      -0.012       0.543
# C(genotype)[T.KLF14-KO:Het]                              0.2343      0.147      1.593      0.116      -0.060       0.528
# C(sex)[T.m]:C(ko)[T.MAT]                                -0.3958      0.197     -2.013      0.048      -0.789      -0.003
# C(sex)[T.m]:C(genotype)[T.KLF14-KO:Het]                 -0.3440      0.215     -1.603      0.114      -0.773       0.085
# C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]                -0.4723      0.200     -2.363      0.021      -0.872      -0.073
# C(sex)[T.m]:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]     0.8631      0.291      2.965      0.004       0.281       1.445
# ==============================================================================
# Omnibus:                        2.059   Durbin-Watson:                   1.556
# Prob(Omnibus):                  0.357   Jarque-Bera (JB):                2.011
# Skew:                          -0.345   Prob(JB):                        0.366
# Kurtosis:                       2.548   Cond. No.                         17.8
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.


########################################################################################################################
### Model SC ~ BW : (C(sex) * C(ko) * C(genotype))
########################################################################################################################

idx_not_nan = np.where(~np.isnan(metainfo['SC']) * ~np.isnan(metainfo['BW']))[0]

model = sm.formula.ols('SC ~ BW : (C(sex) * C(ko) * C(genotype))', data=metainfo, subset=idx_not_nan).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     SC   R-squared:                       0.266
# Model:                            OLS   Adj. R-squared:                  0.179
# Method:                 Least Squares   F-statistic:                     3.041
# Date:                Wed, 19 Feb 2020   Prob (F-statistic):            0.00561
# Time:                        00:17:04   Log-Likelihood:                -17.495
# No. Observations:                  76   AIC:                             52.99
# Df Residuals:                      67   BIC:                             73.97
# Df Model:                           8
# Covariance Type:            nonrobust
# ===========================================================================================================================
#                                                               coef    std err          t      P>|t|      [0.025      0.975]
# ---------------------------------------------------------------------------------------------------------------------------
# Intercept                                                   0.0891      0.279      0.319      0.750      -0.468       0.646
# BW:C(sex)[f]                                                0.0145      0.011      1.282      0.204      -0.008       0.037
# BW:C(sex)[m]                                                0.0149      0.008      1.977      0.052      -0.000       0.030
# BW:C(ko)[T.MAT]                                            -0.0023      0.006     -0.416      0.678      -0.013       0.009
# BW:C(genotype)[T.KLF14-KO:Het]                              0.0088      0.006      1.447      0.152      -0.003       0.021
# BW:C(sex)[T.m]:C(ko)[T.MAT]                                -0.0015      0.007     -0.221      0.826      -0.015       0.012
# BW:C(sex)[T.m]:C(genotype)[T.KLF14-KO:Het]                 -0.0020      0.007     -0.273      0.786      -0.016       0.012
# BW:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]                -0.0148      0.008     -1.915      0.060      -0.030       0.001
# BW:C(sex)[T.m]:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]     0.0088      0.009      0.930      0.356      -0.010       0.028
# ==============================================================================
# Omnibus:                       12.056   Durbin-Watson:                   0.958
# Prob(Omnibus):                  0.002   Jarque-Bera (JB):               12.564
# Skew:                           0.948   Prob(JB):                      0.00187
# Kurtosis:                       3.613   Cond. No.                         359.
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.



if DEBUG:
    sm.graphics.influence_plot(model, criterion="cooks")

# list of point with high influence (large residuals and leverage)
idx_influence = [65, 32, 31, 35]

# list of data points to use in the model
idx_for_model = (set(range(metainfo.shape[0])) - set(idx_influence)) & set(idx_not_nan)
idx_for_model = list(idx_for_model)

model = sm.formula.ols('SC ~ BW : (C(sex) * C(ko) * C(genotype))', data=metainfo, subset=idx_for_model).fit()
print(model.summary())


#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     SC   R-squared:                       0.421
# Model:                            OLS   Adj. R-squared:                  0.347
# Method:                 Least Squares   F-statistic:                     5.717
# Date:                Wed, 19 Feb 2020   Prob (F-statistic):           1.81e-05
# Time:                        00:22:17   Log-Likelihood:               -0.67179
# No. Observations:                  72   AIC:                             19.34
# Df Residuals:                      63   BIC:                             39.83
# Df Model:                           8
# Covariance Type:            nonrobust
# ===========================================================================================================================
#                                                               coef    std err          t      P>|t|      [0.025      0.975]
# ---------------------------------------------------------------------------------------------------------------------------
# Intercept                                                  -0.3033      0.235     -1.289      0.202      -0.773       0.167
# BW:C(sex)[f]                                                0.0294      0.010      3.092      0.003       0.010       0.048
# BW:C(sex)[m]                                                0.0248      0.006      3.931      0.000       0.012       0.037
# BW:C(ko)[T.MAT]                                            -0.0067      0.005     -1.460      0.149      -0.016       0.002
# BW:C(genotype)[T.KLF14-KO:Het]                              0.0051      0.005      1.023      0.310      -0.005       0.015
# BW:C(sex)[T.m]:C(ko)[T.MAT]                                 0.0008      0.005      0.141      0.889      -0.010       0.012
# BW:C(sex)[T.m]:C(genotype)[T.KLF14-KO:Het]                  0.0020      0.006      0.336      0.738      -0.010       0.014
# BW:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]                -0.0080      0.006     -1.251      0.216      -0.021       0.005
# BW:C(sex)[T.m]:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]     0.0020      0.008      0.261      0.795      -0.013       0.018
# ==============================================================================
# Omnibus:                        6.483   Durbin-Watson:                   1.324
# Prob(Omnibus):                  0.039   Jarque-Bera (JB):                6.679
# Skew:                           0.723   Prob(JB):                       0.0355
# Kurtosis:                       2.632   Cond. No.                         364.
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.



########################################################################################################################
### Model gWAT ~ BW : (C(sex) * C(ko) * C(genotype))
########################################################################################################################

idx_not_nan = np.where(~np.isnan(metainfo['gWAT']) * ~np.isnan(metainfo['BW']))[0]

model = sm.formula.ols('gWAT ~ BW : (C(sex) * C(ko) * C(genotype))', data=metainfo, subset=idx_not_nan).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                   gWAT   R-squared:                       0.355
# Model:                            OLS   Adj. R-squared:                  0.277
# Method:                 Least Squares   F-statistic:                     4.600
# Date:                Wed, 19 Feb 2020   Prob (F-statistic):           0.000167
# Time:                        00:24:15   Log-Likelihood:                -13.917
# No. Observations:                  76   AIC:                             45.83
# Df Residuals:                      67   BIC:                             66.81
# Df Model:                           8
# Covariance Type:            nonrobust
# ===========================================================================================================================
#                                                               coef    std err          t      P>|t|      [0.025      0.975]
# ---------------------------------------------------------------------------------------------------------------------------
# Intercept                                                  -0.2316      0.266     -0.870      0.387      -0.763       0.300
# BW:C(sex)[f]                                                0.0374      0.011      3.456      0.001       0.016       0.059
# BW:C(sex)[m]                                                0.0336      0.007      4.674      0.000       0.019       0.048
# BW:C(ko)[T.MAT]                                             0.0011      0.005      0.208      0.836      -0.010       0.012
# BW:C(genotype)[T.KLF14-KO:Het]                              0.0081      0.006      1.398      0.167      -0.003       0.020
# BW:C(sex)[T.m]:C(ko)[T.MAT]                                -0.0039      0.006     -0.621      0.537      -0.017       0.009
# BW:C(sex)[T.m]:C(genotype)[T.KLF14-KO:Het]                 -0.0092      0.007     -1.334      0.187      -0.023       0.005
# BW:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]                -0.0119      0.007     -1.611      0.112      -0.027       0.003
# BW:C(sex)[T.m]:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]     0.0177      0.009      1.973      0.053      -0.000       0.036
# ==============================================================================
# Omnibus:                        1.698   Durbin-Watson:                   1.319
# Prob(Omnibus):                  0.428   Jarque-Bera (JB):                1.493
# Skew:                           0.341   Prob(JB):                        0.474
# Kurtosis:                       2.926   Cond. No.                         359.
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.


if DEBUG:
    sm.graphics.influence_plot(model, criterion="cooks")

# list of point with high influence (large residuals and leverage)
idx_influence = [52, 32, 35]

# list of data points to use in the model
idx_for_model = (set(range(metainfo.shape[0])) - set(idx_influence)) & set(idx_not_nan)
idx_for_model = list(idx_for_model)

model = sm.formula.ols('gWAT ~ BW : (C(sex) * C(ko) * C(genotype))', data=metainfo, subset=idx_for_model).fit()
print(model.summary())


#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                   gWAT   R-squared:                       0.449
# Model:                            OLS   Adj. R-squared:                  0.380
# Method:                 Least Squares   F-statistic:                     6.520
# Date:                Wed, 19 Feb 2020   Prob (F-statistic):           3.45e-06
# Time:                        00:25:43   Log-Likelihood:                -3.1262
# No. Observations:                  73   AIC:                             24.25
# Df Residuals:                      64   BIC:                             44.87
# Df Model:                           8
# Covariance Type:            nonrobust
# ===========================================================================================================================
#                                                               coef    std err          t      P>|t|      [0.025      0.975]
# ---------------------------------------------------------------------------------------------------------------------------
# Intercept                                                  -0.3909      0.239     -1.636      0.107      -0.868       0.086
# BW:C(sex)[f]                                                0.0434      0.010      4.489      0.000       0.024       0.063
# BW:C(sex)[m]                                                0.0376      0.006      5.855      0.000       0.025       0.050
# BW:C(ko)[T.MAT]                                            -0.0019      0.005     -0.404      0.687      -0.011       0.008
# BW:C(genotype)[T.KLF14-KO:Het]                              0.0085      0.005      1.680      0.098      -0.002       0.019
# BW:C(sex)[T.m]:C(ko)[T.MAT]                                -0.0029      0.006     -0.519      0.606      -0.014       0.008
# BW:C(sex)[T.m]:C(genotype)[T.KLF14-KO:Het]                 -0.0122      0.006     -2.005      0.049      -0.024   -4.74e-05
# BW:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]                -0.0098      0.006     -1.506      0.137      -0.023       0.003
# BW:C(sex)[T.m]:C(ko)[T.MAT]:C(genotype)[T.KLF14-KO:Het]     0.0202      0.008      2.531      0.014       0.004       0.036
# ==============================================================================
# Omnibus:                        1.763   Durbin-Watson:                   1.327
# Prob(Omnibus):                  0.414   Jarque-Bera (JB):                1.285
# Skew:                          -0.058   Prob(JB):                        0.526
# Kurtosis:                       2.360   Cond. No.                         364.
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.

########################################################################################################################
### BW ~ sc_vol_for_q_50 * (sex + ko + genotype)
########################################################################################################################

idx_not_nan = np.where(~np.isnan(metainfo['sc_vol_for_q_50']) * ~np.isnan(metainfo['BW']))[0]

if DEBUG:
    plt.clf()
    plt.scatter(metainfo['sc_vol_for_q_50'], metainfo['BW'])

model = sm.formula.ols('BW ~ sc_vol_for_q_50 * (C(sex) + C(ko) + C(genotype))', data=metainfo, subset=idx_not_nan).fit()
model = sm.formula.ols('sc_vol_for_q_50 ~ BW * (C(sex) + C(ko) + C(genotype))', data=metainfo, subset=idx_not_nan).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     BW   R-squared:                       0.815
# Model:                            OLS   Adj. R-squared:                  0.796
# Method:                 Least Squares   F-statistic:                     41.66
# Date:                Wed, 19 Feb 2020   Prob (F-statistic):           7.89e-22
# Time:                        00:58:02   Log-Likelihood:                -191.22
# No. Observations:                  74   AIC:                             398.4
# Df Residuals:                      66   BIC:                             416.9
# Df Model:                           7
# Covariance Type:            nonrobust
# ===============================================================================================================
#                                                   coef    std err          t      P>|t|      [0.025      0.975]
# ---------------------------------------------------------------------------------------------------------------
# Intercept                                      18.8409      1.924      9.792      0.000      14.999      22.682
# C(sex)[T.m]                                    11.9289      2.245      5.313      0.000       7.447      16.411
# C(ko)[T.MAT]                                    4.1352      1.935      2.137      0.036       0.272       7.998
# C(genotype)[T.KLF14-KO:Het]                     0.2840      1.931      0.147      0.884      -3.571       4.139
# sc_vol_for_q_50                                 0.0735      0.015      5.021      0.000       0.044       0.103
# sc_vol_for_q_50:C(sex)[T.m]                    -0.0248      0.014     -1.724      0.089      -0.053       0.004
# sc_vol_for_q_50:C(ko)[T.MAT]                   -0.0178      0.013     -1.393      0.168      -0.043       0.008
# sc_vol_for_q_50:C(genotype)[T.KLF14-KO:Het]    -0.0065      0.012     -0.521      0.604      -0.031       0.018
# ==============================================================================
# Omnibus:                        2.565   Durbin-Watson:                   1.279
# Prob(Omnibus):                  0.277   Jarque-Bera (JB):                2.143
# Skew:                           0.416   Prob(JB):                        0.342
# Kurtosis:                       3.049   Cond. No.                     1.59e+03
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.
# [2] The condition number is large, 1.59e+03. This might indicate that there are
# strong multicollinearity or other numerical problems.

if DEBUG:
    sm.graphics.influence_plot(model, criterion="cooks")

# list of point with high influence (large residuals and leverage)
idx_influence = [72, 38, 26, 7]

# list of data points to use in the model
idx_for_model = (set(range(metainfo.shape[0])) - set(idx_influence)) & set(idx_not_nan)
idx_for_model = list(idx_for_model)

model = sm.formula.ols('BW ~ sc_vol_for_q_50 * (C(sex) + C(ko) + C(genotype))', data=metainfo, subset=idx_for_model).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:                     BW   R-squared:                       0.860
# Model:                            OLS   Adj. R-squared:                  0.844
# Method:                 Least Squares   F-statistic:                     54.49
# Date:                Wed, 19 Feb 2020   Prob (F-statistic):           4.17e-24
# Time:                        00:59:39   Log-Likelihood:                -170.52
# No. Observations:                  70   AIC:                             357.0
# Df Residuals:                      62   BIC:                             375.0
# Df Model:                           7
# Covariance Type:            nonrobust
# ===============================================================================================================
#                                                   coef    std err          t      P>|t|      [0.025      0.975]
# ---------------------------------------------------------------------------------------------------------------
# Intercept                                      19.0180      1.748     10.883      0.000      15.525      22.511
# C(sex)[T.m]                                    12.5882      2.076      6.064      0.000       8.439      16.738
# C(ko)[T.MAT]                                    1.1443      1.781      0.643      0.523      -2.415       4.704
# C(genotype)[T.KLF14-KO:Het]                    -0.1418      1.770     -0.080      0.936      -3.680       3.396
# sc_vol_for_q_50                                 0.0739      0.014      5.311      0.000       0.046       0.102
# sc_vol_for_q_50:C(sex)[T.m]                    -0.0355      0.014     -2.486      0.016      -0.064      -0.007
# sc_vol_for_q_50:C(ko)[T.MAT]                    0.0079      0.012      0.646      0.520      -0.017       0.032
# sc_vol_for_q_50:C(genotype)[T.KLF14-KO:Het]    -0.0007      0.012     -0.056      0.956      -0.025       0.023
# ==============================================================================
# Omnibus:                        1.230   Durbin-Watson:                   1.287
# Prob(Omnibus):                  0.541   Jarque-Bera (JB):                1.102
# Skew:                           0.301   Prob(JB):                        0.576
# Kurtosis:                       2.880   Cond. No.                     1.55e+03
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.
# [2] The condition number is large, 1.55e+03. This might indicate that there are
# strong multicollinearity or other numerical problems.












## TODO: Review from here

########################################################################################################################
### Model SQWAT cell size vs. BW (but with sex, ko and genotype factors)
########################################################################################################################

if DEBUG:
    plt.clf()
    plt.scatter(metainfo['BW'], metainfo['sc_vol_for_q_50'])

idx_not_nan = np.where(~np.isnan(metainfo['sc_vol_for_q_50']) * ~np.isnan(metainfo['BW']))[0]

model = sm.formula.ols('sc_vol_for_q_50 ~ BW : (C(sex) + C(ko) + C(genotype))', data=metainfo, subset=idx_not_nan).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:        sc_vol_for_q_50   R-squared:                       0.592
# Model:                            OLS   Adj. R-squared:                  0.569
# Method:                 Least Squares   F-statistic:                     25.07
# Date:                Tue, 18 Feb 2020   Prob (F-statistic):           7.67e-13
# Time:                        16:38:11   Log-Likelihood:                -382.30
# No. Observations:                  74   AIC:                             774.6
# Df Residuals:                      69   BIC:                             786.1
# Df Model:                           4
# Covariance Type:            nonrobust
# =================================================================================================
#                                     coef    std err          t      P>|t|      [0.025      0.975]
# -------------------------------------------------------------------------------------------------
# Intercept                      -153.1512     36.864     -4.154      0.000    -226.693     -79.609
# BW:C(sex)[f]                      9.2860      1.321      7.031      0.000       6.651      11.921
# BW:C(sex)[m]                      7.9723      0.953      8.364      0.000       6.071       9.874
# BW:C(ko)[T.PAT]                   0.3883      0.313      1.240      0.219      -0.236       1.013
# BW:C(genotype)[T.KLF14-KO:WT]     0.1731      0.301      0.574      0.568      -0.428       0.774
# ==============================================================================
# Omnibus:                       10.597   Durbin-Watson:                   1.353
# Prob(Omnibus):                  0.005   Jarque-Bera (JB):               10.603
# Skew:                           0.821   Prob(JB):                      0.00498
# Kurtosis:                       3.861   Cond. No.                         273.
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.

if DEBUG:
    sm.graphics.influence_plot(model, criterion="cooks")

# list of rows with great influence in the model
idx_influence = [72, 0, 20, 26, 7, 38]

# list of data points to use in the model
idx_for_model = (set(range(metainfo.shape[0])) - set(idx_influence)) & set(idx_not_nan)
idx_for_model = list(idx_for_model)

model = sm.formula.ols('sc_vol_for_q_50 ~ BW : (C(sex) + C(ko) + C(genotype))', data=metainfo, subset=idx_for_model).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:        sc_vol_for_q_50   R-squared:                       0.679
# Model:                            OLS   Adj. R-squared:                  0.658
# Method:                 Least Squares   F-statistic:                     33.27
# Date:                Tue, 18 Feb 2020   Prob (F-statistic):           6.55e-15
# Time:                        16:38:35   Log-Likelihood:                -337.34
# No. Observations:                  68   AIC:                             684.7
# Df Residuals:                      63   BIC:                             695.8
# Df Model:                           4
# Covariance Type:            nonrobust
# =================================================================================================
#                                     coef    std err          t      P>|t|      [0.025      0.975]
# -------------------------------------------------------------------------------------------------
# Intercept                      -163.7451     36.237     -4.519      0.000    -236.159     -91.331
# BW:C(sex)[f]                      9.3124      1.332      6.990      0.000       6.650      11.975
# BW:C(sex)[m]                      8.0760      0.918      8.794      0.000       6.241       9.911
# BW:C(ko)[T.PAT]                   0.7001      0.269      2.605      0.011       0.163       1.237
# BW:C(genotype)[T.KLF14-KO:WT]     0.1238      0.256      0.483      0.631      -0.388       0.636
# ==============================================================================
# Omnibus:                        1.596   Durbin-Watson:                   1.375
# Prob(Omnibus):                  0.450   Jarque-Bera (JB):                1.244
# Skew:                           0.105   Prob(JB):                        0.537
# Kurtosis:                       2.372   Cond. No.                         310.
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.

# partial regression and influence plots
if DEBUG:
    sm.graphics.plot_partregress_grid(model)
    plt.tight_layout()
    sm.graphics.influence_plot(model, criterion="cooks")

########################################################################################################################
### Model gWAT cell size vs. BW (but with sex, ko and genotype factors)
########################################################################################################################

if DEBUG:
    plt.clf()
    plt.scatter(metainfo['BW'], metainfo['gwat_vol_for_q_50'])

idx_not_nan = np.where(~np.isnan(metainfo['gwat_vol_for_q_50']) * ~np.isnan(metainfo['BW']))[0]

model = sm.formula.ols('gwat_vol_for_q_50 ~ BW : (C(sex) + C(ko) + C(genotype))', data=metainfo, subset=idx_not_nan).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:      gwat_vol_for_q_50   R-squared:                       0.557
# Model:                            OLS   Adj. R-squared:                  0.530
# Method:                 Least Squares   F-statistic:                     20.45
# Date:                Tue, 18 Feb 2020   Prob (F-statistic):           6.05e-11
# Time:                        16:49:01   Log-Likelihood:                -395.06
# No. Observations:                  70   AIC:                             800.1
# Df Residuals:                      65   BIC:                             811.4
# Df Model:                           4
# Covariance Type:            nonrobust
# =================================================================================================
#                                     coef    std err          t      P>|t|      [0.025      0.975]
# -------------------------------------------------------------------------------------------------
# Intercept                       -51.3059     58.729     -0.874      0.386    -168.595      65.983
# BW:C(sex)[f]                      8.9495      2.137      4.187      0.000       4.681      13.218
# BW:C(sex)[m]                      9.3598      1.520      6.160      0.000       6.325      12.395
# BW:C(ko)[T.PAT]                   0.0842      0.524      0.161      0.873      -0.961       1.130
# BW:C(genotype)[T.KLF14-KO:WT]     0.0714      0.507      0.141      0.889      -0.942       1.085
# ==============================================================================
# Omnibus:                        4.234   Durbin-Watson:                   1.987
# Prob(Omnibus):                  0.120   Jarque-Bera (JB):                3.653
# Skew:                          -0.348   Prob(JB):                        0.161
# Kurtosis:                       3.876   Cond. No.                         260.
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.

if DEBUG:
    sm.graphics.influence_plot(model, criterion="cooks")

# list of rows with great influence in the model
idx_influence = [72, 2, 3, 20, 0, 71, 37, 45, 16, 65, 50, 21]
if DEBUG:
    print(metainfo.loc[idx_influence, ['id', 'sex', 'ko', 'genotype']])

# list of data points to use in the model
idx_for_model = (set(range(metainfo.shape[0])) - set(idx_influence)) & set(idx_not_nan)
idx_for_model = list(idx_for_model)

model = sm.formula.ols('gwat_vol_for_q_50 ~ BW : (C(sex) + C(ko) + C(genotype))', data=metainfo, subset=idx_for_model).fit()
print(model.summary())

#                             OLS Regression Results
# ==============================================================================
# Dep. Variable:      gwat_vol_for_q_50   R-squared:                       0.759
# Model:                            OLS   Adj. R-squared:                  0.743
# Method:                 Least Squares   F-statistic:                     45.79
# Date:                Tue, 18 Feb 2020   Prob (F-statistic):           2.60e-17
# Time:                        16:49:20   Log-Likelihood:                -334.73
# No. Observations:                  63   AIC:                             679.5
# Df Residuals:                      58   BIC:                             690.2
# Df Model:                           4
# Covariance Type:            nonrobust
# =================================================================================================
#                                     coef    std err          t      P>|t|      [0.025      0.975]
# -------------------------------------------------------------------------------------------------
# Intercept                       -66.9913     52.843     -1.268      0.210    -172.769      38.786
# BW:C(sex)[f]                      9.1700      1.981      4.628      0.000       5.204      13.136
# BW:C(sex)[m]                     10.3586      1.376      7.530      0.000       7.605      13.112
# BW:C(ko)[T.PAT]                   0.2367      0.401      0.591      0.557      -0.566       1.039
# BW:C(genotype)[T.KLF14-KO:WT]    -0.3079      0.394     -0.782      0.437      -1.096       0.480
# ==============================================================================
# Omnibus:                        0.637   Durbin-Watson:                   1.928
# Prob(Omnibus):                  0.727   Jarque-Bera (JB):                0.164
# Skew:                          -0.018   Prob(JB):                        0.921
# Kurtosis:                       3.247   Cond. No.                         301.
# ==============================================================================
# Warnings:
# [1] Standard Errors assume that the covariance matrix of the errors is correctly specified.

# partial regression and influence plots
if DEBUG:
    sm.graphics.plot_partregress_grid(model)
    plt.tight_layout()
    sm.graphics.influence_plot(model, criterion="cooks")

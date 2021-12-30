#!/usr/bin/env python3

import pathlib
import h5py
from tqdm import trange
import cv2
import math
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from common import color
from common import img_overlays
from pose_body.scripts.openpose_joints import openpose_joints
from common.realsense_params import MIN_VALID_DEPTH_METERS
from common.realsense_params import MAX_VALID_DEPTH_METERS
from common.tracking_params import MIN_CONFIDENCE
import ipdb

JNTS = openpose_joints()
PAIRS = [
    (JNTS.index('UpperNeck'), JNTS.index('LShoulder')),
    (JNTS.index('UpperNeck'), JNTS.index('RShoulder')),
    (JNTS.index('LShoulder'), JNTS.index('LElbow')),
    (JNTS.index('RShoulder'), JNTS.index('RElbow')),
    (JNTS.index('LElbow'),    JNTS.index('LWrist')),
    (JNTS.index('RElbow'),    JNTS.index('RWrist')),
    (JNTS.index('UpperNeck'), JNTS.index('LHip')),
    (JNTS.index('UpperNeck'), JNTS.index('RHip'))
]

JOINTS = [openpose_joints().index(key) for key in [
    "Nose", "LEye", "REye", "LEar", "REar", "LShoulder", "RShoulder",
            "LElbow", "RElbow", "LWrist", "RWrist", "LHip", "RHip", "UpperNeck",
            "HeadTop"
]
]

MIN_VALID_DEPTH_MM = MIN_VALID_DEPTH_METERS*1000
MAX_VALID_DEPTH_MM = MAX_VALID_DEPTH_METERS*1000


def stretch_histogram(img):
    """Stretch histogram of 16 bit single channel image

    https://docs.opencv.org/4.x/d5/daf/tutorial_py_histogram_equalization.html
    this does the same thing as cv2.equalizeHist, but for 16 bit images
    (as opposed to 8 bit)

    Args:
        img: The image to stretch

    Returns: the image, stretched
    """
    hist, bins = np.histogram(img.flatten(), 0xFFFF+1, [0, 0xFFFF+1])
    cdf = hist.cumsum()
    cdf_normalized = cdf * float(hist.max()) / cdf.max()
    cdf_m = np.ma.masked_equal(cdf, 0)
    cdf_m = (cdf_m - cdf_m.min())*0xFFFF/(cdf_m.max()-cdf_m.min())
    cdf = np.ma.filled(cdf_m, 0).astype('uint16')
    return cdf[img]


def overlay_2dSkeleton(directory, cam):
    directory = pathlib.Path(directory)
    hdf5_video = h5py.File(directory/'full_data-vid.hdf5')
    hdf5_tracking = h5py.File(directory/'full_data-novid.hdf5')

    cam_root = f'vid/{cam}'
    color_dset_name = f'{cam_root}/color/data'
    depth_dset_name = f'{cam_root}/depth/data'
    depth_mapping_dset_name = f'{cam_root}/color/matched_depth_index'

    # note, video writer can only take unsigned 8 bit integer images
    video_writer = cv2.VideoWriter(
        str(directory/f'viz-{cam}-2dSkeleton.avi'),
        cv2.VideoWriter_fourcc(*'MJPG'), 30, (1920, 2*1080))

    # by default vridis only has 0xFF steps, so lets take that out
    # to a full 16 bits.
    colormap = mcolors.LinearSegmentedColormap.from_list(
        "", plt.cm.viridis.colors, N=0xFFFF)
    for idx in trange(hdf5_video[color_dset_name].shape[0]):
        depth_idx = hdf5_video[depth_mapping_dset_name][idx]
        color_img = hdf5_video[color_dset_name][idx]
        depth_img = hdf5_video[depth_dset_name][depth_idx]
        depth_img = np.uint16(
            np.clip(depth_img, MIN_VALID_DEPTH_MM, MAX_VALID_DEPTH_MM))
        depth_img = stretch_histogram(depth_img)
        # Want to use a colormap to fully utilize the data in the image.
        # depth images are stored as 16 bit ints (realistically use
        # 2500 steps of data). 8 int grayscale only has 255 steps.
        # By using all 3 channels, we get more than enough fidelity.
        # colormap outputs a float 0-1, so take to 16 bit and make integer.
        # The fourth channel is alpha, so get rid of that
        depth_img = (colormap(depth_img) * 0xFFFF).astype(np.uint16)[:, :, :3]
        depth_img = cv2.cvtColor(depth_img, cv2.COLOR_RGB2BGR)
        # convert from 16 to 8 bit
        depth_img = cv2.convertScaleAbs(depth_img, alpha=(0xFF/0xFFFF))

        color_keypoints = hdf5_tracking[f'{cam_root}/openpose/keypoints'][idx]
        depth_keypoints = hdf5_tracking[f'{cam_root}/openpose/keypoints-depth'][idx]
        confidence = hdf5_tracking[f'{cam_root}/openpose/confidence'][idx]
        color_time = hdf5_tracking[f'{cam_root}/color/time'][idx]
        depth_time = hdf5_tracking[f'{cam_root}/depth/time'][depth_idx]

        img_overlays.draw_text(
            color_img, 'frame: {}'.format(idx), pos=(100, 3))
        img_overlays.draw_text(
            color_img, 'time: {:.2f}'.format(color_time), pos=(500, 3))
        img_overlays.draw_text(
            color_img, 'view: {} realsense'.format(cam), pos=(900, 3))
        img_overlays.draw_text(
            depth_img, 'frame: {}'.format(depth_idx), pos=(100, 3))
        img_overlays.draw_text(
            depth_img, 'time: {:.2f}'.format(depth_time), pos=(500, 3))

        # Joints listed here: https://github.com/CMU-Perceptual-Computing-Lab/openpose/
        # blob/master/doc/02_output.md#keypoints-in-cpython

        for img, keypoints in zip((color_img, depth_img), (color_keypoints, depth_keypoints)):
            for joint in JOINTS:
                if ((not np.any(np.isnan(keypoints[joint][0:2]))) and
                        confidence[joint] > MIN_CONFIDENCE):
                    x_pos = int(keypoints[joint][0])
                    y_pos = int(keypoints[joint][1])
                    cv2.circle(img, (x_pos, y_pos), 10,
                               color.color_scale(confidence[joint], 0, 1), 8)

            for joint in PAIRS:
                if ((not np.any(np.isnan([keypoints[joint[jidx]][0:2] for jidx in (0, 1)])))
                        and np.all([confidence[joint[jidx]] > MIN_CONFIDENCE for jidx in (0, 1)])):
                    x_0 = int(keypoints[joint[0]][0])
                    y_0 = int(keypoints[joint[0]][1])

                    x_1 = int(keypoints[joint[1]][0])
                    y_1 = int(keypoints[joint[1]][1])

                    cv2.line(img, (x_0, y_0), (x_1, y_1), color.color_scale(
                        confidence[joint[0]] + confidence[joint[1]], 0, 1))

        w_padding = int((color_img.shape[0]-depth_img.shape[0])/2)
        h_padding = int((color_img.shape[1]-depth_img.shape[1])/2)
        depth_img = cv2.copyMakeBorder(
            depth_img, w_padding, w_padding, h_padding, h_padding, cv2.BORDER_CONSTANT)
        img = cv2.vconcat([color_img, depth_img])
        video_writer.write(img)

    video_writer.release()
    hdf5_video.close()
    hdf5_tracking.close()

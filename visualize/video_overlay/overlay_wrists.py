#!/usr/bin/env python3

"""A module for overlaying data and text onto images"""

import math
import sys
import numpy as np
from utils import draw_text
from utils import colorScale
import h5py
import cv2
from tqdm import tqdm, trange


def color_scale(mag, cmin, cmax):
    """ Return a tuple of floats between 0 and 1 for R, G, and B. """
    # Normalize to 0-1
    try:
        scale = float(mag-cmin)/(cmax-cmin)
    except ZeroDivisionError:
        scale = 0.5  # cmax == cmin
    blue = min((max((4*(0.75-scale), 0.)), 1.))
    red = min((max((4*(scale-0.25), 0.)), 1.))
    green = min((max((4*math.fabs(scale-0.5)-1., 0.)), 1.))
    return int(red*255), int(green*255), int(blue*255)


def overlay_wrists(file_stub, cam):
    hdf5_video = h5py.File(file_stub+'.hdf5')
    hdf5_tracking = h5py.File(file_stub+'-novid.hdf5')

    dset = 'vid/color/data/{}/data'.format(cam)
    video_writer = cv2.VideoWriter(
        file_stub+'-'+cam+'-wrist.avi', cv2.VideoWriter_fourcc(*'MJPG'), 30, (1920, 1080))
    for idx in trange(hdf5_video[dset].shape[0]):
        img = hdf5_video[dset][idx]
        keypoints = hdf5_tracking[dset+'-keypoints'][idx]
        confidence = hdf5_tracking[dset+'-confidence'][idx]
        sec = hdf5_tracking['vid/color/data/{}/secs'.format(cam)][idx]
        nsec = hdf5_tracking['vid/color/data/{}/nsecs'.format(cam)][idx]
        time = sec+nsec*1e-9

        draw_text(img, 'frame: {}'.format(idx), pos=(100, 3))
        draw_text(img, 'time: {:.2f}'.format(time), pos=(500, 3))
        draw_text(img, 'view: {} realsense'.format(cam), pos=(900, 3))

        # Joints listed here: https://github.com/CMU-Perceptual-Computing-Lab/openpose/
        # blob/master/doc/02_output.md#keypoints-in-cpython
        for joint in (4, 7):
            x = int(keypoints[joint][0])  # pylint: disable=invalid-name
            y = int(keypoints[joint][1])  # pylint: disable=invalid-name
            cv2.circle(img, (x, y), 20,
                       color_scale(confidence[4], 0, 1), 8)

        video_writer.write(img)
    video_writer.release()
    hdf5_video.close()
    hdf5_tracking.close()

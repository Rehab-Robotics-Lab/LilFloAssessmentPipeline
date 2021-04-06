#!/usr/bin/env python3
'''Module for extracting poses from images using openpose'''

import sys
import numpy as np
import cv2
from tqdm import tqdm, trange

try:
    sys.path.append('../python')
    from openpose import pyopenpose as op
except ImportError as err:
    print('Error: OpenPose library could not be found. The path is probably not set correctly')
    raise err


def process_frame(img, op_wrapper):
    """Function to take a Frame and return keypoints and output image with keypoints

    Args:
        img: Image to work with
        op_wrapper: The openpose wrapper
    """

    datum = op.Datum()
    if not img.dtype == np.uint8:
        img = np.uint8(img)
        tqdm.write("Wrong image dtype: Changing to np.uint8")
    # To be resolved
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    datum.cvInputData = img
    op_wrapper.emplaceAndPop(op.VectorDatum([datum]))
    # tqdm.write(datum.poseKeypoints.shape)
    #cv2.imwrite('output/test.jpg', datum.cvOutputData)
    return datum.cvOutputData, datum.poseKeypoints


def process_frames(images):
    """Function to take in a array of RGB images and return a array of images
with keypoints and a separate keypoint array

The last channel is taken as number of images

    Args:
        images: the images to process
    """
    # Params defined here: https://github.com/CMU-Perceptual-Computing-Lab/
    #                      openpose/blob/master/include/openpose/flags.hpp
    params = dict()
    params["model_folder"] = "../../models/"
    params["logging_level"] = 5
    params["number_people_max"] = 1
    params["render_pose"] = 0
    params["display"] = 0
    # tqdm.write("Parameters : ", params)

    if len(images.shape) < 4:
        tqdm.write("Adding Extra Dimension")
        images = np.expand_dims(images, 0)

    num_images = 1

    try:
        num_images = images.shape[0]
    except:  # pylint: disable=bare-except
        pass

    # TODO figure out how to run at [higher accuracy](https://github.com/CMU-Perceptual-Computing-Lab/openpose_train/tree/master/experimental_models#body_25b-model---option-1-maximum-accuracy-less-speed) pylint: disable=line-too-long
    output_keypoints = np.zeros((num_images, 25, 3))
    #OutputPoseKeypoints = []
    op_wrapper = op.WrapperPython()
    op_wrapper.configure(params)
    op_wrapper.start()

    for i in trange(images.shape[0], desc='openpose'):

        image2process = images[i, :, :, :]
        _, pose_keypoints = process_frame(image2process, op_wrapper)
        # OutputImages[:, :, :, i] = OutputImage
        # tqdm.write('for image {} found: {}'.format(i, pose_keypoints))

        # TODO: put this either into a log file or return it somehow to be included in the HDF5 file
        if pose_keypoints is None:
            tqdm.write('\tno one found in image')
            continue
        if pose_keypoints.shape[0] > 1:
            tqdm.write("\tMore than one person Detected: skipping frame")
            continue

        output_keypoints[i, :, :] = pose_keypoints
        # OutputPoseKeypoints.append(poseKeypoints)

    return output_keypoints

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 12 11:30:40 2020

@author: gsuveer
"""


from extractPoses import processFrames
import cv2
import numpy as np

import h5py
'''

cap  = cv2.VideoCapture('test_data/video.avi')

n      = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

Images = np.empty((height,width,3,n))

print("Number of Frames", n)

i = 0
ret = True

while(i<n and ret):
    ret, Images[:,:,:,i] = cap.read()
    i = i+1
    
print(i)
print(type(Images))
print(Images.dtype)

cap.release()


'''
hf = h5py.File('output/experiment1.hdf5', 'r')
dset = hf['Experiment_1/Video/lower_realsense/color/group_1']
Images = np.asarray(dset)


print(Images.dtype)
OutputImages, OutputPoseKeypoints = processFrames(Images)
np.save('output/testdata.npy', OutputImages)
np.save('output/testdata_keypoints.npy', OutputPoseKeypoints)


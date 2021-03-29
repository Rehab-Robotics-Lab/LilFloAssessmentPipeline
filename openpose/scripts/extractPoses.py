"""
Created on Wed Jul  8 23:07:00 2020

@author: gsuveer
"""

import sys
import cv2
import os
import argparse
import numpy as np

try:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.append('../python');
    from openpose import pyopenpose as op
except ImportError as e:
    print('Error: OpenPose library could not be found. The path is probably not set correctly')
    raise e
    

'''
Function to take a Frame and return keypoints and output image with keypoints
'''
def processFrame(img, opWrapper) :
    
    
    datum = op.Datum()
    datum.cvInputData = np.uint8(img)
    opWrapper.emplaceAndPop([datum])
    cv2.imwrite('output/test.jpg', datum.cvOutputData)
    return datum.cvOutputData, datum.poseKeypoints

'''
Function to take in a array of RGB images and return a array of images 
with keypoints and a separate keypoint array

The last channel is taken as number of images
'''

def processFrames(Images):
    params = dict()
    params["model_folder"] = "../../models/"
    print("Parameters : ", params)
    
    if len(Images.shape)<4 :
        Images = np.expand_dims(Images,-1)
    
    OutputImages = np.empty(Images.shape)
    num_images = 1
    
    try :
        num_images = Images.shape[3]
    except:
        pass
    
    #OutputPoseKeypoints = np.zeros((num_images,25,3))
    OutputPoseKeypoints = []
    opWrapper = op.WrapperPython()
    opWrapper.configure(params)
    opWrapper.start()

    for i in range(Images.shape[-1]):
        
        imageToProcess = Images[:,:,:,i]
        OutputImage, poseKeypoints = processFrame(imageToProcess, opWrapper)
        OutputImages[:,:,:,i] = OutputImage
        #OutputPoseKeypoints[i,:,:] = poseKeypoints
        OutputPoseKeypoints.append(poseKeypoints)
    
    return OutputImages, OutputPoseKeypoints

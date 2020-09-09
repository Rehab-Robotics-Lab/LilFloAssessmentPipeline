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
    if not img.dtype == np.uint8:
        img=np.uint8(img)
        print("Wrong image dtype: Changing to np.uint8")
    #To be resolved
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    datum.cvInputData = img
    opWrapper.emplaceAndPop([datum])
    #print(datum.poseKeypoints.shape)
    #cv2.imwrite('output/test.jpg', datum.cvOutputData)

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

        print("Adding Extra Dimension")
        Images = np.expand_dims(Images,-1)
    
    OutputImages = np.empty(Images.shape,dtype=np.uint8)
    num_images = 1
    
    try :
        num_images = Images.shape[3]
    except:
        pass
    

    OutputPoseKeypoints = np.zeros((num_images,25,3))
    #OutputPoseKeypoints = []
    opWrapper = op.WrapperPython()
    opWrapper.configure(params)
    opWrapper.start()

    for i in range(Images.shape[-1]):
        
        imageToProcess = Images[:,:,:,i]
        OutputImage, poseKeypoints = processFrame(imageToProcess, opWrapper)
        OutputImages[:,:,:,i] = OutputImage
        
        if(poseKeypoints.shape[0]>1):
            print("More than one person Detected: skipping frame" )
            continue
        
        OutputPoseKeypoints[i,:,:] = poseKeypoints
        #OutputPoseKeypoints.append(poseKeypoints)
        
    return OutputImages, OutputPoseKeypoints

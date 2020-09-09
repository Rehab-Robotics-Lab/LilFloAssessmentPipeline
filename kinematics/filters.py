#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Sep  5 22:05:35 2020

@author: gsuveer
"""
import scipy
import numpy as np

def removeOutliers(image, kernel_size=3, passes=1, threshold= 10):
    '''
    Input
    ----------
    h*w single channel image
    
    Optionally also inputs kernel size, number of passes, and
    threshold to compare between convolution output and input
    image.

    Returns
    -------
    h*w image with outliers removed 
    '''
    
    if(len(image.shape)>2):
        print("Image with multiple channels passed to removeOutliers")
        return 0
    
    if(kernel_size%2 == 0):
        print("Kernel Size should be odd")
        return 0
    
    kernel = (1/(kernel_size*kernel_size)-1) * np.ones((kernel_size,kernel_size))
    kernel[kernel.shape[0]/2,kernel.shape[1]/2] = 0
    conv_output = image
    for p in passes:
        conv_output = scipy.signal.convolve2d(conv_output, kernel, mode='same', boundary='symm')
    
    diff = np.absolute(image-conv_output)
    idx  = diff>threshold
    
    image[idx] = conv_output[idx]
    
    return image


def median_filter(image, kernel_size=3, passes=1):
    '''
    Parameters
    ----------
    image : h*w single channel image
    kernel_size : size of kernel for median filter
    passes : Number of passes of median filter

    Returns
    -------
    h*w filtered image

    '''
    if(len(image.shape)>2):
        print("Image with multiple channels passed to removeOutliers")
        return 0
    
    if(kernel_size%2 == 0):
        print("Kernel Size should be odd")
        return 0
    
    output = image
    for p in passes:
        output = scipy.signal.medfilt2d(output, kernel_size=kernel_size)
    
    return output

def mean_filter(image, kernel_size=3, passes=1):
    '''
    Parameters
    ----------
    image : h*w single channel image
    kernel_size : size of kernel for median filter
    passes : Number of passes of mean filter

    Returns
    -------
    h*w filtered image

    '''
    if(len(image.shape)>2):
        print("Image with multiple channels passed to removeOutliers")
        return 0
    
    if(kernel_size%2 == 0):
        print("Kernel Size should be odd")
        return 0
    
    kernel = (1/(kernel_size*kernel_size)) * np.ones((kernel_size,kernel_size))
    output = image
    for p in passes:
        output = scipy.signal.convolve2d(output, kernel, mode='same', boundary='symm')
    return output
    
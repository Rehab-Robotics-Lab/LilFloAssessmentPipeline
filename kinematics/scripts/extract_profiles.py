#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: gsuveer
"""

import numpy as np
from scipy.spatial.transform import Rotation as R

def extract_body_bottom_center(keypoints):
    '''
    Given a set of 3D keypoints, returns bottom center point
    '''
    return keypoints[8,:] #Shape (,3)

def extract_left_shoulder_point(keypoints):
    '''
    Given a set of 3D keypoints, returns left shoulder keypoint
    '''
    return keypoints[5,:]

def extract_right_shoulder_point(keypoints):
    '''
    Given a set of 3D keypoints, returns right shoulder point
    '''
    return keypoints[2,:] 

def extract_left_wrist_point(keypoints):
    '''
    Given a set of 3D keypoints, return left wrist point
    '''
    return keypoints[7,:] 

def extract_right_wrist_point(keypoints):
    '''
    Given a  set of 3D keypoints, returns right wrist point
    '''
    return keypoints[4,:] 

def extract_right_elbow_point(keypoints):
    '''
    Given a  set of 3D keypoints, returns right elbow point
    '''
    return keypoints[3,:] 

def extract_left_elbow_point(keypoints):
    '''
    Given a  set of 3D keypoints, returns left elbow point
    '''
    return keypoints[6,:] 

def normalize(vector):
    '''
    Given a n*3 vector retuns a n*3 normalised vectors
    '''
    return vector/np.linalg.norm(vector)    

def right_shoulder_fixed_frame(keypoints):
    '''
    Returns fixed Frame at ls as a 3*3 matrix
    '''
    right_shoulder = extract_right_shoulder_point(keypoints)
    left_shoulder = extract_left_shoulder_point(keypoints)

    #Defining Fixed Frame at Left Shoulder (lsf)

    rsf_z = normalize(np.cross(left_shoulder - right_shoulder, [0,1,0]))
    rsf_y = normalize(np.cross(rsf_z, left_shoulder - right_shoulder))
    rsf_x = normalize(left_shoulder - right_shoulder)
    rs_fixed_frame = np.asarray([rsf_x, rsf_y, rsf_z]).T

    return rs_fixed_frame

def right_shoulder_moving_frame(keypoints):
    '''
    Returns moving Frame at rs as a 3*3 matrix
    '''
    right_elbow = extract_right_elbow_point(keypoints)
    right_shoulder = extract_right_shoulder_point(keypoints)
    right_wrist = extract_right_wrist_point(keypoints)
    
    #Defining moving Frame at Left Shoulder (ls)
    rs_x = normalize(right_shoulder - right_elbow)
    rs_z = normalize(np.cross(rs_x, right_elbow - right_wrist))
    rs_y = normalize(np.cross(rs_z, rs_x))
    rs_moving_frame = np.asarray([rs_x,rs_y,rs_z]).T

    return rs_moving_frame

def left_shoulder_fixed_frame(keypoints):
    '''
    Returns fixed Frame at ls as a 3*3 matrix
    '''
    right_shoulder = extract_right_shoulder_point(keypoints)
    left_shoulder = extract_left_shoulder_point(keypoints)

    #Defining Fixed Frame at Left Shoulder (lsf)

    lsf_z = normalize(np.cross(left_shoulder - right_shoulder, [0,1,0]))
    lsf_y = normalize(np.cross(lsf_z, left_shoulder - right_shoulder))
    lsf_x = normalize(left_shoulder - right_shoulder)
    ls_fixed_frame = np.asarray([lsf_x, lsf_y, lsf_z]).T

    return ls_fixed_frame

def left_shoulder_moving_frame(keypoints):
    '''
    Returns moving Frame at ls as a 3*3 matrix
    '''
    left_elbow = extract_left_elbow_point(keypoints)
    left_shoulder = extract_left_shoulder_point(keypoints)
    left_wrist = extract_left_wrist_point(keypoints)
    
    #Defining moving Frame at Left Shoulder (ls)
    ls_x = normalize(left_elbow - left_shoulder)
    ls_z = normalize(np.cross(ls_x, left_elbow - left_wrist,))
    ls_y = normalize(np.cross(ls_z, ls_x))
    ls_moving_frame = np.asarray([ls_x,ls_y,ls_z]).T

    return ls_moving_frame

def shoulder_angular_motion(keypoints):
    '''
    Given a set of 3D keypoints, returns angular of motion 
    for left and right shoulder
    '''
    fixed_frame = right_shoulder_fixed_frame(keypoints)
    moving_frame = right_shoulder_moving_frame(keypoints)
    R_mat = fixed_frame @ np.linalg.inv(moving_frame)
    r_right_shoulder = R.from_matrix(R_mat)

    fixed_frame = left_shoulder_fixed_frame(keypoints)
    moving_frame = left_shoulder_moving_frame(keypoints)
    R_mat = fixed_frame @ np.linalg.inv(moving_frame)
    r_left_shoulder = R.from_matrix(R_mat)

    return r_right_shoulder, r_left_shoulder

    
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug 23 18:17:57 2020
@author: gsuveer
"""

import numpy as np
import h5py
import cv2
import emotion_recognition.src.emotion_recognition as emo
import kinematics.extract_profiles as kp
import kinematics.filters as filters
import tf
import rospy
import matplotlib.pyplot as plt

def draw_on_image(image, kp):
    #print(image.dtype)
    image = (np.float32(image)/np.max(image))*255
    if(len(image.shape)==2):
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    #print(np.max(image))
    #print(np.min(image))
    
    for i in range(kp.shape[0]):
            #print("x: %d, y: %d" %(int(kp[i,1]),int(kp[i,0])))
            cv2.circle(image, (int(kp[i,0]), int(kp[i,1])), 10, (255,0,255), -1)
    
    plt.imshow(np.uint8(image))
    plt.show()


hf = h5py.File('/media/gsuveer/391cd01c-d5a2-4313-947a-da8978447a80/gsuveer/Desktop/Flo_data/experiment1.hdf5', 'r')

dset = hf['Experiment_1/Video/lower_realsense/color/image_raw']
images = np.asarray(dset[:500,:,:,:])
print(images.shape)
timestamps_secs = hf['Experiment_1/Video/lower_realsense/color/timestamp_secs']
timestamps_necs = hf['Experiment_1/Video/lower_realsense/color/timestamp_nsecs']
color_timestamps = (timestamps_secs[:500] * 1e-9) + timestamps_necs[:500]

K = dset.attrs.get("K")
#How to deal with time
dset = hf['Experiment_1/Video/lower_realsense/depth/image_rect_raw']
depth = np.asarray(dset[:500,:,:])
depth_timestamps_secs = hf['Experiment_1/Video/lower_realsense/depth/timestamp_secs']
depth_timestamps_nsecs = hf['Experiment_1/Video/lower_realsense/depth/timestamp_nsecs']
depth_timestamps = (depth_timestamps_secs[:500]*1e-9) + timestamps_necs[:500]

print(depth.shape)
K_inv = np.linalg.inv(np.reshape(K,(3,3)))
print("K_inv", K_inv)

plt.imshow(images[0,:,:,:])
plt.show()

'''
weights = "emotion_recognition/src/model.h5"
predicted_emotion, prediction_scores_array = emo.extract_emotions(images, weights)
height,width = images.shape[0], images.shape[1]
'''
#Run docker here

'''
video=cv2.VideoWriter('/media/gsuveer/391cd01c-d5a2-4313-947a-da8978447a80/gsuveer/Desktop/Flo_data/video.avi',cv2.VideoWriter_fourcc(*'MJPG'),
                      20,(width,height))
images = np.load('/media/gsuveer/391cd01c-d5a2-4313-947a-da8978447a80/gsuveer/Desktop/Flo_data/testdata.npy')

for i in range(images.shape[3]):
    image = cv2.putText(np.float32(images[:,:,:,i]), 
                        predicted_emotion[i], 
                        (30,30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        1, 
                        (255,0,0), 
                        2)
    #print(image.dtype)
    #print(image.shape)
    video.write(np.uint8(image))

cv2.destroyAllWindows()
video.release()
'''

keypoints = np.load('/media/gsuveer/391cd01c-d5a2-4313-947a-da8978447a80/gsuveer/Desktop/Flo_data/testdata_keypoints.npy')
print("K: " ,np.reshape(K,(3,3)))
K_inv = np.linalg.inv(np.reshape(K,(3,3)))
#Depth Keypoint synchronization
for i in range(keypoints.shape[0]):
    
    idx  = np.argmin(np.absolute(depth_timestamps-color_timestamps[i]))
    depth_image_sync = depth[:,:,idx]

    if(i%100==0):
        print("Depth Timestamp: ",depth_timestamps[idx])
        print("Color Timestamp: ",color_timestamps[i])
        print("Difference Timestamps: ", np.absolute(depth_timestamps[idx]-color_timestamps[i]))
        #depth_image_sync[depth_image_sync > 3000]=0
        draw_on_image(depth_image_sync, keypoints[i,:,:2])
        draw_on_image(filters.removeOutliers(depth_image_sync), 
                      keypoints[i,:,:2])
        
        image = images[:,:,:,i]
        image[depth_image_sync > 3000]=0 
        draw_on_image(image, keypoints[i,:,:2])
        
        
        
    
    z = depth_image_sync[np.uint8(keypoints[i,:,0]),np.uint8(keypoints[i,:,1])]
    
    keypoints[i,:,0] = np.multiply(keypoints[i,:,0] , z)
    keypoints[i,:,1] = np.multiply(keypoints[i,:,1] , z)
    keypoints[i,:,2] = z
    
    #25 * 3
    kp_ = keypoints[i,:,:]
    kp_c= np.matmul(K_inv, kp_.T)  
    keypoints[i,:,:] = kp_c.T
    

keypoints = keypoints/100
T_body = kp.body_center_transforms(keypoints)
T_right_shoulder, T_right_elbow, T_left_shoulder, T_left_elbow = kp.angular_motion(keypoints)
rospy.init_node("TF_Broadcaster")
br = tf.TransformBroadcaster()

for i in range(T_body.shape[-1]):
    br.sendTransform((T_body[0,3,i],T_body[1,3,i],T_body[2,3,i]),
                     tf.transformations.quaternion_from_matrix(T_body[:,:,i]),
                     rospy.Time.now(),"body","camera")
    
    #T_right_shoulder[:,:,i] = np.matmul(T_right_shoulder[:,:,i], np.linalg.inv(T_body[:,:,i]))
    br.sendTransform((T_right_shoulder[0,3,i],T_right_shoulder[1,3,i],T_right_shoulder[2,3,i]),
                     tf.transformations.quaternion_from_matrix(T_right_shoulder[:,:,i]),
                     rospy.Time.now(),"right_shoulder","camera")
    #T_right_elbow[:,:,i] = np.matmul(T_right_elbow, np.matmul(np.linalg.inv(T_body),T_right_shoulder))        
    br.sendTransform((T_right_elbow[0,3,i],T_right_elbow[1,3,i],T_right_elbow[2,3,i]),
                     tf.transformations.quaternion_from_matrix(T_right_elbow[:,:,i]),
                     rospy.Time.now(),"right_elbow","camera")
    
    br.sendTransform((T_left_shoulder[0,3,i],T_left_shoulder[1,3,i],T_left_shoulder[2,3,i]),
                     tf.transformations.quaternion_from_matrix(T_left_shoulder[:,:,i]),
                     rospy.Time.now(),"left_shoulder","camera")
    
    br.sendTransform((T_left_elbow[0,3,i],T_left_elbow[1,3,i],T_left_elbow[2,3,i]),
                     tf.transformations.quaternion_from_matrix(T_left_elbow[:,:,i]),
                     rospy.Time.now(),"left_elbow","camera")
    
    rospy.sleep(0.1)





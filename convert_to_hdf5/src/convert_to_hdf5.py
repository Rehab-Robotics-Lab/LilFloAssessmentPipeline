#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 28 23:21:43 2020

@author: gsuveer
"""

import os
import h5py
import numpy as np
import rospy
import rosbag
from sensor_msgs.msg import Image
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge

if __name__ == '__main__':

    rospy.init_node('rosbag_to_hdf5_node')
    rospy.loginfo('started rosbag to hdf5 conversion')    
    pre_processing_bag_file = rospy.get_param("~pre_processing_bag_file", None)
    rospy.loginfo('Bag file: %s', pre_processing_bag_file)        
    hdf5_filename = rospy.get_param("~hdf5_filename", None)
    rospy.loginfo('HDF5 Filename: %s', hdf5_filename)    
    mode = rospy.get_param("~mode", None)
    rospy.loginfo('Mode: %s', mode)    
    experiment_id = rospy.get_param("~experiment_metadata", None)
    rospy.loginfo('Experiment number: %s', experiment_id)    
    # Reading Bag File
    if not pre_processing_bag_file == "":
        try:
            pre_processing_bag = rosbag.Bag(pre_processing_bag_file)
        except:
            rospy.loginfo("BAG FILE COULD NOT BE READ")
    else:
        rospy.loginfo("No Argument provided for Bag Filename")        
    #Reading hdf5 File
    if not hdf5_filename == "":
        try:
            hdf5_database = h5py.File(hdf5_filename, mode)
        except:
            rospy.loginfo("HDF5 Database COULD NOT BE READ/CREATED")
    else:
        rospy.loginfo("No Argument provided for HDF5 Filename")
        
    experiment_subgroup = hdf5_database.create_group(experiment_id)
    video_subgroup = experiment_subgroup.create_group('Video')
    topics = [  "/upper_realsense/depth/image_rect_raw",
                "/lower_realsense/depth/image_rect_raw",
                "/upper_realsense/color/image_raw",
                "/lower_realsense/color/image_raw",
              ]
    
    #Is it possible to change the namespace of the fisheye camera?
    
    topics_metainfo = ["/upper_realsense/color/camera_info", 
                       "/lower_realsense/color/camera_info",
                       "/upper_realsense/depth/camera_info",
                       "/lower_realsense/depth/camera_info",
                       "/fisheye_cam/camera_info"]    
    
    bridge = CvBridge()
    meta_info = {}
    for topic in topics_metainfo:
        rospy.loginfo('Extracting info from : %s', topic)
        for tp, msg, t in pre_processing_bag.read_messages([topic]):
             meta_info[topic] = msg 
             break
         
    #print(meta_info)
    
    batch_size = 500
    
    for topic in topics:
        rospy.loginfo('Extracting info from : %s', topic)        
        n = pre_processing_bag.get_message_count(topic)
        
        topic_meta_info = meta_info["/"+ topic.split('/')[1] + "/" + topic.split('/')[2]+ "/" + "camera_info"]        
        #Number of Groups to break data into based on batch size
        groups = 1      
        if(n>batch_size):
                groups = int(n/batch_size) + 1
                
        topic_subgroup = video_subgroup.create_group(topic.split('/')[1] + "/" + topic.split('/')[2])
        
        print("Messages: ",n)
        print("Groups: ", groups)
        
        if topic.split('/')[2] == "depth":
            data = np.zeros((topic_meta_info.height, topic_meta_info.width, batch_size), dtype=np.uint16)
        else:
            #Should this be float?
            data = np.zeros((topic_meta_info.height, topic_meta_info.width, 3, batch_size), dtype=np.uint8)
        
        timestamps_secs = []
        timestamps_nsecs = []
        i = 0
        group = 1         
        
        for tp, msg, t in pre_processing_bag.read_messages([topic]):
            if len(data.shape)==3:
                data[:,:,i] = bridge.imgmsg_to_cv2(msg,"16UC1")
            else:
                data[:,:,:,i] = bridge.imgmsg_to_cv2(msg,"bgr8")
                
            timestamps_secs.append(msg.header.stamp.secs)
            timestamps_nsecs.append(msg.header.stamp.nsecs)
            i = i+1             
            if(i == data.shape[-1]):
                rospy.loginfo("Number of Frames Extracted : %d", i)     
                dataset = topic_subgroup.create_dataset("group_"+str(group), data=data)
                dataset.attrs.create("timestamps_secs", timestamps_secs)
                dataset.attrs.create("timestamps_nsecs", timestamps_secs)
                dataset.attrs.create("height", topic_meta_info.height)
                dataset.attrs.create("width", topic_meta_info.width)
                dataset.attrs.create("D", topic_meta_info.D)
                dataset.attrs.create("K", topic_meta_info.K)
                dataset.attrs.create("R", topic_meta_info.R)
                dataset.attrs.create("P", topic_meta_info.P)
                dataset.attrs.create("binning_x", topic_meta_info.binning_x)
                dataset.attrs.create("binning_y", topic_meta_info.binning_y)
                i=0
                group= group+1
                timestamps_nsecs=[]
                timestamps_secs=[]
                
                if groups == group:
                    if(len(data.shape) ==3):
                        data=np.zeros((data.shape[0],data.shape[1], n%batch_size), dtype=np.uint16)
                    else:
                        data=np.zeros((data.shape[0],data.shape[1], data.shape[2], n%batch_size), dtype=np.uint8)
                else:
                    data=np.zeros(data.shape, dtype=np.uint8)
                
    hdf5_database.close()            
    rospy.loginfo("Exiting Process")

    
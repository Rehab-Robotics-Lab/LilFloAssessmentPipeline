#!/usr/bin/env python
import numpy as np
import argparse
import cv2
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Flatten
from tensorflow.keras.layers import Conv2D
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.layers import MaxPooling2D
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import os
import rosbag
import rospy
from cv_bridge import CvBridge
from std_msgs.msg import String, Float32MultiArray


def create_model(weights=None):
    # Create the model
    model = Sequential()

    model.add(Conv2D(32, kernel_size=(3, 3),
                     activation='relu', input_shape=(48, 48, 1)))
    model.add(Conv2D(64, kernel_size=(3, 3), activation='relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))

    model.add(Conv2D(128, kernel_size=(3, 3), activation='relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Conv2D(128, kernel_size=(3, 3), activation='relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))

    model.add(Flatten())
    model.add(Dense(1024, activation='relu'))
    model.add(Dropout(0.5))
    model.add(Dense(7, activation='softmax'))

    try:
        model.load_weights(weights)
    except:
        rospy.loginfo("Could not Load Weights")

    return model

# Takes a RGB frame and the NN model to return the emotion detected on that frame


def process_frame(frame, model, facecasc):

    # Loads the Haar cascade file for face area detection
 
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = facecasc.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    maxindex = None
    prediction = np.zeros((1,7))

    for (x, y, w, h) in faces:
        # Extracting Region of interest
        roi_gray = gray[y:y + h, x:x + w]
        cropped_img = np.expand_dims(np.expand_dims(
            cv2.resize(roi_gray, (48, 48)), -1), 0)
        # Passing image through the model
        prediction = model.predict(cropped_img)

        print(prediction.shape)

    return prediction


if __name__ == '__main__':

    rospy.init_node('emotion_recognition')
    rospy.loginfo('started emotion recognition')

    pre_processing_bag_file = rospy.get_param("~pre_processing_bag_file", None)
    weights = rospy.get_param("~model_weights", None)
    topic = rospy.get_param("~topic", None)
    cascade = rospy.get_param("~cascade", None)

    rospy.loginfo('Bag file: %s', pre_processing_bag_file)
    rospy.loginfo('Weights file: %s', weights)
    rospy.loginfo('Topic: %s', topic)
    rospy.loginfo('Cascade File: %s', cascade)

    #Loading HAARCASCADE File
    if(not(cascade == "")):
        try:
            facecasc = cv2.CascadeClassifier(cascade)
        except:
            rospy.loginfo("HAARCASCADE object could not be initialised")
    else:
        rospy.loginfo("No Argument provided for cascade file")

    # Reading Bag File
    if(not(pre_processing_bag_file == "")):
        try:
            pre_processing_bag = rosbag.Bag(pre_processing_bag_file)
        except:
            rospy.loginfo("BAG FILE COULD NOT BE READ")
    else:
        rospy.loginfo("No Argument provided for Bag Filename")

    # Creating Model
    if(not(weights == "")):
        try:
            model = create_model(weights)
        except:
            rospy.loginfo("COULD NOT CREATE MODEL WITH GIVEN WEIGHTS")
    else:
        rospy.loginfo("No Argument provided for model weights")

    if (topic == ""):
        rospy.loginfo("No Argument provided for topics to read")

    # CvBridge object to convert ROS messages to CV images
    bridge = CvBridge()

    # Index to emotion Mapping
    emotion_dict = {0: "Angry", 1: "Disgusted", 2: "Fearful",
                    3: "Happy", 4: "Neutral", 5: "Sad", 6: "Surprised"}

    for topic, frame, t in pre_processing_bag.read_messages(topics=[topic]):
        # Think about desired encoding
        prediction_scores = process_frame(
            bridge.imgmsg_to_cv2(frame, "rgb8"), model, facecasc)

        print(prediction_scores, t)

        max_index = int(np.argmax(prediction_scores))

        # Writing information to post_processing_bag
        scores = Float32MultiArray()
        scores.data = prediction_scores

        #pre_processing_bag.write(topic + '/prediction_scores', scores)

        predicted_emotion = String()
        predicted_emotion.data = emotion_dict[max_index]

        #pre_processing_bag.write(
        #    topic + '/predicted_emotion', predicted_emotion)

    pre_processing_bag.close()

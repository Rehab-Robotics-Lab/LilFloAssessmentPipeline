# pylint: skip-file
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
import matplotlib.pyplot as plt

'''
Function to initialise the model
'''


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
        print("Could not Load Weights")

    return model


'''
Takes a RGB frame and the NN model to return the emotion detected on that frame
'''


def process_frame(frame, model, facecasc):

    # Loads the Haar cascade file for face area detection
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = facecasc.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    maxindex = None
    prediction = np.zeros((1, 7))

    for (x, y, w, h) in faces:
        # Extracting Region of interest
        roi_gray = gray[y:y + h, x:x + w]
        cropped_img = np.expand_dims(np.expand_dims(
            cv2.resize(roi_gray, (48, 48)), -1), 0)
        # Passing image through the model
        prediction = model.predict(cropped_img)

        # print(prediction.shape)

    return prediction


'''
Function that takes in a block of images and return prediction scores on them
'''


def extract_emotions(images, weights):

    print('Weights file: %s', weights)

    # Check if images are the right shape
    if not len(images.shape) == 4 or not images.shape[2] == 3:
        print(
            "Image input are not the correct shape, Expected(h*w*3*n), got: ", images.shape)

    try:
        facecasc = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    except:
        print("HAARCASCADE object could not be initialised")

    # Creating Model
    if(not(weights == "")):
        try:
            model = create_model(weights)
        except:
            print("COULD NOT CREATE MODEL WITH GIVEN WEIGHTS")
    else:
        print("No Argument provided for model weights")

    # Index to emotion Mapping
    emotion_dict = {0: "Angry", 1: "Disgusted", 2: "Fearful",
                    3: "Happy", 4: "Neutral", 5: "Sad", 6: "Surprised", -1: "No Face"}

    n = images.shape[3]
    prediction_scores_array = np.zeros((7, n))
    predicted_emotion = []
    for i in range(n):
        prediction_scores = process_frame(
            images[:, :, :, i], model, facecasc)
        prediction_scores_array[:, i] = prediction_scores
        max_index = int(np.argmax(prediction_scores))

        if np.sum(prediction_scores) == 0:
            max_index = -1

        predicted_emotion.append(emotion_dict[max_index])

    return predicted_emotion, prediction_scores_array

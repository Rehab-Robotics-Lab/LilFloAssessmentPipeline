#!/usr/bin/env python3

import numpy as np
import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d.axes3d as p3
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import proj3d
import h5py
from tqdm import tqdm, trange
import cv2
import math
import sys
from utils import draw_text
from utils import colorScale
import copy

# Inspiration from: https://medium.com/@pnpsegonne/animating-a-3d-scatterplot-with-matplotlib-ca4b676d4b55


def extract_depth(depth_img, keypoints, inv_Kc, Kd, color_img, window_size=3):

    keypoints_with_depth = np.ones((9, 3))
    keypoints_with_depth[:, :2] = keypoints[:9, :]

    shift = (Kd @ np.asarray([[0.015], [0], [0]]))[0]

    keypoints_in_depth = (Kd @ (inv_Kc @ keypoints_with_depth.T)).T
    keypoints_with_depth = (inv_Kc @ keypoints_with_depth.T).T

    depth_img_ws = copy.deepcopy(depth_img)

    for joint in range(0, 9):
        x = int(keypoints[joint][0])
        y = int(keypoints[joint][1])
        cv2.circle(color_img, (x, y), 10,
                   colorScale(0.8, 0, 1), 8)

        xd = int(keypoints_in_depth[joint][0]) - shift
        yd = int(keypoints_in_depth[joint][1])

        cv2.circle(depth_img_ws, (int(xd+shift), int(yd)), 10,
                   colorScale(0.8, 0, 1), 8)

        cv2.circle(depth_img, (int(xd), int(yd)), 10,
                   colorScale(0.8, 0, 1), 8)
    for i in range(keypoints_with_depth.shape[0]):

        x = int(keypoints_in_depth[i, 0] - shift)
        y = int(keypoints_in_depth[i, 1])
        #print("x: %d y: %d" %(x,y))

        Z = np.mean(depth_img[y - window_size: y + window_size,
                              x - window_size: x + window_size])

        keypoints_with_depth[i] = keypoints_with_depth[i] * (Z/1000)

    return keypoints_with_depth


def animate(iteration, data, scatters, lines, texts, ax, joint_pairs):

    for i in range(len(data[0])):
        scatters[i]._offsets3d = (
            data[iteration][i, 0:1], data[iteration][i, 1:2], data[iteration][i, 2:])

    for i, line in enumerate(lines):
        line.set_data([data[iteration][joint_pairs[i][0], 0], data[iteration][joint_pairs[i][1], 0]],
                      [data[iteration][joint_pairs[i][0], 1], data[iteration][joint_pairs[i][1], 1]])
        line.set_3d_properties(
            [data[iteration][joint_pairs[i][0], 2], data[iteration][joint_pairs[i][1], 2]])

    for i, text in enumerate(texts):
        x, y, _ = proj3d.proj_transform(
            data[iteration][i, 0], data[iteration][i, 1], data[iteration][i, 2], ax.get_proj())
        text.set_position((x, y))

    return scatters, lines, texts


def skeleton_3d(file_stub, cam, save=False):
    hdf5_video = h5py.File(file_stub+'.hdf5', 'r')
    hdf5_tracking = h5py.File(file_stub+'-novid.hdf5', 'r')

    color_dset = 'vid/color/data/{}/data'.format(cam)
    depth_match_dset = 'vid/color/data/{}/matched_depth_index'.format(cam)
    depth_dset = "vid/depth/data/{}/data".format(cam)
    sec = hdf5_video['vid/color/data/{}/secs'.format(cam)]
    nsec = hdf5_video['vid/color/data/{}/nsecs'.format(cam)]
    time = sec[:]+nsec[:]*1e-9

    points3d = []

    K_c = hdf5_video[color_dset].attrs['K'].reshape(3, 3)
    P_c = hdf5_video[color_dset].attrs['P'].reshape(3, 4)
    R_c = hdf5_video[color_dset].attrs['R'].reshape(3, 3)
    inv_Kc = np.linalg.inv(K_c)

    K_d = hdf5_video[depth_dset].attrs['K'].reshape(3, 3)
    P_d = hdf5_video[depth_dset].attrs['P'].reshape(3, 4)
    R_d = hdf5_video[depth_dset].attrs['R'].reshape(3, 3)
    inv_Kd = np.linalg.inv(K_d)

    for idx in trange(hdf5_video[color_dset].shape[0]):
        matched_index = hdf5_video[depth_match_dset][idx]
        depth_img = hdf5_video[depth_dset][matched_index]
        keypoints = hdf5_tracking[color_dset+'-keypoints'][idx]
        confidence = hdf5_tracking[color_dset+'-confidence'][idx]
        color_img = hdf5_video[color_dset][idx]
        points3d.append(extract_depth(
            depth_img, keypoints, inv_Kc, K_d, color_img))

    joint_pairs = [(0, 1), (4, 3), (3, 2), (2, 1),
                   (1, 5), (5, 6), (6, 7), (1, 8)]
    annotations = ['nose', 'neck', 'lshoulder', 'lelbow',
                   'lwrist', 'rshoulder', 'relbow', 'rwrists', 'waist']

    pts = np.asarray(points3d)

    time = time-time[0]
    left_wrist_data = np.append(np.atleast_2d(time).T, pts[:, 4, :], axis=1)
    right_wrist_data = np.append(np.atleast_2d(time).T, pts[:, 7, :], axis=1)
    left_wrist_data = left_wrist_data[~np.isnan(
        left_wrist_data).any(axis=1), :]
    right_wrist_data = right_wrist_data[~np.isnan(
        right_wrist_data).any(axis=1), :]

    with open(file_stub+'-3dpoints-left_wrist.csv', 'wb') as file_handle:
        file_handle.write(b'time,x,y,z\n')
        np.savetxt(file_handle, left_wrist_data, delimiter=',')
    with open(file_stub+'-3dpoints-right_wrist.csv', 'wb') as file_handle:
        file_handle.write(b'time,x,y,z\n')
        np.savetxt(file_handle, right_wrist_data, delimiter=',')

    plt.rc('text', usetex=True)
    plt.rc('font', family='serif')
    fig = plt.figure()
    plt.plot(left_wrist_data)
    fig.savefig(file_stub+'-left.pdf', bbox_inches='tight')
    fig = plt.figure()
    ax = p3.Axes3D(fig)

    scatters = [ax.scatter(points3d[0][i, 0:1], points3d[0][i, 1:2],
                           points3d[0][i, 2:]) for i in range(points3d[0].shape[0])]

    lines = [ax.plot([points3d[0][joint[0], 0], points3d[0][joint[1], 0]],
                     [points3d[0][joint[0], 1], points3d[0][joint[1], 1]],
                     [points3d[0][joint[0], 2], points3d[0][joint[1], 2]],
                     'black')[0] for joint in joint_pairs]

    texts = [ax.text2D(points3d[0][i, 0], points3d[0][i, 1],
                       '%s' % (annotations[i]),
                       size=5,
                       zorder=1, color='k') for i in range(len(annotations))]

    ax.set_xlim3d([-1, 1])
    ax.set_xlabel('X')

    ax.set_ylim3d([-1, 1])
    ax.set_ylabel('Y')

    ax.set_zlim3d([0, 5])
    ax.set_zlabel('Z')

    ax.set_title('3D Skeleton')
    ax.view_init(-90, -86)

    ani = animation.FuncAnimation(fig,
                                  animate,
                                  len(points3d),
                                  fargs=(points3d, scatters, lines,
                                         texts, ax, joint_pairs),
                                  interval=50)

    if save:
        writervideo = animation.FFMpegWriter(fps=60)
        import pdb
        pdb.set_trace()
        ani.save(file_stub + '3d-skeleton.avi', writer=writervideo)

    plt.show()

    hdf5_video.close()
    hdf5_tracking.close()

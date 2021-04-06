#!/usr/bin/env python3
"""Module to extract pose using openpose from hdf5 file"""

import pathlib
import sys
import numpy as np
import h5py
from extract_poses import process_frames
from tqdm import tqdm
from scipy.signal import convolve2d


def allkeys(obj):
    "Recursively find all datasets in an h5py.Group."
    keys = (obj.name,)
    if isinstance(obj, h5py.Group):
        for _, value in obj.items():
            if isinstance(value, h5py.Group):
                keys = keys + allkeys(value)
            else:
                keys = keys + (value.name,)
    return keys


def convert(pth):
    """Extract poses from video in hdf5 file and build new hdf
    file with poses, confidences, and other non-video data.

    Args:
        pth: the path of the hdf5 source file to work with
    """
    print('processing on {}'.format(pth))

    # open hdf5 file
    try:
        hdf5_in = h5py.File(pth, 'r')
    except:  # pylint: disable=bare-except
        print('HDF5 database could not be read')
        raise

    print('opened hdf file')

    # open new hdf5 file
    parents = pathlib.Path(pth).parents[0]
    nme = pathlib.Path(pth).stem+'-novid.hdf5'
    new_pth = parents.joinpath(nme)

    try:
        hdf5_out = h5py.File(new_pth, 'w')
    except:  # pylint: disable=bare-except
        print('HDF5 database could not be created')
        raise
    print('created a new hdf5 file: {}'.format(new_pth))
    nodes = allkeys(hdf5_in)
    print('copying datasets over:')
    for dset in tqdm(nodes, desc='datasets'):
        tqdm.write('\t{}'.format(dset))
        # tqdm.write('\t\tcopying attributes over:')
        # for attribute in hdf5_in[dset].attrs:
        #     tqdm.write('\t\t\t{}'.format(attribute))
        #     hdf5_out[dset].attrs[attribute] = hdf5_in[dset].attrs[attribute]
        if not isinstance(hdf5_in[dset], h5py.Dataset):
            tqdm.write('\t\tNot a dataset')
            continue
        if 'depth' in dset:
            tqdm.write('\t\tNot doing anything with depth')
            continue
        if (not 'vid' in dset) or (not dset.split('/')[-1] == 'data'):
            tqdm.write('\t\tNot video, so copied')
            group = '/'.join(dset.split('/')[0:-1])
            hdf5_out.require_group(group)
            hdf5_in.copy(dset, hdf5_out[group])
        elif 'color' in dset:
            tqdm.write('\t\tVideo, so processing')
            keypoints_dset = hdf5_out.create_dataset(
                dset+'-keypoints', (hdf5_in[dset].len(), 25, 2), dtype=np.float32)
            confidence_dset = hdf5_out.create_dataset(
                dset+'-confidence', (hdf5_in[dset].len(), 25), dtype=np.float32)
            metric_dset = hdf5_out.create_dataset(
                dset+'-metric', (hdf5_in[dset].len(), 25, 3), dtype=np.float32)
            depth_keypoints_dset = hdf5_out.create_dataset(
                dset+'-keypoints-depth', (hdf5_in[dset].len(), 25, 2), dtype=np.float32)
            depth_name = dset.replace('color', 'depth')
            depth_match_name = dset[::-1].replace(
                'data'[::-1], 'matched_depth_index'[::-1], 1)[::-1]
            kernel = np.ones((3, 3)) / 9.0
            k_depth = hdf5_in[depth_name].attrs['K'].reshape(3, 3)
            k_color = hdf5_in[dset].attrs['K'].reshape(3, 3)
            k_color_inv = np.linalg.inv(k_color)
            # TODO: get spatial transform in here:
            transformation = k_depth@k_color_inv
            for chunk in tqdm(hdf5_in[dset].iter_chunks(), desc='chunks'):
                color_arr = hdf5_in[dset][chunk]
                depth_indeces = hdf5_in[depth_match_name][chunk[0]]
                keypoints = process_frames(color_arr)
                keypoints_dset[chunk[0], :, 0:2] = keypoints[:, :, 0:2]
                confidence_dset[chunk[0], :] = keypoints[:, :, 2]
                for idx in range(len(depth_indeces)):
                    depth_data = hdf5_in[depth_name][depth_indeces[idx]]
                    depth_avg = convolve2d(
                        depth_data, kernel, mode='same')
                    for kp_idx in range(keypoints.shape[1]):
                        # TODO wrap this into the transformation
                        depth_space_keypoints = k_depth@(k_color_inv@np.append(
                            keypoints[idx, kp_idx, 0:2], 1)-[.0151, 0, .00039])
                        # TODO: these mins should not be necessary
                        import pdb
                        pdb.set_trace()
                        keypoint_y = max(
                            min(round(depth_space_keypoints[0]), 1280), 0)
                        keypoint_x = max(
                            min(round(depth_space_keypoints[1]), 720), 0)
                        depth_keypoints_dset[idx, kp_idx, :] = [
                            keypoint_x, keypoint_y]
                        this_depth = depth_avg[keypoint_x, keypoint_y]
                        metric_dset[idx, kp_idx, :] = k_color_inv@np.append(
                            keypoints[idx, kp_idx, 0:2], 1) * this_depth
        else:
            tqdm.write('not sure what to do with this dataset')

    print('done processing')
    hdf5_in.close()
    hdf5_out.close()
    print('done closing')


if __name__ == '__main__':
    convert(sys.argv[1])

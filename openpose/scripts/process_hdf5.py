#!/usr/bin/env python3
"""Module to extract pose using openpose from hdf5 file"""

import pathlib
import sys
import numpy as np
import h5py
from extract_poses import process_frames
from tqdm import tqdm


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
            for chunk in tqdm(hdf5_in[dset].iter_chunks(), desc='chunks'):
                color_arr = hdf5_in[dset][chunk]
                keypoints = process_frames(color_arr)
                keypoints_dset[chunk[0], :, :] = keypoints[:, :, 0:2]
                confidence_dset[chunk[0], :] = keypoints[:, :, 2]
        else:
            tqdm.write('not sure what to do with this dataset')

    print('done processing')
    hdf5_in.close()
    hdf5_out.close()
    print('done closing')


if __name__ == '__main__':
    convert(sys.argv[1])

'''
Module to extract depth given hdf5_in and hdf5_out files
'''
import numpy as np
import multiprocessing
from tqdm import trange
from tqdm.contrib.concurrent import process_map  # or thread_map
from common.realsense_params import MIN_VALID_DEPTH_METERS
from common.realsense_params import MAX_VALID_DEPTH_METERS
from common.tracking_params import DEPTH_KERNEL_SIZE
from common.tracking_params import MAX_TIME_DISPARITY

assert DEPTH_KERNEL_SIZE % 2 == 1
MIN_VALID_DEPTH_MM = MIN_VALID_DEPTH_METERS*1000
MAX_VALID_DEPTH_MM = MAX_VALID_DEPTH_METERS*1000


def create_depth_projected3(color_img_shape, color_pixels, world_c_h):
    depth_in_color_image = np.zeros((color_img_shape[0], color_img_shape[1]))
    points = np.round(color_pixels[:, :2]).astype('uint16')
    valid = np.all((points[:, 0] > 0, points[:, 1] > 0,
                    points[:, 0] < depth_in_color_image.shape[1],
                    points[:, 1] < depth_in_color_image.shape[0]), axis=0)
    depth_in_color_image[points[valid, 1],
                         points[valid, 0]] = world_c_h[2, valid]
    return depth_in_color_image


def extract_depth(poses, depth_img, indices_h, color_img_shape, transforms,
                  window):

    (h_matrix, k_c_padded, color_cam_matrix, k_d_inv,
     k_c_inv, h_matrix_inv, k_d, k_c) = transforms
    window = int((window-1)/2)
    world_d = (k_d_inv@indices_h)*(np.reshape(depth_img, (1, -1), order='F'))
    # Make world coordinate homogenous
    world_d_h = np.concatenate((world_d, np.ones((1, world_d.shape[1]))))
    # Bring world coordinates from depth camera space to rgb camera space
    # Apply the camera projection matrix to finally end up back in rgb camera pixel coordinates
    px_color = (color_cam_matrix@world_d_h)
    valid_px_color = px_color[2, :] != 0
    px_color_norm = px_color[:, valid_px_color]/px_color[2, valid_px_color]
    # depth_color = world_c_h[2,valid_px_color]
    color_pixels4 = px_color_norm[:2, :].T

    mapped_depth_img = create_depth_projected3(
        color_img_shape, color_pixels4, px_color)
    int_poses = np.round(poses).astype('uint16')
    depths = [np.max(mapped_depth_img[max(0, pose[1]-window):
                                      min(pose[1]+window,
                                          mapped_depth_img.shape[0]),
                                      max(pose[0] - window, 0):
                                      min(pose[0]+window, mapped_depth_img.shape[1])]
                     ) for pose in int_poses]
    poses_3d_c = (
        k_c_inv@np.concatenate((poses, np.ones((poses.shape[0], 1))), axis=1).T)*depths
    poses_d_from_c = (h_matrix_inv@np.concatenate((poses_3d_c,
                                                   np.ones((1, poses_3d_c.shape[1]))), axis=0))[:3, :]
    poses_in_depth = k_d@poses_d_from_c
    poses_in_depth = (poses_in_depth/poses_in_depth[2, :])[:2, :].T
    return(poses_3d_c, poses_in_depth)


def add_stereo_depth(hdf5_in, hdf5_out, cam_root, pose_dset_root, transforms=None):
    """Add stereo depth to hdf5 out file given keypoints and depth images.

    It is necessary to know the camera intrinsics and extrinsics. This can be pulled out
    by the attributes in the hdf5 files if the data was present (isn't always there).
    If not, then this can be pulled out of a transforms file which gets the transforms
    from other bag files. This transforms file is generated by `get_transforms/run`.
    This json file should be opened and this function should only be passed the sub
    dictionary indexed by the source and camera.

    This uses data from both hdf5_in and out but only writes to out.

    This requires that a previous system has already discovered and saved the best
    matching depth image to the color (done by `convert_to_hdf5/src/convert_to_hdf5.py:match_depth`)
    Any depth matches which are outside of MAX_TIME_DISPARITY will be saved as nan.

    Any depth data that falls outside of [ MIN_VALID_DEPTH_METERS, MAX_VALID_DEPTH_METERS ] will be
    saved as nan.

    Creates two new datasets a 3dkeypoints one which is in metric 3d space and a keypoints-depth
    dataset which is the keypoints found by the algorithm mapped into the depth image's image
    space. Note however that the depth image keypoints will be aligned with the color data's time.

    Args:
        hdf5_in: The opened hdf5 file with the full data with video.
        hdf5_out: The opened hdf5 file to put data into and which already has
                  keypoints extracted.
        cam_root: The name of the camera to use ('lower' or 'upper')
        transforms: The dictionary with keys that are timestamps (sec since epoch) with fields
                    'rotation': 9 element list (represents 3x3 rot array) and 'translation': 3
                    element list representing translation.
    """
    # pylint: disable= too-many-locals
    depth_match_dset_name = f'{cam_root}/color/matched_depth_index'
    color_dset_name = f'{cam_root}/color/data'
    color_time_dset_name = f'{cam_root}/color/time'
    depth_dset_name = f"{cam_root}/depth/data"
    depth_time_dset_name = f'{cam_root}/depth/time'

    keypoints_dset_name = f'{pose_dset_root}/color'
    keypoints3d_dset_name = f'{pose_dset_root}/3d-realsense-raw'
    keypoints_depth_dset_name = f'{pose_dset_root}/depth'

    if keypoints3d_dset_name not in hdf5_out:
        keypoints_shape = hdf5_out[keypoints_dset_name].shape
        keypoints3d_dset = hdf5_out.create_dataset(
            keypoints3d_dset_name,
            (keypoints_shape[0], keypoints_shape[1], 3),
            dtype=np.float32)
    else:
        keypoints3d_dset = hdf5_out[keypoints3d_dset_name]
        print('You might be running the Stereo depth extraction twice')

    keypoints3d_dset.attrs['desc'] = \
        'Keypoints in 3D coordinates using the raw depth from the ' +\
        'realsense camera, indexed at keypoints. Depth is used to ' +\
        'provide x, y, and z in metric space (meters)'

    if keypoints_depth_dset_name not in hdf5_out:
        keypoints_shape = hdf5_out[keypoints_dset_name].shape
        keypoints_depth_dset = hdf5_out.create_dataset(
            keypoints_depth_dset_name,
            (keypoints_shape[0], keypoints_shape[1], 2),
            dtype=np.float32)
    else:
        keypoints_depth_dset = hdf5_out[keypoints_depth_dset_name]
        print('You might be running the Stereo depth extraction twice')

    keypoints_depth_dset.attrs['desc'] =\
        'Keypoints in the depth image frame space (pixels)'

    if ('depth_to_color-rotation' in hdf5_in[color_dset_name].attrs and
            'depth_to_color-translation' in hdf5_in[color_dset_name].attrs):
        r_cd_raw = hdf5_in[color_dset_name].attrs['depth_to_color-rotation']
        t_cd_raw = hdf5_in[color_dset_name].attrs['depth_to_color-translation']
    else:
        # transforms is already the
        time_target = hdf5_in[color_time_dset_name][0] + \
            (hdf5_in[color_time_dset_name][-1] -
             hdf5_in[color_time_dset_name][0])/2
        transform_idx = np.argmin(
            np.abs(np.asarray([float(v) for v in transforms.keys()])-time_target))
        best_transform = transforms[[*transforms][transform_idx]]
        r_cd_raw = best_transform['rotation']
        t_cd_raw = best_transform['translation']

    k_c = hdf5_in[color_dset_name].attrs['K'].reshape(3, 3)
    k_d = hdf5_in[depth_dset_name].attrs['K'].reshape(3, 3)
    r_cd = np.asarray(r_cd_raw).reshape(3, 3)
    t_cd = np.asarray(t_cd_raw).reshape(3, 1)

    depth_img_shape = hdf5_in[depth_dset_name][0].shape
    color_img_shape = hdf5_in[color_dset_name][0].shape
    indices = np.reshape(np.indices(
        np.flip(depth_img_shape)), (2, -1))
    indices_h = np.concatenate((indices, np.ones((1, indices.shape[1]))))
    h_matrix = np.eye(4)
    h_matrix[:3, :3] = r_cd
    h_matrix[:3, 3] = (t_cd).flatten()
    k_c_padded = np.concatenate((k_c, np.zeros((3, 1))), axis=1)
    color_cam_matrix = k_c_padded@h_matrix
    k_d_inv = np.linalg.inv(k_d)
    k_c_inv = np.linalg.inv(k_c)
    h_matrix_inv = h_matrix.copy()
    h_matrix_inv[:3, :3] = np.linalg.inv(h_matrix[:3, :3])
    h_matrix_inv[:3, 3] = -h_matrix_inv[:3, :3]@h_matrix[:3, 3]

    transform_mats = (h_matrix, k_c_padded, color_cam_matrix, k_d_inv,
                      k_c_inv, h_matrix_inv, k_d, k_c)

    # with Pool(len(os.sched_getaffinity(0)) as pool:
    for idx in trange(hdf5_in[color_dset_name].shape[0]):
        # extract_depth_wrap(hdf5_in, depth_match_dset_name, )
        matched_index = hdf5_in[depth_match_dset_name][idx]
        if np.abs(
                hdf5_in[depth_time_dset_name][matched_index] -
                hdf5_in[color_time_dset_name][idx]
        ) > MAX_TIME_DISPARITY:
            keypoints3d_dset[idx, :, :] = np.NaN
            keypoints_depth_dset[idx, :, :] = np.NaN
        else:
            depth_img = hdf5_in[depth_dset_name][matched_index]
            depth_img = hdf5_in[depth_dset_name][matched_index]
            depth_img[depth_img < MIN_VALID_DEPTH_MM] = 0
            depth_img[depth_img > MAX_VALID_DEPTH_MM] = 0
            keypoints = hdf5_out[keypoints_dset_name][idx]
            poses_3d_c, poses_in_depth = extract_depth(keypoints, depth_img, indices_h,
                                                       color_img_shape, transform_mats, DEPTH_KERNEL_SIZE)
            invalid_indeces = np.logical_or(
                poses_3d_c[2, :] < MIN_VALID_DEPTH_METERS,
                poses_3d_c[2, :] > MAX_VALID_DEPTH_METERS
            )
            poses_3d_c[:, invalid_indeces] = np.nan
            poses_in_depth[invalid_indeces, :] = np.nan
            keypoints3d_dset[idx, :, :] = poses_3d_c.T
            keypoints_depth_dset[idx, :, :] = poses_in_depth

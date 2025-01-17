'''
Module to extract depth given hdf5_in and hdf5_out files
'''
import multiprocessing
import math
from functools import partial
import tqdm
import numpy as np
from common.realsense_params import MIN_VALID_DEPTH_METERS
from common.realsense_params import MAX_VALID_DEPTH_METERS
from common.tracking_params import DEPTH_KERNEL_SIZE
from common.tracking_params import MAX_TIME_DISPARITY

assert DEPTH_KERNEL_SIZE % 2 == 1
MIN_VALID_DEPTH_MM = MIN_VALID_DEPTH_METERS*1000
MAX_VALID_DEPTH_MM = MAX_VALID_DEPTH_METERS*1000

# How many frames to process. These will all be
DATA_PROCESSING_CHUNK_SIZE = 5000
# loaded into memory, so need to make sure there
# is enough memory to handle. about 18 GB / 1000 frames


def generate_image_h_indices(depth_img_shape):
    """Generate matrix of indeces for image in homogenous form

    Args:
        depth_img_shape: Shape of image to work with
    """
    indices = np.reshape(np.indices(np.flip(depth_img_shape)), (2, -1))
    indices_h = np.concatenate((indices, np.ones((1, indices.shape[1]))))
    return indices_h


def de_project_depth(points, k_inv, img):
    """Take points in the depth image from pixel space to 3D space,
    using the values in the image as the z-values to prevent scale
    ambiguity.

    Args:
        points: The points to bring through
        k_inv: The inverse intrinsics for the depth camera
        img: The actual image
    """
    return (k_inv@points) * \
        (np.reshape(img, (1, -1), order='F'))


def transform_depth_world2color_pixels(color_cam_matrix, world_d):
    """Take 3D points in the depth camera reference frame, convert
    to color camera frame and project to color camera pixels.

    Args:
        color_cam_matrix: The camera matrix for the color camera,
                          relative to the depth camera.
        world_d: The pixels in 3D in the depth camera frame.
    """
    return (color_cam_matrix @
            (np.concatenate((world_d, np.ones((1, world_d.shape[1]))))))


def project_depth_to_colorframe(px_color, color_img_shape):
    """Place depth data that has been converted into pixels in the color
    space into a color image.

    It is expected that the pixels are not yet homogonized and are in
    fact still rays with x, y, z. The z will be used to place the ray
    on the image sensor and to define the value which the pixel should have.

    Discards pixels that end up falling outside of the image.

    Args:
        px_color: List of pixels, unnormalized, in color space, to place.
        color_img_shape: The shape of the desired output image.
    """
    valid_px_color = px_color[2, :] != 0

    mapped_depth_img = np.zeros((color_img_shape[0], color_img_shape[1]))
    points = np.round(
        (px_color[:, valid_px_color] /
         px_color[2, valid_px_color])[:2, :].T[:, :2]).astype('uint16')
    valid = np.all((points[:, 0] > 0, points[:, 1] > 0,
                    points[:, 0] < mapped_depth_img.shape[1],
                    points[:, 1] < mapped_depth_img.shape[0]), axis=0)
    mapped_depth_img[points[valid, 1],
                     points[valid, 0]] = px_color[2, valid]
    return mapped_depth_img


def calc_depth_from_sparse_image(mapped_depth_img, poses, window):
    """Calculate the depth at a 2D pose estimate given an image of sparse
    depth values.

    Based on the expected sparsity, you should select a window to look for
    valid values at. The kernel size will actually be 2window+1.

    The values within the kernel, centered at the pose will be retrieved
    from the image, any zero values will be removed, and the minimum
    remaining value will be taken.

    When the kernel places target coordinates beyond the edge of the image,
    those points are ignored.

    Args:
        mapped_depth_img: A sparse image of depth values
        poses: An array of x, y pixel poses, assumed to all fall within the
               mapped_depth_img coordinates.
        window: The distance +/- the target pixels to look for a value.
    """
    depths = [mapped_depth_img[max(0, pose[1]-window):
                               min(pose[1] + window,
                                   mapped_depth_img.shape[0]),
                               max(pose[0] - window, 0):
                               min(pose[0]+window, mapped_depth_img.shape[1])].flatten()
              for pose in np.round(poses).astype('uint16')]
    for idx, _ in enumerate(depths):
        depths[idx] = depths[idx][depths[idx] != 0]
        if len(depths[idx]) > 0:  # the above command will make some depths empty
            depths[idx] = min(depths[idx])
        else:
            depths[idx] = 0

    return depths


def deproject_colordepth(k_inv, poses, depths):
    """Givven pixel locations of interest in an image and the depths
    at those locations, determine the full 3D representation of the
    points of inerest.

    Args:
        k_inv: Inverse K matrix (intrinsics) for the imager
        poses: The points of interest
        depths: The depths at the points of interest
    """
    poses_3d_c = (
        k_inv @
        np.concatenate((poses, np.ones((poses.shape[0], 1))), axis=1).T)*depths
    return poses_3d_c


def project_keypoints2depth(k_d, h_matrix_inv, poses_3d_c):
    """Given 3d poses in the camera frame, project them to pixels in the depth
    image frame.

    Args:
        k_d: K matrix (intrinsics) for the depth camera
        h_matrix_inv: Inverse transformation between depth and color imager
        poses_3d_c: 3D points in camera coordinate frame
    """
    poses_in_depth = (k_d @
                      (h_matrix_inv @
                       np.concatenate((poses_3d_c,
                                       np.ones((1, poses_3d_c.shape[1]))), axis=0))[:3, :])
    poses_in_depth = (poses_in_depth/poses_in_depth[2, :])[:2, :].T
    return poses_in_depth


def extract_depth(poses, depth_img, color_img_shape, transform_mats,
                  window, mapped_depth_img):
    """Extract depth of poses.

    If this is passed in a mapped_depth_img, then that will be used.
    If not, then it will be generated and returned.

    Args:
        poses: The 2D pixel joint keypoints in the color image
        depth_img: the depth image. Only needed if mapped_depth_img is None.
                   if mapped_depth_img is passed in, you can pass None for
                   depth_img (this is particullarly useful in multiprocessing
                   situations where passing images around is costly).
        color_img_shape: The shape of the color image
        transform_mats: A dictionary with the various extrinsics and intrinsics
                        related to the RGBD sensor set
        window: How big of an area to get depth from. This should not be 1.
                when the depth image is mapped to the color space, it will likely
                be sparse due to depth images generally being smaller than the
                relevant color images and as a result of transformations not dropping
                pixels from the depth camera cleanly onto the color imager.
        mapped_depth_img: The depth image transformed into the color image space. This
                          will be the same size as the color image. If you do not have
                          this, pass in None.

    Returns:
        poses_3d_c: the poses in 3D relative to the color imager frame
        poses_in_depth: the poses in 2D coordinates on the depth image
        mapped_depth_img: Same as the argument above
    """
    # pylint: disable= too-many-arguments
    if mapped_depth_img is None:
        indices_h = generate_image_h_indices(depth_img.shape)
        window = int((window-1)/2)
        world_d = de_project_depth(
            indices_h, transform_mats['k_d_inv'], depth_img)
        px_color = transform_depth_world2color_pixels(
            transform_mats['color_cam_matrix'], world_d)
        mapped_depth_img = project_depth_to_colorframe(
            px_color, color_img_shape)
    depths = calc_depth_from_sparse_image(mapped_depth_img, poses, window)
    poses_3d_c = deproject_colordepth(transform_mats['k_c_inv'], poses, depths)
    poses_in_depth = project_keypoints2depth(
        transform_mats['k_d'], transform_mats['h_matrix_inv'], poses_3d_c)
    return(poses_3d_c, poses_in_depth, mapped_depth_img)


def extract_depth_wrap_multiprocess(color_img_shape, transform_mats, zipped_args):
    """wraps extract_depth_wrap so that it can be used with a variety off multiprocessing
    tools. The arguments mirror extract_depth_wrap, except that all but the first two
    are zipped into a tuple like structure and passed as the third argument.
    """
    (depth_img, keypoints, depth_time, color_time,
     depth_in_color,  idx) = zipped_args
    return extract_depth_wrap(color_img_shape, transform_mats,
                              depth_img, keypoints, depth_time, color_time, depth_in_color,  idx)


def extract_depth_wrap(color_img_shape, transform_mats,
                       depth_img, keypoints, depth_time, color_time, depth_in_color,  idx):
    """Calculate 3D pose and pose in depth pixel

    This is meant to be safe to run in a multiprocessing pool.

    Prior to doing calculations, any values which are too close
    or too far away to be valid are set to zero. After all calculations,
    prior to returning, any keypoints which have a depth value that is
    too close or too far will be set to NaN.

    Args:
        color_img_shape: The shape of the color image that the
                         keypoints were detected in.
        transform_mats: A dictionary of various transformation
                        matricies.
        depth_img: The depth image with pixel values = millimeters.
        keypoints: The keypoints in the depth frame pixels.
        depth_time: The time that the depth image was captured.
        color_time: The time that the color image was captured.
        idx: IDX to operate at. This is just used to keep track
             of what job is being returned in certain async
             scenarios
    Returns:
        idx: The id that is being operated at
        poses_3d_c: The poses in 3D space in millimeters
        poses_in_depth: The poses in pixels in the depth frame
    """
    # pylint: disable= too-many-arguments

    if np.abs(
            depth_time -
            color_time
    ) > MAX_TIME_DISPARITY:
        return (idx, np.NaN, np.NaN, np.NaN)
        # keypoints3d_dset[idx, :, :] = np.NaN
        # keypoints_depth_dset[idx, :, :] = np.NaN
    if depth_img is not None:
        depth_img[depth_img < MIN_VALID_DEPTH_MM] = 0
        depth_img[depth_img > MAX_VALID_DEPTH_MM] = 0
    poses_3d_c, poses_in_depth, depth_in_color = \
        extract_depth(keypoints, depth_img,
                      color_img_shape, transform_mats, DEPTH_KERNEL_SIZE, depth_in_color)
    invalid_indeces = np.logical_or(
        poses_3d_c[2, :] < MIN_VALID_DEPTH_MM,
        poses_3d_c[2, :] > MAX_VALID_DEPTH_MM
    )
    poses_3d_c[:, invalid_indeces] = np.nan
    poses_in_depth[invalid_indeces, :] = np.nan
    # keypoints3d_dset[idx, :, :] = poses_3d_c.T
    # keypoints_depth_dset[idx, :, :] = poses_in_depth
    if depth_img is None:
        # if the depth map was passed in, no need to pass it back out
        return (idx, poses_3d_c.T, poses_in_depth, None)
    return (idx, poses_3d_c.T, poses_in_depth, depth_in_color)


def build_tranformations(r_cd, t_cd, k_d, k_c):
    """Build useful transformations and return in a dictionary.

    Args:
        r_cd: The rotation matrix between the color and depth imagers
        t_cd: The translation between the color and depth imagers
        k_d: The K matrix (intrinsics) for the depth imager
        k_c: The K matrix (intrinsics) for the color imager
    """
    h_matrix = np.eye(4)
    h_matrix[:3, :3] = r_cd.T
    h_matrix[:3, 3] = (t_cd).flatten()
    k_c_padded = np.concatenate((k_c, np.zeros((3, 1))), axis=1)
    color_cam_matrix = k_c_padded@h_matrix
    k_d_inv = np.linalg.inv(k_d)
    k_c_inv = np.linalg.inv(k_c)
    h_matrix_inv = h_matrix.copy()
    h_matrix_inv[:3, :3] = np.linalg.inv(h_matrix[:3, :3])
    h_matrix_inv[:3, 3] = -h_matrix_inv[:3, :3]@h_matrix[:3, 3]

    transform_mats = {}
    transform_mats['h_matrix'] = h_matrix
    transform_mats['k_c_padded'] = k_c_padded
    transform_mats['color_cam_matrix'] = color_cam_matrix
    transform_mats['k_d_inv'] = k_d_inv
    transform_mats['k_c_inv'] = k_c_inv
    transform_mats['h_matrix_inv'] = h_matrix_inv
    transform_mats['k_d'] = k_d
    transform_mats['k_c'] = k_c

    return transform_mats


def generate_keypoints_3d_dset(hdf5_out, pose_dset_root, keypoints_dset_name):
    """Get the dataset to store 3D keypoints in.

    This dataset will hold the keypoints in 3D in millimeters.

    If the dataset already exists, just return it. If not, create it.

    Args:
        hdf5_out: The HDF5 file to put the keypoints in
        pose_dset_root: The root of the keypoint detections to work on
        keypoints_dset_name: The name of the dataset which holds the
                             keypoints to work on.
    """
    keypoints3d_dset_name = f'{pose_dset_root}/3d-realsense-raw'
    if keypoints3d_dset_name not in hdf5_out:
        keypoints_shape = hdf5_out[keypoints_dset_name].shape
        keypoints3d_dset = hdf5_out.create_dataset(
            keypoints3d_dset_name,
            (keypoints_shape[0], keypoints_shape[1], 3),
            dtype=np.float32)
    else:
        keypoints3d_dset = hdf5_out[keypoints3d_dset_name]

    keypoints3d_dset.attrs['desc'] = \
        'Keypoints in 3D coordinates using the raw depth from the ' +\
        'realsense camera, indexed at keypoints. Depth is used to ' +\
        'provide x, y, and z in metric space (meters)'
    return keypoints3d_dset


def generate_keypoints_depth_dset(hdf5_out, pose_dset_root, keypoints_dset_name):
    """Get the dataset to store keypoints in the depth frame in.

    This dataset will hold the pixel coordinates for the keypoints, in the depth
    image.

    If the dataset already exists, just return it. If not, create it.

    Args:
        hdf5_out: The HDF5 file to put the keypoints in
        pose_dset_root: The root of the keypoint detections to work on
        keypoints_dset_name: The name of the dataset which holds the
                             keypoints to work on.
    """
    keypoints_depth_dset_name = f'{pose_dset_root}/depth'
    if keypoints_depth_dset_name not in hdf5_out:
        keypoints_shape = hdf5_out[keypoints_dset_name].shape
        keypoints_depth_dset = hdf5_out.create_dataset(
            keypoints_depth_dset_name,
            (keypoints_shape[0], keypoints_shape[1], 2),
            dtype=np.float32)
    else:
        keypoints_depth_dset = hdf5_out[keypoints_depth_dset_name]

    keypoints_depth_dset.attrs['desc'] =\
        'Keypoints in the depth image frame space (pixels)'
    return keypoints_depth_dset


def generate_depth_in_color_dset(hdf5_file,  cam_root):
    """Get the dataset to store depth frames in.

    This dataset is used to store the data that is mapped from the depth
    image to the color image space, vastly speeding up the depth extraction.

    If the dataset already exists, just return it. If not, create it.

    Args:
        hdf5_file: The HDF5 file to put the data into
        cam_root: The string representing the root of the camera for this data
    """
    dset_name = f'{cam_root}/color/depth_map'
    color_dset_name = f'{cam_root}/color/data'
    already_exists = False
    if dset_name not in hdf5_file:
        img_shape = hdf5_file[color_dset_name].shape[:3]
        dset = hdf5_file.create_dataset(
            dset_name,
            img_shape,
            dtype=np.float32)
        dset.attrs['complete'] = False
    else:
        dset = hdf5_file[dset_name]
        if 'complete' in dset.attrs and dset.attrs['complete']:
            already_exists = True
        else:
            dset.attrs['complete'] = False

    dset.attrs['desc'] =\
        'Depth points mapped into the color image frame as depth in millimeters'
    return (dset, already_exists)


def get_extinsics(hdf5_in, color_dset_name, color_time_dset_name, transforms):
    """Get the camera extrinsics (color to depth camera)

    Will attempt to find the extrinsics in the hdf5 file. If not availalbe,
    then will find the best transform in the transforms dictionary.

    Args:
        hdf5_in: The HDF5 file wwith the full video feeds
        color_dset_name: Name of the color image dataset
        color_time_dset_name: Name of the dataset with the times the color images
                              were captured
        transforms: The backup dictionary of known extrinsics between the cameras
    """
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
    r_cd = np.asarray(r_cd_raw).reshape(3, 3)
    t_cd = np.asarray(t_cd_raw).reshape(3, 1)*1000  # get to millimeters
    return(t_cd, r_cd)


def max_slice_len(slc: slice):
    """Find the max length that a slice will produce accounting
    for possible missing components

    # https://stackoverflow.com/a/65500526/5274985

    Args:
        slc (slice): slice to process on
    """
    assert slc.stop or slc.stop == 0, "Must define stop for max slice len!"
    assert slc.step != 0, "Step slice cannot be zero"

    start = slc.start or 0
    stop = slc.stop
    step = slc.step or 1

    delta = (stop - start)
    dsteps = int(math.ceil(delta / step))

    return dsteps if dsteps >= 0 else 0


def slice_len(slc: slice, src_len: int):
    """Determine the length of a slice taking into account
    the end point of the slice and the actual end point
    of the array that is being sliced.

    https://stackoverflow.com/a/65500526/5274985

    Args:
        slc (slice): slice to process on
        src_len (int): src_len
    """
    stop = min(slc.stop, src_len)
    return max_slice_len(slice(slc.start, stop, slc.step))


def get_intrinsics(hdf5_in, color_dset_name, depth_dset_name):
    """Get intrinsics for the depth and color cameras

    Args:
        hdf5_in: The HDF5 file wwith the full video feeds
        color_dset_name: Name of the color image dataset
        depth_dset_name: Neme of the depth image dataset
    """
    k_c = hdf5_in[color_dset_name].attrs['K'].reshape(3, 3)
    k_d = hdf5_in[depth_dset_name].attrs['K'].reshape(3, 3)
    return(k_c, k_d)


def add_stereo_depth(hdf5_in, hdf5_out, cam_root, pose_dset_root, rerun=False, transforms=None):
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
    # pylint: disable= too-many-arguments
    depth_match_dset_name = f'{cam_root}/color/matched_depth_index'
    color_dset_name = f'{cam_root}/color/data'
    color_time_dset_name = f'{cam_root}/color/time'
    depth_dset_name = f"{cam_root}/depth/data"
    depth_time_dset_name = f'{cam_root}/depth/time'

    keypoints_dset_name = f'{pose_dset_root}/color'

    keypoints3d_dset = generate_keypoints_3d_dset(
        hdf5_out, pose_dset_root, keypoints_dset_name)

    keypoints_depth_dset = generate_keypoints_depth_dset(
        hdf5_out, pose_dset_root, keypoints_dset_name)

    depth_in_color_dset, depth_color_filled = generate_depth_in_color_dset(
        hdf5_in,  cam_root)
    if rerun:
        depth_color_filled = False

    if (depth_match_dset_name not in hdf5_in) or (len(hdf5_in[depth_match_dset_name]) == 0):
        keypoints3d_dset[:] = np.nan
        keypoints_depth_dset[:] = np.nan
        depth_in_color_dset[:] = np.nan
        depth_in_color_dset.attrs['complete'] = True
        print('No available depth data')
        return

    t_cd, r_cd = get_extinsics(
        hdf5_in, color_dset_name, color_time_dset_name, transforms)
    k_c, k_d = get_intrinsics(hdf5_in, color_dset_name, depth_dset_name)

    with tqdm.tqdm(total=len(hdf5_in[color_dset_name])) as pbar:
        for start_idx in range(0, len(hdf5_in[color_dset_name]), DATA_PROCESSING_CHUNK_SIZE):
            chunk = slice(start_idx, min(
                len(hdf5_in[color_dset_name]), start_idx+DATA_PROCESSING_CHUNK_SIZE), 1)
            # we n
            num_frames = slice_len(chunk, len(hdf5_in[color_dset_name]))
            depth_time_l = [None]*num_frames
            depth_img_l = [None]*num_frames
            matched_index_l = hdf5_in[depth_match_dset_name][chunk]
            for frame in range(num_frames):
                depth_time_l[frame] = hdf5_in[depth_time_dset_name][matched_index_l[frame]]
            if depth_color_filled:
                color_depth_l = depth_in_color_dset[chunk]
            else:
                color_depth_l = [None]*num_frames
                for frame in range(num_frames):
                    depth_img_l[frame] = hdf5_in[depth_dset_name][matched_index_l[frame]]
            bound_func = partial(
                extract_depth_wrap_multiprocess,
                hdf5_in[color_dset_name][5].shape,
                build_tranformations(r_cd, t_cd, k_d, k_c))
            zipped_args = zip(depth_img_l,
                              hdf5_out[keypoints_dset_name][chunk][:, :, :2],
                              depth_time_l,
                              hdf5_in[color_time_dset_name][chunk],
                              color_depth_l,
                              range(chunk.start, chunk.stop, chunk.step))

            if depth_color_filled:
                pbar.set_postfix(num_processes=1)
                # calculating the depth color map is computationally expensive. Iff we
                # already have it, no need for multiprocessing
                for result in map(bound_func, zipped_args):
                    idx = result[0]
                    keypoints3d_dset[idx, :, :] = result[1]
                    keypoints_depth_dset[idx, :, :] = result[2]
                    # If the depth color map was already filled, it will not be returned
                    pbar.update(1)

            else:
                with multiprocessing.Pool() as pool:
                    # pylint: disable=protected-access
                    pbar.set_postfix(num_processes=pool._processes)
                    for result in pool.imap_unordered(bound_func,
                                                      zipped_args, chunksize=10):
                        idx = result[0]
                        keypoints3d_dset[idx, :, :] = result[1]
                        keypoints_depth_dset[idx, :, :] = result[2]
                        depth_in_color_dset[idx, :, :] = result[3]
                        pbar.update(1)
    depth_in_color_dset.attrs['complete'] = True

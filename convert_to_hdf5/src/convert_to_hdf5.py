#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 28 23:21:43 2020

@author: gsuveer

Module to take a rosbag and output a hdf5 database or append to existing hdf5
database.

Attributes:
    pre_processing_bag_file  : Name of the bag file to convert to HDF5 Database
    hdf5_filename : Name of output file
    Mode: 'a' for append, 'w' for write
    experiment_id: Initial namespace for HDF5

TODO
    Figure out if chunk size improves speed. Currently letting API call infer.
    Add additional topics apart from image topics
"""

import pathlib
import copy
import numpy as np
import yaml
import h5py
import rospy
import rosbag
from cv_bridge import CvBridge
from tqdm import tqdm

INITIAL_SIZE = 0
CHUNK_SIZE = 500


def generate_record_defs(meta_data):
    """Parse meta data to determine the names of segments, start, and end times.

    Args:
        meta_data: the dictionary of metadata

    Returns:
        record_names: the names of the segments
        start_times: the time that each segment starts
        end_times: the time that each segment ends
    """
    record_names = []
    start_times = []
    end_times = []
    for segment in meta_data['segments']:
        for activity in meta_data['segments'][segment]:
            if 'ros' in meta_data['segments'][segment][activity]:
                record_names.append(segment+'/'+activity)
                start_times.append(meta_data['segments']
                                   [segment][activity]['ros']['start'])
                end_times.append(meta_data['segments']
                                 [segment][activity]['ros']['end'])
    return record_names, start_times, end_times


def match_video_2_data(meta_data):
    """Create a dictionary mapping from video topic names to their corresponding info topic names

    Args:
        meta_data: the metadata dictionary

    Returns: A dictionary with keys video data topic names and values info topic names
    """
    info_topics = filter(lambda x: 'vid' and 'info' in x,
                         meta_data['bag-mapping'].keys())
    data_topics = filter(lambda x: 'vid' and 'data' in x,
                         meta_data['bag-mapping'].keys())
    data_info_mapping = dict()
    for topic in data_topics:
        target_name = topic.replace('data', 'info')
        if target_name in info_topics:
            data_info_mapping[topic] = target_name
        else:
            rospy.logerr('video topic without matching info topic: %s', topic)
    return data_info_mapping


def load_bag_file(bag_filename):
    """Load a bag file from disk

    Args:
        bag_filename: the filename of the bag file

    Returns: The bag file
    """
    if not bag_filename == '':
        try:
            bag_file = rosbag.Bag(bag_filename)
        except:  # pylint: disable=bare-except
            rospy.loginfo('BAG FILE COULD NOT BE READ')
            raise
    else:
        rospy.logerr('No Argument provided for Bag Filename')
        return None

    topics = bag_file.get_type_and_topic_info()[1].keys()
    rospy.loginfo('Successfully read bag file with topics:')
    for topic in topics:
        rospy.loginfo('\t\t%s', topic)
    return bag_file


def load_meta_file(meta_filename):
    """Load meta file from disk and parse yaml to return a dictionary

    Args:
        meta_filename: The filename of the meta yaml file

    Returns: dictionary of parsed meta file
    """
    # Read in meta file
    with open(meta_filename, 'r') as stream:
        try:
            meta_data = yaml.safe_load(stream)
        except yaml.YAMLError as err:
            rospy.logerr(err)
            raise
    return meta_data


def get_topic_info(data_info_mapping, bag_file, meta_data):
    """Get the first info message for each video file

    Args:
        data_info_mapping: a dictionary mapping from data topic names to info topic names
        bag_file: The bag file to extract from
        meta_data: The meta data as a dictionary

    Returns: A dictionary with the information in the first message for each video,
             keyed on the video topic name
    """
    topic_info = {}
    for vid_topic in data_info_mapping:
        true_topic = meta_data['bag-mapping'][data_info_mapping[vid_topic]]
        rospy.loginfo(
            'Extracting meta info from standard video topic: %s', vid_topic)
        rospy.loginfo('\t\tmapped to real info topic: %s', true_topic)
        try:
            _, msg, _ = next(bag_file.read_messages([true_topic]))
        except StopIteration:
            topic_info[vid_topic] = None
            continue
        topic_info[vid_topic] = msg
    return topic_info


def load_hdf_files(record_names, out_dir, data_info_mapping, meta_data, topic_info):  # pylint: disable=too-many-locals
    """Load HDF files to prepare to add data. Will create necessary databases in the hdf5
       file and will fill in atrributes using the topic info where relevant

    Args:
        record_names: The names of the records in each bag sequence, this is essentially
                      the name of the relevant activities, each of which will create a
                      unique hdf5 file
        out_dir: The directory to save to
        data_info_mapping: The mapping between video data topics and info data topics
        meta_data: The meta data as a dictionary
        topic_info: The data from the info topics in a dictionary keyed on the video topic name

    Returns: List of the HDF5 File data objects
    """
    hdf5_files = len(record_names)*[None]
    for idx, hdf5_fn in enumerate(record_names):
        rospy.loginfo('Working on seq/act: %s', hdf5_fn)
        hdf5_fn_full = pathlib.Path(out_dir, hdf5_fn).with_suffix('.hdf5')
        pth = pathlib.Path(hdf5_fn_full)
        pth.parent.mkdir(parents=True, exist_ok=True)
        try:
            hdf5_files[idx] = h5py.File(hdf5_fn_full, 'a')
        except:  # pylint: disable=bare-except
            rospy.logerr(
                'HDF5 Database COULD NOT BE READ/CREATED: %s', hdf5_fn_full)
            raise

        for vid_topic in data_info_mapping:
            raw_topic = meta_data['bag-mapping'][vid_topic]
            rospy.loginfo(
                '\tParsing for standard topic : %s' % (vid_topic))
            rospy.loginfo(
                '\t\traw topic : %s' % (raw_topic))
            topic_meta_info = topic_info[vid_topic]
            if topic_meta_info:
                hdf5_database = hdf5_files[idx]
                vid_topic_data_name = vid_topic + '/data'
                vid_topic_secs_name = vid_topic + '/secs'
                vid_topic_nsecs_name = vid_topic + '/nsecs'
                if 'depth' in vid_topic and vid_topic_data_name not in hdf5_database:
                    rospy.loginfo('\t\tnew depth dataset')
                    dataset = hdf5_database.create_dataset(vid_topic_data_name,
                                                           (INITIAL_SIZE, topic_meta_info.height,
                                                            topic_meta_info.width),
                                                           maxshape=(
                                                               None, topic_meta_info.height,
                                                               topic_meta_info.width),
                                                           dtype=np.uint16,
                                                           chunks=(
                                                               CHUNK_SIZE,
                                                               topic_meta_info.height,
                                                               topic_meta_info.width))
                elif 'color' in vid_topic and vid_topic_data_name not in hdf5_database:
                    rospy.loginfo('\t\tnew color dataset')
                    dataset = hdf5_database.create_dataset(vid_topic_data_name,
                                                           (INITIAL_SIZE, topic_meta_info.height,
                                                            topic_meta_info.width, 3),
                                                           maxshape=(
                                                               None, topic_meta_info.height,
                                                               topic_meta_info.width, 3),
                                                           dtype=np.uint8,
                                                           chunks=(
                                                               CHUNK_SIZE,
                                                               topic_meta_info.height,
                                                               topic_meta_info.width,
                                                               3))
                else:
                    rospy.loginfo(
                        '\t\tDataset already existed!! no action taken')
                    continue

                hdf5_database.create_dataset(vid_topic_secs_name, (INITIAL_SIZE,),
                                             maxshape=(None,),
                                             dtype=np.uint32, chunks=(CHUNK_SIZE,))

                hdf5_database.create_dataset(vid_topic_nsecs_name, (INITIAL_SIZE,),
                                             maxshape=(None,),
                                             dtype=np.uint32, chunks=(CHUNK_SIZE,))

                dataset.attrs.create('height', topic_meta_info.height)
                dataset.attrs.create('width', topic_meta_info.width)
                dataset.attrs.create('D', topic_meta_info.D)
                dataset.attrs.create('K', topic_meta_info.K)
                dataset.attrs.create('R', topic_meta_info.R)
                dataset.attrs.create('P', topic_meta_info.P)
                dataset.attrs.create('binning_x', topic_meta_info.binning_x)
                dataset.attrs.create('binning_y', topic_meta_info.binning_y)
            else:
                rospy.loginfo('\t\tNo meta info')
    return hdf5_files


def match_depth(hdf5_files, data_info_mapping):  # pylint: disable=too-many-branches
    """Match the depth to the color topics for videos.

    Adds a data structure to the hdf5 file objects which are passed in (modifying the
    existing objects).

    Args:
        hdf5_files: the list of hdf file objects to work on
        data_info_mapping: The mapping between video data topics and info data topics
    """
    upper_color_match_topic = 'vid/color/data/upper/matched_depth_index'
    lower_color_match_topic = 'vid/color/data/lower/matched_depth_index'

    timestamps = {}
    dataset_upper = None
    dataset_lower = None

    for hdf5_database in hdf5_files:
        if upper_color_match_topic not in hdf5_database:
            dataset_upper = hdf5_database.create_dataset(upper_color_match_topic, (INITIAL_SIZE,),
                                                         maxshape=(None,),
                                                         dtype=np.uint32, chunks=(CHUNK_SIZE,))
        else:
            dataset_upper = hdf5_database[upper_color_match_topic]

        if lower_color_match_topic not in hdf5_database:
            dataset_lower = hdf5_database.create_dataset(lower_color_match_topic, (INITIAL_SIZE,),
                                                         maxshape=(None,),
                                                         dtype=np.uint32, chunks=(CHUNK_SIZE,))
        else:
            dataset_lower = hdf5_database[lower_color_match_topic]

        for vid_topic in data_info_mapping:
            if 'vid' in vid_topic:  # This addresses that we read only from vid topics
                timestamp_secs = hdf5_database[vid_topic + '/secs']
                timestamp_nsecs = hdf5_database[vid_topic + '/nsecs']

                if timestamp_secs.shape[0] == 0 or timestamp_nsecs.shape[0] == 0:
                    tstamp = None
                else:
                    timestamp_secs = np.asarray(timestamp_secs)
                    timestamp_nsecs = np.asarray(timestamp_nsecs)
                    tstamp = np.expand_dims(
                        timestamp_secs + 1e-9 * timestamp_nsecs, 0)

                if 'upper' in vid_topic and 'color' in vid_topic:
                    timestamps['upper_color'] = copy.deepcopy(tstamp)
                if 'upper' in vid_topic and 'depth' in vid_topic:
                    timestamps['upper_depth'] = copy.deepcopy(tstamp)
                if 'lower' in vid_topic and 'color' in vid_topic:
                    timestamps['lower_color'] = copy.deepcopy(tstamp)
                if 'lower' in vid_topic and 'depth' in vid_topic:
                    timestamps['lower_depth'] = copy.deepcopy(tstamp)

        if timestamps['lower_color'] is None or timestamps['lower_color'] is None:
            rospy.loginfo('No Lower camera in current HDF5 database')
        else:
            dataset_lower.resize(timestamps['lower_color'].shape[1], axis=0)
            dataset_lower[...] = np.argmin(np.abs(timestamps['lower_color'] -
                                                  timestamps['lower_depth'].T), axis=0)

        if timestamps['upper_color'] is None or timestamps['upper_depth'] is None:
            rospy.loginfo('No Upper Camera Timestamps in current HDF5 database')
        else:
            dataset_upper.resize(timestamps['upper_color'].shape[1], axis=0)
            dataset_upper[...] = np.argmin(np.abs(timestamps['upper_color'] -
                                              timestamps['upper_depth'].T), axis=0)

def node():  # pylint: disable=too-many-statements, too-many-locals
    """The ROS node from which bag access, data parsing, and and hdf5 file generation
       is orchestrated
    """
    rospy.init_node('rosbag_to_hdf5_node')
    rospy.loginfo('started rosbag to hdf5 conversion')
    bag_filename = rospy.get_param('~bag_file', None)
    rospy.loginfo('Bag file: %s', bag_filename)
    meta_filename = rospy.get_param('~meta_file', None)
    rospy.loginfo('meta Filename: %s', meta_filename)
    out_dir = rospy.get_param('~out_dir', None)
    rospy.loginfo('output directory: %s', out_dir)

    bag_file = load_bag_file(bag_filename)
    meta_data = load_meta_file(meta_filename)
    data_info_mapping = match_video_2_data(meta_data)

    record_names, start_times, end_times = generate_record_defs(meta_data)
    topic_info = get_topic_info(data_info_mapping, bag_file, meta_data)
    hdf5_files = load_hdf_files(
        record_names, out_dir, data_info_mapping, meta_data, topic_info)

    bridge = CvBridge()
    outer_progress_bar = tqdm(data_info_mapping)

    for vid_topic in outer_progress_bar:
        # rospy.loginfo('Extracting info from : %s' % (vid_topic))
        raw_topic = meta_data['bag-mapping'][vid_topic]
        # rospy.loginfo('\t\tWith raw topic name : %s' % (raw_topic))
        vid_topic_data_name = vid_topic + '/data'
        vid_topic_secs_name = vid_topic + '/secs'
        vid_topic_nsecs_name = vid_topic + '/nsecs'
        # resizing_time = 0
        # writing_time = 0
        # bridge_time = 0
        # first_time = 0
        # second_time = 0
        # bag_read_time = 0
        # clk_total = time.perf_counter()
        outer_progress_bar.set_description('Working on: {}'.format(vid_topic))

        with tqdm(total=bag_file.get_message_count(raw_topic)) as inner_progress_bar:
            # clck = time.perf_counter()
            for _, msg, _ in bag_file.read_messages([raw_topic]):
                # bag_read_time += time.perf_counter()-clck
                # clck = time.perf_counter()
                timestamp = msg.header.stamp.secs + 1e-9*msg.header.stamp.nsecs
                gts = timestamp > np.asarray(start_times)
                lte = timestamp < np.asarray(end_times)

                relevant_database = gts & lte

                if relevant_database.sum() == 0:
                    continue
                if relevant_database.sum() > 1:
                    rospy.logerr(
                        'something is wrong with start and end times')
                    continue

                relevant_database = np.flatnonzero(relevant_database)[0]
                hdf5_file = hdf5_files[relevant_database]

                dataset = hdf5_file[vid_topic_data_name]
                timestamp_secs = hdf5_file[vid_topic_secs_name]
                timestamp_nsecs = hdf5_file[vid_topic_nsecs_name]
                # first_time += time.perf_counter()-clck

                # clck = time.perf_counter()
                dataset.resize(dataset.shape[0]+1, axis=0)
                timestamp_secs.resize(timestamp_secs.shape[0]+1, axis=0)
                timestamp_nsecs.resize(timestamp_nsecs.shape[0]+1, axis=0)
                # resizing_time += time.perf_counter()-clck

                if 'depth' in vid_topic:
                    # clck = time.perf_counter()
                    img = bridge.imgmsg_to_cv2(msg, '16UC1')
                    # bridge_time += time.perf_counter()-clck
                    # clck = time.perf_counter()
                    dataset[dataset.shape[0]-1, :,
                            :] = img
                    # writing_time += time.perf_counter()-clck
                else:
                    # clck = time.perf_counter()
                    img = bridge.imgmsg_to_cv2(msg, 'bgr8')
                    # bridge_time += time.perf_counter()-clck
                    # clck = time.perf_counter()
                    dataset[dataset.shape[0]-1, :, :,
                            :] = img
                    # writing_time += time.perf_counter()-clck

                # clck = time.perf_counter()
                timestamp_secs[timestamp_secs.shape[0] -
                               1] = msg.header.stamp.secs
                timestamp_nsecs[timestamp_nsecs.shape[0] -
                                1] = msg.header.stamp.nsecs
                # writing_time += time.perf_counter()-clck
                # clck = time.perf_counter()
                inner_progress_bar.update(1)
                # second_time = time.perf_counter()-clck
                # clck = time.perf_counter()
            # total_time = time.perf_counter()-clk_total
            # rospy.loginfo('writing time:  {}'.format(writing_time/total_time))
            # rospy.loginfo('bridge time:   {}'.format(bridge_time/total_time))
            # rospy.loginfo('resizing time: {}'.format(resizing_time/total_time))
            # rospy.loginfo('first time: {}'.format(first_time/total_time))
            # rospy.loginfo('second time: {}'.format(second_time/total_time))
            # rospy.loginfo('bag read time: {}'.format(bag_read_time/total_time))

    match_depth(hdf5_files, data_info_mapping)

    for file in hdf5_files:
        file.close()

    rospy.loginfo('Exiting Process')
    rospy.signal_shutdown('Exiting Cleanly')


if __name__ == '__main__':
    node()

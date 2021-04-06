# Convet To HDF5

This package converts bag files from the Lil'Flo platform to HDF5 files.

## Running

### With Docker

Temporary:

1.  Put a bag file named `in.bag` into a data folder somewhere
2.  Run `test.sh <path to data folder>` from within this directory
3.  Your HDF5 file will now be in in your data folder

### EC2

1.  Setup an instance of type c5ad.12xlarge
2.  Install curl and unzip
3.  Install aws cli (make sure to get x86 version)
4.  install lbzip2
5.  on every start, run `convert_to_hdf5/mount_instance_store.sh`
6.  build docker file: `docker build . --tag hdf5convert`
7.  run `./convert_to_hdf5/src/process-in-ec2.sh`

## TODO
1. Explore using szip as a filter for compression
2. Explore using smaller chunk sizes

## General architecture

job def: subj no
parallelization: multiple subjects at once

1.  copy meta file for this subj
2.  for each file in ros archive, in parallel (implemented in `convert_to_hdf5/src/run_script.bash`):
    *   copy first bag file from s3 ros folder into local
    *   uncompress: `lbzip2 -d filename` or other similar
3.  for each rosbag, append the rosbag to the desired hdf5 file
    *   use the mapping in the metadata file to determine which topics to record
    *   scan through the hdf5 file to see if each message is within the time range for any of the segments from the meta file (note, this does not include calibration for now)
    *   add any found messages on target topics to the hdf5 file for that experiment/activity/modality. Name hdf5 files per the segment names in the meta files ex: `in-person_simon-says_ros.hdf5`
4.  put hdf5 file into the hdf5 s3 bucket with prefix for the appropriate subject: `flo-exp-aim1-data-hdf5/<user id, three digits: 008>`

# FloAssessmentPipeline

This is the pipeline for assessing patient function based on data from the FloSystem
Data is ingested as compressed bag files. That data is put into HDF5 files.
All of the non-video generated data (poses, etc) go into a seperate hdf5 file
to make it easier to manage.

Everything is done on AWS

## Some tools

ViTables is really great for being able to explore hdf5 files

## skething pipeline

The pipeline will be running in AWS batch (eventually, for now all in EC2)

### getting rosbags into hdf5

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
    *   use szip compression on the hdf5 file as a filter
4.  put hdf5 file into the hdf5 s3 bucket with prefix for the appropriate subject: `flo-exp-aim1-data-hdf5/<user id, three digits: 008>`

### Getting gopro into hdf5

job def: subj no
parallelization: multiple subjects at once

Why are we putting go pro videos into hdf5 files? So that the rest of the pipeline can work on them without needing adjustment and to allow arbitrary frame access.

Why don't we combine with the ros data? MJS proposed an approach where the grid would be tracked through the calibrationi process for both the gopro and the realsense sensors. The path could then be aligned in time and space giving both camera extrinsics as well as time offsets. Unfortunately, to propogate across go pro files, this would require an accurate offset between those files. The hope was that the date of creation could be used. Unfortunately gopros only store the creation date with second precision, so the alignment would be off by up to one second. With that level of misalignment, we might as well just keep them seperate.

1.  copy meta file for this subj
2.  copy the files needed from the calibration section
3.  Develop an intrinsic calibration matrix from these files (maybe randomly select frames, check for a grid, get 300 frames with grid, then calibrate off those? could make better by selecting with sharp focus on grid and by looking for grids that are well spaced out, but start with random for now)
4.  for each sequence, grab all of the frames, rectify them, and put them in their respective hdf5 file under the name `vid_gopro` name each hdf5 file per: `in-person_simon-says_gopro.hdf5`
5.  put hdf5 file into the hdf5 s3 bucket with prefix for the appropriate subject: `flo-exp-aim1-data-hdf5/<user id, three digits: 008>`

### OpenPose

job def: subj no, hdf5 file name
parallelization: multiple hdf5 files (each subject has multiple)

Input: exiting HDF5 file with videos

There is a single output: an HDF5 file with the poses extracted from each view, the depth values (for depth cameras) at those pixel locations

1.  Look in HDF5 file for any datasets starting with `vid_color_data_` and run openpose on those
2.  if there is matching `vid_depth_data_` set, then extract the depth values that correspond to the pixel locations
3.  put in new hdf5 file with `pose_<upper/lower>` (need to think through that data structure a bit more I think)

### QC and publications

we need a way to generate videos overlaying everything and visualizing it all to make sure it is workin and to put in publications

## Metadata

In order to run, we will need some metadata.
This is done in meta.yaml, which should be in each subjects root dir.
This specifies the start and end times for each segment of the experiment.

for an example see inspect/template.yaml

## Setting up for AWS Batch Jobs

1.  Setup an ECR repository and push the docker file for the job you want to it
2.

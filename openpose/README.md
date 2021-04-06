# OpenPose for Pose Detection

To do this, we run in a docker image, openpose is just easier that way.

## on AWS

1.  provision instance with Ubuntu 20
2.  type g4dn.2xlarge 20GB of disk space
3.  Push over code, ex: `scp -rp -i ~/.aws/keys/flo-exp-aim1-openpose-key.pem ~/Documents/git/LilFloAssessmentPipeline/openpose ubuntu@10.128.253.74:/home/ubuntu`
4.  run setup script
5.  Edit `/etc/docker/daemon.json` to have `"default-runtime": "nvidia",` as the second line, [like this](https://docs.nvidia.com/dgx/nvidia-container-runtime-upgrade/index.html#using-nv-container-runtime)
6.  build dockerfile: `docker build . --tag openpose`
7.  attach ssd: `./mount_instance_store.sh`
8.  Run script: ` ./scripts/process-in-ec2.sh -s <subj> -c <cond: augmented-telepresence, classical-telepresence, in-person> -a <activity: simon-says, target-touch>
     `

### permission denied error

you can get permission denied errors if you haven't properly run the mount_instance_store.sh file

## General Architecture:

job def: subj no, hdf5 file name
parallelization: multiple hdf5 files (each subject has multiple)

Input: exiting HDF5 file with videos

There is a single output: an HDF5 file with the poses extracted from each view, the depth values (for depth cameras) at those pixel locations

1.  Look in HDF5 file for any datasets starting with `vid_color_data_` and run openpose on those
2.  if there is matching `vid_depth_data_` set, then extract the depth values that correspond to the pixel locations
3.  put in new hdf5 file with `pose_<upper/lower>` (need to think through that data structure a bit more I think)

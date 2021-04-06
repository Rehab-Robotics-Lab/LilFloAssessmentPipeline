# Visualize Results

## Video with wrist annotation

### Setup

1.  provision an instance of c6gd.xlarge
2.  Ubuntu 20 arm
3.  run the setup script

### Run AWS

1.  docker build . --tag video-overlay
2.  attach drive: `./mount_instance_store.py`
3.  Run script: `./process-in-ec2.sh -s <subj> -c <cond: augmented-telepresence, classical-telepresence, in-person> -a <activity: simon-says, target-touch>`

### RUN Locally

1.  docker build . --tag video-overlay
2.  Run script: `./run-locally.sh -s <subj> -c <cond: augmented-telepresence, classical-telepresence, in-person> -a <activity: simon-says, target-touch> -p <camera>, -d <data_directory(looks for /data/condition/activity.hdf5)>, -o <overlay: wrists, 2dSkeleton, 3dSkelton>`

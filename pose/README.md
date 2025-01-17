# Pose Detection

We need to detect the pose of subjects using the two cameras feeds
we have available. From the upper camera, we can only reliably see
hands and wrists, so we extract those. From the forward facing (lower)
camera, we want to get hands, arms, torso, and eye gaze direction.

Most pose detection algorithms operate in 2D only. We do however
have 3D data. So we use the 2D algorithms and then simply overlay
the 3D data and extract the keypoints from the depth. Later pipeline
steps can transform this into more useful data.

To maximize efficiency, all pose detection is done in the same step.
This allows all of the data to be downloaded only once for pose detection.

We use different algorithms for the different pose components:

*   OpenPose: whole body and hand
*   Detectron2: whole body
*   MediaPipe: Hand

One of the steps here is finding the depth of the detected poses.
This requires that the camera intrinsics and depth-to-color extrinsics.
Sometimes this is avaialable in the HDF5 file directly, other times
it has to be read from the transforms.json file. That file is generated
using `get_transformss/run.sh`. This file is already generated and [stored
in OCI](https://cloud.oracle.com/object-storage/buckets/idtxkczoknc2/rrl-flo-transforms/objects?region=us-ashburn-1).

## OpenPose

To do this, we run in a docker image, openpose is just easier that way.

We run openpose using the 25b model at non-maximum accuracy,
which requires 5.6 GB of GPU memory.
If multiple GPUs are available, they will all be used.

Note: there is a higher accuracy mode that takes 16GB of memory,
it just isn't worth it.

## Running

### On OCI

#### Body Pose

You will need to run the openpose pose detections on a GPU enabled machine.

Once that is done, you will need to run the hand detector and depth detection on a machine
with many more GPUs.

1.  push the code files to OCI by running `./oci_utilities/push_code.sh`
2.  Provision instance of:
    *   Image: Oracle Linux 8 GPU Build, [supported version](https://nvidia.github.io/nvidia-docker/)
    *   Shape: VM.GPU3.1
    *   vcn: flo vcn
    *   subnet: private
    *   SSH Keys: None
    *   Boot Volume: 2000GB
3.  Enable Bastion Service on the instance
4.  Remote into that instance. Ex:
    `oci-cli-helpers/utilities/oci-ssh.sh $(oci-cli-helpers/utilities/ocid.sh instance flo-hdf5-1)`
5.  Check if the nvidia drivers are working: `nvidia-smi`
6.  Setup permissions: `OCI_CLI_AUTH=instance_principal && export OCI_CLI_AUTH`
7.  Install the oci cli: `sudo dnf -y install oraclelinux-developer-release-el8 && sudo dnf -y install python36-oci-cli`
8.  Pull down code onto the remote instance:
    `oci os object bulk-download -bn 'rrl-flo-run' --download-dir "$HOME/LilFloAssessmentPipeline" --overwrite`
9.  Run setup script: `bash LilFloAssessmentPipeline/oci_utilities/pose/machine_setup_openpose.sh`
10. Test that nvidia docker installed properly:
11. Run tmux: `tmux`. If you disconnect, reconect: `tmux a`. You could also use screen.
12. Run Script: `bash "$HOME/LilFloAssessmentPipeline/oci_utilities/openpose/run_manual.sh" <subj number> 2>&1 | tee -a "$HOME/logs/runs/$(date +"%Y-%m-%d-%H-%M-%S-%N" | cut -b1-22)-subj_<subj number>"`
13. To keep an eye on the processes running under the hood in docker, you can run:
    a. `while true; do sleep 1; docker logs -f openpose-runner 2>&1 | tee -a "$HOME/logs/runs/docker"; done`
    b. `journalctl -f -u docker CONTAINER_NAME=openpose-runner`
14. To view logs after an image has been destroyed, use jornalctl to query the system logs.

If you want to run a bunch of subjects at once, you can do that with something like:

```{bash}
bash "$HOME/LilFloAssessmentPipeline/oci_utilities/pose/run_manual_multi_openpose.sh" 001 003 004 005 006 008 500-2 500-3 500-4
```

#### Hand Pose/Depth and Body Depth

For the hand detector and depth extraction:

1.  push the code files to OCI by running `./oci_utilities/push_code.sh`
2.  Provision instance of:
    *   Image: Oracle Linux 8
    *   Shape: VM.Standard.E4.Flex (40 ocpu, 140 GB RAM)
    *   vcn: flo vcn
    *   subnet: private
    *   SSH Keys: None
    *   Boot Volume: 2000GB
3.  Enable Bastion Service on the instance
4.  Remote into that instance. Ex:
    `oci-cli-helpers/utilities/oci-ssh.sh $(oci-cli-helpers/utilities/ocid.sh instance flo-hdf5-1)`
5.  Setup permissions: `OCI_CLI_AUTH=instance_principal && export OCI_CLI_AUTH`
6.  Install the oci cli: `sudo dnf -y install oraclelinux-developer-release-el8 && sudo dnf -y install python36-oci-cli`
7.  Pull down code onto the remote instance:
    `oci os object bulk-download -bn 'rrl-flo-run' --download-dir "$HOME/LilFloAssessmentPipeline" --overwrite`
8.  Run setup script: `bash LilFloAssessmentPipeline/oci_utilities/pose/machine_setup_mediapipe_depth.sh`
9.  Run tmux: `tmux`. If you disconnect, reconect: `tmux a`. You could also use screen.
10. Run Script: `bash "$HOME/LilFloAssessmentPipeline/oci_utilities/openpose/run_manual_multi_mediapipe_depth.sh" <subj number> 2>&1 | tee -a "$HOME/logs/runs/$(date +"%Y-%m-%d-%H-%M-%S-%N" | cut -b1-22)-subj_<subj number>"`
11. To keep an eye on the processes running under the hood in docker, you can run:
    a. `while true; do sleep 1; docker logs -f openpose-runner 2>&1 | tee -a "$HOME/logs/runs/docker"; done`
    b. `while true; do sleep 1; docker logs -f mediapipe-runner 2>&1 | tee -a "$HOME/logs/runs/docker"; done`
12. Or you can run:
    a. `journalctl -f -u docker CONTAINER_NAME=openpose-runner`
    a. `journalctl -f -u docker CONTAINER_NAME=mediapipe-runner`

If you want to run a bunch of subjects at once, you can do that with something like:

```{bash}
bash "$HOME/LilFloAssessmentPipeline/oci_utilities/pose/run_manual_multi_mediapipe_depth.sh" 001 003 004 005 006 008 500-2 500-3 500-4
```

### Running Locally

1.  Install Dependencies:
    a. You can try to use the local setup script `pose-body/setup_local.sh`
    b. You can manually install: cuda, docker, nvidia-docker
2.  Run script: `./pose-body/scripts/run_local.sh -d <"Location to data directory">`

You might get a common GPU architecture not supported error. In that case, make sure to restart docker with :

`sudo systemctl restart docker`

Make sure you are able to run:
`sudo docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi`

You also might find that your gpu runs out of memory. To check this,
run `nvidia-smi`. You can keep an updated window with this by running
something like: `watch -n .1 nvidia-smi`.

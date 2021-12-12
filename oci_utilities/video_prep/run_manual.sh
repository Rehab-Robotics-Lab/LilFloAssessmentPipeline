#!/usr/bin/env bash
set -o errexit
set -o pipefail

OCI_CLI_AUTH=instance_principal
export OCI_CLI_AUTH

script="$(realpath "$0")"
scriptpath="$(dirname "$script")"

# shellcheck source=../includes/parse_input_subj_no.sh
source "$scriptpath/../includes/parse_input_subj_no.sh"

### download files
mkdir -p "$HOME/data"
rm -rf "$HOME/data/*"
oci os object bulk-download -bn 'rrl-flo-raw' --dest-dir "$HOME/data" --prefix "$subject_padded"

### uncompress files
echo 'uncompressing files'
find "$HOME/data" -name '*.bz2' -exec lbzip2 -d -f -n 48 {} \;

### If podium
if [ -d "$HOME/data/$subject_padded/ros/podium/" ]
then
echo 'processing podium files'
# shellcheck source=../../bag2video/run_docker_bag2vid.sh
bash "$scriptpath/../../bag2video/run_docker_bag2vid.sh" -d "$HOME/data/$subject_padded/ros/podium" -s 90 -v info --audio_topic /robot_audio/audio_relay /lower_realsense/color/image_raw_relay /upper_realsense/color/image_raw_relay
# shellcheck source=../../prep_code_vids/transcode-to_davinci.sh
bash "$scriptpath/../../prep_code_vids/transcode-to_davinci.sh"  -t "$HOME/data/$subject_padded/ros/podium"
fi

### If robot
if [ -d "$HOME/data/$subject_padded/ros/robot/" ]
then
# shellcheck source=../../bag2video/run_docker_bag2vid.sh
bash "$scriptpath/../../bag2video/run_docker_bag2vid.sh" -d "$HOME/data/$subject_padded/ros/robot" -s 90 -v info --audio_topic /robot_audio/audio_relay /lower_realsense/color/image_raw_relay /upper_realsense/color/image_raw_relay
# shellcheck source=../../prep_code_vids/transcode-to_davinci.sh
bash "$scriptpath/../../prep_code_vids/transcode-to_davinci.sh" -t "$HOME/data/$subject_padded/ros/robot"
fi

### If all together
if ls "$HOME/data/$subject_padded/ros/"*.bag &> /dev/null
then
# shellcheck source=../../bag2video/run_docker_bag2vid.sh
bash "$scriptpath/../../bag2video/run_docker_bag2vid.sh" -d "$HOME/data/$subject_padded/ros" -s 90 -v info --audio_topic /robot_audio/audio_relay /lower_realsense/color/image_raw_relay /upper_realsense/color/image_raw_relay
# shellcheck source=../../prep_code_vids/transcode-to_davinci.sh
bash "$scriptpath/../../prep_code_vids/transcode-to_davinci.sh" -t "$HOME/data/$subject_padded/ros"
fi

### For gopro
# shellcheck source=../../prep_code_vids/concatenate_vids.sh
bash "$scriptpath/../../prep_code_vids/concatenate_vids.sh" -t "$HOME/data/$subject_padded/gopro"
# shellcheck source=../../prep_code_vids/transcode-to_davinci.sh
bash "$scriptpath/../../prep_code_vids/transcode-to_davinci.sh" -t "$HOME/data/$subject_padded/gopro/concatenated"

### For 3rd-person
# shellcheck source=../../prep_code_vids/concatenate_vids.sh
bash "$scriptpath/../../prep_code_vids/concatenate_vids.sh" -t "$HOME/data/$subject_padded/3rd-person"
# shellcheck source=../../prep_code_vids/transcode-to_davinci.sh
bash "$scriptpath/../../prep_code_vids/transcode-to_davinci.sh" -t "$HOME/data/$subject_padded/3rd-person/concatenated"

### upload data
oci os object bulk-upload -bn 'rrl-flo-vids' --src-dir "$HOME/data/$subject_padded" --include '*.mov' --include '*.MOV' --include '*.mp4' --include '*.MP4' --include '*.avi' --include '*.AVI' --prefix "$subject_padded/" --overwrite

rm -rf "$HOME/data/$subject_padded"

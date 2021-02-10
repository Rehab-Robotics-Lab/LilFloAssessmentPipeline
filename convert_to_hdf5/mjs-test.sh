#!/bin/bash
set -o errexit
set -o pipefail

data="/media/mjsobrep/Hybrid Drive/flo_data/008/"
bag_files=$(ls "$data")

for bag_fn in $bag_files
do
    "$HOME"/Documents/git/LilFloAssessmentPipeline/convert_to_hdf5/test.sh -d "$data" -b "$bag_fn"
done

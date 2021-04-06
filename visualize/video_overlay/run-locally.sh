#!/bin/bash
set -o errexit
set -o pipefail

# parse options
while getopts :c:a:p:d:o:r flag
do
    case "${flag}" in
        c) condition=${OPTARG};;
        a) activity=${OPTARG};;
        p) camera=${OPTARG};;
        o) overlay=${OPTARG};;
	    d) data=${OPTARG};;
        r) rebuild=true;;
        :) echo 'missing argument' >&2; exit 1;;
        \?) echo 'invalid option' >&2; exit 1
    esac
done

if [ "$rebuild" = true ] ; then
    echo 'rebuilding docker image'
    docker build . --tag video-overlay
fi

if [[ "$camera" =~ ^(upper|lower|all)$ ]]; then
    echo "processing for $camera realsense"
else
    echo "invalid camera parameter passed: $camera"
fi

echo "Data directory: $data"
echo "Condition: $condition"
echo "Activity: $activity"
echo "Camera: $camera"

if [[ "$camera" == "all" ]]; then

docker run \
    --mount type=bind,source="$data",target=/code/data \
    --rm \
    -i \
    video-overlay \
    "data/$condition/$activity" \
    "lower"\
    "$overlay"

docker run \
    --mount type=bind,source="$data",target=/code/data \
    --rm \
    -i \
    video-overlay \
    "data/$condition/$activity"\
    "upper"\
    "$overlay"
else
docker run \
    --mount type=bind,source="$data",target=/code/data \
    --rm \
    -i \
    video-overlay\
    "data/$condition/$activity"\
    "$camera"\
    "$overlay"
fi

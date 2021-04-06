#!/bin/bash
set -o errexit
set -o pipefail

# parse options
while getopts :d:r flag
do
    case "${flag}" in
        d) data=${OPTARG};;
        r) rebuild=true;;
        :) echo 'missing argument' >&2; exit 1;;
        \?) echo 'invalid option' >&2; exit 1
    esac
done

echo "processing hdf5 files in $data"

if [ "$rebuild" = true ] ; then
    echo 'rebuilding docker image'
    docker build . --tag openpose
fi
docker run \
    --mount type=bind,source="$data",target=/data \
    --rm \
    -i \
    openpose

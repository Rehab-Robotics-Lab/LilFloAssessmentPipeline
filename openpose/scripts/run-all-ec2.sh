#!/bin/bash
set -o errexit
set -o pipefail

# parse options
while getopts :s: flag
do
    case "${flag}" in
        s) subject=${OPTARG};;
        :) echo 'missing argument' >&2; exit 1;;
        \?) echo 'invalid option' >&2; exit 1
    esac
done

# check subject number
echo "Passed: $subject"
re='^[0-9]+$'
if ! [[ $subject =~ $re ]] ; then
   echo "error: Subject number is not a number" >&2; exit 1
fi

./process-in-ec2.sh -s "$subject" -c augmented-telepresence -a simon-says
./process-in-ec2.sh -s "$subject" -c augmented-telepresence -a target-touch
./process-in-ec2.sh -s "$subject" -c classical-telepresence -a simon-says
./process-in-ec2.sh -s "$subject" -c classical-telepresence -a target-touch
./process-in-ec2.sh -s "$subject" -c in-person -a simon-says
./process-in-ec2.sh -s "$subject" -c in-person -a target-touch

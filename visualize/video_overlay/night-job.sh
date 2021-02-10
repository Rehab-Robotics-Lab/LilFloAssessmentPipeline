#!/bin/bash
set -o errexit
set -o pipefail

./process-in-ec2.sh -s 6 -a simon-says -c augmented-telepresence -p lower
./process-in-ec2.sh -s 8 -a simon-says -c augmented-telepresence -p lower

./process-in-ec2.sh -s 6 -a simon-says -c in-person -p lower
./process-in-ec2.sh -s 8 -a simon-says -c in-person -p lower

./process-in-ec2.sh -s 6 -a target-touch -c augmented-telepresence -p upper
./process-in-ec2.sh -s 6 -a target-touch -c in-person -p upper

./process-in-ec2.sh -s 8 -a target-touch -c augmented-telepresence -p upper
./process-in-ec2.sh -s 8 -a target-touch -c in-person -p upper
./process-in-ec2.sh -s 8 -a simon-says -c classical-telepresence -p lower
./process-in-ec2.sh -s 8 -a target-touch -c classical-telepresence -p upper

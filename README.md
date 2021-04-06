# FloAssessmentPipeline

This is the pipeline for assessing patient function based on data from the Flo System.
The fundamental idea is to operate over a 3 step pipeline:

1.  Extract pose
2.  Calculate features of motion
3.  Classify/Regress measure of function

Along the way there is data cleaning, manipulation, and visualization.

Data is ingested as compressed bag files. That data is put into HDF5 files.
All of the non-video generated data (poses, etc.) go into a separate hdf5 file
to make it easier to manage.

Everything is done on AWS.

## Some tools

*   **ViTables:** is really great for being able to explore hdf5 files

## Pipeline

The pipeline will be running in AWS batch (eventually, for now all in EC2)

### Uploading data

1.  create a folder for the subject with three digits `NNN` ex: `009` or `024`
2.  compress all of the bagfiles: `lbzip2 *.bag`
3.  packup the parameter files: `tar -cvf flo_parameters-yyyy-mm-dd_.tar *.yaml`
4.  put the compressed bag files and tar parameter file into a folder `NNN/ros`
5.  put all of the gopro videos into a folder `NNN/gopro` next to the `NNN/ros` folder
6.  put all of the 3rd person videos into a folder `NNN/3rd-person` next to the `NNN/ros` and `NNN/gopro` folders

#### Upload to AWS

1.  Go one level above the subject folder
2.  start with a dryrun: `aws s3 sync NNN s3://flo-exp-aim1-data-raw/NNN --dryrun` to make sure everything looks good
3.  Then run for real with no dry run

#### Upload data to Penn+Box

1.  Drag the subjects folder into the [Penn+Box Folder](https://upenn.app.box.com/folder/126576235920)

### Generate Metadata

Metadata must be gathered before begining the pipeline. For instructions,
see [inpsect/README.md](inpsect/README.md)

This is done in meta.yaml, which should be in each subjects root dir.
This specifies the start and end times for each segment of the experiment.

For an example see inspect/template.yaml

### getting rosbags into hdf5

In order to make processing easier, we move everything into HDF5 files.
This allows easier indexing and out of order processing

For instructions on running, see: [convert_to_hdf5/README.md](convert_to_hdf5/README.md)

### Pose Detection

A central component of the pipeline is extracting pose from video.
There are a few different tools that can be used to do that, all of them
imperfect.

#### OpenPose

OpenPose provides 2D pose of subjects. You can view more information at [openpose/README.md](openpose/README.md).

### QC and publications

we need a way to generate videos overlaying everything and visualize it all to make sure it is working and to put in publications...

For information look to [visualize/README.md](visualize/README.md)

## Setting up for AWS Batch Jobs

1.  Setup an ECR repository and push the docker file for the job you want to it
2.

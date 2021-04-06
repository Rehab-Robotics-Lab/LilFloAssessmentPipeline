#!/bin/bash
set -o errexit
set -o pipefail

# https://stackoverflow.com/a/21189044/5274985
function parse_yaml {
   local prefix=$2
   local s w fs
   s='[[:space:]]*' w='[a-zA-Z0-9_]*' fs=$(echo @|tr @ '\034')
   # shellcheck disable=SC1087
   sed -ne "s|^\($s\):|\1|" \
        -e "s|^\($s\)\($w\)$s:$s[\"']\(.*\)[\"']$s\$|\1$fs\2$fs\3|p" \
        -e "s|^\($s\)\($w\)$s:$s\(.*\)$s\$|\1$fs\2$fs\3|p"  "$1" |
   awk "-F$fs" '{
      indent = length($1)/2;
      vname[indent] = $2;
      for (i in vname) {if (i > indent) {delete vname[i]}}
      if (length($3) > 0) {
         vn=""; for (i=0; i<indent; i++) {vn=(vn)(vname[i])("_")}
         printf("%s%s%s=\"%s\"\n", "'"$prefix"'",vn, $2, $3);
      }
   }'
}

eval "$(parse_yaml /data/meta.yaml YAML_)"
# shellcheck disable=SC2154
subject="${YAML_id##+(0)}"
#subject=$(echo $YAML_id | sed 's/^0*//')
echo "reading subject $YAML_id"
# check subject number
re='^[0-9]+$'
if ! [[ $subject =~ $re ]] ; then
   echo "error: Subject number is not a number" >&2; exit 1
fi

subject_padded=$(printf '%03d' "$subject")
echo "Processing for subj: $subject_padded"

aws s3 cp /data/meta.yaml "s3://flo-exp-aim1-data-meta/$subject_padded/"

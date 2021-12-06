#!/usr/bin/env bash

# Should be sourced from another script
# Gets all of the subjects listed in the raw data bucket


# shellcheck disable=SC2034
# This should be sourced and used elsewhere
subjects=$(oci os object list \
    --config-file "$HOME/.oci/config" \
    --profile 'token-oci-profile' \
    --auth security_token \
    -bn 'rrl-flo-raw' \
    --all \
    --query 'data[].name' \
    | jq 'map(split("/")[0]) | unique | .[]' -r)

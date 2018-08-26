#!/bin/bash

# @Author: Andreas Werschlan
# @Date:   2018-07-05T09:41:11+02:00
# @Email:  anw@visotech.com
# @Last modified by:   anw
# @Last modified time: 2018-07-06T14:08:44+02:00

ENTED_ETC_DIR=/etc/ented

get_nbroot () {
    if [ -d $ENTED_ETC_DIR ]; then
        symlinks=$(readlink $ENTED_ETC_DIR/*|wc -l)
        if [ $symlinks -lt 1 ] ; then
                # symlinks less than 1 -> no instance configured -> $NBROOT will be set
                exit 0
        elif [ $symlinks -gt 1 ] ; then
                echo "$0: only one instance supported by this script" >&2
                echo "Bailing out." >&2
                exit 2
        fi
        # everything looks good -> return $NBROOT
        dirname $(dirname $(readlink $ENTED_ETC_DIR/*))
    fi
}

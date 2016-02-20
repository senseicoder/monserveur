#!/bin/bash

source ~/bin/docker.inc.sh

for i in "data/mysql logs/fulltextrss conf/fulltextrss logs/ttrss conf/ttrss"; do mkdir -p $i; done

#docker_needed_image apt_cacher_ng

docker-compose up

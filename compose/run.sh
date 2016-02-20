#!/bin/bash

source ~/bin/docker.inc.sh

docker_needed_image test_apt_cacher_ng

docker-compose up
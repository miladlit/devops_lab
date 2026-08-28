# Docker part 2 Lab notes
* step 3: Create linux-net and test inter container communication


# Linux 2 Docker Compose Lab

This lab demonstrates how to run multiple containers using Docker Compose. A webserver container (linux2-web) and a client container (Ubuntu) are started together and communicate using Docker’s internal DNS on a shared custom network.

## compose.yaml
services:
  webserver:
    image: linux2-web
    networks:
      - linux2-net

  client:
    image: ubuntu
    command: sleep infinity
    networks:
      - linux2-net

networks:
  linux2-net:
    external: true

## Commands Used
sudo docker-compose up -d
sudo docker-compose ps
sudo docker-compose exec client bash

Inside client:
apt update && apt install -y curl
curl http://webserver

## What I Learned
- How to define multi-container setups in compose.yaml
- How services share networks in Compose
- How Docker DNS resolves service names
- How to exec into containers using Compose
- How Compose simplifies multi-container workflows

## Next Steps
Docker volumes, bind mounts, and LVM lab.

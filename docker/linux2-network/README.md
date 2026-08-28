# Linux 2 – Docker Networking Lab

This lab shows how to create a custom Docker network and run multiple containers inside it. A webserver container (linux2-web) and a client container (Ubuntu) communicate using Docker’s internal DNS.

## Commands Used
sudo docker network create linux2-net
sudo docker network ls

sudo docker run -d --name webserver --network linux2-net linux2-web
sudo docker run -it --name client --network linux2-net ubuntu bash

Inside client:
apt update && apt install -y curl
curl http://webserver

## What I Learned
- How to create custom Docker networks
- How containers communicate internally
- How Docker DNS resolves container names
- How to test communication using curl
- How internal-only containers work without exposing ports

## Next Steps
Docker Compose, Docker volumes, LVM lab.

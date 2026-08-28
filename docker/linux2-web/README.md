# Linux 2 – Docker Web Lab

This project is part of my Linux 2 course. It shows how to build, run, and inspect a custom Docker container based on Ubuntu 24.04 running an nginx web server. The lab covers building an image, running a container, inspecting processes, networking, and understanding how containers share the host kernel while providing an isolated user space.

## Dockerfile
FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y nginx curl iproute2 procps
COPY index.html /var/www/html/index.html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

## Build Image
sudo docker build -t linux2-web .

## Run Container
sudo docker run -d --name web -p 8080:80 linux2-web

## Inspect Container
sudo docker exec -it web bash  
ps aux  
ip a  
ss -ltn  
uname -a  
cat /etc/os-release  

## What I Learned
- Difference between image and container  
- How nginx runs inside a Docker container  
- How port mapping works (8080 → 80)  
- How containers share the host kernel but have their own user space  
- How to inspect processes, network, and OS inside a container  

## Next Steps
Docker networking, multi-container communication, Docker Compose, Docker volumes, and LVM lab.

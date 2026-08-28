# Linux 2 – Docker Volumes Lab

This lab demonstrates how Docker volumes provide persistent storage for containers. A named volume (`linux2-data`) is created and mounted into multiple containers to verify that data persists even after container deletion.

## Commands Used

### Create Volume
sudo docker volume create linux2-data
sudo docker volume ls

### Use Volume in Container
sudo docker run -it --name voltest -v linux2-data:/data ubuntu bash
echo "Hello from Milad" > /data/test.txt
cat /data/test.txt

### Verify Persistence
sudo docker rm voltest
sudo docker run -it --name voltest2 -v linux2-data:/data ubuntu bash
cat /data/test.txt

## What I Learned
- Difference between anonymous and named volumes
- How volumes persist after container removal
- How to mount volumes into containers
- How to inspect and manage Docker volumes

## Next Steps
Bind mounts and LVM lab.

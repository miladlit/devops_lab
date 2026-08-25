FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y nginx curl iproute2 procps

COPY index.html /var/www/html/index.html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

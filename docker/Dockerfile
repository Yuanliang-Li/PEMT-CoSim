# syntax=docker/dockerfile:1
#
# docker file for creating hyperledger fabric ubuntu container
#
FROM ubuntu:focal

# environment variables
ENV USER="root"
ENV HOME="/root"

# container startup scripts
ARG STARTUP="startup"
ENV STARTUP_DIR=$HOME/$STARTUP

# github desktop
ENV GITHUB_DESKTOP_FILE="GitHubDesktop-linux-2.6.3-linux1.deb"
ARG GITHUB_DESKTOP_PATH="https://github.com/shiftkey/desktop/releases/download/release-2.6.3-linux1/GitHubDesktop-linux-2.6.3-linux1.deb"

# latest version of docker-compose
ENV DOCKER_COMPOSE_DESTINATION="/usr/bin/docker-compose"

# latest TESP release
ARG TESP_RELEASE_DIR="https://github.com/pnnl/tesp/releases/download/v1.0.0"
ENV TESP_RELEASE_FILE="tesp-1.0.0-linux-x64-installer.run"
ARG TESP_RELEASE_URL=${TESP_RELEASE_DIR}/${TESP_RELEASE_FILE}

# copy bash startup script
ADD $STARTUP $STARTUP_DIR

# expose ports for ssh
EXPOSE 22
# expose ports for tightvncserver
# tightvncserver runs display 1 on port 5901 and display 2 on port 5902, et cetera
EXPOSE 5901

# create a volume to share data between host and other containers
VOLUME /shared-volume

# prevent installer from runnning in interactive mode, 
# in order to allow automation of the installation
ARG DEBIAN_FRONTEND=noninteractive

# set the time zone
ENV TZ=America/Los_Angeles

# update, install wget, githubdesktop, xfce window manager, vncserver
RUN apt-get update && \
    apt upgrade -y && \
    # base ubuntu system build w/ ssh and vnc support
    apt-get install -y && \
    apt-get install -y wget && \
    apt-get install -y openssh-server && \
    wget $GITHUB_DESKTOP_PATH && \
    apt-get install -y gdebi && \
    gdebi $GITHUB_DESKTOP_FILE && \
    apt-get install -y tightvncserver && \
    apt-get install -y dbus-x11 && \
    apt-get install -y net-tools && \
    apt-get install -y xfce4 --no-install-recommends && \
    apt install -y xfce4-goodies && \
    apt-get install -y git && \
    apt-get install -y nano && \
    apt-get install -y vim && \
    # essential tools & docker that are needed for fabric
    apt-get install -y build-essential && \
    apt-get install -y curl && \
    apt-get install -y gnupg lsb-release && \
    apt-get install -y apt-transport-https && \
    apt-get install -y ca-certificates && \
    apt-get install -y software-properties-common && \
    apt-get install -y docker && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - && \
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu bionic stable" && \
    apt-get install -y containerd.io && \
    apt-get install -y docker-ce && \
    apt-cache policy docker-ce && \
    apt-get install -y docker-ce-cli && \
    curl -L https://github.com/docker/compose/releases/download/1.29.2/docker-compose-Linux-x86_64 -o $DOCKER_COMPOSE_DESTINATION && \
    # ubuntu utilities
    apt-get install -y golang-go && \
    apt-get install -y python3 && \
    apt-get install -y nodejs && \
    apt-get install -y  npm && \
    apt-get install -y  xfce4-terminal && \
    apt-get install -y  tree && \
    apt-get install -y  jq && \
    apt-get install -y dos2unix && \
    apt-get install -y busybox && \
    # tesp installation, and needs to be run in ubuntu.sh
    apt-get -y install libjsoncpp-dev && \
    apt-get -y install libxerces-c-dev && \
    apt-get -y install libzmq5 && \
    apt-get -y install libczmq-dev && \
    apt-get -y install libklu1 && \
    apt-get -y install coinor-cbc && \
    apt-get -y install openjdk-11-jre-headless && \
    apt-get -y install openjdk-11-jdk-headless && \
    apt-get -y install python3-tk && \
    apt-get -y install python3-pip && \
    apt-get -y install lsof && \
#    pip3 install tesp_support --upgrade && \
#    pip3 install psst --upgrade && \
#    pip3 install helics==2.5.2 && \
    pip3 install psutil && \
    pip3 install glm==0.4.3 && \
    pip3 install numpy==1.21.3 && \
    pip3 install torch==1.11.0+cpu torchvision==0.12.0+cpu torchaudio==0.11.0 --extra-index-url https://download.pytorch.org/whl/cpu  && \
    # download the tesp installer
    curl -L ${TESP_RELEASE_URL} -o ${TESP_RELEASE_FILE}


# upon creation of the container run the startup script, and do any clean 
# up on the container, set time zone, then start bash

CMD chmod +x $STARTUP_DIR/ubuntu-start.sh ; \
    sed -i -e 's/\r$//' $STARTUP_DIR/ubuntu-start.sh ;\
    $STARTUP_DIR/ubuntu-start.sh ; \
    # mv github desktop to startup dir
    mv $GITHUB_DESKTOP_FILE $STARTUP_DIR ; \
    # complete docker-compose installation
    chmod a+rx $DOCKER_COMPOSE_DESTINATION ; \
    # set timezone
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone ; \
    # start a bash shell
    /bin/bash

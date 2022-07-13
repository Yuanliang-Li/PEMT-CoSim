#!/usr/bin/bash

echo "------------------------------------------------------------------"
echo "STATUS: Starting..."
currentDate=`date`
echo "Date = " $currentDate
echo "------------------------------------------------------------------"

echo "------------------------------------------------------------------"
echo "STATUS:       Starting vncserver..."
echo "------------------------------------------------------------------"
# vncserver with complain unless ~/.Xauthority exists
touch ~/.Xauthority

# export vncserver variables
USER=root
HOME=/root
export USER HOME

# copy the xstartup file that runs xfce4 desktop for tightvnc
mkdir $HOME/.vnc
touch $HOME/.Xresources

# setup display for vnc
DISPLAY=:1
export DISPLAY

# start vncserver
# 1280×720 lowres hd
vncserver -geometry 1920x1080

# run the ssh server
echo "------------------------------------------------------------------"
echo "STATUS:       Starting ssh service..."
echo "------------------------------------------------------------------"
service ssh start

# start the docker service
echo "------------------------------------------------------------------"
echo "STATUS:       Starting docker daemon..."
echo "------------------------------------------------------------------"
service docker start

# add golang to paths
echo "------------------------------------------------------------------"
echo "STATUS:       Adding golang paths..."
echo "------------------------------------------------------------------"
echo 'export GOPATH=$HOME/go' >> ~/.bashrc
echo 'export PATH=$GOPATH/bin:$PATH' >> ~/.bashrc

# add fabric bin to path
echo "------------------------------------------------------------------"
echo "STATUS:       Adding fabric path..."
echo "------------------------------------------------------------------"
echo 'export PATH=/fabric-samples/bin/:$PATH' >> ~/.bashrc

# add path to where fabric samples is located
echo 'export FABRIC_SAMPLES=/fabric-samples' >> ~/.bashrc

# export docker compose variables (or create a .env file)
echo 'export COMPOSE_PROJECT_NAME=fabricnet' >> ~/.bashrc
# echo 'export IMAGE_TAG=latest' >> ~/.bashrc


# pull the fabric images, note: *** unable to do this in docker build because the docker
# daemon needs to be running prior to it executing ***
echo "------------------------------------------------------------------"
echo "STATUS:       Downloading and installing hyperledger fabric"
echo "------------------------------------------------------------------"

# download recommended version of fabric from per
# https://hyperledger-fabric.readthedocs.io/en/release-2.2/install.html
curl -sSL https://bit.ly/2ysbOFE | bash -s


# install TESP
echo "------------------------------------------------------------------"
echo "STATUS:       Installing TESP"
echo "------------------------------------------------------------------"
# run TESP installation
chmod +x ./${TESP_RELEASE_FILE}
mv $TESP_RELEASE_FILE $STARTUP_DIR

# set TESP env variables
echo 'export TESPDIR=/opt/tesp' >> ~/.bashrc
echo 'export GLPATH=/opt/tesp/lib/gridlabd:/opt/tesp/share/gridlabd' >> ~/.bashrc
echo 'export TESP_INSTALL=/opt/tesp' >> ~/.bashrc

# add TESP bin to path
echo 'export PATH=/opt/tesp/bin:$PATH' >> ~/.bashrc

# add to load library path
echo 'export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/opt/tesp/lib/gridlabd:$LD_LIBRARY_PATH' >> ~/.bashrc

# add path to energyplus
echo 'export PATH=/opt/tesp:$PATH' >> ~/.bashrc

# add path to TESP PostProcess and PreProcess
echo 'export PATH=/opt/tesp/PreProcess:/opt/tesp/PostProcess:$PATH' >> ~/.bashrc

# tesp chokes on timezone for some reason..., so unset it
echo "unset TZ"  >> ~/.bashrc
unset TZ
source ~/.bashrc

# install tesp manually
echo "------------------------------------------------------------------"
echo "NOTE: Please type the following to manually install TESP"
echo ${STARTUP_DIR}/${TESP_RELEASE_FILE}
echo "------------------------------------------------------------------"


echo "------------------------------------------------------------------"
echo "STATUS: Done"
echo "------------------------------------------------------------------"

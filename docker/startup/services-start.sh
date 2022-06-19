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


echo "------------------------------------------------------------------"
echo "STATUS: Done"
echo "------------------------------------------------------------------"

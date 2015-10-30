#!/usr/bin/env bash
export NODES_COUNT=4
#export ISO_PATH=/home/yyekovenko/ironic_resources/fuel-gerrit-8.0-216-2015-10-12_16-54-24.iso
export ISO_PATH=/srv/downloads/fuel-gerrit-8.0-367-2015-10-28_14-10-13.iso
export DEFAULT_IMAGES_UBUNTU=/home/yyekovenko/ironic_resources/trusty-server-cloudimg-amd64.img

export IRONIC_ENABLED=true
export IRONIC_NODES_COUNT=2

## cz5578
#export HW_SERVER_IP=172.18.170.7
#export HW_SSH_USER=ironic
#export HW_SSH_PASS=ironic_password
#export VENV_PATH=/home/yyekovenko/venv/october-env
#export ENV_NAME=yyekovenko-ironic-iso-216

# cz7764
export HW_SERVER_IP=172.18.170.44
export HW_SSH_USER=<username>
export HW_SSH_PASS=<********>
export DRIVER_USE_HOST_CPU=false
export VENV_PATH=/home/yyekovenko/venv/devops
export ENV_NAME=yyekovenko-ironic-367

#export IRONIC_PLUGIN_PATH=/home/yyekovenko/ironic_resources/fuel-plugin-ironic-1.0-1.0.0-1.noarch.rpm
#export BAREMETAL_NET='10.109.47.1/24'
#export IRONIC_VM_MAC='64:49:29:47:d9:a6'
#export IRONIC_BM_MAC='00:25:90:7f:79:60'
#export IPMI_SERVER_IP=185.8.58.246
#export IPMI_USER=engineer
#export IPMI_PASS=09ejm7HGViwbg

export MAKE_SNAPSHOT=true

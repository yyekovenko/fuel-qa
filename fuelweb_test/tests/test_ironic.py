#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Before test run, ensure the following environment variables are defined:
  - NODES_COUNT
  - IRONIC_PLUGIN_PATH
  - ENV_NAME
  - VENV_PATH
  - ISO_PATH

See ironic_env_vars.sh for example.

If the environment with name=ENV_NAME does not exist it will be created before
test execution start.

Navigate to fuel-qa directory and use this command to launch tests:
  ./utils/jenkins/system_tests.sh -t test -k -K -w $(pwd) -j $ENV_NAME -i
    $ISO_PATH -o --group="ironic_plugin"
"""

import json
import os
import random

from proboscis.asserts import assert_equal, assert_true
from proboscis import test

from fuelweb_test import logger
from fuelweb_test import settings as conf
from fuelweb_test.helpers import os_actions
from fuelweb_test.helpers import ironic_actions
from fuelweb_test.tests.test_ironic_base import TestIronicBase


@test(groups=["ironic"])
class IronicTest(TestIronicBase):
    """Tests for Ironic."""

    @test(depends_on=[TestIronicBase.ironic_base],
          groups=["ironic"])
    def boot_ironic_node_with_fuel_ssh_agent(self):
        """Boot ironic node with fuel ssh agent

        Scenario:
            . Create baremetal flavor
            . Import Ubuntu image
            . Create ironic node
            . Create ironic port for this node
            . Verify that ironic instance can be booted successfully

        Duration 35m
        Snapshot boot_ironic_node_with_fuel_ssh_agent
        """
        # self.env.revert_snapshot("ironic_base")

        cluster_id = self.fuel_web.get_last_created_cluster()

        controller_ip = self.fuel_web.get_public_vip(cluster_id)
        os_conn = os_actions.OpenStackActions(controller_ip)
        ironic = ironic_actions.IronicActions(controller_ip)

        # Get ironic nodes characteristics
        cpus = self.env.d_env.nodes().ironics[0].vcpu
        memory_mb = self.env.d_env.nodes().ironics[0].memory
        local_gb = conf.NODE_VOLUME_SIZE
        mac = self.env.d_env.nodes().ironics[0].interface_by_network_name(
            'ironic')[0].mac_address

        logger.debug('Create ironic node')
        ironic_node = ironic.create_virtual_node(
            server_ip=os.environ['HW_SERVER_IP'],
            ssh_username=os.environ['HW_SSH_USER'],
            ssh_password=os.environ['HW_SSH_PASS'],
            cpus=cpus,
            memory_mb=memory_mb,
            local_gb=local_gb
        )
        logger.debug('Create ironic port')
        ironic.create_port(address=mac, node_uuid=ironic_node.uuid)
        ironic.wait_for_hypervisors(ironic_nodes=[ironic_node],
                                    timeout=900)

        bm_flavor = os_conn.create_flavor(
            "virtual-baremetal-" + str(random.randint(1, 0x7fff)),
            memory_mb, cpus, local_gb
        )
        key = os_conn.create_key('ironic_key' + str(random.randint(1, 0x7fff)))

        # #############################################
        img = os_conn.get_image_by_name('virtual_trusty')
        if img is None:
            img = ironic.import_ironic_image()
        # #############################################

        logger.debug('Boot ironic VM')
        srv = ironic.boot_ironic_instance(
            image_id=img.id,
            flavor_id=bm_flavor.id,
            timeout=600,
            key_name=key.name,
            userdata='#!/bin/bash\ntouch /home/ubuntu/success.txt'
        )
        floating_ip = os_conn.assign_floating_ip(srv)

        self.check_userdata_executed(cluster_id, floating_ip.ip, key)

        self.env.make_snapshot("boot_ironic_node_with_fuel_ssh_agent")

    # @test(#depends_on=[TestIronicBase.test_ironic_base],
          # groups=['ironic_hw']
    # )
    def boot_ironic_node_with_fuel_ipmi_agent(self):
        self.env.revert_snapshot("ironic_base")

        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "test_ironic_hw.json")) as hw_file:
            hw = json.load(hw_file)

        cpus = hw[0]['cpus']
        memory_mb = hw[0]['memory_mb']
        local_gb = hw[0]['local_gb']

        cluster_id = self.fuel_web.get_last_created_cluster()

        controller_ip = self.fuel_web.get_public_vip(cluster_id)
        os_conn = os_actions.OpenStackActions(controller_ip)
        ironic = ironic_actions.IronicActions(controller_ip)

        # #############################################
        img = os_conn.get_image_by_name('bm_trusty')
        if img is None:
            img = ironic.import_ironic_image(image_name='bm_trusty',
                                             disk='sda')
        # #############################################

        logger.debug('Create ironic node')
        # ironic_node = ironic.create_baremetal_node(
        #     server_ip=os.environ['IPMI_SERVER_IP'],
        #     ipmi_username=os.environ['IPMI_USER'],
        #     ipmi_password=os.environ['IPMI_PASS']
        # )
        # ironic_node = ironic.create_baremetal_node(
        #     server_ip=hw[0]['ip'],
        #     ipmi_username=hw[0]['ipmi_user'],
        #     ipmi_password=hw[0]['ipmi_pass'],
        #     cpus=cpus,
        #     memory_mb=memory_mb,
        #     local_gb=local_gb
        # )
        # ironic.wait_for_hypervisors(ironic_nodes=[ironic_node],
        #                             timeout=900)

        logger.debug('Create ironic port')
        # ironic.create_port(
        #     address=os.environ['IRONIC_BM_MAC'],
        #     node_uuid=ironic_node.uuid
        # )
        # ironic.create_port(address=hw[0]['mac'], node_uuid="0d3776fd-c2b5-489e-880d-4e91a76ac490")#ironic_node.uuid)

        key = os_conn.create_key('ironic_key' + str(random.randint(1, 0x7fff)))
        bm_flavor = os_conn.create_flavor(
            "real-baremetal-" + str(random.randint(1, 0x7fff)),
            memory_mb, cpus, local_gb
        )

        logger.debug('Boot ironic baremetal instance')
        srv = ironic.boot_ironic_instance(
            image_id=img.id,
            flavor_id=bm_flavor.id,
            timeout=600,
            key_name=key.name,
            userdata='#!/bin/bash\ntouch /home/ubuntu/success.txt'
        )
        floating_ip = os_conn.assign_floating_ip(srv)
        self.check_userdata_executed(cluster_id, floating_ip.ip, key)

    #     # self.env.make_snapshot("boot_ironic_node_with_fuel_ipmi_agent")

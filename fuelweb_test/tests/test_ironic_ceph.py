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

import os

from proboscis import test

from fuelweb_test import logger
from fuelweb_test import settings as conf
from fuelweb_test.helpers import ironic_actions
from fuelweb_test.helpers import os_actions
from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.settings import DEPLOYMENT_MODE
from fuelweb_test.settings import NEUTRON_SEGMENT
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.test_ironic_base import TestIronicBase



@test(groups=["ironic_ceph"])
class TestIronicCeph(TestIronicBase):
    """TestIronicCeph"""  # TODO documentation

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["ironic_ceph"])
    @log_snapshot_after_test
    def deploy_ironic_ceph(self):
        """Deploy cluster in HA mode with Ironic and Ceph:

           Scenario:
               1. Create cluster
               2. Add 1 controller+Ceph OSD node
               3. Add 1 compute+Ceph OSD node
               4. Add 1 ironic node

           Snapshot: deploy_ironic_ceph
        """

        self.check_run("deploy_ironic_ceph")

        self.env.revert_snapshot("ready_with_3_slaves")

        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                'net_provider': 'neutron',
                'net_segment_type': NEUTRON_SEGMENT['vlan'],
                'ironic': True,
                'volumes_ceph': True,
                'images_ceph': True,
                'volumes_lvm': False,
                'ephemeral_ceph': True,
                'objects_ceph': True,
                'osd_pool_size': 2
            }
        )

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller', 'ceph-osd'],
                'slave-02': ['compute', 'ceph-osd'],
                'slave-03': ['ironic'],
            }
        )

        self.fuel_web.deploy_cluster_wait(cluster_id)
        self.fuel_web.verify_network(cluster_id)
        self.fuel_web.run_ostf(
            cluster_id=cluster_id)

        self.env.make_snapshot("deploy_ironic_ceph")

    @test(depends_on=[deploy_ironic_ceph],
          groups=["ironic_ceph"])
    def boot_ironic_node_with_fuel_ssh_agent(self):
        """Boot ironic node with fuel ssh agent

        Scenario:
            1. Create baremetal flavor
            2. Import Ubuntu image
            3. Create ironic node
            4. Create ironic port for this node
            5. Verify that ironic instance can be booted successfully
            6. Ensure userdata have been executed during instance boot

        Duration 35m
        Snapshot boot_ironic_node_with_fuel_ssh_agent
        """ # TODO docstring
        self.env.revert_snapshot("deploy_ironic_ceph")

        cluster_id = self.fuel_web.get_last_created_cluster()

        controller_ip = self.fuel_web.get_public_vip(cluster_id)
        os_conn = os_actions.OpenStackActions(controller_ip)
        ironic = ironic_actions.IronicActions(controller_ip)

        # # Get ironic nodes characteristics
        # self.ironics = [
        #     {
        #         'cpus': node.vcpu,
        #         'memory_mb': node.memory,
        #         'local_gb': conf.NODE_VOLUME_SIZE,
        #         'mac': node.interface_by_network_name('ironic')[0].mac_address
        #     }
        #     for node in self.env.d_env.nodes().ironics
        # ]
        ironic.create_ironic_virtual_nodes_wait(self.ironics)

        key, img, flavor = ironic.prepare_ironic_resources(
            self.ironics[0]['cpus'],
            self.ironics[0]['memory_mb'],
            self.ironics[0]['local_gb'],
            is_hw=False)

        # cpus = self.env.d_env.nodes().ironics[0].vcpu
        # memory_mb = self.env.d_env.nodes().ironics[0].memory
        # local_gb = conf.NODE_VOLUME_SIZE
        # mac = self.env.d_env.nodes().ironics[0].interface_by_network_name(
        #     'ironic')[0].mac_address
        #
        # logger.debug('Create ironic node')
        # ironic_node = ironic.create_virtual_node(
        #     server_ip=os.environ['HW_SERVER_IP'],
        #     ssh_username=os.environ['HW_SSH_USER'],
        #     ssh_password=os.environ['HW_SSH_PASS'],
        #     cpus=cpus,
        #     memory_mb=memory_mb,
        #     local_gb=local_gb
        # )
        # logger.debug('Create ironic port')
        # ironic.create_port(address=mac, node_uuid=ironic_node.uuid)
        # ironic.wait_for_hypervisors(ironic_nodes=[ironic_node],
        #                             timeout=900)

        # key, img, flavor = ironic.prepare_ironic_resources(
        #     cpus, memory_mb, local_gb, is_hw=False)

        logger.debug('Boot ironic VM')
        srv = ironic.boot_ironic_instance(
            image_id=img.id,
            flavor_id=flavor.id,
            timeout=600,
            key_name=key.name,
            userdata='#!/bin/bash\ntouch /home/ubuntu/success.txt'
        )
        floating_ip = os_conn.assign_floating_ip(srv)
        self.check_userdata_executed(cluster_id, floating_ip.ip, key)

        self.env.make_snapshot("boot_ironic_node_with_fuel_ssh_agent")

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

from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.settings import DEPLOYMENT_MODE
from fuelweb_test.settings import NEUTRON_SEGMENT
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic

from proboscis import test


# @test(groups=["ironic"])
@test(groups=["ironic_ceph"])
class TestIronicCeph(TestBasic):
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
        controllers = self.fuel_web.get_nailgun_cluster_nodes_by_roles(
            cluster_id, ['controller'])
        remote = self.fuel_web.get_ssh_for_nailgun_node(controllers[0])

        self.check_userdata_executed(remote, floating_ip.ip, key)

        self.env.make_snapshot("boot_ironic_node_with_fuel_ssh_agent")

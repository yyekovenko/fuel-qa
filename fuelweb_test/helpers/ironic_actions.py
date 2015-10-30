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

from proboscis import asserts
import time
import random

from devops.error import TimeoutError
from devops.helpers import helpers
from fuelweb_test import logger
from fuelweb_test.helpers import common
from fuelweb_test.helpers import os_actions
from fuelweb_test.settings import DEFAULT_IMAGES_UBUNTU
# from ironicclient import client as ironicclient


class IronicActions(common.Common):
    """
    IronicActions class provides a set of methods to
    prepare OpenStack resources for Ironic workflows execution
    and wrap Ironic client methods.
    """

    def __init__(self, controller_ip, user='admin',
                 passwd='admin', tenant='admin'):

        super(IronicActions, self).__init__(controller_ip, user,
                                            passwd, tenant)
        # token = self.keystone.auth_token
        # logger.debug('Token is {0}'.format(token))
        # ironic_endpoint = self.keystone.service_catalog.url_for(
        #     service_type='baremetal', endpoint_type='publicURL')
        # logger.debug('Ironic endpoint is {0}'.format(ironic_endpoint))
        # from fuelweb_test.settings import PATH_TO_CERT
        # logger.info("PATH_TO_CERT=%s" % PATH_TO_CERT)
        # self.ironic = ironicclient.get_client(api_version=1,
        #                                       os_auth_token=token,
        #                                       ironic_url=ironic_endpoint,
        #                                       ca_file=PATH_TO_CERT)

        self.os_conn = os_actions.OpenStackActions(controller_ip)

    def import_ironic_image(self, image_name='virtual_trusty', disk='vda'):
        image_properties = {
            'mos_disk_info': '[{{"name": "{disk}", "extra": [], '
                             '"free_space": 11000, "type": "disk", '
                             '"id": "{disk}", "size": 11000, '
                             '"volumes": [{{"mount": "/", '
                             '"type": "partition", '
                             '"file_system": "ext4", '
                             '"size": 10000}}]}}]'.format(disk=disk),
            'hypervisor_type': 'baremetal',
            'cpu_arch': 'x86_64'
        }
        logger.debug('Import Ubuntu image for Ironic')
        with open(DEFAULT_IMAGES_UBUNTU) as data:
            img = self.os_conn.create_image(
                name=image_name + str(random.randint(1, 0x7fff)),
                properties=image_properties,
                data=data,
                is_public=True,
                disk_format='raw',
                container_format='bare')
        return img

    def _create_ironic_node(self, driver, server_ip, username, password,
                            cpus, memory_mb, local_gb):

        driver_info = {
            'deploy_kernel': self.os_conn.get_image(
                'ironic-deploy-linux').id,
            'deploy_ramdisk': self.os_conn.get_image(
                'ironic-deploy-initramfs').id,
            'deploy_squashfs': self.os_conn.get_image(
                'ironic-deploy-squashfs').id
        }
        if 'ipmi' in driver:
            driver_info['ipmi_address'] = server_ip
            driver_info['ipmi_username'] = username
            driver_info['ipmi_password'] = password
        elif 'ssh' in driver:
            driver_info['ssh_address'] = server_ip
            driver_info['ssh_username'] = username
            driver_info['ssh_password'] = password
            driver_info['ssh_virt_type'] = 'virsh'

        properties = {
            'cpus': cpus,
            'memory_mb': memory_mb,
            'local_gb': local_gb,
            'cpu_arch': 'x86_64'
        }

        return self.ironic.node.create(driver=driver,
                                       driver_info=driver_info,
                                       properties=properties)

    def wait_for_hypervisors(self, ironic_nodes, timeout=1800):
        # TODO For now (iso-216) hypervisors are not updated in time.
        # hostnames = [node.uuid for node in ironic_nodes]
        #
        # def check_hypervisors():
        #     return len([hyper for hyper in self.os_conn.get_hypervisors()
        #                 if hyper.hypervisor_hostname in hostnames
        #                 and hyper.memory_mb == 0]) == 0
        #
        # try:
        #     helpers.wait(check_hypervisors, timeout=timeout)
        # except TimeoutError:
        #     logger.debug("Ironic hypervisors failed to update wihtin timeout.")
        #     asserts.assert_true(check_hypervisors,
        #                         "Ironic hypervisors did not get "
        #                         "correct HW data.")
        time.sleep(timeout)

    def create_virtual_node(self, server_ip, ssh_username, ssh_password,
                            cpus, memory_mb, local_gb):

        return self._create_ironic_node('fuel_ssh', server_ip, ssh_username,
                                        ssh_password, cpus, memory_mb,
                                        local_gb)

    def create_baremetal_node(self, server_ip, ipmi_username, ipmi_password,
                              cpus, memory_mb, local_gb):

        return self._create_ironic_node('fuel_ipmitool', server_ip,
                                        ipmi_username, ipmi_password, cpus,
                                        memory_mb, local_gb)

    def create_port(self, address, node_uuid):
        return self.ironic.port.create(**{'address': address,
                                          'node_uuid': node_uuid})

    def delete_node(self, node_uuid):
        return self.ironic.node.delete(node_uuid)

    def boot_ironic_instance(self, image_id, flavor_id, net_name='baremetal',
                             neutron=True, key_name=None, timeout=100,
                             **kwargs):
        name = "ironic-vm-" + str(random.randint(1, 0x7fff))
        if neutron:
            kwargs.update(
                {
                    'nics': [
                        {'net-id': self.os_conn.get_network(net_name)['id']}
                    ],
                    'security_groups': [
                        self.os_conn.create_sec_group_for_ssh().name
                    ]
                }
            )
        srv = self.nova.servers.create(name=name, image=image_id,
                                       flavor=flavor_id,
                                       key_name=key_name, **kwargs)
        try:
            helpers.wait(
                lambda: self.get_instance_detail(srv).status == "ACTIVE",
                timeout=timeout)
            return self.get_instance_detail(srv.id)
        except TimeoutError:
            logger.debug("Create server for migration failed by timeout")
            asserts.assert_equal(
                self.get_instance_detail(srv).status,
                "ACTIVE",
                "Instance hasn't reached active state, current state"
                " is {0}".format(self.get_instance_detail(srv).status))

    def check_userdata_executed(self, cluster_id, instance_ip,
                                instance_keypair):
        controllers = self.fuel_web.get_nailgun_cluster_nodes_by_roles(
            cluster_id, ['controller'])
        remote = self.fuel_web.get_ssh_for_nailgun_node(controllers[0])

        # save private key to the controller node
        instance_key_path = '/root/.ssh/instancekey_rsa'
        run_on_remote(remote,
                      'echo "{0}" > {1} && chmod 400 {1}'.format(
                          instance_keypair.private_key, instance_key_path))

        cmd = "ssh -o 'StrictHostKeyChecking no' -i {0} ubuntu@{1} " \
              "\"if [ -f /home/ubuntu/success.txt ] ; " \
              "then echo -n yes ; " \
              "else echo -n no ; fi\"".format(instance_key_path,
                                              instance_ip)

        wait(lambda: remote.execute(cmd)['exit_code'] == 0,
             timeout=2 * 60)
        res = remote.execute(cmd)
        assert_equal(0, res['exit_code'],
                     'Instance has no connectivity, exit code {0},'
                     'stdout {1}, stderr {2}'.format(res['exit_code'],
                                                     res['stdout'],
                                                     res['stderr']))
        assert_true('yes' in res['stdout'], 'Userdata was not executed.')

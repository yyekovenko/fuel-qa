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

from devops.helpers.helpers import wait
from fuelweb_test import logwrap
from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.helpers.utils import run_on_remote
from fuelweb_test.settings import DEPLOYMENT_MODE
from fuelweb_test.settings import NEUTRON_SEGMENT
from fuelweb_test.tests.base_test_case import TestBasic
from fuelweb_test.tests.base_test_case import SetupEnvironment
from proboscis import test
from proboscis.asserts import assert_equal, assert_true


@test(groups=["ironic"])
class TestIronicBase(TestBasic):
    """TestIronicBase"""  # TODO documentation

    @logwrap
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

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["ironic_base"])
    @log_snapshot_after_test
    def ironic_base(
            self):
        """Deploy cluster in HA mode with Ironic:

           Scenario:
               1. Create cluster
               2. Add 1 controller node
               3. Add 1 compute node
               4. Add 1 ironic node

           Snapshot: test_ironic_base
        """

        self.check_run("ironic_base")

        self.env.revert_snapshot("ready_with_3_slaves")

        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": NEUTRON_SEGMENT['vlan'],
                "ironic": True,
            }
        )

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller'],
                'slave-02': ['compute'],
                'slave-03': ['ironic'],
            }
        )

        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.fuel_web.verify_network(cluster_id)
        self.fuel_web.run_ostf(
            cluster_id=cluster_id)

        self.env.make_snapshot("ironic_base")

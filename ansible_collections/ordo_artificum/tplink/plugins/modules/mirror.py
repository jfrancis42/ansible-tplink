#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: mirror
short_description: Manage port mirroring on a TP-Link managed switch
description:
  - Enable or disable port mirroring on a TP-Link managed switch.
options:
  host:
    description: Switch management IP or hostname.
    required: true
    type: str
  username:
    description: Login username.
    type: str
    default: admin
  password:
    description: Login password.
    required: true
    type: str
  timeout:
    description: HTTP request timeout in seconds.
    type: float
    default: 10.0
  model:
    description: >
      Override model autodetection. Accepts a hardware model prefix
      (e.g. C(TL-SG108E), C(TL-SG1016DE)) or a class name (C(Switch),
      C(SwitchDE)). Only needed if autodetection fails.
    type: str
    required: false
  dest_port:
    description: >
      Port that receives the mirrored traffic (1-based).
      Required when C(state=present).
    type: int
  ingress_ports:
    description: Ports whose ingress (incoming) traffic is mirrored.
    type: list
    elements: int
    default: []
  egress_ports:
    description: Ports whose egress (outgoing) traffic is mirrored.
    type: list
    elements: int
    default: []
  state:
    description: >
      C(present) enables mirroring with the specified configuration.
      C(absent) disables mirroring.
    type: str
    choices: [present, absent]
    default: present
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - At least one of C(ingress_ports) or C(egress_ports) should be non-empty
    when C(state=present).
'''

EXAMPLES = r'''
- name: Mirror ingress+egress from port 1 to port 8
  ordo_artificum.tplink.mirror:
    host: 192.168.0.1
    password: admin
    dest_port: 8
    ingress_ports: [1]
    egress_ports: [1]
    state: present
  connection: local

- name: Disable port mirroring
  ordo_artificum.tplink.mirror:
    host: 192.168.0.1
    password: admin
    state: absent
  connection: local
'''

RETURN = r'''
mirror:
  description: Current mirroring configuration after any changes.
  returned: always
  type: dict
changed:
  description: Whether the mirroring configuration was changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR, serialize_mirror,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        dest_port=dict(type='int'),
        ingress_ports=dict(type='list', elements='int', default=[]),
        egress_ports=dict(type='list', elements='int', default=[]),
        state=dict(type='str', default='present', choices=['present', 'absent']),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[['state', 'present', ['dest_port']]],
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    changed = False

    try:
        with make_switch(p) as sw:
            current = sw.get_port_mirror()

            if p['state'] == 'present':
                desired_ingress = sorted(p['ingress_ports'] or [])
                desired_egress = sorted(p['egress_ports'] or [])
                needs_change = (
                    not current.enabled or
                    current.dest_port != p['dest_port'] or
                    sorted(current.ingress_ports) != desired_ingress or
                    sorted(current.egress_ports) != desired_egress
                )
                if needs_change:
                    changed = True
                    if not module.check_mode:
                        sw.set_port_mirror(
                            enabled=True,
                            dest_port=p['dest_port'],
                            ingress_ports=p['ingress_ports'],
                            egress_ports=p['egress_ports'],
                        )

            else:  # absent
                if current.enabled:
                    changed = True
                    if not module.check_mode:
                        sw.set_port_mirror(enabled=False, dest_port=1,
                                           ingress_ports=[], egress_ports=[])

            if changed and not module.check_mode:
                current = sw.get_port_mirror()

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=changed, mirror=serialize_mirror(current))


def main():
    run_module()


if __name__ == '__main__':
    main()

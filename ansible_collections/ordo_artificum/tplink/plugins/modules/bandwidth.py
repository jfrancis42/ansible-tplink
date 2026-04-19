#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: bandwidth
short_description: Manage bandwidth control on a TP-Link managed switch
description:
  - Set ingress and/or egress bandwidth limits on one or more ports of
    a TP-Link managed switch.
  - All listed ports receive the same limits in a single request.
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
  port:
    description: Port number(s) to configure (1-based).
    required: true
    type: list
    elements: int
  ingress_kbps:
    description: >
      Ingress (incoming) rate limit in kbps.  0 removes the limit.
      Valid non-zero values: 512, 1024, 2048, 4096, 8192, 16384, 32768,
      65536, 131072, 262144, 524288, 1000000.
    type: int
    default: 0
  egress_kbps:
    description: >
      Egress (outgoing) rate limit in kbps.  0 removes the limit.
      Valid non-zero values: same as C(ingress_kbps).
    type: int
    default: 0
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - Some firmware versions drop the TCP connection after applying bandwidth
    changes; the SDK handles reconnection transparently.
'''

EXAMPLES = r'''
- name: Limit port 3 ingress to 1 Mbps, egress to 512 kbps
  ordo_artificum.tplink.bandwidth:
    host: 192.168.0.1
    password: admin
    port: [3]
    ingress_kbps: 1024
    egress_kbps: 512
  connection: local

- name: Remove bandwidth limits from ports 1 and 2
  ordo_artificum.tplink.bandwidth:
    host: 192.168.0.1
    password: admin
    port: [1, 2]
    ingress_kbps: 0
    egress_kbps: 0
  connection: local
'''

RETURN = r'''
bandwidth:
  description: Current bandwidth settings for the configured ports.
  returned: always
  type: list
changed:
  description: Whether any bandwidth settings were changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR, serialize_bandwidth,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        port=dict(type='list', elements='int', required=True),
        ingress_kbps=dict(type='int', default=0),
        egress_kbps=dict(type='int', default=0),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    target_ports = p['port']
    desired_ingress = p['ingress_kbps']
    desired_egress = p['egress_kbps']
    changed = False

    try:
        with make_switch(p) as sw:
            all_bw = sw.get_bandwidth_control()
            bw_map = {b.port: b for b in all_bw}

            needs_change = any(
                bw_map[n].ingress_rate != desired_ingress or
                bw_map[n].egress_rate != desired_egress
                for n in target_ports if n in bw_map
            )

            if needs_change:
                changed = True
                if not module.check_mode:
                    sw.set_bandwidth_control(target_ports, desired_ingress, desired_egress)
                    sw.save_config()
                    all_bw = sw.get_bandwidth_control()
                    bw_map = {b.port: b for b in all_bw}

            result = [serialize_bandwidth(bw_map[n]) for n in target_ports if n in bw_map]

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=changed, bandwidth=result)


def main():
    run_module()


if __name__ == '__main__':
    main()

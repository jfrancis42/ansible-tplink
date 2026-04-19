#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: igmp
short_description: Manage IGMP snooping and loop prevention on a TP-Link managed switch
description:
  - Enable or disable IGMP snooping, report suppression, and loop prevention
    on a TP-Link managed switch.
  - Any parameter left unset is left unchanged on the switch.
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
  igmp_enabled:
    description: Enable IGMP snooping.
    type: bool
  report_suppression:
    description: >
      Enable IGMP report suppression.  Only meaningful when
      C(igmp_enabled=true).
    type: bool
  loop_prevention:
    description: Enable loop prevention.
    type: bool
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - At least one of C(igmp_enabled), C(report_suppression), or
    C(loop_prevention) must be specified.
'''

EXAMPLES = r'''
- name: Enable IGMP snooping with report suppression
  jfrancis42.tplink.igmp:
    host: 192.168.0.1
    password: admin
    igmp_enabled: true
    report_suppression: true
  connection: local

- name: Enable loop prevention only
  jfrancis42.tplink.igmp:
    host: 192.168.0.1
    password: admin
    loop_prevention: true
  connection: local
'''

RETURN = r'''
igmp_snooping:
  description: Current IGMP snooping configuration.
  returned: always
  type: dict
loop_prevention:
  description: Current loop prevention state.
  returned: always
  type: bool
changed:
  description: Whether any settings were changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.jfrancis42.tplink.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR, serialize_igmp,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        igmp_enabled=dict(type='bool'),
        report_suppression=dict(type='bool'),
        loop_prevention=dict(type='bool'),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[['igmp_enabled', 'report_suppression', 'loop_prevention']],
    )

    if not HAS_SDK:
        module.fail_json(msg='tplink_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    changed = False

    try:
        with make_switch(p) as sw:
            current_igmp = sw.get_igmp_snooping()
            current_lp = sw.get_loop_prevention()

            # Determine desired IGMP state (merge with current if not specified)
            desired_igmp = p['igmp_enabled'] if p['igmp_enabled'] is not None else current_igmp.enabled
            desired_supp = p['report_suppression'] if p['report_suppression'] is not None else current_igmp.report_suppression

            igmp_needs_change = (
                desired_igmp != current_igmp.enabled or
                desired_supp != current_igmp.report_suppression
            )
            if igmp_needs_change:
                changed = True
                if not module.check_mode:
                    sw.set_igmp_snooping(desired_igmp, desired_supp)

            if p['loop_prevention'] is not None and p['loop_prevention'] != current_lp:
                changed = True
                if not module.check_mode:
                    sw.set_loop_prevention(p['loop_prevention'])

            if changed and not module.check_mode:
                sw.save_config()
                current_igmp = sw.get_igmp_snooping()
                current_lp = sw.get_loop_prevention()

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(
        changed=changed,
        igmp_snooping=serialize_igmp(current_igmp),
        loop_prevention=current_lp,
    )


def main():
    run_module()


if __name__ == '__main__':
    main()

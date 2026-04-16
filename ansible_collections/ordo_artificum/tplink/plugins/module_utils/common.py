from __future__ import absolute_import, division, print_function
__metaclass__ = type

# ---------------------------------------------------------------------------
# SDK import — sets HAS_SDK / SDK_ERROR used by every module
# ---------------------------------------------------------------------------

try:
    from ansible_collections.ordo_artificum.tplink.plugins.module_utils.tplink_switch import (
        Switch, PortSpeed, QoSMode, StormType, STORM_RATE_KBPS,
        _bits_to_ports, _ports_to_bits,
    )
    HAS_SDK = True
    SDK_ERROR = None
except ImportError as e:
    HAS_SDK = False
    SDK_ERROR = str(e)
    Switch = None
    PortSpeed = None
    QoSMode = None
    StormType = None
    STORM_RATE_KBPS = {}
    _bits_to_ports = None
    _ports_to_bits = None


# ---------------------------------------------------------------------------
# Common argument spec — included by every module
# ---------------------------------------------------------------------------

CONNECTION_ARGS = dict(
    host=dict(type='str', required=True),
    username=dict(type='str', default='admin'),
    password=dict(type='str', required=True, no_log=True),
    timeout=dict(type='float', default=10.0),
)


def make_switch(params):
    """Instantiate a Switch from module parameters."""
    return Switch(
        host=params['host'],
        username=params['username'],
        password=params['password'],
        timeout=params['timeout'],
    )


# ---------------------------------------------------------------------------
# Serialisation helpers — convert SDK dataclass instances to plain dicts
# ---------------------------------------------------------------------------

def _speed_str(speed):
    """Return str(PortSpeed) or None."""
    return str(speed) if speed is not None else None


def serialize_system_info(info):
    return dict(
        description=info.description,
        mac=info.mac,
        ip=info.ip,
        netmask=info.netmask,
        gateway=info.gateway,
        firmware=info.firmware,
        hardware=info.hardware,
    )


def serialize_ip_settings(ip):
    return dict(
        dhcp=ip.dhcp,
        ip=ip.ip,
        netmask=ip.netmask,
        gateway=ip.gateway,
    )


def serialize_port_info(p):
    return dict(
        port=p.port,
        enabled=p.enabled,
        speed_cfg=_speed_str(p.speed_cfg),
        speed_act=_speed_str(p.speed_act),
        flow_control_cfg=p.fc_cfg,
        flow_control_act=p.fc_act,
        trunk_id=p.trunk_id,
    )


def serialize_port_stats(s):
    return dict(port=s.port, tx_pkts=s.tx_pkts, rx_pkts=s.rx_pkts)


def serialize_mirror(m):
    return dict(
        enabled=m.enabled,
        dest_port=m.dest_port,
        mode=m.mode,
        ingress_ports=sorted(m.ingress_ports),
        egress_ports=sorted(m.egress_ports),
    )


def serialize_trunk(tc):
    return dict(
        max_groups=tc.max_groups,
        port_count=tc.port_count,
        groups={str(k): sorted(v) for k, v in tc.groups.items()},
    )


def serialize_igmp(igmp):
    return dict(
        enabled=igmp.enabled,
        report_suppression=igmp.report_suppression,
        group_count=igmp.group_count,
    )


def serialize_mtu_vlan(mv):
    return dict(
        enabled=mv.enabled,
        port_count=mv.port_count,
        uplink_port=mv.uplink_port,
    )


def serialize_port_vlan_entry(v):
    return dict(
        vid=v.vid,
        members=v.members,
        member_ports=_bits_to_ports(v.members),
    )


def serialize_dot1q_vlan_entry(v):
    return dict(
        vid=v.vid,
        name=v.name,
        tagged_members=v.tagged_members,
        untagged_members=v.untagged_members,
        tagged_ports=_bits_to_ports(v.tagged_members),
        untagged_ports=_bits_to_ports(v.untagged_members),
    )


def serialize_qos_port(q):
    return dict(port=q.port, priority=q.priority)


def serialize_bandwidth(b):
    return dict(port=b.port, ingress_kbps=b.ingress_rate, egress_kbps=b.egress_rate)


def serialize_storm(s):
    return dict(
        port=s.port,
        enabled=s.enabled,
        rate_index=s.rate_index,
        rate_kbps=STORM_RATE_KBPS.get(s.rate_index) if s.enabled and s.rate_index else None,
        storm_types=s.storm_types,
    )


def serialize_cable_diag(r):
    return dict(port=r.port, status=r.status, length_m=r.length_m)

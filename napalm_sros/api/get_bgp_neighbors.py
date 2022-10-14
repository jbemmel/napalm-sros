#!/usr/bin/env python

# -*- coding: utf-8 -*-
# © 2022 Nokia
# Licensed under the Apache License 2.0 License
# SPDX-License-Identifier: Apache-2.0

#
# The contents of this file are licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import logging, datetime

from ncclient.xml_ import to_xml, to_ele
from napalm.base.helpers import convert

from .util import _find_txt, NSMAP
from .bgp_neighbor import BGPNeighbor

#
# Netconf filters to retrieve only required attributes
#
NEIGHBOR_CONF = """
<autonomous-system/>
<bgp>
    <group>
    <local-as>
     <as-number/>
    </local-as>
    <dynamic-neighbor/>
    </group>
    <neighbor>
        <ip-address/>
        <group/>
        <admin-state/>
        <description/>
        <peer-as/>
        <local-as>
         <as-number/>
        </local-as>
    </neighbor>
</bgp>
"""

NEIGHBOR_STATS = """
<oper-router-id/>
<bgp>
    <neighbor>
        <ip-address/>
        <statistics>
            <peer-identifier/>
            <peer-as/>
            <session-state/>
            <last-established-time/>
            <dynamically-configured/>
            <family-prefix>
                <ipv4>
                    <received/>
                    <active/>
                    <sent/>
                </ipv4>
                <ipv6>
                    <received/>
                    <active/>
                    <sent/>
                </ipv6>
            </family-prefix>
        </statistics>
    </neighbor>
</bgp>
"""

GET_BGP_NEIGHBORS = """
    <filter>
        <configure xmlns="urn:nokia.com:sros:ns:yang:sr:conf">
            <router>
            """+NEIGHBOR_CONF+"""
            </router>
            <service>
                <vprn>
            """+NEIGHBOR_CONF+"""
                </vprn>
            </service>
        </configure>
        <state xmlns="urn:nokia.com:sros:ns:yang:sr:state">
            <system>
                <current-time/>
            </system>
            <router>
                """+NEIGHBOR_STATS+"""
            </router>
            <service>
                <vprn>
                <service-name/>
                """+NEIGHBOR_STATS+"""
                </vprn>
            </service>
        </state>
    </filter>
"""

log = logging.getLogger(__file__)

def get_bgp_neighbors(conn):
  data = to_ele(
      conn.get(
          filter=GET_BGP_NEIGHBORS,
          with_defaults="report-all",
      ).data_xml
  )
  if log.isEnabledFor(logging.DEBUG):
    log.debug(to_xml(data, pretty_print=True))
  print( to_xml(data, pretty_print=True) )

  current_time_str = _find_txt(data,'//state_ns:system/state_ns:current-time')

  # List all VRFs and the operational local router ID
  result = {
    'global': {
      'router_id': _find_txt(data,"//state_ns:router/state_ns:oper-router-id"),
      'peers': {}
    }
  }
  for vprn in data.xpath("//state_ns:service/state_ns:vprn",namespaces=NSMAP):
    name = _find_txt(vprn, "state_ns:service-name")
    router_id = _find_txt(vprn, "state_ns:oper-router-id")
    result[ name ] = { 'router_id': router_id, 'peers': {} }

  # Iterate over neighbors found in state - this may include dynamic neighbors
  for nb in BGPNeighbor.list(data):

    def to_timestamp(time:str):
      if time:
        # Remove 'Z' timezone
        return datetime.datetime.strptime(time[:-1], "%Y-%m-%dT%H:%M:%S.%f").timestamp()
      return 0

    count = nb.counters(attrs=['received','active','sent'])

    last_established_time = to_timestamp(nb.state_str('last-established-time'))
    uptime = to_timestamp(current_time_str) - last_established_time
    is_dynamic = nb.state_str('dynamically-configured')=="true"
    peer = {
      'local_as': nb.local_as(),
      'remote_as': nb.state_int('peer-as') if is_dynamic else nb.conf_int('peer-as'),
      'remote_id': nb.state_str('peer-identifier'),
      'is_up': nb.state_str('session-state').lower()=="established",
      'is_enabled': nb.conf_str('admin-state') == "enable" or is_dynamic,
      'description': "Dynamic neighbor" if is_dynamic else nb.conf_str('description'),
      'uptime': convert(int,uptime), # Current or time since down if is_up=False
      'address_family': {
        'ipv4': {
         'received_prefixes': count['received']['ipv4'],
         'accepted_prefixes': count['active']['ipv4'],
         'sent_prefixes': count['sent']['ipv4'],
        },
        'ipv6': {
         'received_prefixes': count['received']['ipv6'],
         'accepted_prefixes': count['active']['ipv6'],
         'sent_prefixes': count['sent']['ipv6'],
        }
      }
    }
    result[nb.vrf]['peers'][nb.ip_address] = peer

  return result

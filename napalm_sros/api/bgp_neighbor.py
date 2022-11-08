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

import netaddr
from napalm.base.helpers import convert
from ncclient.xml_ import to_xml, to_ele
from .util import NSMAP, _find_txt

class BGPNeighbor:
  """
  Utility class to process Netconf XML stanzas containing bgp neighbor parameters
  """

  @classmethod
  def list(cls,data):
    """
    Lists all bgp neighbors found under <state>, and yields them for enumeration
    """
    for n in data.xpath("//state_ns:neighbor",namespaces=NSMAP):
      name = _find_txt(n, "../../state_ns:service-name") or "global"
      if name=="global":
        base_path = "//configure_ns:router/configure_ns:router-name[ text() = 'Base' ]"
      else:
        base_path = f"//configure_ns:vprn/configure_ns:service-name[ text() = '{name}' ]"

      # Note: Could be overridden by local AS, determined below
      node_as = convert(int, _find_txt( n, base_path + "/../configure_ns:autonomous-system" ))
      ip_address = _find_txt( n, "state_ns:ip-address" )
      yield BGPNeighbor(ip_address,node_as,name,n,data,base_path)

  def __init__(self,ip_address,node_as,vrf,state,data,base_path):
    """
    Initializes bgp neighbor state collected so far
    """
    self.state = state
    self.ip_address = ip_address
    self.node_as = node_as
    self.vrf = vrf
    self.bgp = data.xpath(base_path+"/../configure_ns:bgp", namespaces=NSMAP) # for global atts like import/export policies
    self.conf = data.xpath( f"//configure_ns:ip-address[ text()='{ip_address}']/..", namespaces=NSMAP)

    # print( f"Read BGP neighbor { to_xml(self.conf[0] if self.conf else data) }" )
    # print( f"Read BGP neighbor {ip_address} { to_xml(data) }" )

    # Lookup corresponding group config
    if self.conf:
      group = _find_txt(self.conf[0],"configure_ns:group")
      self.group_conf = self.conf[0].xpath(f"../configure_ns:group/configure_ns:group-name[text()='{group}']/..", namespaces=NSMAP)
    else:  # Dynamic neighbor, lookup group by ip-prefix matching
      # lookup under correct scope, i.e. Base or VPRN
      for p in data.xpath(base_path+"/..//configure_ns:ip-prefix",namespaces=NSMAP):
        if ip_address in netaddr.IPNetwork(p.text):
          self.group_conf = p.xpath('../../../../../configure_ns:group', namespaces=NSMAP)
          break

  def state_int(self,attr: str,default=0):
    return convert( int, _find_txt(self.state,f"state_ns:statistics/state_ns:{attr}")) or default

  def state_str(self,attr: str):
    return _find_txt(self.state,f"state_ns:statistics/state_ns:{attr}")

  def conf_str(self,attr: str, allow_from_group:bool = True, include_global:bool = True ):
    """
    Retrieves an XML string from the configuration section, using XPath
    Follows neighbor -> group -> global hierarchy
    """
    sources = [ self.conf[0] ] if self.conf else []
    if self.group_conf and allow_from_group:
      sources.append( self.group_conf[0] )
    if include_global:
      sources.append( self.bgp[0] ) # for global

    for src in sources:
      _s = _find_txt(src,f"configure_ns:{attr}")
      if _s:
        return _s
    return ""

  def conf_int(self,attr: str,default=0,include_global=True):
    return convert( int, self.conf_str(attr,include_global=include_global) or default )

  def conf_bool(self,attr:str):
    return self.conf_str(attr).lower() == "true"

  def router_id(self) -> str:
    return _find_txt( self.state, "../../state_ns:oper-router-id" )

  def counters(self,attrs=['received','active','sent'],total=False):
    count = {}
    for attr in attrs:
      count[attr] = {}
      for af in ('ipv4','ipv6'):
        count[attr][af] = convert(
            int,
            _find_txt(
                self.state,
                f"state_ns:statistics/state_ns:family-prefix/state_ns:{af}/state_ns:{attr}"
            )
        )
      if total:
        count[attr]['total'] = count[attr]['ipv4'] + count[attr]['ipv6']
    return count

  def local_as(self) -> int:
    """
    Returns local AS number as determined by configuration, accounting for override
    at neighbor or group level. Default: global AS
    """
    local_as = 0
    if self.conf:
      local_as = _find_txt(self.conf[0],"configure_ns:local-as/configure_ns:as-number")
    if not local_as and self.group_conf: # dynamic neighbor
      local_as = _find_txt(self.group_conf[0],"configure_ns:local-as/configure_ns:as-number")
    return convert( int, local_as ) or self.node_as

  def remote_as(self) -> int:
    """
    Returns remote AS number as determined by configuration, accounting for override
    at neighbor or group level.

    Note: 'peer-as' in state is only set for dynamic neighbors (handled elsewhere)
    """
    remote_as = 0
    if self.conf:
      remote_as = _find_txt(self.conf[0],"configure_ns:peer-as")
    if not remote_as and self.group_conf: # check group level
      remote_as = _find_txt(self.group_conf[0],"configure_ns:peer-as")

    if not remote_as: # Can be unconfigured for ibgp with type=internal
      return self.local_as()
    return convert( int, remote_as )

  def conf_policies(self,attr:str) -> str:
    """
    Returns import or export policies configured at neighbor,group or global level
    """
    sources = [ self.conf[0] ] if self.conf else []
    if self.group_conf:
      sources.append( self.group_conf[0] )
    sources.append( self.bgp[0] ) # for global import/export policies
    for src in sources:
      policies = [ele.text for ele in src.xpath(f"configure_ns:{attr}",namespaces=NSMAP)]
      if policies:
        return ",".join(policies)
    return ""

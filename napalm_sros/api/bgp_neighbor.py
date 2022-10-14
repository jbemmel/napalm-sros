import netaddr
from napalm.base.helpers import convert
from .util import NSMAP, _find_txt

class BGPNeighbor:

  @classmethod
  def list(cls,data):
    for n in data.xpath("//state_ns:neighbor",namespaces=NSMAP):
      name = _find_txt(n, "../../state_ns:service-name") or "global"
      if name=="global":
        base_path = "//configure_ns:router/configure_ns:router-name[ text() = 'Base' ]"
      else:
        base_path = f"//configure_ns:vprn/configure_ns:service-name[ text() = '{name}' ]"

      # Note: Could be overridden by local AS, determined below
      node_as = convert(int, _find_txt( n, base_path + "/../configure_ns:autonomous-system" ))

      ip_address = _find_txt( n, "state_ns:ip-address" )

      yield BGPNeighbor(ip_address,node_as,name,n,data)

  def __init__(self,ip_address,node_as,vrf,state,data):
    self.state = state
    self.data = data
    self.ip_address = ip_address
    self.node_as = node_as
    self.vrf = vrf
    self.conf = data.xpath( f"//configure_ns:ip-address[ text()='{ip_address}']/..", namespaces=NSMAP)

  def state_int(self,attr: str,default=0):
    return convert( int, _find_txt(self.state,f"state_ns:statistics/state_ns:{attr}")) or default

  def state_str(self,attr: str):
    return _find_txt(self.state,f"state_ns:statistics/state_ns:{attr}")

  def conf_str(self,attr: str):
    return _find_txt(self.conf[0],f"configure_ns:{attr}") if self.conf else ""

  def conf_int(self,attr: str,default=0):
    if self.conf:
      return convert( int, _find_txt(self.conf[0],f"configure_ns:{attr}")) or default
    return default

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
    if self.conf:
      local_as = _find_txt(self.conf[0],"//configure_ns:as-number")
      if not local_as:
        group = self.conf_str("group")
        group_conf = self.conf[0].xpath(f"../configure_ns:group/configure_ns:group-name[text()={g}]/..", namespaces=NSMAP)
        local_as = _find_txt(group_conf[0],"//configure_ns:as-number")
    else: # dynamic neighbor
      for p in self.data.xpath("//configure_ns:ip-prefix",namespaces=NSMAP):
        print( f"Match IP prefix {p.text}" )
        if self.ip_address in netaddr.IPNetwork(p.text):
          group_conf = p.xpath('../../../../../configure_ns:group', namespaces=NSMAP)
          print( f"Found match: { _find_txt(group_conf[0],'configure_ns:group-name') }" )
          local_as = _find_txt(group_conf[0],"//configure_ns:as-number")
          break

    return convert( int, local_as ) or self.node_as

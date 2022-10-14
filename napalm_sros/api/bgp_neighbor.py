import netaddr
from napalm.base.helpers import convert
from .util import NSMAP, _find_txt

class BGPNeighbor:

  def __init__(self,ip_address,data):
    self.data = data
    self.ip_address = ip_address
    self.conf = data.xpath( f"//configure_ns:ip-address[ text()='{ip_address}']/..", namespaces=NSMAP)

  def conf_str(self,attr: str):
    return _find_txt(self.conf[0],f"configure_ns:{attr}") if self.conf else ""

  def conf_int(self,attr: str,default=0):
    if self.conf:
      return convert( int, _find_txt(self.conf[0],f"configure_ns:{attr}")) or default
    return default

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

    return convert( int, local_as )

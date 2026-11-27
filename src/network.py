"""Public HTTPS transport: resolve once per connection, connect only to validated IPs.
The original hostname is retained by urllib3 for TLS SNI and certificate validation.
"""
import ipaddress
import socket
import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError


def public_ip(value):
    ip = ipaddress.ip_address(value)
    return ip.is_global and not ip.is_multicast and not ip.is_reserved and not ip.is_loopback and not ip.is_link_local and not ip.is_unspecified


def public_addresses(host, port=443):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not public_ip(a[4][0]) for a in addresses):
        raise ValueError('Privatne, lokalne i rezervirane mreže nisu dopuštene.')
    return addresses


class PublicHTTPSConnection(HTTPSConnection):
    def _new_conn(self):
        try:
            addresses = public_addresses(self._dns_host, self.port)
        except (OSError, ValueError) as exc:
            raise NewConnectionError(self, 'DNS resolution rejected') from exc
        for family, kind, proto, _, sockaddr in addresses:
            sock = socket.socket(family, kind, proto)
            try:
                sock.settimeout(self.timeout)
                for opt in self.socket_options or ():
                    sock.setsockopt(*opt)
                if self.source_address:
                    sock.bind(self.source_address)
                sock.connect(sockaddr)
                if not public_ip(sock.getpeername()[0]):
                    raise OSError('Non-public peer')
                return sock
            except OSError:
                sock.close()
        raise NewConnectionError(self, 'Public HTTPS connection failed')


class PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = PublicHTTPSConnection


class PublicAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {'https': PublicHTTPSPool}

    def proxy_manager_for(self, *args, **kwargs):
        raise ValueError('Proxy nije dopušten.')


def public_session():
    session = requests.Session()
    session.trust_env = False
    session.adapters.clear()
    session.mount('https://', PublicAdapter())
    return session

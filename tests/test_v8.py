import unittest
from network import public_ip

class PublicAddressTests(unittest.TestCase):
    def test_public_ip_rejects_multicast(self):
        for ip in ('224.0.0.1','ff02::1','127.0.0.1','169.254.1.1','::1','192.168.0.1'):
            self.assertFalse(public_ip(ip),ip)
        self.assertTrue(public_ip('8.8.8.8'))

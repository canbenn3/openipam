import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import datetime

module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if module_path not in sys.path:
    sys.path.insert(0, module_path)

from openipam import dhcp_server  # noqa: E402
from openipam.backend.db import interface  # noqa: E402
from openipam.backend.db import obj # noqa: E402


class TestDataConversions(unittest.TestCase):
    """Test pure functions responsible for data conversions."""

    def test_decode_mac(self):
        mac_bytes = [0x00, 0x1A, 0x2B, 0x3C, 0x4D, 0x5E, 0xFF]  # Includes extra padding
        expected = "00:1a:2b:3c:4d:5e"
        self.assertEqual(dhcp_server.decode_mac(mac_bytes), expected)

    def test_int_to_4_bytes(self):
        num = 258  # hex 0x0102
        expected = b"\x00\x00\x01\x02"
        self.assertEqual(dhcp_server.int_to_4_bytes(num), expected)

    def test_ip_to_list(self):
        ip = "192.168.1.1"
        expected = [192, 168, 1, 1]
        self.assertEqual(dhcp_server.ip_to_list(ip), expected)

    def test_bytes_to_ints_from_bytes(self):
        b_data = b"\x01\x02\x03"
        expected = [1, 2, 3]
        self.assertEqual(dhcp_server.bytes_to_ints(b_data), expected)

    def test_bytes_to_ints_from_string(self):
        s_data = "ABC"
        expected = [65, 66, 67]
        self.assertEqual(dhcp_server.bytes_to_ints(s_data), expected)

    def test_bytes_to_int(self):
        b_list = [0x01, 0x02]  # 258
        self.assertEqual(dhcp_server.bytes_to_int(b_list), 258)


class TestPacketHelpers(unittest.TestCase):
    """Test functions that extract and format data from DHCP packets."""

    def setUp(self):
        self.packet = MagicMock()

    def test_bytes_to_ip_valid(self):
        self.packet.GetOption.return_value = [10, 0, 0, 1]
        result = dhcp_server.bytes_to_ip(self.packet, "request_ip_address")
        self.assertEqual(result, "10.0.0.1")

    def test_bytes_to_ip_missing(self):
        self.packet.GetOption.side_effect = Exception("Option not found")
        result = dhcp_server.bytes_to_ip(self.packet, "request_ip_address")
        self.assertIsNone(result)

    def test_bytes_to_ip_invalid_length(self):
        def mock_get_option(opt):
            if opt == "request_ip_address":
                return [10, 0, 0]  # Invalid length (3 bytes instead of 4)
            if opt == "chaddr":
                return [0x00, 0x11, 0x22, 0x33, 0x44, 0x55]
            return None

        self.packet.GetOption.side_effect = mock_get_option
        result = dhcp_server.bytes_to_ip(self.packet, "request_ip_address")
        self.assertIsNone(result)

    def test_get_packet_type_valid(self):
        self.packet.IsOption.return_value = True
        self.packet.GetOption.return_value = [3]  # DHCP Request
        result = dhcp_server.get_packet_type(self.packet)
        self.assertEqual(result, 3)

    def test_get_packet_type_invalid(self):
        self.packet.IsOption.return_value = True
        self.packet.GetOption.return_value = [99]  # Unknown type
        result = dhcp_server.get_packet_type(self.packet)
        self.assertFalse(result)


class TestServerLogic(unittest.TestCase):
    """Test isolated logic within the Server class."""

    def setUp(self):
        self.dbq = MagicMock()
        self.server = dhcp_server.Server(self.dbq)

    def test_init_missing_config(self):
        # Notice the full patch path here to match how it's imported
        with patch("openipam.dhcp_server.dhcp.server_listen", None):
            with self.assertRaises(Exception) as context:
                dhcp_server.Server(self.dbq)
            self.assertIn("Missing configuration option", str(context.exception))

    def test_do_seen_cleanup(self):
        mac = "00:11:22:33:44:55"
        now = datetime.datetime.now()

        old_time = now - datetime.timedelta(minutes=2)
        new_time = now - datetime.timedelta(seconds=10)

        self.server.seen[mac] = [(old_time, 1), (new_time, 1)]
        min_timestamp = now - datetime.timedelta(minutes=1)

        cleaned_seen = self.server.do_seen_cleanup(mac, min_timestamp)

        self.assertEqual(len(cleaned_seen), 1)
        self.assertEqual(cleaned_seen[0][0], new_time)


def test_queue_packet_rate_limiting(self):
    packet = MagicMock()
    mac = "aa:bb:cc:dd:ee:ff"

    # Provide dummy data for all options the logger will try to parse
    def mock_get_option(opt):
        options = {
            "chaddr": [0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF],
            "secs": [0x00, 0x10],  # 16 seconds
            "dhcp_message_type": [1],  # Discover
            "xid": [0x01, 0x02, 0x03, 0x04],
            "parameter_request_list": [1, 3, 6],
            "giaddr": [0, 0, 0, 0],
            "yiaddr": [0, 0, 0, 0],
            "ciaddr": [0, 0, 0, 0],
            "request_ip_address": [192, 168, 1, 100],
        }
        # Return the option, or an empty list if not found to prevent NoneType errors
        return options.get(opt, [])

    packet.GetOption.side_effect = mock_get_option

    # The logger also checks IsOption, so let's mock that to return True if we defined it
    packet.IsOption.side_effect = lambda opt: opt in ["dhcp_message_type"]

    # The logger also needs sender and interface info
    packet.get_sender.return_value = ("192.168.1.1", 68)
    packet.get_recv_interface.return_value = {"address": "10.0.0.1"}

    now = datetime.datetime.now()
    # Discover type limit is 6. We populate 7 recent requests to trigger the limit.
    self.server.seen[mac] = [(now, 1) for _ in range(7)]

    # Action
    self.server.QueuePacket(packet, pkttype=1)

    # Assertion: put_nowait should NOT be called because rate limit is hit
    self.dbq.put_nowait.assert_not_called()


class mock_q:
    def __init__(self):
        self.q = []

    def put_nowait(self, items):
        self.q.append(items)

    def get(self):
        if len(self.q) > 0:
            return self.q.pop()
        return None


def make_dhcp_packet(msg_type, mac, giaddr, req_list, sender):
    packet = dhcp_server.dhcp_packet.DhcpPacket()
    mock_if = {
        "address": "192.168.56.3",
        "broadcast": "192.168.56.255",
        "interface": "eth0",
        "unicast": True,
    }
    packet.retry_count = 0
    packet.set_recv_interface(mock_if)
    packet.SetOption("dhcp_message_type", [msg_type])  # Discover
    chaddr = []
    for t in mac.split(":"):
        hex = int(t.strip(), 16)
        chaddr.append(hex)
    for _ in range(16 - len(chaddr)):
        chaddr.append(0)
    packet.SetOption("chaddr", chaddr)
    packet.SetOption("giaddr", [int(b) for b in giaddr.split(".")])
    packet.SetOption("parameter_request_list", req_list)
    packet.set_sender(sender)
    return packet


class TestDORA(unittest.TestCase):
    def setUp(self):
        self.db_instance = interface.DBDHCPInterface()
        # Avoid internal transaction warning logic
        self.db_instance.make_dhcp_lease = self.db_instance._make_dhcp_lease
        # Run entirely within transaction
        self.db_instance._begin_transaction()

        # Populate transaction with seed test data (all will be deleted at rollback)
        shared_net_id = self.db_instance._do_insert(
            obj.shared_networks, {"name": "Test-10x"}
        )
        self.db_instance._do_insert(
            obj.networks,
            {
                "network": "10.0.0.0/24",
                "gateway": "10.0.0.1",
                "shared_network": shared_net_id.inserted_primary_key[0],
                "description": "Test Subnet",
            },
        )
        pool_id = self.db_instance._do_insert(
            obj.pools,
            {
                "name": "Test-Pool-10x",
                "description": "Test Pool",
                "lease_time": 144000,
                "allow_unknown": True,
            },
        )
        for i in range(10, 20):
            self.db_instance._do_insert(
                obj.addresses,
                {
                    "address": f"10.0.0.{i}",
                    "pool": pool_id.inserted_primary_key[0],
                    "network": "10.0.0.0/24",
                    "reserved": False,
                },
            )
        # Create lease for mac address
        self.unknown_mac = "00:11:22:33:44:55"
        # self.db_instance._do_insert(obj.leases, {})
        self.dbq = mock_q()
        self.sent_packets: list[dhcp_server.dhcp_packet.DhcpPacket] = []
        self.consumer = dhcp_server.db_consumer(
            self.dbq, self.mock_send, self.db_instance, production=False
        )
        return super().setUp()

    def tearDown(self):
        self.db_instance._rollback()
        return super().tearDown()

    def mock_send(self, packet, sent_to=None, bootp=None):
        self.sent_packets.append(packet)

    def testDiscoveryPoolUnknown(self):
        # Do discovery for a packet with a lease
        pkttype = 1
        packet = make_dhcp_packet(
            1, self.unknown_mac, "10.0.0.1", [1, 3, 6, 15], ("10.0.0.1", 68)
        )
        self.dbq.put_nowait((pkttype, packet))
        # Process a single packet
        self.consumer.process_pkt()
        disc_pkt = self.sent_packets.pop()
        self.assertTrue(disc_pkt.IsDhcpDiscoverPacket)
        q = self.db_instance._get_leases(mac=self.unknown_mac)
        leases = self.db_instance._execute(q)
        discovery_lease = next(lease for lease in leases if lease.address.startswith('10.0.0'))
        self.assertIsNotNone(discovery_lease)


if __name__ == "__main__":
    unittest.main(verbosity=2)

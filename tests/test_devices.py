import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import device_manager as d

class Devices(unittest.TestCase):
    def test_registry(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ",{},clear=True):
            root=Path(tmp)
            self.assertIsNone(d.registry(root)["active"])
            a=d.save_device(root,{"name":"One","host":"192.0.2.1","port":12345})["active"]
            b=d.save_device(root,{"name":"Two","host":"192.0.2.2","port":23456})["active"]
            self.assertNotEqual(a,b)
            d.store(root,a,{"original_context":{"source":9},"profiles":{"1":{}}})
            self.assertEqual(d.snapshot(root,b)["profiles"],{})
            d.select_device(root,a)
            d.save_device(root,{"id":a,"name":"One","host":"192.0.2.1","port":34567})
            self.assertEqual(d.active_device(root)["port"],34567)
            self.assertIn("1",d.snapshot(root,a,9)["profiles"])
    def test_invalid_port(self):
        with self.assertRaises(ValueError): d.address("192.0.2.1",True)

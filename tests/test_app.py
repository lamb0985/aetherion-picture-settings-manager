import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as manager

def sample():
    return {
        "original_context": {"source": 5},
        "profiles": {"1": {"format": "SDR 4K", "profiles": {"3": {
            "name": "Theater Day",
            "settings": {
                "source": {"value": 5}, "signal_dr_type": {"value": 1},
                "pic_mode": {"value": 3}, "color_temp": {"value": 2, "range": [0,0,0], "state": 1}
            },
            "indexed": {}
        }}}}
    }

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.patch = patch.multiple(manager, CONFIG=self.dir, CATALOG=self.dir/"catalog.json")
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)
        self.client = manager.app.test_client()

    def test_empty_catalog(self):
        response = self.client.get("/api/catalog")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["summary"]["profiles"], 0)

    def test_import_and_summary(self):
        data = sample()
        data["adb_endpoint"] = "private"
        response = self.client.post("/api/catalog", json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["summary"]["profiles"], 1)
        self.assertEqual(response.json["summary"]["source"], 5)
        result = self.client.get("/api/catalog").json
        self.assertNotIn("adb_endpoint", result)
        self.assertEqual(result["summary"]["general"], 4)

    def test_reject_mismatched_source(self):
        data = sample()
        data["profiles"]["1"]["profiles"]["3"]["settings"]["source"]["value"] = 9
        self.assertEqual(self.client.post("/api/catalog", json=data).status_code, 400)
        self.assertFalse(manager.CATALOG.exists())

    def test_reject_cross_site(self):
        self.assertEqual(self.client.post("/api/catalog", json=sample(),
            headers={"Sec-Fetch-Site":"cross-site"}).status_code, 403)

    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_connection_read_only(self):
        with patch.object(manager, "endpoint", return_value="192.0.2.1:12345"), \
             patch.object(manager, "adb", side_effect=["connected", "device\n"]) as adb, \
             patch.object(manager, "live_context", return_value={"source":5,"signal_dr_type":1,"pic_mode":3}):
            result = self.client.post("/api/connection", json={})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json["context"]["source"], 5)
            self.assertEqual(adb.call_count, 2)

    def test_disconnect_selected_projector(self):
        target="192.0.2.1:12345"
        with patch.object(manager,"endpoint",return_value=target), patch.object(manager.remote,"target",target), patch.object(manager.remote,"stop") as stop, patch.object(manager,"REMOTE_TOKEN","token"), patch.object(manager,"BULK_PLAN",{"token":"preview"}), patch.object(manager,"adb",side_effect=["disconnected","List of devices attached\n192.0.2.2:5555 device\n"]) as adb:
            result=self.client.post("/api/connection/disconnect",json={})
            self.assertEqual(result.status_code,200,result.json)
            stop.assert_called_once()
            self.assertEqual(adb.call_args_list[0].args,("disconnect",target))
            self.assertEqual(adb.call_args_list[1].args,("devices",))
            self.assertIsNone(manager.REMOTE_TOKEN)
            self.assertIsNone(manager.BULK_PLAN)

    def test_disconnect_busy(self):
        with manager.ADB_LOCK, patch.object(manager,"adb") as adb:
            result=self.client.post("/api/connection/disconnect",json={})
            self.assertEqual(result.status_code,409)
            adb.assert_not_called()

class ParcelTests(unittest.TestCase):
    def test_decode(self):
        obj = {"msg": {"source": {"value":5}}}
        payload = json.dumps(obj).encode("utf-16le")
        raw = struct.pack("<ii", 0, len(payload)//2) + payload + b"\0\0"
        raw += b"\0" * (-len(raw)%4)
        words = [f"{w:08x}" for w, in struct.iter_unpack("<I", raw)]
        parcel = "Result: Parcel(\n" + "\n".join(
            "  0x%08x: %s  'ignored'" % (i*4, " ".join(words[i:i+4]))
            for i in range(0,len(words),4)) + "\n)"
        self.assertEqual(manager.decode_parcel(parcel), obj)

    def test_truncated(self):
        with self.assertRaises(ValueError):
            manager.decode_parcel("Result: Parcel(00000000 000000ff)")

if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch
import app as a

class HdmiTests(unittest.TestCase):
    def test_switches(self):
        for port in (1,2,3):
            with self.subTest(port=port), patch.object(a,"REMOTE_TOKEN","t"), patch.object(a,"endpoint",return_value="device"), patch.object(a.remote,"target","device"), patch.object(a.remote,"running",return_value=True), patch.object(a.remote,"touch"), patch.object(a,"adb",return_value="Status: ok") as adb, patch.object(a,"live_context",return_value={"source":port+3}), patch.object(a.time,"sleep"):
                response=a.app.test_client().post("/api/remote/key",json={"key":f"HDMI_{port}","token":"t"})
                self.assertEqual(response.status_code,200)
                self.assertTrue(adb.call_args.args[-1].endswith(f"HW{port+1}"))
    def test_unlisted_live_key(self):
        response=a.app.test_client().post("/api/live/setting",json={"key":"source"})
        self.assertEqual(response.status_code,400)

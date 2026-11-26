import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import app as a

class LiveStateTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        config=patch.object(a,"CONFIG",Path(folder.name))
        config.start()
        self.addCleanup(config.stop)

    def test_reads_without_snapshot(self):
        context={"source":5,"signal_dr_type":1,"pic_mode":8}
        values={k:{"value":v} for k,v in {**context,"pq_apply":1,"contrast":53}.items()}
        with patch.object(a.devices,"active_device",return_value={"id":"d","host":"192.0.2.1","port":5555}),patch.object(a,"adb",return_value="device"),patch.object(a,"live_context",return_value=context),patch.object(a,"picture_call",return_value={"msg":values}) as call:
            result=a.app.test_client().post("/api/live/state",json={"device":"d","keys":["contrast"]})
            self.assertEqual(result.status_code,200,result.json)
            self.assertEqual(result.json["settings"]["contrast"]["value"],53)
            self.assertEqual(result.json["context"],context)
            self.assertTrue(all(c.args[1]==1 for c in call.call_args_list))
            requested={k for c in call.call_args_list for k in c.args[2]["msg"]}
            self.assertIn("laser_type",requested)
            self.assertNotIn("iris_mode",requested)
            self.assertIn("laser_type",result.json["missing"])
            self.assertEqual(a.devices.snapshot(a.CONFIG,"d"),{"profiles":{}})
    def test_reject_unknown_key(self):
        with patch.object(a.devices,"active_device",return_value={"id":"d","host":"192.0.2.1","port":5555}),patch.object(a,"adb",return_value="device"),patch.object(a,"live_context",return_value={"source":5,"signal_dr_type":1,"pic_mode":8}),patch.object(a,"picture_call") as call:
            result=a.app.test_client().post("/api/live/state",json={"device":"d","keys":["invalid"]})
            self.assertEqual(result.status_code,503)
            call.assert_not_called()

    def test_refresh_matching_snapshot_preserves_indexed(self):
        context={"source":5,"signal_dr_type":1,"pic_mode":8}
        values={k:{"value":v} for k,v in {**context,"pq_apply":1,"contrast":53,"laser_type":1}.items()}
        indexed={"white_balance_20_point":{"values":{"0":{"settings":{"20p_wb_red":{"value":7}}}}}}
        a.devices.store(a.CONFIG,"d",{"original_context":context,"profiles":{"1":{"profiles":{"8":{"settings":{"contrast":{"value":50},"iris_mode":{"value":4}},"indexed":indexed}}}}})
        with patch.object(a.devices,"active_device",return_value={"id":"d","host":"192.0.2.1","port":5555}),patch.object(a,"adb",return_value="device"),patch.object(a,"live_context",return_value=context),patch.object(a,"picture_call",return_value={"msg":values}):
            result=a.app.test_client().post("/api/live/state",json={"device":"d"})
            self.assertEqual(result.status_code,200,result.json)
        profile=a.devices.snapshot(a.CONFIG,"d",5)["profiles"]["1"]["profiles"]["8"]
        self.assertEqual(profile["settings"]["contrast"]["value"],53)
        self.assertEqual(profile["settings"]["laser_type"]["value"],1)
        self.assertNotIn("iris_mode",profile["settings"])
        self.assertEqual(profile["indexed"],indexed)

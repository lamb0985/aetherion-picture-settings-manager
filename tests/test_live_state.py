import unittest
from unittest.mock import patch
import app as a

class LiveStateTests(unittest.TestCase):
    def test_reads_without_snapshot(self):
        context={"source":5,"signal_dr_type":1,"pic_mode":8}
        values={k:{"value":v} for k,v in {**context,"pq_apply":1,"contrast":53}.items()}
        with patch.object(a.devices,"active_device",return_value={"id":"d","host":"192.0.2.1","port":5555}),patch.object(a,"adb",return_value="device"),patch.object(a,"live_context",return_value=context),patch.object(a,"picture_call",return_value={"msg":values}) as call:
            result=a.app.test_client().post("/api/live/state",json={"device":"d","keys":["contrast"]})
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json["settings"]["contrast"]["value"],53)
            self.assertEqual(result.json["context"],context)
            self.assertEqual(call.call_args.args[1],1)
    def test_reject_unknown_key(self):
        with patch.object(a.devices,"active_device",return_value={"id":"d","host":"192.0.2.1","port":5555}),patch.object(a,"adb",return_value="device"),patch.object(a,"live_context",return_value={"source":5,"signal_dr_type":1,"pic_mode":8}),patch.object(a,"picture_call") as call:
            result=a.app.test_client().post("/api/live/state",json={"device":"d","keys":["invalid"]})
            self.assertEqual(result.status_code,503)
            call.assert_not_called()

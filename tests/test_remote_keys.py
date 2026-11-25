import unittest
from unittest.mock import patch
import app as apsm

class RemoteKeysTest(unittest.TestCase):
    def test_native_buttons(self):
        cases = {
            "MENU": ("shell", "input", "keyevent", "1578"),
            "SETTINGS": ("shell", "input", "keyevent", "KEYCODE_SETTINGS"),
            "PICTURE_SETTINGS": ("shell", "am", "start", "-n", "com.vt.customsettings/com.vt.customsettings.picture.ui.PictureActivity"),
            "DPAD_UP": ("shell", "input", "keyevent", "KEYCODE_DPAD_UP"),
        }
        with patch.object(apsm, "REMOTE_TOKEN", "test-token"), patch.object(apsm, "endpoint", return_value="device"), patch.object(apsm.remote, "target", "device"), patch.object(apsm.remote, "running", return_value=True), patch.object(apsm.remote, "touch"), patch.object(apsm, "adb", return_value="Starting: Intent") as adb:
            for key, args in cases.items():
                with self.subTest(key=key):
                    response = apsm.app.test_client().post("/api/remote/key", json={"key":key,"token":"test-token"})
                    self.assertEqual(response.status_code, 200)
                    adb.assert_called_with("-s","device",*args)

    def test_invalid_key(self):
        response = apsm.app.test_client().post("/api/remote/key", json={"key":"unrecognized"})
        self.assertEqual(response.status_code,400)

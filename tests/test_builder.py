import tempfile
import unittest
from pathlib import Path
from builder import kernel_entry, release_zip, SMBIOS, EXTRA

class BuilderTests(unittest.TestCase):
    def test_profiles(self):
        self.assertIn("desktop", SMBIOS)
        self.assertIn("laptop", SMBIOS)

    def test_feature_names(self):
        self.assertIn("intel-graphics", EXTRA)
        self.assertIn("audio", EXTRA)

    def test_kext_metadata(self):
        import plistlib
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "Example.kext" / "Contents"
            root.mkdir(parents=True)
            (root / "Info.plist").write_bytes(plistlib.dumps({"CFBundleExecutable": "Example"}))
            (root / "MacOS").mkdir()
            (root / "MacOS" / "Example").write_bytes(b"binary")
            item = kernel_entry(root.parent)
            self.assertEqual(item["ExecutablePath"], "Contents/MacOS/Example")
            self.assertEqual(item["BundlePath"], "Example.kext")
            self.assertTrue(item["Enabled"])

if __name__ == "__main__":
    unittest.main()

import contextlib
import hashlib
import io
import json
import pathlib
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import Mock, patch

import instalar_maxobd as app


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.target = self.root / "output"
        self.target.mkdir()
        self.files = {
            "com.jiawei.maxobd.apk": b"synthetic base for tests; never executable",
            "config.arm64_v8a.apk": b"synthetic native component",
            "config.xxhdpi.apk": b"synthetic images component",
        }
        self.profile = {
            "version_name": "1.0.30", "version_code": 46, "min_sdk": 21,
            "abi": "arm64-v8a", "sha256": {
                name: hashlib.sha256(data).hexdigest() for name, data in self.files.items()
            },
        }
        self.manifest = {
            "package_name": app.PACKAGE, "version_name": "1.0.30", "version_code": "46",
            "min_sdk_version": "21", "split_apks": [{"file": n} for n in self.files],
        }

    def archive(self, files=None, manifest=None):
        path = self.root / "input.xapk"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("manifest.json", json.dumps(self.manifest if manifest is None else manifest))
            for name, data in (self.files if files is None else files).items():
                archive.writestr(name, data)
        return path

    def prepare(self, path):
        return app.prepare_package(path, self.target, [self.profile])

    def test_complete_known_package_preserves_all_bytes(self):
        result = self.prepare(self.archive())
        self.assertEqual(len(result.files), 3)
        for path in result.files:
            self.assertEqual(path.read_bytes(), self.files[path.name])

    def test_tampered_base_is_rejected(self):
        files = dict(self.files)
        files["com.jiawei.maxobd.apk"] += b"changed"
        with self.assertRaisesRegex(app.InstallerError, "SHA-256"):
            self.prepare(self.archive(files=files))

    def test_incomplete_native_component_is_rejected(self):
        files = dict(self.files)
        del files["config.arm64_v8a.apk"]
        with self.assertRaises(app.InstallerError):
            self.prepare(self.archive(files=files))

    def test_extra_apk_is_not_installed(self):
        with self.assertRaises(app.InstallerError):
            self.prepare(self.archive(files={**self.files, "unrelated.apk": b"unwanted"}))

    def test_path_traversal_is_rejected_and_never_extracted(self):
        with self.assertRaises(app.InstallerError):
            self.prepare(self.archive(files={**self.files, "../escape.apk": b"unwanted"}))
        self.assertFalse((self.root / "escape.apk").exists())

    def test_duplicate_entry_is_rejected(self):
        path = self.archive()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "a") as archive:
                archive.writestr("com.jiawei.maxobd.apk", b"second copy")
        with self.assertRaisesRegex(app.InstallerError, "duplicados"):
            self.prepare(path)

    def test_wrong_package_is_rejected(self):
        with self.assertRaises(app.InstallerError):
            self.prepare(self.archive(manifest={**self.manifest, "package_name": "another.app"}))

    def test_unknown_version_is_rejected(self):
        with self.assertRaises(app.InstallerError):
            self.prepare(self.archive(manifest={**self.manifest, "version_code": "999"}))

    def test_manifest_omitting_components_is_rejected(self):
        with self.assertRaises(app.InstallerError):
            self.prepare(self.archive(manifest={**self.manifest, "split_apks": []}))

    def test_mismatched_minimum_sdk_is_rejected(self):
        with self.assertRaises(app.InstallerError):
            self.prepare(self.archive(manifest={**self.manifest, "min_sdk_version": "24"}))

    def test_uncompressed_size_limit_prevents_extraction(self):
        path = self.archive()
        with patch.object(app, "MAX_ARCHIVE_BYTES", 10), self.assertRaises(app.InstallerError):
            self.prepare(path)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_offline_mode_never_constructs_adb(self):
        path = self.archive()
        with patch.object(app, "load_profiles", return_value=[self.profile]), patch.object(app, "Adb") as adb:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(app.main(["--xapk", str(path), "--solo-archivo"]), 0)
            adb.assert_not_called()

    def test_default_mode_never_installs(self):
        path = self.archive()
        adb = Mock()
        adb.run.side_effect = [
            "List of devices attached\nTEST_DEVICE device model:Test\n",
            "[ro.product.model]: [Test]\n[ro.build.version.sdk]: [22]\n[ro.product.cpu.abilist]: [arm64-v8a]\n",
            "versionName=1.0.30\nversionCode=46 targetSdk=35",
        ]
        with patch.object(app, "load_profiles", return_value=[self.profile]), \
                patch.object(app.shutil, "which", return_value="adb"), \
                patch.object(app, "Adb", return_value=adb):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(app.main(["--xapk", str(path)]), 0)
        self.assertFalse(any("install-multiple" in call.args for call in adb.run.call_args_list))


class DeviceTests(unittest.TestCase):
    profile = {"min_sdk": 21, "abi": "arm64-v8a", "version_name": "1.0.30", "version_code": 46}

    def test_multiple_devices_require_selection(self):
        adb = Mock()
        adb.run.return_value = "List of devices attached\nA device\nB device\n"
        with self.assertRaisesRegex(app.InstallerError, "varios"):
            app.select_device(adb)
        self.assertEqual(app.select_device(adb, "B"), "B")

    def test_unauthorized_reports_tablet_confirmation(self):
        adb = Mock()
        adb.run.return_value = "List of devices attached\nA unauthorized\n"
        with self.assertRaisesRegex(app.InstallerError, "Permitir depuración USB"):
            app.select_device(adb)

    def test_offline_and_absent_requested_device_are_rejected(self):
        adb = Mock()
        adb.run.return_value = "List of devices attached\nA offline\n"
        for serial in [None, "B"]:
            with self.subTest(serial=serial), self.assertRaises(app.InstallerError):
                app.select_device(adb, serial)

    def test_api_below_21_is_rejected(self):
        with self.assertRaises(app.InstallerError):
            app.validate_device({"ro.build.version.sdk": "20", "ro.product.cpu.abilist": "arm64-v8a"}, self.profile)

    def test_android_5_api21_satisfies_declared_minimum(self):
        self.assertEqual(app.validate_device({"ro.build.version.sdk": "21", "ro.product.cpu.abi": "arm64-v8a"}, self.profile), 21)

    def test_abi_mismatch_is_rejected(self):
        with self.assertRaisesRegex(app.InstallerError, "Arquitectura"):
            app.validate_device({"ro.build.version.sdk": "22", "ro.product.cpu.abilist": "armeabi-v7a"}, self.profile)

    def test_different_existing_version_is_never_downgraded_or_replaced(self):
        for code, name in [(99, "1.1.04"), (44, "1.0.29")]:
            with self.subTest(code=code), self.assertRaises(app.InstallerError):
                app.validate_installed_version(f"versionName={name}\nversionCode={code}", self.profile)

    def test_incomplete_version_information_is_rejected(self):
        with self.assertRaises(app.InstallerError):
            app.validate_installed_version("versionName=1.0.30", self.profile)

    def test_absent_package_can_be_installed(self):
        self.assertIsNone(app.validate_installed_version("Unable to find package", self.profile))

    def test_success_verifies_all_three_components_without_launching_vehicle_operations(self):
        adb = Mock(serial="TEST_DEVICE")
        adb.run.side_effect = ["Success", "versionName=1.0.30\nversionCode=46", "package:/base.apk\npackage:/split1.apk\npackage:/split2.apk"]
        prepared = app.PreparedPackage(self.profile, [pathlib.Path(n) for n in ["base.apk", "native.apk", "graphics.apk"]])
        with contextlib.redirect_stdout(io.StringIO()):
            app.install_package(adb, prepared)
        self.assertEqual(adb.run.call_args_list[0].args[:2], ("install-multiple", "-r"))
        self.assertEqual(len(adb.run.call_args_list), 3)

    def test_success_without_all_installed_components_is_not_reported_as_complete(self):
        adb = Mock()
        adb.run.side_effect = ["Success", "versionName=1.0.30\nversionCode=46", "package:/base.apk"]
        prepared = app.PreparedPackage(self.profile, [pathlib.Path(n) for n in ["base.apk", "native.apk", "graphics.apk"]])
        with self.assertRaisesRegex(app.InstallerError, "número de componentes"):
            app.install_package(adb, prepared)


if __name__ == "__main__":
    unittest.main()

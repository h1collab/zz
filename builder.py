#!/usr/bin/env python3
"""Build a conservative OpenCore starter EFI; never modifies a local disk."""
import argparse
import json
import plistlib
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.github.com/repos/"
PROJECTS = {
    "Lilu": "acidanthera/Lilu",
    "VirtualSMC": "acidanthera/VirtualSMC",
    "WhateverGreen": "acidanthera/WhateverGreen",
    "AppleALC": "acidanthera/AppleALC",
    "IntelMausi": "acidanthera/IntelMausi",
    "NVMeFix": "acidanthera/NVMeFix",
}
SMBIOS = {"desktop": "iMac19,1", "laptop": "MacBookPro15,2"}
BASE = ("Lilu", "VirtualSMC")
EXTRA = {
    "intel-graphics": ("WhateverGreen",),
    "audio": ("AppleALC",),
    "intel-ethernet": ("IntelMausi",),
    "nvme": ("NVMeFix",),
}

def download(url, target):
    req = urllib.request.Request(url, headers={"User-Agent": "oc-efi-builder", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=90) as response, open(target, "wb") as out:
        shutil.copyfileobj(response, out)

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "oc-efi-builder", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)

def release_zip(repo):
    release = get_json(API + repo + "/releases/latest")
    assets = [x for x in release["assets"] if x["name"].endswith("-RELEASE.zip")]
    if len(assets) != 1:
        raise RuntimeError("Unable to identify release archive for " + repo)
    return release["tag_name"], assets[0]["browser_download_url"]

def extract_archive(archive, destination):
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            name = Path(member.filename)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("Unsafe archive path")
        z.extractall(destination)

def unique_file(root, file_name):
    matches = [p for p in root.rglob(file_name) if p.is_file() and "__MACOSX" not in p.parts]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {file_name}, got {len(matches)}")
    return matches[0]

def unique_kext(root, name):
    matches = [p for p in root.rglob(name + ".kext") if p.is_dir() and (p / "Contents/Info.plist").exists() and "DEBUG" not in p.parts]
    if not matches:
        raise RuntimeError("Missing kext " + name)
    return matches[0]

def kernel_entry(kext):
    info = plistlib.loads((kext / "Contents/Info.plist").read_bytes())
    executable = info.get("CFBundleExecutable", "")
    executable_path = "Contents/MacOS/" + executable if executable and (kext / "Contents/MacOS" / executable).is_file() else ""
    return {
        "Arch": "Any", "BundlePath": kext.name, "Comment": "Auto selected; verify hardware",
        "Enabled": True, "ExecutablePath": executable_path,
        "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"
    }

def build(args):
    selected = list(BASE)
    for feature in args.features:
        for name in EXTRA[feature]:
            if name not in selected:
                selected.append(name)
    dest = Path(args.output).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        tmp = Path(scratch)
        versions = {}
        oc_ver, oc_url = release_zip("acidanthera/OpenCorePkg")
        download(oc_url, tmp / "opencore.zip")
        extract_archive(tmp / "opencore.zip", tmp / "oc")
        versions["OpenCore"] = oc_ver
        source = tmp / "oc/X64/EFI"
        if not source.exists():
            raise RuntimeError("OpenCore archive lacks X64 EFI directory")
        efi = dest / "EFI"
        shutil.copytree(source, efi, dirs_exist_ok=True)
        oc = efi / "OC"
        # Remove unused sample drivers and tools, retaining only required binaries.
        drivers = oc / "Drivers"
        for path in drivers.glob("*.efi"):
            if path.name != "OpenRuntime.efi":
                path.unlink()
        tools = oc / "Tools"
        if tools.exists():
            shutil.rmtree(tools)
        tools.mkdir(exist_ok=True)
        (oc / "Kexts").mkdir(exist_ok=True)
        for entry in (oc / "Kexts").iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
        download("https://raw.githubusercontent.com/acidanthera/OcBinaryData/master/Drivers/HfsPlus.efi", drivers / "HfsPlus.efi")
        # Build from matching release Sample.plist, not a hand-written incompatible schema.
        sample = tmp / "oc/Docs/Sample.plist"
        if not sample.exists():
            sample = unique_file(tmp / "oc", "Sample.plist")
        config = plistlib.loads(sample.read_bytes())
        kext_entries = []
        for name in selected:
            version, asset = release_zip(PROJECTS[name])
            versions[name] = version
            download(asset, tmp / (name + ".zip"))
            pkg = tmp / ("pkg-" + name)
            extract_archive(tmp / (name + ".zip"), pkg)
            source_kext = unique_kext(pkg, name)
            target = oc / "Kexts" / (name + ".kext")
            shutil.copytree(source_kext, target)
            kext_entries.append(kernel_entry(target))
        config["Kernel"]["Add"] = kext_entries
        config["UEFI"]["Drivers"] = [
            {"Arguments": "", "Comment": "", "Enabled": True, "HideVerbose": False, "LoadEarly": False, "Path": "OpenRuntime.efi"},
            {"Arguments": "", "Comment": "", "Enabled": True, "HideVerbose": False, "LoadEarly": False, "Path": "HfsPlus.efi"}
        ]
        for item in config["ACPI"]["Add"]:
            item["Enabled"] = False
        for section in ("Patch", "Block", "Force"):
            for item in config["Kernel"].get(section, []):
                item["Enabled"] = False
        for item in config["Misc"].get("Tools", []):
            item["Enabled"] = False
        config["Misc"]["Security"]["Vault"] = "Optional"
        config["Misc"]["Security"]["DmgLoading"] = "Signed"
        config["Misc"]["Security"]["SecureBootModel"] = "Default"
        config["PlatformInfo"]["Generic"]["SystemProductName"] = SMBIOS[args.profile]
        # Deliberately invalid placeholder identity. User must generate unique values locally.
        config["PlatformInfo"]["Generic"]["SystemSerialNumber"] = "REPLACE_ME"
        config["PlatformInfo"]["Generic"]["MLB"] = "REPLACE_ME"
        config["PlatformInfo"]["Generic"]["SystemUUID"] = "00000000-0000-0000-0000-000000000000"
        config["PlatformInfo"]["Generic"]["ROM"] = bytes(6)
        # Never copy sample device properties for unrelated PCs.
        config["DeviceProperties"]["Add"] = {}
        config["DeviceProperties"]["Delete"] = {}
        config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["csr-active-config"] = bytes(4)
        for key in list(config):
            if str(key).startswith("#"):
                del config[key]
        (oc / "config.plist").write_bytes(plistlib.dumps(config, sort_keys=False))
        report = {
            "status": "STARTER_ONLY_NOT_BOOT_READY",
            "profile": args.profile, "features": args.features, "versions": versions,
            "manual_steps": [
                "Generate a unique valid SMBIOS locally; never publish serial numbers",
                "Select ACPI SSDTs and BIOS quirks for your specific motherboard",
                "Inspect USB topology and supply a compatible USB map if required",
                "Check GPU, Wi-Fi, storage and macOS version compatibility",
                "Run ocvalidate from matching OpenCore release; review any warnings",
                "Test only with a full backup and an independently recoverable EFI"
            ]
        }
        (dest / "build-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (dest / "READ_BEFORE_BOOT.txt").write_text(
            "STARTER EFI - NOT BOOT READY.\nDo not boot until SMBIOS, ACPI, quirks and hardware are configured.\nNo Apple installer, kernel patches or bypass tools are included.\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=SMBIOS, default="desktop")
    ap.add_argument("--features", nargs="*", choices=list(EXTRA), default=[])
    ap.add_argument("--output", default="dist")
    args = ap.parse_args()
    build(args)

if __name__ == "__main__":
    main()

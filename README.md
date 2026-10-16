# OpenCore Hackintosh Starter EFI Builder

This project builds a **starter OpenCore EFI ZIP** on GitHub Actions using the official release assets from Acidanthera projects. The ZIP is **not a verified bootable Hackintosh configuration**.

## Run in GitHub Actions

1. Open **Actions** → **Build OpenCore starter EFI** → **Run workflow** (on a branch containing this workflow).
2. Select the desktop/laptop starter profile and optional Kext packages.
3. After the run finishes, download the **OpenCore-starter-EFI** artifact from the workflow run.
4. Unpack it; inspect `EFI/OC/config.plist`, `build-report.json`, and `READ_BEFORE_BOOT.txt`.

The build uses the latest published RELEASE ZIP files, so versions can change between runs; a JSON report records versions. The CI job validates XML plist readability and referenced files, **not hardware compatibility or boot correctness**.

## Local usage

Requires Python 3.10+ and internet access:

```bash
python builder.py --profile desktop --features intel-graphics audio --output dist
python -m unittest discover -s tests -v
```

## Before testing

- Record CPU, motherboard/chipset, GPU, storage controller, audio codec, network adapters, USB controller and your macOS target version.
- Select hardware-specific ACPI SSDTs and OpenCore quirks. All sampled ACPI entries remain disabled by default.
- Generate unique SMBIOS values **locally** and keep them private. The generated placeholders are intentionally invalid.
- Validate with the matching official `ocvalidate`; adjust `config.plist` based on your actual hardware.
- Choose the correct USB mapping and Wi-Fi/Bluetooth Kexts for your hardware.
- Back up data, preserve an independently bootable recovery environment, and test on a removable EFI first.

## Installation media

This repository **does not distribute macOS or create a universal PC bootable macOS installer**. Use Apple's official recovery/installer process and the OpenCore installation documentation on compatible hardware. Neither a custom macOS kernel nor Apple activation/server bypassing is implemented.

### Limitations

No universal driver exists for every unsupported GPU, USB device, Wi-Fi chipset or PC. The generator does not modify the macOS system volume, disable SIP globally, patch firmware, spoof valid identity values automatically, or promise that Apple updates will remain compatible. It only constructs an **editable starting point**.

Upstream references:
- https://github.com/acidanthera/OpenCorePkg
- https://github.com/acidanthera/OcBinaryData
- https://dortania.github.io/OpenCore-Install-Guide/

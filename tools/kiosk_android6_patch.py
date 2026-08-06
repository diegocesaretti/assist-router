#!/usr/bin/env python3
"""Patch a Kiosk Satellite 2026.8.x checkout for a private Android 6 build."""

from __future__ import annotations

import re
import sys
from pathlib import Path

FLUTTER_3_32_8_REVISION = "edada7c56edf4a183c1735310e123c7f923584f1"


def replace_required(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def patch(root: Path) -> None:
    app = root / "app"
    if not (app / "pubspec.yaml").is_file():
        raise RuntimeError(f"Not a Kiosk Satellite checkout: {root}")

    metadata = app / ".metadata"
    text = metadata.read_text(encoding="utf-8")
    text = re.sub(r'revision: "[0-9a-f]+"', f'revision: "{FLUTTER_3_32_8_REVISION}"', text, count=1)
    metadata.write_text(text, encoding="utf-8")

    pubspec = app / "pubspec.yaml"
    text = pubspec.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^\s+sdk:\s*\^3\.12\.2\s*$", '  sdk: ">=3.8.0 <4.0.0"', text)
    text = text.replace("flutter_inappwebview: ^6.2.0-beta.3", "flutter_inappwebview: 6.2.0-beta.3")
    text = text.replace("intl: ^0.20.3", "intl: 0.20.2")
    pubspec.write_text(text, encoding="utf-8")
    (app / "pubspec.lock").unlink(missing_ok=True)

    settings = app / "android/settings.gradle.kts"
    text = settings.read_text(encoding="utf-8")
    text = re.sub(
        r'id\("com\.android\.application"\) version "[^"]+" apply false',
        'id("com.android.application") version "8.9.1" apply false',
        text,
    )
    text = re.sub(
        r'id\("org\.jetbrains\.kotlin\.android"\) version "[^"]+" apply false',
        'id("org.jetbrains.kotlin.android") version "2.1.0" apply false',
        text,
    )
    settings.write_text(text, encoding="utf-8")

    wrapper = app / "android/gradle/wrapper/gradle-wrapper.properties"
    text = wrapper.read_text(encoding="utf-8")
    text = re.sub(r"gradle-[0-9.]+-all\.zip", "gradle-8.12-all.zip", text)
    wrapper.write_text(text, encoding="utf-8")

    app_gradle = app / "android/app/build.gradle.kts"
    text = app_gradle.read_text(encoding="utf-8")
    if 'id("kotlin-android")' not in text:
        text = text.replace(
            '    id("com.android.application")\n',
            '    id("com.android.application")\n    id("kotlin-android")\n',
            1,
        )
    text = text.replace("compileSdk = flutter.compileSdkVersion", "compileSdk = 36")
    text = text.replace("ndkVersion = flutter.ndkVersion", 'ndkVersion = "27.0.12077973"')
    text = text.replace("minSdk = maxOf(24, flutter.minSdkVersion)", "minSdk = 23")
    text = text.replace(
        "androidx.media3:media3-exoplayer:1.10.1",
        "androidx.media3:media3-exoplayer:1.6.1",
    )
    app_gradle.write_text(text, encoding="utf-8")

    for rel in ("lib/ui/camera_settings.dart", "lib/ui/gesture_settings.dart"):
        path = app / rel
        text = path.read_text(encoding="utf-8")
        text = text.replace("initialValue:", "value:")
        path.write_text(text, encoding="utf-8")

    for rel in ("lib/ui/camera_settings.dart", "lib/ui/glance_entity_picker.dart"):
        path = app / rel
        text = path.read_text(encoding="utf-8")
        text = text.replace("onReorderItem:", "onReorder:")
        path.write_text(text, encoding="utf-8")

    kit = app / "lib/ui/kit.dart"
    text = kit.read_text(encoding="utf-8")
    old = """      RadioGroup<T>(
        groupValue: selected,
        onChanged: (v) => Navigator.of(context).pop(v),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final option in options)
              RadioListTile<T>(
                value: option.value,
                title: Text(option.label),
                subtitle: option.detail == null ? null : Text(option.detail!),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12),
              ),
          ],
        ),
      ),
"""
    new = """      Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final option in options)
            RadioListTile<T>(
              value: option.value,
              groupValue: selected,
              onChanged: (v) => Navigator.of(context).pop(v),
              title: Text(option.label),
              subtitle: option.detail == null ? null : Text(option.detail!),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12),
            ),
        ],
      ),
"""
    if old not in text:
        raise RuntimeError("RadioGroup block not found in lib/ui/kit.dart")
    kit.write_text(text.replace(old, new), encoding="utf-8")

    manifest = app / "android/app/src/main/AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    if "io.flutter.embedding.android.EnableImpeller" not in text:
        marker = "        <!-- Don't delete the meta-data below."
        legacy = """        <!-- Android 6 legacy build: force Skia for old GPU drivers. -->
        <meta-data
            android:name="io.flutter.embedding.android.EnableImpeller"
            android:value="false" />
"""
        if marker not in text:
            raise RuntimeError("Flutter metadata marker not found in AndroidManifest.xml")
        text = text.replace(marker, legacy + marker)
    manifest.write_text(text, encoding="utf-8")

    (root / "ANDROID6-PORT.md").write_text(
        """# Private Android 6 compatibility build

Generated from Kiosk Satellite for personal compatibility testing.

Changes made by the patcher:

- Flutter 3.32.8 / Dart 3.8
- Android API 23 minimum
- Android Gradle Plugin 8.9.1
- Kotlin 2.1.0
- Gradle 8.12
- compileSdk 36 and NDK 27.0.12077973
- flutter_inappwebview 6.2.0-beta.3 with a fresh lockfile
- intl 0.20.2
- Media3 ExoPlayer 1.6.1
- Flutter 3.32 widget API compatibility edits
- Skia renderer forced instead of Impeller

The upstream CC BY-NC-ND licence does not permit distributing a modified build.
Keep the generated source and APK private unless the upstream author grants permission.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    try:
        patch(Path(sys.argv[1] if len(sys.argv) > 1 else "kiosk-satellite-android6"))
    except Exception as exc:
        print(f"patch failed: {exc}", file=sys.stderr)
        raise

#!/usr/bin/env python3
"""Add an Android 6 safe-start/diagnostic mode to an already patched checkout."""

from pathlib import Path
import sys


def replace_required(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def patch(root: Path) -> None:
    app = root / "app"

    # Install beside the first build so a different CI debug key is harmless.
    gradle = app / "android/app/build.gradle.kts"
    text = gradle.read_text(encoding="utf-8")
    text = text.replace(
        'applicationId = "me.jxl.kiosk_satellite"',
        'applicationId = "me.jxl.kiosk_satellite.a6safe"',
    )
    gradle.write_text(text, encoding="utf-8")

    manifest = app / "android/app/src/main/AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace('android:label="Kiosk Satellite"', 'android:label="Kiosk Satellite A6 Safe"')
    text = text.replace(
        'android:usesCleartextTraffic="true">',
        'android:usesCleartextTraffic="true"\n        android:largeHeap="true">',
    )
    manifest.write_text(text, encoding="utf-8")

    # Any Dart-side startup failure becomes a visible screen with the stack,
    # rather than a silent splash/exit before the normal UI exists.
    main = app / "lib/main.dart"
    replace_required(
        main,
        "Future<void> main() async {\n  WidgetsFlutterBinding.ensureInitialized();\n",
        "Future<void> main() async {\n  WidgetsFlutterBinding.ensureInitialized();\n  try {\n",
    )
    old_tail = "  FrameWatchdog(container).start();\n  runApp(KioskSatelliteApp(container: container));\n}\n\nclass KioskSatelliteApp"
    new_tail = """  FrameWatchdog(container).start();
  runApp(KioskSatelliteApp(container: container));
  } catch (error, stack) {
    runApp(_StartupFailureApp(error: error, stack: stack));
  }
}

class _StartupFailureApp extends StatelessWidget {
  const _StartupFailureApp({required this.error, required this.stack});

  final Object error;
  final StackTrace stack;

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        home: Scaffold(
          appBar: AppBar(title: const Text('Kiosk Satellite A6 Safe')),
          body: SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: ListView(
                children: [
                  const Text(
                    'Startup failed. Send a photo of this screen or the ADB log.',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 12),
                  SelectableText('$error\\n\\n$stack'),
                ],
              ),
            ),
          ),
        ),
      );
}

class KioskSatelliteApp"""
    replace_required(main, old_tail, new_tail)

    # Make process-wide Flutter startup survivable. On API 23 we force Skia
    # explicitly, catch plugin/bridge linkage errors, and let the Activity
    # create a fallback engine if the cached engine could not be made.
    application = app / "android/app/src/main/kotlin/me/jxl/kiosk_satellite/KioskApplication.kt"
    text = application.read_text(encoding="utf-8")
    text = text.replace("import android.util.Log", "import android.os.Build\nimport android.util.Log")
    text = text.replace(
        '        const val ENGINE_ID = "main"\n',
        '        const val ENGINE_ID = "main"\n        @Volatile var startupError: String? = null\n',
    )
    old_on_create = """    override fun onCreate() {
        super.onCreate()

        // Before any bridge: they all read volume state through it.
        VolumeController.init(applicationContext)

        // Renderer choice before the engine exists: old GPUs whose drivers
        // crash under Impeller get Skia instead (issue #127, RendererGuard).
        val engine = FlutterEngine(this, RendererGuard.engineArgs(this))
        // Plugins before the entrypoint: Dart main() starts the admin server and
        // reads shared_preferences immediately, so shared_preferences,
        // path_provider et al. must already be registered when it runs.
        GeneratedPluginRegistrant.registerWith(engine)
        engine.dartExecutor.executeDartEntrypoint(
            DartExecutor.DartEntrypoint.createDefault(),
        )
        FlutterEngineCache.getInstance().put(ENGINE_ID, engine)

        val messenger = engine.dartExecutor.binaryMessenger
        // Before the mic: MicRecorder resolves its preferred device through
        // AudioRouting, which the bridge initializes.
        audioRouting = AudioRoutingBridge(applicationContext, messenger)
        micRecorder = MicRecorder(applicationContext, messenger)
        background = BackgroundBridge(applicationContext, messenger)
        deviceDetails = DeviceDetails(applicationContext, messenger)
        brightness = BrightnessBridge(applicationContext, messenger)
        sendspin = SendspinBridge(applicationContext, messenger)
        soundPlayer = SoundPlayer(applicationContext, messenger)
        apkInstaller = ApkInstaller(applicationContext, messenger)
        lightSensor = LightSensor(applicationContext, messenger)
    }
"""
    new_on_create = """    override fun onCreate() {
        super.onCreate()
        try {
            VolumeController.init(applicationContext)
            val args = if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.M) {
                arrayOf("--enable-impeller=false")
            } else {
                RendererGuard.engineArgs(this)
            }
            val engine = FlutterEngine(this, args)
            try {
                GeneratedPluginRegistrant.registerWith(engine)
            } catch (t: Throwable) {
                startupError = "plugin registration: ${t.javaClass.name}: ${t.message}"
                Log.e("KioskApplication", startupError, t)
            }
            engine.dartExecutor.executeDartEntrypoint(
                DartExecutor.DartEntrypoint.createDefault(),
            )
            FlutterEngineCache.getInstance().put(ENGINE_ID, engine)

            val messenger = engine.dartExecutor.binaryMessenger
            fun safe(name: String, block: () -> Unit) {
                try { block() } catch (t: Throwable) {
                    Log.e("KioskApplication", "bridge $name failed", t)
                }
            }
            safe("audioRouting") { audioRouting = AudioRoutingBridge(applicationContext, messenger) }
            safe("micRecorder") { micRecorder = MicRecorder(applicationContext, messenger) }
            safe("background") { background = BackgroundBridge(applicationContext, messenger) }
            safe("deviceDetails") { deviceDetails = DeviceDetails(applicationContext, messenger) }
            safe("brightness") { brightness = BrightnessBridge(applicationContext, messenger) }
            safe("sendspin") { sendspin = SendspinBridge(applicationContext, messenger) }
            safe("soundPlayer") { soundPlayer = SoundPlayer(applicationContext, messenger) }
            safe("apkInstaller") { apkInstaller = ApkInstaller(applicationContext, messenger) }
            safe("lightSensor") { lightSensor = LightSensor(applicationContext, messenger) }
        } catch (t: Throwable) {
            startupError = "native startup: ${t.javaClass.name}: ${t.message}"
            Log.e("KioskApplication", startupError, t)
        }
    }
"""
    if old_on_create not in text:
        raise RuntimeError("KioskApplication.onCreate block not found")
    application.write_text(text.replace(old_on_create, new_on_create), encoding="utf-8")

    # If Application startup failed, use an Activity-owned engine. Register
    # its plugins normally and recreate the process-scoped bridges there.
    activity = app / "android/app/src/main/kotlin/me/jxl/kiosk_satellite/MainActivity.kt"
    text = activity.read_text(encoding="utf-8")
    text = text.replace("import android.view.MotionEvent", "import android.view.MotionEvent\nimport android.util.Log")
    fields = "    private var webViewFreeze: WebViewFreeze? = null\n"
    expanded_fields = """    private var webViewFreeze: WebViewFreeze? = null
    private var legacyAudioRouting: AudioRoutingBridge? = null
    private var legacyMicRecorder: MicRecorder? = null
    private var legacyBackground: BackgroundBridge? = null
    private var legacyDeviceDetails: DeviceDetails? = null
    private var legacyBrightness: BrightnessBridge? = null
    private var legacySendspin: SendspinBridge? = null
    private var legacySoundPlayer: SoundPlayer? = null
    private var legacyApkInstaller: ApkInstaller? = null
    private var legacyLightSensor: LightSensor? = null

    private fun safeNative(name: String, block: () -> Unit) {
        try { block() } catch (t: Throwable) {
            Log.e("MainActivity", "$name failed on legacy startup", t)
        }
    }
"""
    if fields not in text:
        raise RuntimeError("MainActivity field marker not found")
    text = text.replace(fields, expanded_fields)
    old_configure = """    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        // Deliberately not calling super: plugins are registered once on the
        // cached engine in KioskApplication. Only Activity-scoped bridges here.
        val messenger = flutterEngine.dartExecutor.binaryMessenger
"""
    new_configure = """    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        val cached = FlutterEngineCache.getInstance().get(KioskApplication.ENGINE_ID)
        val fallbackEngine = cached !== flutterEngine
        if (fallbackEngine) {
            super.configureFlutterEngine(flutterEngine)
        }
        val messenger = flutterEngine.dartExecutor.binaryMessenger
        if (fallbackEngine) {
            safeNative("volume") { VolumeController.init(applicationContext) }
            safeNative("audioRouting") { legacyAudioRouting = AudioRoutingBridge(applicationContext, messenger) }
            safeNative("micRecorder") { legacyMicRecorder = MicRecorder(applicationContext, messenger) }
            safeNative("background") { legacyBackground = BackgroundBridge(applicationContext, messenger) }
            safeNative("deviceDetails") { legacyDeviceDetails = DeviceDetails(applicationContext, messenger) }
            safeNative("brightness") { legacyBrightness = BrightnessBridge(applicationContext, messenger) }
            safeNative("sendspin") { legacySendspin = SendspinBridge(applicationContext, messenger) }
            safeNative("soundPlayer") { legacySoundPlayer = SoundPlayer(applicationContext, messenger) }
            safeNative("apkInstaller") { legacyApkInstaller = ApkInstaller(applicationContext, messenger) }
            safeNative("lightSensor") { legacyLightSensor = LightSensor(applicationContext, messenger) }
        }
"""
    if old_configure not in text:
        raise RuntimeError("MainActivity.configureFlutterEngine marker not found")
    text = text.replace(old_configure, new_configure)
    text = text.replace(
        """        deviceCamera = DeviceCamera(this, messenger)
        cameraMotion = CameraMotion(this, messenger, deviceCamera)
        screenCapture = ScreenCapture(this, messenger)
        kioskLock = KioskLock(this, messenger)
        webViewFreeze = WebViewFreeze(this, messenger)
""",
        """        safeNative("deviceCamera") { deviceCamera = DeviceCamera(this, messenger) }
        safeNative("cameraMotion") { cameraMotion = CameraMotion(this, messenger, deviceCamera) }
        safeNative("screenCapture") { screenCapture = ScreenCapture(this, messenger) }
        safeNative("kioskLock") { kioskLock = KioskLock(this, messenger) }
        safeNative("webViewFreeze") { webViewFreeze = WebViewFreeze(this, messenger) }
""",
    )
    text = text.replace(
        "        CrashSelfHeal.arm(this)\n",
        "        if (Build.VERSION.SDK_INT > Build.VERSION_CODES.M) CrashSelfHeal.arm(this)\n",
    )
    activity.write_text(text, encoding="utf-8")

    (root / "ANDROID6-SAFE-MODE.md").write_text(
        """# Android 6 Safe diagnostic build

- Separate application id: `me.jxl.kiosk_satellite.a6safe`
- Forces Skia on API 23
- Catches native plugin/bridge linkage errors
- Falls back to an Activity-owned Flutter engine
- Displays Dart startup exceptions on screen
- Disables crash-relaunch hooks on API 23
- Uses a larger heap for old low-memory tablets
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    patch(Path(sys.argv[1] if len(sys.argv) > 1 else "kiosk-satellite-android6"))

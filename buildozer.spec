[app]

# (string) Title of your application
title = DHK-OMR-Pro

# (string) Package name
package.name = dhkomrpro

# (string) Package domain (needed for android/ios packaging)
package.domain = org.dhk

# (string) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas

# (string) Application versioning (method 1)
version = 0.1

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,numpy,opencv

# (list) Permissions
android.permissions = CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support (MUST BE 24 FOR NUMPY)
android.minapi = 24

# (int) Android NDK API to use
android.ndk_api = 24

# (string) Android NDK version to use
android.ndk = 25b

# (string) Android Build Tools version to use
android.build_tools_version = 33.0.2

# (bool) If True, then skip trying to update the Android SDK
android.skip_update = False

# (bool) If True, then automatically accept SDK license
android.accept_sdk_license = True

# (list) The Android archs to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = arm64-v8a

# (bool) Copy library instead of making a libpymodules.so
android.copy_libs = 1

# (list) The format of logcat to use
android.logcat_filters = *:S python:D

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

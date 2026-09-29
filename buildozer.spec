[app]

# (str) Title of your application
title = DHK OMR Pro

# (str) Package name
package.name = dhkomrpro

# (str) Package domain (needed for android packaging)
package.domain = org.dhk

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json

# (str) Application versioning
version = 0.1

# (list) Application requirements
# Pinning python3==3.11.9 prevents the Python 3.14 cp314 unsupported wheel error
requirements = python3,kivy==2.3.0,pillow


# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen to not
fullscreen = 0

# (list) Permissions
android.permissions = CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# (int) Target Android API
android.api = 33

# (int) Minimum API your APK will support
android.minapi = 24

# (str) Android NDK version to use
android.ndk = 25b

# (int) Android NDK API to use
android.ndk_api = 24

# (bool) Skip trying to update the Android SDK
android.skip_update = False

# (bool) Automatically accept SDK license
android.accept_sdk_license = True

# (str) The Android arch to build for
android.archs = arm64-v8a

# (str) python-for-android branch to use
p4a.branch = master

# (bool) Enable Android auto backup feature
android.allow_backup = True

[buildozer]

# (int) Log level (2 = debug info)
log_level = 2

# (int) Warn on root (0 = don't prompt interactively)
warn_on_root = 0

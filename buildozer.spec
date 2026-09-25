[app]

# (str) Title of your application
title = DHK OMR Pro

# (str) Package name
package.name = dhkomrpro

# (str) Package domain (needed for android/ios packaging)
package.domain = org.dhk

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,pillow,numpy==1.26.4

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen to the user
fullscreen = 0

# (list) Permissions
android.permissions = CAMERA,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support.
android.minapi = 24

# (str) Android NDK version to use
android.ndk = 25b

# (str) Android build-tools version to use
android.build_tools_version = 33.0.2

# (bool) Automatically accept SDK licenses
android.accept_sdk_license = True

# (list) The Android archs to build for
android.archs = arm64-v8a

# (bool) Android logcat filters to showcase
android.logcat_filters = *:S python:D

# (bool) Copy library instead of making a libdir and dynamic link
android.copy_libs = 1

# (bool) Skip byte compile for .py files
android.no-byte-compile-python = False

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 0

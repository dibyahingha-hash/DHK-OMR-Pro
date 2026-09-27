[app]

# (str) Title of your application
title = DHK OMR Pro

# (str) Package name (lowercase, no spaces, letters only)
package.name = dhkomrpro

# (str) Package domain (needed for android packaging)
package.domain = org.dhk

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,kv,atlas,json,txt

# (list) Source files to exclude
source.exclude_exts = spec

# (list) Directory names to exclude
source.exclude_dirs = bin, .buildozer, tests

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# Added jpeg and png native recipes to satisfy Pillow's C headers
requirements = python3,kivy,pillow,pyjnius,jpeg,png

# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen
fullscreen = 0

#
# Android specific
#

# (list) Permissions
android.permissions = CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# (list) Features
android.features = android.hardware.camera,android.hardware.camera.autofocus

# (int) Target Android API level
android.api = 33

# (int) Minimum API supported (Android 7.0+)
android.minapi = 24

# (str) Android SDK build tools version
android.build_tools_version = 33.0.2

# (str) Android NDK version to use (Pins to stable 25b)
android.ndk = 25b

# (bool) Auto accept Android SDK license
android.accept_sdk_license = True

# (bool) Use private data storage
android.private_storage = True

# (str) Android logcat filters to use
android.logcat_filters = *:S python:D

# (bool) Copy library instead of making a libpymodules.so
android.copy_libs = 1

# (list) Target architecture
android.archs = arm64-v8a

# (bool) Enable Android auto backup feature
android.allow_backup = True

#
# Buildozer options
#

[buildozer]

# (int) Log level (2 = full debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1

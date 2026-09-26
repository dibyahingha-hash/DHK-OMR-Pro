[app]

# (str) Title of your application
title = DHK OMR Pro

# (str) Package name (lowercase, no spaces, letters only)
package.name = dhkomrpro

# (str) Package domain (needed for android packaging)
package.domain = org.dhk

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json,txt

# (list) List of inclusions using pattern matching
#source.include_patterns = assets/*,images/*.png

# (list) Source files to exclude (let empty to not exclude anything)
source.exclude_exts = spec

# (list) List of directory to exclude (let empty to not exclude anything)
source.exclude_dirs = bin, .buildozer, tests

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# Pure Python & lightweight imaging (NO opencv/numpy to prevent fatal start-up crashes)
requirements = python3,kivy,pillow

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen
fullscreen = 0

#
# Android specific
#

# (list) Permissions
android.permissions = CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# (list) Features (essential for live camera scanning & auto-focus)
android.features = android.hardware.camera,android.hardware.camera.autofocus

# (int) Target Android API level (33 or 34 recommended for modern Android devices)
android.api = 33

# (int) Minimum API supported (Android 7.0+)
android.minapi = 24

# (int) Android SDK version to use
#android.sdk = 33

# (str) Android NDK version to use
#android.ndk = 25b

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (str) Android logcat filters to use
android.logcat_filters = *:S python:D

# (bool) Copy library instead of making a libpymodules.so
android.copy_libs = 1

# (list) The Android archs to build for (arm64-v8a covers all modern phones)
android.archs = arm64-v8a, armeabi-v7a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (str) XML file for network security configuration
#android.network_security_config = 

# (list) Java classes to add to the android manifest
#android.add_activities = 

#
# Buildozer options
#

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

# (str) Path to build artifact storage
#build_dir = ./.buildozer

# (str) Path to build cache storage
#bin_dir = ./bin

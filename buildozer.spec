[app]

# Application metadata
title = DHK OMR Pro
package.name = dhkomrpro
package.domain = org.dhk

# Source configuration
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0

# Target dependencies
requirements = python3,kivy,pillow

# python-for-android stable release pin
p4a.branch = release-2024.01.21

# Display & permissions
orientation = portrait
fullscreen = 0
android.permissions = CAMERA,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# Android build environment
android.api = 33
android.minapi = 24
android.ndk = 25b
android.build_tools_version = 33.0.2
android.accept_sdk_license = True
android.archs = arm64-v8a
android.copy_libs = 1
android.logcat_filters = *:S python:D

[buildozer]

log_level = 2
warn_on_root = 0

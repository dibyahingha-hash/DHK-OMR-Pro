[app]
title = DHK OMR Pro
package.name = dhkomrpro
package.domain = org.dhk
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0

# OpenCV recipe in python-for-android requires numpy
requirements = python3,kivy,numpy,opencv

orientation = portrait
fullscreen = 0

# Android permissions & SDK settings
android.permissions = CAMERA,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.build_tools_version = 33.0.2
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1

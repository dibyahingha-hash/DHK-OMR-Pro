[app]

# Title of your application
title = DHK OMR Pro

# Package name
package.name = dhkomrpro

# Package domain (needed for android packaging)
package.domain = org.dhk

# Source code where the main.py lives
source.dir = .

# Source files to include
source.include_exts = py,png,jpg,kv,atlas,json

# Application versioning
version = 0.1

# Application requirements
requirements = python3,kivy,pillow

# Supported orientation
orientation = portrait

# Fullscreen toggle
fullscreen = 0

# Android permissions needed for camera & storage
android.permissions = CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# Android API targeting
android.api = 33
android.minapi = 24

# Let Buildozer auto-match the compatible NDK
# android.ndk = 

# Skip SDK update prompt
android.skip_update = False

# Automatically accept SDK licenses
android.accept_sdk_license = True

# Target modern 64-bit Android architecture
android.archs = arm64-v8a

# Allow Android backup
android.allow_backup = True

[buildozer]

# Log level (2 = debug info)
log_level = 2

# Warn on root
warn_on_root = 1

[app]
title = 팔찌 반납 확인
package.name = rfidcheck
package.domain = org.wisehealth

source.dir = .
source.include_exts = py,png,jpg,kv,json

version = 1.0.0

requirements = python3,kivy==2.3.0,sqlite3

orientation = portrait
fullscreen = 0

android.permissions = NFC
android.features = android.hardware.nfc

android.minapi = 26
android.api = 34
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1

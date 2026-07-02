[app]
title = 팔찌 반납 확인
package.name = rfidcheck
package.domain = org.wisehealth

source.dir = .
source.include_exts = py,png,jpg,kv,json,db

version = 1.0.0

requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

android.permissions = android.permission.NFC

android.minapi = 21
android.api = 33
android.ndk = 25b
android.ndk_api = 21
android.accept_sdk_license = True
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1

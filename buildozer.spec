[app]
title = 팔찌 반납 확인
package.name = rfidcheck
package.domain = org.wisehealth

source.dir = .
source.include_exts = py,png,jpg,kv,json

version = 1.0.0

requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

android.permissions = NFC
android.features = android.hardware.nfc

android.minapi = 26
android.api = 31
android.ndk = 23b
android.ndk_api = 26
android.accept_sdk_license = True
android.archs = arm64-v8a

# SDK/NDK 경로는 환경변수(ANDROIDSDK/ANDROIDNDK)로 전달하므로 spec에서 제거

[buildozer]
log_level = 2
warn_on_root = 1

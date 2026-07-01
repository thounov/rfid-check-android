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

# SDK/NDK 경로 — GitHub Actions에서 미리 설치한 경로를 사용
android.sdk_path = /root/.buildozer/android/platform/android-sdk
android.ndk_path = /root/.buildozer/android/platform/android-ndk-r23b

[buildozer]
log_level = 2
warn_on_root = 1

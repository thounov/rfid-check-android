# RFID 팔찌 반납 확인 - Android 독립 앱

서버 없이 스마트폰 단독으로 동작합니다.
데이터는 폰 내부 SQLite DB에 저장됩니다.

---

## APK 빌드 방법 (GitHub Actions)

### 1단계: GitHub 저장소 만들기
1. https://github.com 로그인
2. 우측 상단 + → New repository
3. 이름: `rfid-check-android`, Public 선택
4. Create repository 클릭

### 2단계: 파일 올리기 (git 명령어 권장)
```bash
git init
git add .
git commit -m "first commit"
git remote add origin https://github.com/계정명/rfid-check-android.git
git push -u origin main
```

※ .github 폴더가 반드시 포함되어야 합니다.

### 3단계: APK 다운로드
1. GitHub → Actions 탭 클릭
2. Build Android APK 워크플로우 실행 확인 (처음 30~50분)
3. 완료 후 Artifacts → rfid-check-apk 다운로드
4. zip 압축 해제 → .apk 파일 스마트폰으로 전송 후 설치

### 4단계: 설치
- 스마트폰 설정 → 보안 → 알 수 없는 앱 설치 허용
- apk 파일 탭하여 설치

---

## 앱 기능

| 탭 | 기능 |
|---|---|
| 📡 스캔 | NFC 태그 또는 직접 입력으로 반납 처리 |
| 📋 현황 | 미반납 / 반납완료 / 분실 배지 그리드, 탭하면 상태 변경 |
| ⚙ 관리 | 팔찌 등록(NFC로 UID 읽기 가능) / 삭제 / 마감 초기화 |
| 🎨 색상 | 팔찌 색상 추가 / 삭제 |

---

## PC 앱과 데이터 공유

PC 앱(main.py)과 데이터를 공유하려면 server.py + start_server.bat을
같이 사용하면 됩니다. 독립 모드에서는 폰에만 데이터가 저장됩니다.


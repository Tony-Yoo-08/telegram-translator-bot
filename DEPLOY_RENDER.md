# Render.com 무료 클라우드 배포 가이드 (카드 등록 0% / 100% 무료)

Render 클라우드를 통해 내 컴퓨터를 꺼도 24시간 내내 텔레그램 번역 봇이 작동하도록 배포하는 방법입니다.

---

## 📌 준비 사항 (모두 신용카드 등록 없음)
1. **GitHub 계정** ([github.com](https://github.com/))
2. **Render 계정** ([render.com](https://render.com/))
3. **UptimeRobot 계정** ([uptimerobot.com](https://uptimerobot.com/))

---

## 1단계: GitHub에 코드 올리기

1. [GitHub](https://github.com/) 로그인 후 우측 상단 **`+` ➡️ `New repository`** 클릭
2. Repository name 입력: `telegram-translator-bot`
3. 공개 범위: **Private** 또는 Public 선택 (Private 권장)
4. `Create repository` 클릭
5. 프로젝트 폴더의 파일들을 업로드합니다:
   - **올릴 파일들**:
     - `bot.py`
     - `translator.py`
     - `requirements.txt`
     - `render.yaml`
     - `.gitignore`
   - ⚠️ **주의**: `.env` 파일은 절대 올리지 마세요! (토큰 보안)

---

## 2단계: Render.com에서 배포하기

1. [Render.com](https://render.com/) 접속 후 **`Sign In` ➡️ `GitHub`** 아이콘 클릭하여 로그인 (카드 등록 창 없음)
2. 대시보드 우측 상단 **`New +` ➡️ `Web Service`** 클릭
3. **`Build and deploy from a Git repository`** 선택 후 `Next`
4. 방금 만든 `telegram-translator-bot` 저장소 우측의 **`Connect`** 클릭
5. 기본 설정 확인:
   - **Name**: `telegram-translator-bot` (원하는 이름)
   - **Region**: Singapore 또는 Oregon
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Instance Type**: **`Free`** ($0/month)
6. **Environment Variables (환경변수) 추가**:
   - `Add Environment Variable` 클릭 후 아래 입력:
     - Key: `TELEGRAM_BOT_TOKEN`
     - Value: `8582435459:AAELB_C3EMvtFFv4eaWWO2ubK1Xvax3dB2E`
     - (추후 DeepL 사용 시 `DEEPL_API_KEY`도 여기에 추가하시면 됩니다.)
7. 맨 아래 **`Deploy Web Service`** 버튼 클릭!
8. 약 1~2분 뒤 로그에 `Telegram Translator Bot is active and running!` 메시지가 뜨며 배포가 완료됩니다.
9. 상단에 생성된 고유 웹 주소를 복사합니다:
   - 예시: `https://telegram-translator-bot-xxxx.onrender.com`

---

## 3단계: 24시간 절전 방지 설정 (UptimeRobot)

Render 무료 플랜은 15분간 요청이 없으면 잠에 듭니다. 이를 5분마다 찔러서 깨워주면 24시간 365일 무중단으로 작동합니다!

1. [UptimeRobot](https://uptimerobot.com/) 회원가입 및 로그인 (카드 불필요)
2. 대시보드에서 **`+ Add New Monitor`** 클릭
3. 설정값 입력:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Telegram Bot`
   - **URL (or IP)**: Render에서 복사한 주소 붙여넣기 (`https://telegram-translator-bot-xxxx.onrender.com`)
   - **Monitoring Interval**: `5 minutes` (기본값)
4. 맨 아래 **`Create Monitor`** 클릭

🎉 **축하합니다! 이제 내 컴퓨터를 꺼도 텔레그램 번역 봇이 24시간 내내 단체방에서 살아있습니다.**

---

## 4단계: 깃허브 업데이트 시 대화방 번역 설정 영구 보존하기 (필독)

Render 무료 플랜은 깃허브에 코드를 올려 새로 배포될 때마다 **내부 임시 파일(DB)이 새로 생성**됩니다.  
이 때문에 업데이트 후 기존 방들의 설정이 기본값(5개국어 전체)으로 초기화될 수 있습니다.

### 💡 해결 방법 (Render 환경변수에 영구 고정):
1. 봇과의 1:1 대화창(DM)에서 `/export_settings` 명령어를 입력하거나, `/groups` 메뉴 하단의 **[📋 Render 영구보존 설정 복사]** 버튼을 누릅니다.
2. 출력된 `GROUP_LANG_MAP` 값(예: `-100123456789:ko-en, -100987654321:ko-vi`)을 복사합니다.
3. [Render 대시보드](https://dashboard.render.com/) 접속 ➡️ 내 봇 서비스 클릭 ➡️ 좌측 **`Environment`** 탭 클릭
4. **`Add Environment Variable`** 클릭:
   - **Key**: `GROUP_LANG_MAP`
   - **Value**: 복사한 방 설정값 붙여넣기
   - *(선택)* **Key**: `DEFAULT_LANG_MODE` / **Value**: `ko-en` (미설정 신규 방의 기본 언어)
5. **`Save Changes`** 클릭!

✅ 이제 깃허브에 코드를 몇 번 업데이트하더라도, **기존 방들의 번역 언어 설정이 절대 날아가지 않고 100% 영구 보존**됩니다!

# 🚀 AI Git Assistant (MVP)

**PySide6 GUI**와 **로컬 Ollama 모델**을 활용하여 Git staged 변경사항을 분석하고, **AI가 커밋 메시지를 자동 생성**해주는 안전한 데스크톱 도구입니다.

복잡한 설정 파일 수정 없이, **앱 내 설정 메뉴**에서 직관적으로 모든 환경을 제어할 수 있습니다.

## 🌟 주요 기능

- **📂 프로젝트 관리**: Git 저장소를 손쉽게 열고 스테이지/언스테이지 파일 상태를 한눈에 파악합니다.
- **🧠 AI 커밋 메시지**: 로컬 LLM(Ollama)이 변경 사항(Diff)을 분석하여 문맥에 맞는 커밋 메시지를 제안합니다.
- **⚙️ 간편한 UI 설정**: 타임아웃, Diff 크기 제한, 모델 선택 등 모든 옵션을 앱 내 **'설정(Settings)'** 메뉴에서 변경합니다.
- **🛡️ 안전한 커밋 (Safe Commit)**:
  - 대용량 변경 사항 감지 및 경고
  - 실수 방지를 위한 크기 검사 로직 내장
- **⚡ 작업 제어**: AI 분석이 길어질 경우 언제든 작업을 취소할 수 있는 비동기 처리 지원.

## 🛠️ 요구사항

- **Python 3.9+**
- **Git** (시스템 경로에 설치됨)
- **Ollama** (로컬 AI 구동용)

## 📥 설치 (Installation)

⚠️ **주의**: 이 프로젝트는 기여와 관리를 위해 **반드시 Fork 후 설치**를 진행해 주세요. (ZIP 다운로드 금지)

### 1. GitHub에서 프로젝트 Fork
상단의 `Fork` 버튼을 눌러 본인의 계정으로 저장소를 가져옵니다.

### 2. Fork된 저장소 클론
```bash
# 본인 계정의 저장소를 클론합니다
git clone [https://github.com/YOUR_USERNAME/ai-git-assistant1.git](https://github.com/YOUR_USERNAME/ai-git-assistant1.git)
cd ai-git-assistant1
```
### 3. 가상환경 생성 및 의존성 설치
```bash
# 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# 패키지 설치
pip install -r requirements.txt
```
## 🦙 로컬 Ollama 설정 (필수)

AI 기능을 사용하기 위해 로컬 환경에 Ollama가 실행 중이어야 합니다.

```bash
# 1. Ollama 설치 ([https://ollama.ai](https://ollama.ai))
#    macOS: brew install ollama
#    Windows/Linux: 공식 사이트 참조
```
# 2. 모델 다운로드 (기본 권장 모델)
ollama pull exaone3.5:2.4b

# 3. 백그라운드 서비스 실행
ollama serve

## 🚀 실행 및 설정 가이드

### 1. 앱 실행
```bash
python main.py
```
### 2. ⚙️ 앱 내 설정 (Settings)
앱 실행 후 우측 상단의 **[설정]** 버튼을 누르면 다음 항목들을 조정할 수 있습니다. **복잡하게 파일을 직접 수정할 필요가 없습니다.**

- **AI Model**: 사용할 Ollama 모델 이름 (기본값: `exaone3.5:2.4b`)
- **Max Diff Size**: AI에게 보낼 최대 코드 변경량 (기본값: 2MB)
- **Timeout**: AI 응답 대기 시간 (기본값: 30초)

> **참고**: 설정한 내용은 `~/.ai-git-assistant/config.json` 경로에 자동으로 저장되어 다음 실행 시에도 유지됩니다.

---

## 👨‍💻 개발자용 옵션 (Advanced)

일반 사용자는 이 단계가 필요하지 않으나, 개발 및 디버깅 목적으로 다음 환경 변수를 사용할 수 있습니다.

**Mock 모드 (AI 없이 테스트)**
Ollama가 설치되지 않은 환경에서 UI/UX를 테스트하려면 아래 명령어로 실행하세요.
```bash
# AI 호출을 가짜(Mock) 응답으로 대체
AI_MOCK_MODE=1 python main.py
```
## 📂 프로젝트 구조
```
.
├── backend/
│   ├── config.py         # 설정 입출력 관리
│   ├── git_utils.py      # Git 명령어 및 Safe Commit 로직
│   └── ollama_client.py  # Ollama API 통신
├── ui/
│   └── main_window.py    # PySide6 메인 화면 및 설정 다이얼로그
├── scripts/
│   └── e2e_simulate.py   # E2E 테스트 스크립트
├── main.py               # 앱 진입점
└── requirements.txt      # 필요 라이브러리 목록
```

## 🗓️ 향후 로드맵 (Roadmap)

- [ ] **커밋 히스토리 뷰어**: 이전 커밋 내역 확인 및 수정
- [ ] **프롬프트 커스터마이징**: 사용자별 맞춤 AI 명령어 설정 기능
- [ ] **Diff 미리보기**: 커밋 전 변경사항을 앱 내에서 시각적으로 확인
- [ ] **다중 모델 지원**: 원격 API 및 다양한 로컬 모델 선택지 확장

## 📄 라이선스

MIT License


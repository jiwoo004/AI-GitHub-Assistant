````markdown
# AI Git Assistant (MVP)

PySide6 GUI와 로컬 Ollama 모델을 사용하여 Git staged 변경사항의 diff를 분석해 커밋 메시지를 생성하고 안전하게 커밋을 실행하는 도구입니다.

## 주요 기능

- **프로젝트 열기**: Git 저장소를 선택해 스테이지된/언스테이지된 파일 목록 표시
- **AI 커밋 메시지 생성**: 스테이지된 diff를 Ollama 로컬 모델에 보내 커밋 메시지 자동 생성
- **안전한 커밋**: 크기 검사(safe_commit) 및 큰 변경사항에 대한 경고
- **설정 조정**: UI에서 diff 경고 임계값과 AI 타임아웃 조정 가능 (설정은 `~/.ai-git-assistant/config.json`에 저장)
- **작업 취소**: 긴 작업 중 UI에서 취소 버튼으로 중단 가능

## 요구사항

- Python 3.9+
- Git 설치
- Ollama 설치 및 모델 준비 (기본: `exaone3.5:2.4b`)

## 설치

```bash
# 1. 프로젝트 클론 또는 다운로드 후
cd ai-git-assistant1

# 2. 가상환경 생성
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# 또는
.venv\Scripts\activate  # Windows

# 3. 의존성 설치
pip install -r requirements.txt

# 4. (선택) 개발용 의존성 설치 (테스트 실행 시)
pip install -r requirements-dev.txt
```

## 로컬 Ollama 설정

이 프로젝트는 로컬 Ollama 데몬을 사용하도록 설계되었습니다.

```bash
# 1. Ollama 설치 (공식 사이트: https://ollama.ai)
#    macOS: brew install ollama
#    Linux: curl https://ollama.ai/install.sh | sh
#    Windows: 설치 프로그램 다운로드

# 2. 모델 풀다운
ollama pull exaone3.5:2.4b

# 3. Ollama 데몬 시작 (백그라운드)
ollama serve
```

## 실행

```bash
# 기본 모드 (로컬 Ollama 필요)
python main.py

# Mock 모드 (개발/테스트용, Ollama 없이 동작)
AI_MOCK_MODE=1 python main.py
```

## 환경 변수

- **OLLAMA_MODEL**: 사용할 Ollama 모델 (기본: `exaone3.5:2.4b`)
- **AI_MOCK_MODE**: 모의(mock) 모드 활성화 (값: `1`이면 활성화, Ollama 호출 없음)

## 설정 파일

사용자 설정은 `~/.ai-git-assistant/config.json`에 자동 저장됩니다.

```json
{
  "max_diff_bytes": 2000000,
  "ai_timeout_seconds": 30.0
}
```

- **max_diff_bytes**: diff 크기 경고 임계값 (바이트, 기본: 2MB, 범위: 100KB ~ 100MB)
- **ai_timeout_seconds**: Ollama 호출 타임아웃 (초, 기본: 30초, 범위: 5 ~ 300초)

## 테스트

```bash
# 단위 테스트 실행 (git_utils)
pytest -q

# E2E 시뮬레이션 (전체 워크플로우, mock Ollama 사용)
python scripts/e2e_simulate.py

# 깃 유틸리티 진단
python scripts/check_git_utils.py /path/to/repo
```

## 프로젝트 구조

```
.
├── backend/
│   ├── config.py           # 설정 관리 (저장/불러오기)
│   ├── git_utils.py        # Git 명령어 래퍼
│   ├── ollama_client.py    # Ollama 호출 (timeout/retry/mock)
├── ui/
│   └── main_window.py      # PySide6 메인 UI + 설정 다이얼로그
├── tests/
│   ├── conftest.py         # pytest 설정
│   └── test_git_utils.py   # git_utils 단위 테스트
├── scripts/
│   ├── check_git_utils.py  # git_utils 진단 스크립트
│   └── e2e_simulate.py     # E2E 시뮬레이션 (mock Ollama)
├── main.py                 # 앱 진입점
├── requirements.txt        # 런타임 의존성
└── requirements-dev.txt    # 개발용 의존성
```

## 주요 개선 사항 (MVP 이후)

- [ ] 커밋 히스토리 표시 및 재시도
- [ ] 커스텀 프롬프트 템플릿
- [ ] 여러 모델 지원 (로컬 + 원격)
- [ ] 커밋 전 diff 미리보기
- [ ] 설정 UI 고급 옵션 확장

## 라이선스

MIT
````

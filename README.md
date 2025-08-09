# AI Meeting Orchestrator

Notion 회의록을 분석하여 자동으로 Jira 티켓을 생성하는 Streamlit 기반 대화형 도구입니다. Claude Code와 Atlassian MCP를 활용합니다.

## 주요 기능

- 📋 Notion 데이터베이스에서 회의록 자동 불러오기
- 🤖 Claude AI를 통한 회의록 분석 및 액션 아이템 추출
- 🎫 Jira 티켓 자동 생성 및 관리
- 💬 대화형 인터페이스로 티켓 내용 수정 가능
- ⚙️ Claude Code + MCP (Model Context Protocol) 활용

## 사전 요구사항

### 1. Python 환경
- Python 3.11 이상
- uv 패키지 매니저 (권장)

### 2. Claude Code CLI
- Claude Code CLI 설치 및 Anthropic API 키 설정

### 3. 외부 서비스 계정
- **Notion**: API 키 및 데이터베이스 ID
- **Jira**: 인스턴스 URL, 사용자명, API 토큰

## 설치 및 설정

### 1. 프로젝트 클론 및 의존성 설치

```bash
git clone <repository-url>
cd jira-dashboard

# uv를 사용하는 경우 (권장)
uv sync

# 또는 pip를 사용하는 경우
pip install -r pyproject.toml
```

### 2. Claude Code CLI 설치

```bash
# Claude Code CLI 설치 (MacOS/Linux)
curl -fsSL https://claude.ai/install.sh | sh

# 설치 후 로그인
claude login
```

### 3. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 정보를 입력하세요:

```bash
# Anthropic API
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Notion API 설정
NOTION_API_KEY=your_notion_api_key_here
NOTION_DATABASE_ID=your_notion_database_id_here

# Jira 설정
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your_jira_email@example.com
JIRA_API_TOKEN=your_jira_api_token_here

# Claude MCP 자동 연결
CLAUDE_MCP_AUTO_CONNECT=true
```

### 4. Atlassian MCP 설정

Claude Code에서 Atlassian MCP 서버를 설정하세요:

```bash
# MCP 서버 추가 (대화형으로 Jira 인증 정보 입력)
claude mcp add atlassian

# 또는 MCP 설정 파일을 직접 사용
cp mcp-config.json ~/.config/claude-cli/mcp-config.json
```

### 5. Notion 설정

#### 5.1 Notion API 키 생성
1. [Notion Developers](https://developers.notion.com/)에서 새 integration 생성
2. API 키 복사하여 `.env` 파일에 추가

#### 5.2 회의록 데이터베이스 설정
1. Notion에서 회의록용 데이터베이스 생성
2. 데이터베이스를 integration과 공유
3. 데이터베이스 URL에서 ID 추출하여 `.env` 파일에 추가

### 6. Jira API 토큰 생성

1. [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)에서 API 토큰 생성
2. 토큰을 `.env` 파일에 추가

## 실행 방법

### 개발 환경에서 실행

```bash
# uv를 사용하는 경우
uv run streamlit run main.py

# 또는 직접 실행
streamlit run main.py
```

### 배포 환경에서 실행

```bash
# Streamlit Cloud, Heroku 등에 배포 시
streamlit run main.py --server.port $PORT --server.address 0.0.0.0
```

## 사용 방법

1. **웹 애플리케이션 접속**: 브라우저에서 `http://localhost:8501` 접속

2. **회의록 선택**: 사이드바에서 분석하고 싶은 회의록 선택

3. **분석 시작**: 채팅창에 "분석 시작" 입력

4. **결과 검토**: AI가 추천한 Jira 티켓 내용을 확인하고 필요시 수정

5. **티켓 생성**: "티켓 생성" 또는 "생성" 입력하여 실제 Jira 티켓 생성

### 주요 명령어

- `분석 시작` / `분석해` / `시작`: 선택한 회의록 분석 시작
- `티켓 생성` / `생성` / `만들어` / `진행`: 검토된 티켓들을 Jira에 실제 생성
- 기타 자연어 요청: 티켓 내용 수정, 질문 등

## 문제 해결

### Claude Code 관련 문제

```bash
# Claude Code 버전 확인
claude --version

# MCP 연결 상태 확인
claude mcp list

# 로그 확인
claude --verbose
```

### 환경변수 문제

```bash
# 환경변수 로드 확인
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('NOTION_API_KEY:', bool(os.getenv('NOTION_API_KEY')))"
```

### Streamlit 관련 문제

```bash
# Streamlit 설정 초기화
streamlit config show

# 캐시 정리
streamlit cache clear
```

## 프로젝트 구조

```
jira-dashboard/
├── main.py                 # 메인 Streamlit 애플리케이션
├── pyproject.toml          # Python 의존성 설정
├── mcp-config.json         # Claude MCP 설정 파일
├── .env                    # 환경변수 (생성 필요)
├── uv.lock                 # uv 락 파일
└── README.md               # 이 파일
```

## 기술 스택

- **Frontend**: Streamlit
- **AI**: Claude 3.5 Sonnet (via Claude Code CLI)
- **MCP**: Atlassian MCP Server
- **Integration**: Notion API, Jira REST API
- **Language**: Python 3.11+

## 주의사항

- API 키와 토큰은 절대 공개하지 마세요
- `.env` 파일을 git에 커밋하지 마세요
- Notion 데이터베이스 권한을 적절히 설정하세요
- Jira 프로젝트에 티켓 생성 권한이 있는지 확인하세요

## 라이선스

이 프로젝트는 개인/교육용으로 사용하세요.
EOF < /dev/null
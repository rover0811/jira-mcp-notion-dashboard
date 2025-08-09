import streamlit as st
import os
import subprocess
import json
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client

# --------------------------------------------------------------------------
# 0. 설정 및 초기화
# --------------------------------------------------------------------------

st.set_page_config(
    layout="wide",
    page_title="AI Meeting Orchestrator Chat",
    page_icon="🤖"
)

load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

script_dir = os.path.dirname(os.path.abspath(__file__))

if not all([NOTION_API_KEY, NOTION_DATABASE_ID]):
    st.error("`.env` 파일에 NOTION_API_KEY, NOTION_DATABASE_ID를 설정해주세요.")
    st.stop()

notion = Client(auth=NOTION_API_KEY)

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_meeting" not in st.session_state:
    st.session_state.selected_meeting = None
if "workflow_stage" not in st.session_state:
    st.session_state.workflow_stage = "start"  # start, analyzing, discussing, creating
if "project_key" not in st.session_state:
    st.session_state.project_key = "SCRUM"


# --------------------------------------------------------------------------
# 1. 핵심 기능 함수
# --------------------------------------------------------------------------

@st.cache_data(ttl=600)
def get_recent_meetings(_notion_client, _database_id, page_size=10):
    """Notion DB에서 최근 회의록들을 가져옵니다."""
    try:
        raw_pages = _notion_client.databases.query(
            database_id=_database_id,
            page_size=page_size,
        ).get("results")

        meetings = []
        for page in raw_pages:
            title_parts = page["properties"].get("Name", {}).get("title", [])
            if not title_parts:
                continue
            title = "".join([part["plain_text"] for part in title_parts])

            blocks = _notion_client.blocks.children.list(block_id=page["id"]).get("results")
            content = "\n".join(
                text_part["plain_text"]
                for block in blocks
                if "rich_text" in block.get(block.get("type", {}), {})
                for text_part in block[block["type"]]["rich_text"]
            )
            meetings.append({"title": title, "content": content})
        return meetings
    except Exception as e:
        st.error(f"Notion 데이터 로딩 실패: {e}")
        return []


def call_claude_code_streaming(prompt, context="", placeholder=None):
    """Claude Code를 통해 프롬프트를 스트리밍으로 실행합니다."""
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    current_env = os.environ.copy()
    
    # MCP 인증을 위한 환경변수 명시적 설정
    current_env.update({
        'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
        'JIRA_URL': os.getenv('JIRA_URL'),
        'JIRA_USERNAME': os.getenv('JIRA_USERNAME'),  
        'JIRA_API_TOKEN': os.getenv('JIRA_API_TOKEN'),
        'CLAUDE_MCP_AUTO_CONNECT': 'true'
    })

    try:
        command = ['claude', '--print']

        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            bufsize=1,
            universal_newlines=True,
            env=current_env,
            cwd=script_dir,
            user=os.geteuid(),
            group=os.getegid()
        )

        process.stdin.write(full_prompt)
        process.stdin.close()

        output_lines = []
        if placeholder:
            current_text = ""
            for line in iter(process.stdout.readline, ''):
                current_text += line
                output_lines.append(line.rstrip())
                placeholder.markdown(current_text)
        else:
            output_lines = process.stdout.readlines()

        error_output = process.stderr.read()
        return_code = process.wait(timeout=120)

        return {
            'success': return_code == 0,
            'output': ''.join(output_lines).strip(),
            'error': error_output.strip()
        }

    except subprocess.TimeoutExpired:
        if 'process' in locals() and process.poll() is None:
            process.kill()
        return {'success': False, 'output': '', 'error': '작업 시간이 초과되었습니다'}
    except Exception as e:
        return {'success': False, 'output': '', 'error': f'실행 중 오류: {str(e)}'}


def call_claude_code(prompt, context=""):
    """Claude Code를 통해 프롬프트를 실행합니다 (비스트리밍)."""
    return call_claude_code_streaming(prompt, context, placeholder=None)


def call_claude_code_with_mcp_streaming(prompt, project_key, placeholder=None):
    """MCP 서버를 활용한 Claude Code 스트리밍 호출"""
    # MCP 도구 사용 가능한지 먼저 확인하고 시작
    mcp_init_prompt = """먼저 MCP Atlassian 도구들이 사용 가능한지 확인해주세요. 사용 가능하다면 "MCP 연결됨"이라고 답변하고, 그렇지 않다면 "MCP 연결 실패"라고 답변해주세요."""
    
    full_prompt = f"""당신은 회의록 분석 및 Jira 티켓 생성을 도와주는 AI 어시스턴트입니다.

MCP의 Atlassian 도구들을 사용할 수 있습니다:
- mcp__atlassian__createJiraIssue: Jira 티켓 생성
- mcp__atlassian__searchJiraIssuesUsingJql: Jira 이슈 검색
- mcp__atlassian__getVisibleJiraProjects: 프로젝트 조회

프로젝트 키: {project_key}

{prompt}

응답할 때는 자연스러운 대화체로 답변해주세요."""

    return call_claude_code_streaming(full_prompt, "", placeholder)


def call_claude_code_with_mcp(prompt, project_key):
    """MCP 서버를 활용한 Claude Code 호출 (비스트리밍)"""
    return call_claude_code_with_mcp_streaming(prompt, project_key, placeholder=None)


def add_message(role, content, metadata=None):
    """채팅 메시지를 세션에 추가합니다."""
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(),
        "metadata": metadata or {}
    })


def display_chat_messages():
    """채팅 메시지들을 화면에 표시합니다."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "metadata" in message and "tickets" in message["metadata"]:
                with st.expander("🎫 제안된 티켓들"):
                    for i, ticket in enumerate(message["metadata"]["tickets"]):
                        st.write(f"**{i + 1}. {ticket.get('summary', '제목 없음')}**")
                        st.write(ticket.get('description', '설명 없음'))
                        st.divider()


def check_claude_code_setup():
    """Claude Code가 제대로 설치되고 설정되었는지 확인"""
    try:
        result = subprocess.run(
            ['claude', '--version'],
            capture_output=True, text=True, timeout=10, env=os.environ.copy(), cwd=script_dir, user=os.geteuid(),
            group=os.getegid()

        )
        if result.returncode == 0:
            return True, f"Claude Code 설치됨: {result.stdout.strip()}"
        else:
            return False, f"Claude Code가 설치되지 않았거나 PATH에 없습니다: {result.stderr.strip()}"
    except Exception as e:
        return False, f"Claude Code 확인 중 오류: {str(e)}"


def check_mcp_connection():
    """Claude Code의 MCP Atlassian 연결 상태 확인 - shell=True 방식"""
    try:
        # zsh를 명시적으로 사용하고 로그인 쉘로 실행
        test_prompt = "MCP Atlassian 도구가 사용 가능한지 간단히 '연결됨' 또는 '연결 실패'라고만 답변해주세요."

        # 방법 1: zsh 로그인 쉘로 실행
        cmd = f'echo "{test_prompt}" | claude --print'
        result = subprocess.run(
            ['/bin/zsh', '-l', '-c', cmd],  # -l: 로그인 쉘로 실행
            capture_output=True,
            text=True,
            timeout=15,
            cwd=script_dir
        )

        if result.returncode == 0 and "연결됨" in result.stdout:
            return True, "Claude Code MCP Atlassian 연결 확인됨"
        else:
            error_details = result.stderr.strip() or result.stdout.strip()
            return False, f"Claude Code MCP 연결 실패: {error_details}"

    except Exception as e:
        return False, f"MCP 연결 확인 중 오류: {str(e)}"


# --------------------------------------------------------------------------
# 2. 워크플로우 핸들러
# --------------------------------------------------------------------------

def handle_meeting_analysis():
    """회의록 분석을 처리합니다."""
    if not st.session_state.selected_meeting:
        add_message("assistant", "먼저 사이드바에서 분석할 회의록을 선택해주세요! 📋")
        return

    with st.chat_message("assistant"):
        with st.spinner("🔍 Claude가 회의록을 분석 중입니다..."):
            placeholder = st.empty()
            prompt = f"""다음 회의록을 분석해서 Jira 티켓으로 만들 수 있는 액션 아이템들을 추출해주세요:

=== 회의록 ===
{st.session_state.selected_meeting["content"]}

=== 요청사항 ===
1. 회의록에서 구체적이고 실행 가능한 액션 아이템들을 찾아주세요.
2. 각 액션 아이템을 Jira 티켓 형태로 '제목(summary)'과 '설명(description)'으로 명확히 구분해서 정리해주세요.
3. 너무 일반적이거나 모호한 내용은 제외해주세요.
4. 각 티켓에 대해 간단히 설명해주세요.
5. 티켓은 아직 생성하지 말고, 어떤 티켓들을 만들 수 있는지 제안만 해주세요."""

            result = call_claude_code_streaming(prompt, "", placeholder)

    if result['success']:
        response_content = f"**'{st.session_state.selected_meeting['title']}'** 회의록을 분석했습니다! 🎯\n\n{result['output']}\n\n이 티켓들을 생성하시겠습니까? 수정하고 싶은 부분이 있다면 말씀해주세요!"
        add_message("assistant", response_content)
        st.session_state.workflow_stage = "discussing"
    else:
        add_message("assistant", f"분석 중 오류가 발생했습니다: {result['error']}")


def handle_ticket_creation():
    """최종 티켓 생성을 처리합니다."""
    with st.chat_message("assistant"):
        with st.spinner("🎫 Claude가 MCP를 통해 Jira 티켓들을 생성 중입니다..."):
            placeholder = st.empty()
            tickets_context = "\n".join([msg["content"] for msg in st.session_state.messages[-5:]])
            prompt = f"""다음 티켓들을 Jira에 실제로 생성해주세요.

프로젝트 키: {st.session_state.project_key}

이전 대화 내용:
{tickets_context}

MCP의 `create_jira_issue` 도구를 사용해서 앞서 논의한 각 티켓을 생성하고, 생성된 티켓의 키와 URL을 알려주세요.
각 티켓은 다음 형식으로 생성해주세요:
- 이슈 타입: Task
- 우선순위: Medium (달리 명시되지 않은 경우)
- 적절한 제목과 상세 설명 포함"""

            result = call_claude_code_with_mcp_streaming(
                prompt, st.session_state.project_key, placeholder
            )

    if result['success']:
        response_content = f"🎉 티켓 생성이 완료되었습니다!\n\n{result['output']}\n\n추가로 필요한 작업이 있으시면 언제든 말씀해주세요!"
        add_message("assistant", response_content)
        st.session_state.workflow_stage = "completed"
    else:
        add_message("assistant", f"티켓 생성 중 오류가 발생했습니다: {result['error']}\n\n다시 시도해보시겠습니까?")


# --------------------------------------------------------------------------
# 3. Streamlit UI 구성
# --------------------------------------------------------------------------

st.title("🤖 AI Meeting Orchestrator Chat")
st.caption("Claude Code + MCP를 통한 대화형 Jira 티켓 생성")

with st.sidebar:
    st.header("📋 회의록 선택")
    meetings = get_recent_meetings(notion, NOTION_DATABASE_ID)
    meeting_titles = ["선택하세요..."] + [m['title'] for m in meetings] if meetings else ["선택하세요..."]

    selected_title = st.selectbox("분석할 회의록:", options=meeting_titles, key="meeting_selector")

    if selected_title and selected_title != "선택하세요...":
        selected_meeting = next((m for m in meetings if m['title'] == selected_title), None)
        if selected_meeting and selected_meeting != st.session_state.selected_meeting:
            st.session_state.selected_meeting = selected_meeting
            if st.session_state.messages:
                add_message("assistant", f"새로운 회의록 **'{selected_title}'**을 선택하셨네요! 분석을 시작하시려면 '분석 시작'을 입력해주세요. 📝")
    elif not meetings:
        st.warning("Notion에서 회의록을 불러올 수 없습니다.")

    st.divider()

    st.header("⚙️ 설정")
    st.session_state.project_key = st.text_input(
        "Jira 프로젝트 키", value=st.session_state.get("project_key", "DEV"),
        help="티켓을 생성할 Jira 프로젝트 키"
    )

    st.divider()

    st.header("📊 현재 상태")
    status_map = {
        "start": "🏁 시작 대기", "analyzing": "🔍 분석 중",
        "discussing": "💬 논의 중", "creating": "🎫 티켓 생성 중",
        "completed": "✅ 완료"
    }
    st.info(f"현재 단계: {status_map.get(st.session_state.workflow_stage, '알 수 없음')}")
    if st.session_state.selected_meeting:
        st.success(f"선택된 회의록: {st.session_state.selected_meeting['title']}")

    with st.expander("🔍 시스템 상태 확인", expanded=True):
        claude_ok, claude_msg = check_claude_code_setup()
        st.write(f"**Claude CLI:** {'✅' if claude_ok else '❌'} {claude_msg}")
        mcp_ok, mcp_msg = check_mcp_connection()
        st.write(f"**MCP Atlassian:** {'✅' if mcp_ok else '❌'} {mcp_msg}")
        if not mcp_ok:
            st.info("터미널에서 `claude mcp add atlassian` 명령어로 Jira 인증 정보를 설정해주세요.")

    if st.button("🔄 새로 시작", help="대화를 처음부터 다시 시작합니다"):
        st.session_state.clear()
        st.rerun()

# 메인 화면 - 채팅 인터페이스
if not st.session_state.messages:
    add_message("assistant", """안녕하세요! 저는 AI Meeting Orchestrator입니다. 🤖

**다음과 같이 도와드릴 수 있습니다:**
1. 📋 Notion 회의록 분석
2. 🎫 Jira 티켓 생성 제안
3. 💬 티켓 세부사항 조정
4. ✅ 실제 Jira 티켓 생성

시작하려면 사이드바에서 회의록을 선택하고 **'분석 시작'**이라고 입력해주세요!""")

display_chat_messages()

if prompt := st.chat_input("메시지를 입력하세요..."):
    add_message("user", prompt)

    prompt_lower = prompt.lower()

    if any(keyword in prompt_lower for keyword in ["분석 시작", "분석해", "시작"]):
        if st.session_state.workflow_stage in ["start", "completed"]:
            st.session_state.workflow_stage = "analyzing"
            handle_meeting_analysis()
    elif any(keyword in prompt_lower for keyword in ["생성", "만들어", "티켓 생성", "진행"]):
        if st.session_state.workflow_stage == "discussing":
            st.session_state.workflow_stage = "creating"
            handle_ticket_creation()
        else:
            add_message("assistant", "먼저 회의록 분석을 통해 티켓을 제안받아야 합니다!")
    else:  # 일반 대화 및 수정 요청
        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                placeholder = st.empty()
                result = call_claude_code_streaming(f"사용자 요청: {prompt}\n\n현재 대화의 맥락에 맞춰 친절하게 답변하거나 요청을 처리해주세요.", "",
                                                    placeholder)

        if result['success']:
            add_message("assistant", result['output'])
        else:
            add_message("assistant", "죄송합니다, 응답 생성 중 오류가 발생했습니다.")

    st.rerun()

with st.expander("💡 사용 팁"):
    st.markdown("""
    - **명령어 예시**: "분석 시작", "티켓 생성", "1번 티켓 제목을 '버그 수정'으로 바꿔줘"
    - **워크플로우**: 회의록 선택 → `분석 시작` → 티켓 검토 및 수정 → `티켓 생성`
    - **사전 조건**:
        1. `.env` 파일에 Notion API 정보 설정
        2. `claude` CLI 설치 및 로그인
        3. `claude mcp add atlassian`을 통한 Jira 인증 정보 설정
    """)

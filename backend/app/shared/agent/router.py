"""에이전트 채팅 라우터 — Issue #7 구현.

[이 파일의 역할]
STT가 변환한 텍스트를 LangGraph 에이전트에 전달하고,
에이전트가 적절한 tool을 선택·실행한 뒤 action JSON을 반환합니다.

[요청/응답 흐름]
프론트엔드(MicButton) → POST /api/agent/chat
  → 에이전트(LangGraph) → tool 선택(parse_transfer_slots 등)
  → action JSON 반환 → 프론트 Zustand 슬롯 업데이트 or 화면 전환

[반환되는 action 종류]
  tts_reply        : 슬롯 미완성, TTS 재질문 후 재녹음 대기
  navigate_confirm : 슬롯 완성, 이체 확인 화면으로 전환

[설계 변경 이력]
v1 (결함): user_id를 thread_id로만 전달 → tool 내부 user_id 소실, crash
           응답을 raw string 반환 → 프론트 data.action undefined 파싱 실패
v2 (현재): HumanMessage에 [사용자ID:{user_id}] 태그 포함 → LLM이 tool 호출 시 추출
           json.loads(last) 파싱 후 반환 → 프론트 data.action 정상 접근
"""

import json

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.jwt_utils import get_current_user_id
from app.shared.agent.graph import build_graph
from app.shared.agent.tools import ALL_TOOLS

router = APIRouter(prefix="/api/agent", tags=["agent"])

# 앱 기동 시 그래프를 한 번만 빌드해 재사용합니다.
# ALL_TOOLS에 등록된 tool이 변경되면 서버를 재시작해야 반영됩니다.
_graph = build_graph(ALL_TOOLS)


class AgentChatRequest(BaseModel):
    """POST /api/agent/chat 요청 바디."""

    transcript: str
    current_slots: str = "{}"


@router.post("/chat", response_model=dict)
async def chat(
    body: AgentChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    """STT 결과를 에이전트에 전달하고 action JSON을 반환합니다.

    프론트엔드는 응답의 data.action 값을 보고 다음 행동을 결정합니다:
      - tts_reply        → data.tts_text를 TTS로 재생 후 재녹음 대기
      - navigate_confirm → data.slots를 Zustand에 저장 후 이체 확인 화면 전환
    """
    # [핵심 설계 포인트 — user_id 전달 방식]
    # config의 thread_id는 LangGraph 메모리 체크포인팅 전용이며 tool 파라미터로 주입되지 않습니다.
    # parse_transfer_slots의 user_id 파라미터는 LLM이 [사용자ID:...] 태그에서
    # 직접 읽어 tool 호출 인자로 채워야 합니다.
    message = f"[사용자ID:{user_id}]\n{body.transcript}\n[슬롯:{body.current_slots}]"

    result = await _graph.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": user_id}},
    )

    last = result["messages"][-1].content

    # [핵심 설계 포인트 — 응답 형식 파싱]
    # parse_transfer_slots는 JSON 문자열을 반환하지만,
    # LangGraph 최종 AIMessage가 항상 그 JSON을 그대로 전달하지 않을 수 있습니다.
    # json.loads()로 파싱해 프론트엔드가 data.action, data.slots를 바로 참조할 수 있게 합니다.
    # LLM이 자연어로 답변한 경우(JSONDecodeError) tts_reply로 안전하게 감싸 반환합니다.
    try:
        data = json.loads(last)
    except (json.JSONDecodeError, TypeError):
        data = {"action": "tts_reply", "tts_text": last, "slots": {}}

    return {"success": True, "data": data, "message": ""}

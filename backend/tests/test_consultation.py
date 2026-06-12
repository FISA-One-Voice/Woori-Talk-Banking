import pytest
from langchain_core.messages import HumanMessage
from app.shared.agent.state import VoiceState
from app.shared.agent.subgraphs.consultation import rag_graph

@pytest.mark.asyncio
async def test_rag_graph_financial_qa_routing():
    """RAG 에이전트가 질문을 받고 financial_qa 툴을 거쳐 자연어 응답과 navigate_to=None을 반환하는지 테스트합니다."""
    # 초기 상태(State) 세팅
    initial_state = VoiceState(
        messages=[HumanMessage(content="자동이체 수수료 면제 조건이 뭐야?")],
        user_id="test_user",
        navigate_to="home"  # 기존에 다른 곳으로 가려고 했더라도
    )
    
    # RAG 노드 실행 (실제 LLM과 OpenSearch 연동)
    result = await rag_graph(initial_state)
    
    # 검증 1: LLM이 툴을 거쳐 최종 자연어 응답(AIMessage)을 뱉어내야 함
    final_messages = result.get("messages", [])
    assert len(final_messages) > 1  # 기존 HumanMessage 외에 Tool/AI 메시지가 추가되었어야 함
    final_ai_msg = final_messages[-1]
    
    # 검증 2: TTS에 방해되는 마크다운이나 날것의 JSON이 없어야 함
    assert "{" not in final_ai_msg.content
    assert "*" not in final_ai_msg.content
    
    # 검증 3: 아키텍처 규칙에 따라 화면 이동 제어권 박탈(None 강제화) 확인
    assert result.get("navigate_to") is None

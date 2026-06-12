"""Supervisor LLM 통합 테스트 — 실제 OpenAI 호출로 도메인 분류 검증.

graph.py의 발화 예시(intent_node 시스템 프롬프트 §응답 지침)를 기반으로
Supervisor _decide_domain의 실제 분류 동작을 검증한다.

역할 분리 원칙:
    Supervisor  : 도메인 라우팅 (transfer / asset / rag / cancel / unknown)
    Subgraph    : 슬롯 추출 + intent 세분화 (transfer vs auto_transfer 등)

Fast-path vs LLM-path 범례:
    ■ fast-path : is_plain_transfer_start() = True
                  → LLM 미호출, 즉시 "transfer" 반환
                  조건: 이체 키워드("보내", "송금", "이체" 등) 포함
                        + 자동이체·홈·잔액 키워드 미포함
                  슬롯(금액·수취인) 유무는 판단 기준이 아님 — subgraph 책임
    □ LLM-path  : 위 조건 미충족 → gpt-4o-mini 실제 호출

현재 fast-path 대상:
    transfer : is_plain_transfer_start() (명시적 이체 키워드)
    asset    : 계획됨 (supervisor.py §4 주석 참조)
    rag      : 계획됨 (supervisor.py §4 주석 참조)

Design Ref: docs/02-design/features/dev-a-supervisor-plan.design.md §4.5

실행 방법:
    cd backend
    .venv/bin/pytest tests/test_supervisor_llm.py -v

주의: OpenAI API 키 필요 / 실제 비용 발생.
"""

from app.shared.agent.supervisor import _decide_domain


def _make_state(**kwargs) -> dict:
    """테스트용 최소 VoiceState 딕셔너리."""
    base = {
        "messages": [],
        "user_id": "test-user",
        "pending_action": None,
        "collected_slots": {},
        "awaiting_confirmation": False,
        "awaiting_asv_audio": False,
        "awaiting_memo_decision": False,
        "awaiting_transfer_clarification": False,
        "draft_recipient": None,
        "asv_retry_count": 0,
        "navigate_to": None,
        "execution_ready": False,
        "recipient_validated": False,
        "last_tx_id": None,
        "last_order_id": None,
        "agent_domain": None,
        "analytics_period": None,
    }
    base.update(kwargs)
    return base


# ── Transfer 도메인 ───────────────────────────────────────────────────────────
# graph.py VALID_INTENTS: transfer, auto_transfer → supervisor "transfer"
#
# fast-path: is_plain_transfer_start() = True (이체 키워드 포함, 자동이체·홈·잔액 제외)
#   슬롯이 있어도 도메인은 "transfer" → subgraph가 슬롯 추출
# LLM-path : 자동이체 전용 키워드("자동이체", "정기이체" 등) → LLM이 "transfer" 분류


async def test_fastpath_transfer_bare():
    """■ fast-path: '송금하고 싶어' — 이체 키워드 + 슬롯 없음."""
    state = _make_state()
    result = await _decide_domain("송금하고 싶어", state)
    assert result == "transfer", f"expected transfer, got {result!r}"


async def test_fastpath_transfer_with_amount():
    """■ fast-path: '삼만원 보내줘' — 이체 키워드 + 금액 슬롯 포함.

    슬롯 유무는 supervisor 라우팅 기준이 아니다.
    금액 추출은 subgraph(intent_node)가 messages를 통해 처리한다.
    """
    state = _make_state()
    result = await _decide_domain("삼만원 보내줘", state)
    assert result == "transfer", f"expected transfer, got {result!r}"


async def test_fastpath_transfer_with_recipient():
    """■ fast-path: '엄마한테 이체해줘' — 이체 키워드 + 수취인 슬롯 포함.

    수취인 추출은 subgraph(intent_node)가 처리한다.
    """
    state = _make_state()
    result = await _decide_domain("엄마한테 이체해줘", state)
    assert result == "transfer", f"expected transfer, got {result!r}"


async def test_llm_auto_transfer_explicit():
    """□ LLM: '자동이체' → is_plain_transfer_start=False (auto 키워드 제외) → LLM.

    graph.py: '자동이체', '정기 이체', '자동 송금' → intent=auto_transfer.
    Supervisor는 transfer/auto_transfer를 모두 "transfer" 도메인으로 라우팅한다.
    """
    state = _make_state()
    result = await _decide_domain("자동이체 등록해줘", state)
    assert result == "transfer", f"expected transfer, got {result!r}"


async def test_llm_auto_transfer_weekly():
    """□ LLM: '정기이체' → auto 키워드 제외 → LLM → transfer."""
    state = _make_state()
    result = await _decide_domain("매주 금요일마다 정기이체 등록해줘", state)
    assert result == "transfer", f"expected transfer, got {result!r}"


async def test_llm_auto_transfer_implicit():
    """□ LLM: '매달 친구한테 용돈 드리고 싶어' — 이체 키워드 없음 → LLM.

    graph.py: '매달', '꾸준히', '정기적으로' → auto_transfer 인텐트.
    이체 키워드 없이 맥락만으로 송금 의도를 표현 → LLM이 "transfer"로 분류해야 한다.
    """
    state = _make_state()
    result = await _decide_domain("매달 친구한테 용돈 드리고 싶어", state)
    assert result == "transfer", f"expected transfer, got {result!r}"


# ── Asset 도메인 ─────────────────────────────────────────────────────────────
# graph.py VALID_INTENTS: balance, history → supervisor "asset"
#
# 계획 (fast-path 미구현):
#   ■ fast-path 후보: "잔액", "잔고", "내역", "출금" 키워드 → 즉시 "asset"
#   현재는 전부 □ LLM-path. supervisor.py §4 주석 참조.


async def test_llm_balance_query():
    """□ LLM: '잔액 얼마야' → is_plain_transfer_start=False (balance 힌트 제외) → LLM.

    graph.py: '잔액 얼마야', '내역 보여줘' → intent=balance.
    [계획] '잔액' 키워드 fast-path 도입 시 ■로 전환 가능.
    """
    state = _make_state()
    result = await _decide_domain("잔액 얼마야", state)
    assert result == "asset", f"expected asset, got {result!r}"


async def test_llm_history_query():
    """□ LLM: '거래 내역 보여줘' → transfer 힌트 없음 → LLM → asset.

    [계획] '내역' 키워드 fast-path 도입 시 ■로 전환 가능.
    """
    state = _make_state()
    result = await _decide_domain("거래 내역 보여줘", state)
    assert result == "asset", f"expected asset, got {result!r}"


async def test_llm_spending_analysis():
    """□ LLM: '이번 달 지출 분석해줘' → transfer 힌트 없음 → LLM → asset."""
    state = _make_state()
    result = await _decide_domain("이번 달 지출 분석해줘", state)
    assert result == "asset", f"expected asset, got {result!r}"


# ── RAG 도메인 ────────────────────────────────────────────────────────────────
# graph.py VALID_INTENTS: event → supervisor "rag"; 금융 FAQ/금리/환율도 포함
#
# 계획 (fast-path 미구현):
#   ■ fast-path 후보: "이벤트", "금리", "환율", "영업시간" 키워드 → 즉시 "rag"
#   현재는 전부 □ LLM-path. supervisor.py §4 주석 참조.


async def test_llm_event_query():
    """□ LLM: '이벤트 뭐 있어' → graph.py intent=event → supervisor rag.

    [계획] '이벤트' 키워드 fast-path 도입 시 ■로 전환 가능.
    """
    state = _make_state()
    result = await _decide_domain("이벤트 뭐 있어", state)
    assert result == "rag", f"expected rag, got {result!r}"


async def test_llm_exchange_rate():
    """□ LLM: '오늘 달러 환율 얼마야' → 금융 정보 질의 → rag.

    [계획] '환율' 키워드 fast-path 도입 시 ■로 전환 가능.
    """
    state = _make_state()
    result = await _decide_domain("오늘 달러 환율 얼마야", state)
    assert result == "rag", f"expected rag, got {result!r}"


async def test_llm_interest_rate():
    """□ LLM: '우리은행 주택 대출 금리 얼마야' → 금융 FAQ → rag.

    [계획] '금리' 키워드 fast-path 도입 시 ■로 전환 가능.
    """
    state = _make_state()
    result = await _decide_domain("우리은행 주택 대출 금리 얼마야", state)
    assert result == "rag", f"expected rag, got {result!r}"


async def test_llm_faq_business_hours():
    """□ LLM: '우리은행 영업시간 알려줘' → 금융 FAQ → rag.

    graph.py에서는 챗봇이 직접 답하는 케이스이지만,
    Supervisor는 RAG 도메인으로 라우팅해야 한다.
    [계획] '영업시간' 키워드 fast-path 도입 시 ■로 전환 가능.
    """
    state = _make_state()
    result = await _decide_domain("우리은행 영업시간 알려줘", state)
    assert result == "rag", f"expected rag, got {result!r}"


# ── Unknown 도메인 ────────────────────────────────────────────────────────────


async def test_llm_greeting():
    """□ LLM: '안녕' → 금융 무관 → unknown."""
    state = _make_state()
    result = await _decide_domain("안녕", state)
    assert result == "unknown", f"expected unknown, got {result!r}"


async def test_llm_home_without_session():
    """□ LLM: '홈으로 가줘' + 세션 없음 → navigation 키워드, 세션 없어 cancel 아님
    → is_plain_transfer_start=False (home 키워드 명시 제외) → LLM → unknown.

    navigate 도메인 없음. DOMAIN_CLASSIFY_PROMPT에 해당 카테고리 없어 unknown 반환.
    supervisor는 재질문 TTS로 응답한다.
    """
    state = _make_state()
    result = await _decide_domain("홈으로 가줘", state)
    assert result == "unknown", f"expected unknown, got {result!r}"


async def test_llm_unrelated_utterance():
    """□ LLM: '오늘 날씨 어때' → 금융 무관 → unknown."""
    state = _make_state()
    result = await _decide_domain("오늘 날씨 어때", state)
    assert result == "unknown", f"expected unknown, got {result!r}"


async def test_llm_confirmation_without_session():
    """□ LLM: '네' + 세션 없음 → 활성 세션 없어 fast-path 미적용 → LLM → unknown.

    graph.py: '네'는 awaiting_confirmation=True 시 user_confirmed=true.
    세션 없으면 banking 도메인 분류 불가 → unknown.
    """
    state = _make_state()
    result = await _decide_domain("네", state)
    assert result == "unknown", f"expected unknown, got {result!r}"

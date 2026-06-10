# AssetAgent 리팩토링 계획: create_react_agent 방식으로 전환

## Context

현재 `subgraphs/asset.py`의 `asset_node`는 다음 2단계 rule-based 방식으로 동작한다.

1. **키워드 fast-path** (`_fast_classify`) → 잔액·분석·거래내역 키워드 직접 매칭  
2. **LLM JSON 분류** (`_QUERY_SYSTEM_PROMPT`) → JSON `{"action": ..., "period": ...}` 출력  
3. **if/elif dispatch** → `tool_registry[name].invoke(...)` 수동 실행

이 방식은 LLM이 tool을 직접 선택하지 않고 rule이 대신한다. RAGAgent(`consultation.py`)는 이미 `create_react_agent`로 LLM이 직접 tool을 선택하는 구조다. AssetAgent도 단순 단발성 조회이므로 같은 패턴으로 통일한다.

**목표**: LLM이 `bind_tools`를 통해 직접 tool을 선택·실행하도록 전환하고, 기존의 `navigate_to`·`collected_slots`·`analytics_period` 반환 계약은 유지한다.

---

## 변경 파일

**단일 파일**: `backend/app/shared/agent/subgraphs/asset.py`  
그 외 파일은 변경 없음.

---

## 삭제 목록

| 항목 | 이유 |
|------|------|
| `ASSET_DOMAIN_ACTIONS` frozenset | LLM이 직접 tool 선택하므로 action 목록 불필요 |
| `_BALANCE_KEYWORDS`, `_TRANSACTION_LIST_KEYWORDS`, `_HISTORY_KEYWORDS`, `_ANALYSIS_KEYWORDS` | fast-path 키워드 매칭 전부 제거 |
| `_QUERY_SYSTEM_PROMPT` | JSON 분류용 LLM 호출 대체됨 |
| `_get_llm()`, `_last_user_text()`, `_parse_llm_action()` | 사용처 없어짐 |
| `_fast_classify()`, `_has_period_keyword()`, `_fast_period()` | rule-based 분류 로직 전부 제거 |
| `asset_node` 함수 전체 | if/elif dispatch 포함 |
| `StateGraph` builder 블록 | create_react_agent가 대체 |
| `_NAVIGATE_MAP["spending_analysis"]` key | `"spending_report"`로 key 하나만 수정 (tool 이름 맞춤) |

---

## 추가 코드

### imports 변경

```python
# 삭제
import json
import re
from langchain_core.messages import AIMessage, HumanMessage

# 추가
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
```

---

### 1. `_ASSET_SYSTEM_PROMPT` (동적 프롬프트 — user_id 포함)

```python
_ASSET_SYSTEM_PROMPT = """\
당신은 자산 조회 전용 에이전트입니다.
현재 사용자 ID: {user_id}
모든 tool 호출 시 반드시 user_id="{user_id}"를 전달하세요.

[tool 선택 기준]
- query_balance       : 잔액 조회 ("잔액 얼마야", "통장 잔액")
- query_history       : 수입/지출 요약 ("이번달 지출 얼마야", "수입 얼마야")
- query_category      : 카테고리별 지출 ("식비 얼마야", "교통비 알려줘")
- query_top_category  : 최다 지출 카테고리 ("어디에 제일 많이 썼어")
- query_transaction_list : 거래 내역 목록 ("거래내역 보여줘", "최근 내역")
- query_spending_report  : 지출 분석 리포트 ("지출 분석", "소비 분석", "리포트")
- query_compare       : 두 기간 지출 비교 ("이번달 지난달 비교", "이번주 지난주 대비")

[기간 처리 규칙]
- query_history 요청인데 기간이 명시되지 않았으면:
  tool을 호출하지 말고 "어느 기간을 알려드릴까요?" 라고만 답하세요.
- 그 외 모든 tool은 기간이 없으면 "이번달"을 기본값으로 사용해 tool을 호출하세요.

[응답 규칙]
- tool 반환값을 그대로 사용자에게 전달하세요. 내용 추가·요약·수정 금지.
- 마크다운·이모지 사용 금지. 음성(TTS)으로 전달됩니다.
- 숫자는 한국어로 읽히도록 작성하세요. (예: "오십만 원")
"""
```

---

### 2. `_NAVIGATE_MAP` (기존 유지 + key 1개 수정)

기존 `_NAVIGATE_MAP`을 그대로 유지한다. 단, `"spending_analysis"` 키를 `"spending_report"`로 수정한다.  
이유: tool 이름이 `query_spending_report`이므로 `removeprefix("query_")` 결과가 `"spending_report"`임.

```python
_NAVIGATE_MAP: dict[str, str] = {
    "balance":          "asset",
    "history":          "asset/history",
    "category":         "asset/history",
    "top_category":     "asset/history",
    "transaction_list": "asset/history",
    "spending_report":  "report",          # 변경: spending_analysis → spending_report
    "compare":          "asset/compare",
    # [Dev-A에게] ROUTING_CONSTANTS.ASSET_NAVIGATE_VALUES에 "asset/compare" 추가 요청
}
```

`build_asset_graph` 내에서 tool 이름을 action key로 변환하는 방법:
```python
action_key = tool_name.removeprefix("query_")   # "query_spending_report" → "spending_report"
navigate_to = _NAVIGATE_MAP.get(action_key)      # "report"
```

---

### 3. `_extract_tool_info`

```python
def _extract_tool_info(messages: list) -> tuple[str | None, dict]:
    """result["messages"] 역순 순회해 첫 tool_call 정보 반환."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            tc = msg.tool_calls[0]
            return tc["name"], tc.get("args", {})
    return None, {}
```

---

### 4. `build_asset_graph` (전체 재작성)

```python
def build_asset_graph(tools: list):
    """AssetAgent 서브그래프를 빌드한다. RAGAgent 패턴(create_react_agent) 사용."""
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_CHAT_API_KEY,
        temperature=0,
    )
    agent = create_react_agent(model=llm, tools=tools, state_schema=VoiceState)

    async def _asset_graph(state: VoiceState) -> dict:
        user_id = state["user_id"]

        # user_id를 시스템 프롬프트에 주입 — create_react_agent prompt는 정적이므로 여기서 prepend
        system_msg = SystemMessage(content=_ASSET_SYSTEM_PROMPT.format(user_id=user_id))
        result = await agent.ainvoke({
            **state,
            "messages": [system_msg, *state["messages"]],
        })

        # MemorySaver 오염 방지: SystemMessage는 반환 메시지에서 제거
        clean_msgs = [m for m in result["messages"] if not isinstance(m, SystemMessage)]

        tool_name, tool_args = _extract_tool_info(result["messages"])

        # navigate_to 결정
        action_key = tool_name.removeprefix("query_") if tool_name else None
        navigate_to = _NAVIGATE_MAP.get(action_key) if action_key else None
        if navigate_to not in ASSET_NAVIGATE_VALUES and navigate_to != "asset/compare":
            logger.error("AssetAgent navigate_to 계약 위반: %s", navigate_to)
            navigate_to = "asset"

        # collected_slots 구성
        slots: dict = {}
        if tool_name:
            slots["action"] = action_key
            period = tool_args.get("period")
            if period:                           slots["period"] = period
            if tool_args.get("compare_period"):  slots["compare_period"] = tool_args["compare_period"]
            if tool_args.get("category"):        slots["category"] = tool_args["category"]
            if tool_args.get("filter_type"):     slots["filter_type"] = tool_args["filter_type"]
        else:
            # 되묻기: 이전 collected_slots 유지 (다음 턴에서 action 기억)
            slots = state.get("collected_slots") or {}

        period = tool_args.get("period") if tool_args else None

        return {
            "messages": clean_msgs,
            "navigate_to": navigate_to,
            "analytics_period": period if tool_name and tool_name != "query_balance" else None,
            "collected_slots": slots,
        }

    return _asset_graph
```

---

## 동작 원리 및 설계 근거

### TTS 흐름 (message_utils.py 연계)

`last_assistant_text`는 `reversed(messages)`에서 첫 `AIMessage`를 반환한다.  
`create_react_agent` 메시지 순서:

| 케이스 | 메시지 순서 | TTS 결과 |
|--------|------------|---------|
| 정상 tool 호출 | `[HumanMessage, AIMessage(tool_calls, content=""), ToolMessage, AIMessage(content="잔액은...")]` | "잔액은..." ✓ |
| 되묻기 (tool 없음) | `[HumanMessage, AIMessage(content="어느 기간을 알려드릴까요?")]` | "어느 기간을..." ✓ |

> `AIMessage(tool_calls, content="")`는 content가 비어 있어 `tts_text_from_messages`에서 자동 skip된다.

### user_id 주입 방식

`create_react_agent`의 `prompt` 파라미터는 정적 문자열만 받는다 (state에 접근 불가).  
`_asset_graph` wrapper에서 `SystemMessage`를 messages 앞에 prepend 후 ainvoke → 결과에서 SystemMessage 필터링.  
RAGAgent와 유일한 구조적 차이이며, MemorySaver에는 SystemMessage가 저장되지 않는다.

### 되묻기 이후 다음 턴 처리

- `state.get("agent_domain") == "asset"` 조건이 supervisor에 있으므로 연속 발화는 자동으로 asset으로 라우팅된다.
- LLM은 conversation history 전체(이전 AIMessage "어느 기간을 알려드릴까요?" + HumanMessage "이번달")를 보고 컨텍스트에서 `query_history(period="이번달")` 호출을 유추한다.
- `collected_slots`를 이전 값으로 유지해 추가적인 action 힌트도 제공한다.

### "asset/compare" 계약 미완

`ROUTING_CONSTANTS.ASSET_NAVIGATE_VALUES`에 `"asset/compare"` 미포함 → 기존 코드의 예외 처리 로직 그대로 유지.  
**Dev-A 작업 필요**: `ASSET_NAVIGATE_VALUES`에 `"asset/compare"` 추가.

### frontend collected_slots 호환성

| 프론트 파일 | 필요 필드 | 제공 여부 |
|------------|---------|---------|
| `history.tsx` | `period`, `action` | ✓ (`query_history` args에서 추출) |
| `compare.tsx` | `period`, `compare_period`, `category` | ✓ (`query_compare` args에서 추출) |

---

## 검증 방법

아래 발화로 `/v1/voice/process` API를 호출해 응답 확인:

| 발화 | 기대 navigate_to | 기대 collected_slots.action |
|------|-----------------|--------------------------|
| "잔액 얼마야" | `"asset"` | `"balance"` |
| "이번달 지출 얼마야" | `"asset/history"` | `"history"`, period="이번달" |
| "거래내역 보여줘" (기간 없음) | `None` | — (되묻기) |
| "이번달" (되묻기 다음 턴) | `"asset/history"` | `"history"`, period="이번달" |
| "이번달 지난달 비교" | `"asset/compare"` | `"compare"`, period="이번달", compare_period="지난달" |
| "지출 분석해줘" | `"report"` | `"spending_report"` |
| "식비 얼마야" | `"asset/history"` | `"category"`, category="식비" |

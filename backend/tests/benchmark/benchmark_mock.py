"""LLM 모델 벤치마크 — Mock 버전 (DB 연결 없음).

수취인 조회·잔액 조회를 mock으로 대체하여 LLM 순수 응답 시간만 측정합니다.

실행:
    cd backend
    .venv/bin/python tests/benchmark/benchmark_mock.py
"""

import asyncio
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# backend/ 를 sys.path에 추가 (직접 실행 시)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import settings
from app.features.recipients.schema import ResolvedRecipient
from app.shared.agent.supervisor import build_supervisor

MODELS = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-5.4-nano", "gpt-5-mini"]
REPEAT = 10
BENCH_USER_ID = "00000000-0000-0000-0000-000000000099"
REPORT_DIR = Path(__file__).resolve().parents[3] / "docs" / "report"

_MOCK_RECIPIENT = ResolvedRecipient(
    recipient_id=None,
    account_number="110-123-456789",
    bank_name="우리은행",
    recipient_name="바보",
)
_MOCK_ACCOUNTS = [MagicMock(balance=5_000_000, bank_name="우리은행")]
_MOCK_ACCOUNT = MagicMock(balance=5_000_000, bank_name="우리은행")


# ── 시나리오 ───────────────────────────────────────────────────────────────────

@dataclass
class Scenario:
    name: str
    utterance: str
    expected_keywords: list[str]
    expects_slot_collection: bool = False
    elapsed_s: float = field(default=0.0, repr=False)
    response_text: str = field(default="", repr=False)
    collected_slots: dict = field(default_factory=dict, repr=False)
    success_count: int = field(default=0, repr=False)
    fail_count: int = field(default=0, repr=False)


def _make_scenarios() -> list[Scenario]:
    return [
        # ── 임시 비활성화 ──────────────────────────────────────────────────────
        # Scenario(
        #     name="잔액조회",
        #     utterance="내 통장 잔액 알려줘",
        #     expected_keywords=["잔액", "원", "5,000,000"],
        # ),
        # Scenario(
        #     name="이체_풀슬롯",
        #     utterance="바보에게 십만원 이체해줘",
        #     expected_keywords=["바보", "이체", "확인"],
        #     expects_slot_collection=True,
        # ),
        # Scenario(
        #     name="이체_단순발화",
        #     utterance="이체하고 싶어",
        #     expected_keywords=["받는", "수신인", "누구", "얼마", "계좌"],
        # ),
        # Scenario(
        #     name="금융QA_예금이란",
        #     utterance="예금이 뭐야?",
        #     expected_keywords=["예금", "이자", "은행", "저축"],
        # ),
        # ── fast path 우회 이체 시나리오 ───────────────────────────────────────
        # 아래 발화는 _TRANSFER_START_HINTS(이체/송금/보내 계열)에 해당 없음
        # → supervisor LLM 분류 → transfer subgraph LLM 슬롯 추출 (LLM 2회 호출)
        Scenario(
            name="이체_드려줘",
            utterance="바보한테 십만원 드려줘",
            expected_keywords=["바보", "이체", "확인"],
            expects_slot_collection=True,
        ),
        Scenario(
            name="이체_드릴까요",
            utterance="바보한테 십만원 드릴까요?",
            expected_keywords=["바보", "이체", "확인"],
            expects_slot_collection=True,
        ),
        Scenario(
            name="이체_전달해줘",
            utterance="바보한테 십만원 전달해줘",
            expected_keywords=["바보", "이체", "확인"],
            expects_slot_collection=True,
        ),
    ]


# ── 헬퍼 ───────────────────────────────────────────────────────────────────────

def _rebuild_consultation(model: str) -> None:
    """consultation.py의 module-level rag_agent를 새 모델로 교체한다."""
    import app.shared.agent.subgraphs.consultation as _mod
    from app.shared.agent.prompts import RAG_SYSTEM_PROMPT
    from app.shared.agent.state import VoiceState
    from app.shared.agent.tools.financial_qa import search_financial_docs
    from app.shared.agent.tools.market_info import get_exchange_rate, get_base_rate

    new_llm = ChatOpenAI(model=model, api_key=settings.OPENAI_CHAT_API_KEY, temperature=0)
    _mod._llm = new_llm
    _mod.rag_agent = create_react_agent(
        model=new_llm,
        tools=[search_financial_docs, get_exchange_rate, get_base_rate],
        prompt=RAG_SYSTEM_PROMPT,
        state_schema=VoiceState,
    )


def _extract_response_text(result: dict[str, Any]) -> str:
    for msg in reversed(result.get("messages", [])):
        content = getattr(msg, "content", "")
        if content and isinstance(content, str):
            return content
    return ""


def _check_keywords(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords)


# ── 핵심 실행 함수 ─────────────────────────────────────────────────────────────

async def _run_scenario(graph, scenario: Scenario) -> None:
    success_elapsed: list[float] = []
    last_result: dict = {}

    for i in range(REPEAT):
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        t0 = time.perf_counter()
        with (
            patch(
                "app.features.recipients.service.lookup_recipient_by_voice",
                return_value=_MOCK_RECIPIENT,
            ),
            patch(
                "app.features.asset.service.get_asset_summary",
                return_value=_MOCK_ACCOUNTS,
            ),
            patch(
                "app.features.asset.service.get_account_balance",
                return_value=_MOCK_ACCOUNT,
            ),
        ):
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=scenario.utterance)], "user_id": BENCH_USER_ID},
                config=config,
            )
        elapsed = time.perf_counter() - t0
        last_result = result

        response = _extract_response_text(result)
        kw_ok = _check_keywords(response, scenario.expected_keywords)
        if kw_ok:
            scenario.success_count += 1
            success_elapsed.append(elapsed)
        else:
            scenario.fail_count += 1
        print(f"  [{scenario.name}] run {i + 1}/{REPEAT}: {elapsed:.2f}s  {'✓' if kw_ok else '✗'}")

    # 성공한 run만 평균 (실패 run은 제외)
    scenario.elapsed_s = sum(success_elapsed) / len(success_elapsed) if success_elapsed else 0.0
    scenario.response_text = _extract_response_text(last_result)
    scenario.collected_slots = last_result.get("collected_slots") or {}

    total = scenario.success_count + scenario.fail_count
    print(
        f"\n{'=' * 60}\n"
        f"  시나리오 : {scenario.name}\n"
        f"  평균     : {scenario.elapsed_s:.2f}s\n"
        f"  통과     : {scenario.success_count}/{total}\n"
        f"  슬롯     : {list(scenario.collected_slots.keys()) or '없음'}\n"
        f"  응답(앞120): {scenario.response_text[:120]}\n"
        f"{'=' * 60}"
    )


async def _run_model(model: str) -> list[Scenario]:
    print(f"\n{'#' * 70}\n  모델 실행: {model}  (repeat={REPEAT})\n{'#' * 70}")
    settings.OPENAI_MODEL = model
    _rebuild_consultation(model)
    graph = build_supervisor()

    scenarios = _make_scenarios()
    for s in scenarios:
        await _run_scenario(graph, s)
    return scenarios


# ── 결과 출력 및 저장 ───────────────────────────────────────────────────────────

def _print_and_save_summary(all_results: dict[str, list[Scenario]]) -> None:
    models = list(all_results.keys())
    scenario_names = [s.name for s in next(iter(all_results.values()))]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── 콘솔 출력 ──────────────────────────────────────────────────────────────
    col_w = 18
    cell_w = 16
    total_w = col_w + cell_w * len(models) + 2
    print(f"\n\n{'=' * total_w}")
    print(f"  [MOCK] LLM 벤치마크 요약  repeat={REPEAT}")
    print(f"{'=' * total_w}")
    header = f"  {'시나리오':<{col_w}}" + "".join(f"  {m:<{cell_w}}" for m in models)
    print(header)
    print(f"  {'-' * (total_w - 2)}")
    for name in scenario_names:
        row = f"  {name:<{col_w}}"
        for model in models:
            s = next(sc for sc in all_results[model] if sc.name == name)
            total = s.success_count + s.fail_count
            cell = f"{s.elapsed_s:.2f}s  {s.success_count}/{total}"
            row += f"  {cell:<{cell_w}}"
        print(row)
    print(f"  {'-' * (total_w - 2)}")
    avg_row = f"  {'전체 평균':<{col_w}}"
    for model in models:
        avg = sum(s.elapsed_s for s in all_results[model]) / len(all_results[model])
        avg_row += f"  {avg:.2f}s{' ' * (cell_w - 7)}"
    print(avg_row)
    print(f"{'=' * total_w}\n")

    # ── 파일 저장 ───────────────────────────────────────────────────────────────
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"benchmark_mock_all_{ts}.md"

    col_header = " | ".join(f"{m} (평균 / 통과)" for m in models)
    sep = " | ".join(["---"] * (len(models) + 1))
    md_rows = []
    for name in scenario_names:
        cells = []
        for model in models:
            s = next(sc for sc in all_results[model] if sc.name == name)
            total = s.success_count + s.fail_count
            cells.append(f"{s.elapsed_s:.2f}s / {s.success_count}/{total}")
        md_rows.append(f"| {name} | " + " | ".join(cells) + " |")
    avg_cells = []
    for model in models:
        avg = sum(s.elapsed_s for s in all_results[model]) / len(all_results[model])
        avg_cells.append(f"**{avg:.2f}s**")
    md_rows.append(f"| **전체 평균** | " + " | ".join(avg_cells) + " |")

    content = f"""# LLM 벤치마크 결과 [MOCK]

- **모델 비교**: {", ".join(models)}
- **반복**: {REPEAT}회
- **유저**: {BENCH_USER_ID}
- **일시**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 결과 비교

| 시나리오 | {col_header} |
| {sep} |
""" + "\n".join(md_rows) + "\n"

    for model, scenarios in all_results.items():
        content += f"\n## {model} 시나리오별 상세\n\n"
        for s in scenarios:
            total = s.success_count + s.fail_count
            content += (
                f"### {s.name}\n"
                f"- 발화: `{s.utterance}`\n"
                f"- 평균: {s.elapsed_s:.2f}s\n"
                f"- 통과: {s.success_count}/{total}\n"
                f"- 슬롯: {list(s.collected_slots.keys()) or '없음'}\n"
                f"- 응답: {s.response_text[:200]}\n\n"
            )

    report_path.write_text(content, encoding="utf-8")
    print(f"  📄 리포트 저장: {report_path}")


# ── 진입점 ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    all_results: dict[str, list[Scenario]] = {}
    for model in MODELS:
        all_results[model] = await _run_model(model)
    _print_and_save_summary(all_results)


if __name__ == "__main__":
    asyncio.run(main())

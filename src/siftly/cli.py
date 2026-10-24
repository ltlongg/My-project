"""Dòng lệnh `siftly`: nạp dữ liệu khởi tạo, chạy một Kỳ ngay bây giờ, thử endpoint LLM."""

import argparse
import io
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

import httpx
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from siftly.agents.editor import Editor
from siftly.agents.verifier import Verifier
from siftly.collectors.rss import RssCollector
from siftly.config import Settings
from siftly.db import make_engine, make_session_factory, open_checkpointer, upgrade
from siftly.embeddings.endpoint import EndpointEmbedder
from siftly.extractors.article import ArticleExtractor
from siftly.llm_probe import (
    EndpointError,
    LLMEndpoint,
    burst,
    probe_embedding,
    probe_models,
    report,
)
from siftly.models import ChannelKind, RunOutcome, SourceKind
from siftly.publishers.telegram import TelegramPublisher
from siftly.runner import Runner
from siftly.search import Searcher
from siftly.search.brave import BraveSearch
from siftly.search.tavily import TavilySearch
from siftly.seed import TECH_SLUG, seed

OUTCOME_LABELS = {
    RunOutcome.PUBLISHED: "Đã phát",
    RunOutcome.NOT_PUBLISHED: "Không phát",
    RunOutcome.FAILED: "Hỏng",
}


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        # Console Windows mặc định không in được tiếng Việt khi đầu ra bị chuyển hướng.
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # httpx ghi lại địa chỉ từng lời gọi, mà địa chỉ của Telegram có chứa token của bot.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(prog="siftly", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Nâng cấp lược đồ và nạp dữ liệu khởi tạo")
    run_command = commands.add_parser("run", help="Chạy một Kỳ cho một Chuyên mục ngay bây giờ")
    run_command.add_argument("section", nargs="?", default=TECH_SLUG, help="Mã Chuyên mục")
    run_command.add_argument(
        "--resume",
        action="store_true",
        help="Chạy tiếp Kỳ gần nhất nếu nó bị gián đoạn giữa chừng, thay vì chạy một Kỳ mới",
    )
    probe_command = commands.add_parser(
        "probe-llm", help="Thử từng model của endpoint LLM và in báo cáo markdown"
    )
    probe_command.add_argument("model", nargs="*", help="Model cần thử; bỏ trống là mọi model")
    probe_command.add_argument(
        "--embedding", default="text-embedding-3-small", help="Model dùng để thử tạo vector nhúng"
    )
    probe_command.add_argument(
        "--burst",
        nargs=2,
        metavar=("MODEL", "CALL_COUNT"),
        help="Gửi cùng lúc ngần ấy lời gọi tới một model để xem endpoint trả gì khi bị dồn",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    if args.command == "probe-llm":
        return _probe_llm(settings, args)

    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    if args.command == "init":
        upgrade(engine)
        seed(session_factory, settings.telegram_chat_id)
        if not settings.telegram_chat_id:
            print("Chưa có TELEGRAM_CHAT_ID nên chưa tạo Kênh đăng; điền vào .env rồi chạy lại.")
        print("Đã nạp dữ liệu khởi tạo.")
        return 0

    search_keys = {"tavily": settings.tavily_api_key, "brave": settings.brave_api_key}
    editor_model = settings.editor_model or settings.model
    verifier_model = settings.verifier_model or settings.model
    missing = [
        name
        for name, value in {
            "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
            "OPENAI_BASE_URL": settings.openai_base_url,
            "OPENAI_API_KEY": settings.openai_api_key,
            "EDITOR_MODEL hoặc MODEL": editor_model,
            "VERIFIER_MODEL hoặc MODEL": verifier_model,
            f"{settings.search_provider.upper()}_API_KEY": search_keys[settings.search_provider],
        }.items()
        if not value
    ]
    if missing:
        print(f"Thiếu {', '.join(missing)}; điền vào .env rồi chạy lại.", file=sys.stderr)
        return 2
    assert settings.telegram_bot_token and settings.openai_api_key
    assert editor_model and verifier_model
    with (
        httpx.Client(
            timeout=20, headers={"User-Agent": "Mozilla/5.0 (compatible; siftly/0.1)"}
        ) as client,
        # Model nhúng chạy trên CPU: một lô văn bản có thể mất vài chục giây.
        httpx.Client(timeout=httpx.Timeout(300, connect=10)) as embedding_client,
        open_checkpointer(engine) as checkpointer,
    ):
        searcher: Searcher = (
            BraveSearch(client, settings.brave_api_key or "")
            if settings.search_provider == "brave"
            else TavilySearch(client, settings.tavily_api_key or "")
        )
        runner = Runner(
            session_factory,
            collectors={SourceKind.RSS: RssCollector(client)},
            publishers={
                ChannelKind.TELEGRAM: TelegramPublisher(client, settings.telegram_bot_token)
            },
            extractor=ArticleExtractor(client),
            embedder=EndpointEmbedder(
                embedding_client,
                settings.embedding_base_url,
                settings.embedding_model,
                settings.embedding_api_key,
            ),
            editor=Editor(
                _llm(settings, editor_model),
                Verifier(_llm(settings, verifier_model)),
                searcher,
                checkpointer,
            ),
        )
        try:
            if args.resume:
                record = runner.resume(args.section)
            else:
                record = runner.run(args.section, datetime.now(UTC))
        except LookupError as error:
            print(f"{error}. Đã chạy `siftly init` chưa?", file=sys.stderr)
            return 2

    if record is None:
        print("Kỳ gần nhất đã có kết quả; không có gì để chạy tiếp.")
        return 0
    assert record.outcome is not None
    print(f"{OUTCOME_LABELS[record.outcome]}" + (f": {record.reason}" if record.reason else ""))
    if record.editor_guideline_version is not None:
        print(
            f"Hướng dẫn của Biên tập: phiên bản {record.editor_guideline_version}; "
            f"của Kiểm chứng: phiên bản {record.verifier_guideline_version}"
        )
    stories = record.bulletin.stories if record.bulletin else ()
    for position, story in enumerate(stories, start=1):
        print(f"  {position}. {story.labeled_title}\n     {story.summary}\n     {story.url}")
    return 1 if record.outcome is RunOutcome.FAILED else 0


def _llm(settings: Settings, model: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        base_url=settings.openai_base_url,
        api_key=SecretStr(settings.openai_api_key or ""),
        # Model suy luận có thể nghĩ rất lâu trước khi trả chữ đầu tiên.
        timeout=300,
        max_retries=3,
    )


def _probe_llm(settings: Settings, args: argparse.Namespace) -> int:
    if not settings.openai_base_url or not settings.openai_api_key:
        print(
            "Thiếu OPENAI_BASE_URL hoặc OPENAI_API_KEY; điền vào .env rồi chạy lại.",
            file=sys.stderr,
        )
        return 2
    base_url, api_key = settings.openai_base_url, settings.openai_api_key
    # Model suy luận có thể nghĩ rất lâu trước khi trả chữ đầu tiên.
    with httpx.Client(timeout=httpx.Timeout(300, connect=10)) as client:
        endpoint = LLMEndpoint(client, base_url, api_key)
        try:
            models = args.model or endpoint.models()
        except EndpointError as error:
            print(f"Không lấy được danh sách model: {error}", file=sys.stderr)
            return 1
        results = probe_models(endpoint, models)
        print("## Từng model", "", report(results), sep="\n")

        embedding = probe_embedding(endpoint, args.embedding)
        verdict = "đạt" if embedding.passed else "KHÔNG"
        print("", "## Vector nhúng", "", sep="\n")
        print(f"- `{args.embedding}`: {verdict}, {embedding.note}")

        working_model = next(
            (result.model for result in results if result.checks["basic_call"].passed), None
        )
        rejections = {
            "Khoá sai": (LLMEndpoint(client, base_url, "sk-invalid"), working_model or models[0]),
            "Model không tồn tại": (endpoint, "no-such/model"),
        }
        print("", "## Khi endpoint từ chối", "", sep="\n")
        for case, (target, model) in rejections.items():
            try:
                target.chat(model, [{"role": "user", "content": "xin chào"}])
                print(f"- {case}: endpoint vẫn trả lời")
            except EndpointError as error:
                print(f"- {case}: {error}")

        if args.burst:
            model, call_count = args.burst[0], int(args.burst[1])
            print("", f"## {call_count} lời gọi cùng lúc tới `{model}`", "", sep="\n")
            for outcome, count in burst(endpoint, model, call_count).most_common():
                print(f"- {count} lần: {outcome}")
    return 0

"""Chạy Kỳ: lối vào duy nhất để làm một Bản tin cho một Chuyên mục tại một thời điểm."""

import logging
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from siftly import clustering
from siftly.agents import editor
from siftly.agents.editor import Assignment, Editor, EditorError
from siftly.agents.verifier import VerifierError
from siftly.collectors import Collector, NewArticle
from siftly.embeddings import Embedder
from siftly.extractors import Extractor
from siftly.images import Camera, Capture, ImageKind
from siftly.models import (
    Article,
    Bulletin,
    Candidate,
    Channel,
    ChannelKind,
    Delivery,
    Guideline,
    Role,
    Run,
    RunOutcome,
    Section,
    Source,
    SourceKind,
    Story,
    StoryImage,
    Verification,
    article_sources,
    section_sources,
)
from siftly.publishers import BulletinContent, Publisher, StoryContent
from siftly.shortlisting import Shortlister, ShortlistError
from siftly.urls import normalize_url

log = logging.getLogger(__name__)

# Kỳ đầu tiên của một Chuyên mục chưa có Bản tin trước để làm mốc.
FIRST_RUN_WINDOW = timedelta(hours=24)
# Số Bài gốc mới nhất của Kỳ được đưa vào Gom Tin; chặn trên để một Nguồn bất thường không làm
# Kỳ chậm đi nhiều.
MAX_ARTICLES = 500
# Bản tin có ít Tin qua Kiểm chứng hơn số này thì không phát, coi như Kỳ hỏng.
MIN_STORIES = 3
# Thu thập định kỳ lấy Bài gốc xuất bản trong khoảng này; bài đã có thì không lưu lại.
COLLECT_WINDOW = timedelta(hours=24)
# Khoá tư vấn của Postgres giữ suốt lúc làm một Kỳ: số đầu là loại khoá, số sau là mã Chuyên mục.
RUN_LOCK = 1


class RunInProgressError(Exception):
    """Một tiến trình khác đang làm một Kỳ của cùng Chuyên mục."""


@dataclass(frozen=True)
class RunRecord:
    """Một Kỳ đúng như đã lưu."""

    run_at: datetime
    # Chưa có kết quả nghĩa là Kỳ đang chạy hoặc bị gián đoạn giữa chừng.
    outcome: RunOutcome | None
    reason: str | None
    bulletin: BulletinContent | None
    # Phiên bản Hướng dẫn mà Biên tập và Kiểm chứng đã dùng; chưa tới bước Biên tập thì để trống.
    editor_guideline_version: int | None = None
    verifier_guideline_version: int | None = None
    # Số lần đã chạy Kỳ: lần đầu, cộng các lần thử lại.
    attempts: int = 1


class Runner:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        collectors: Mapping[SourceKind, Collector],
        publishers: Mapping[ChannelKind, Publisher],
        extractor: Extractor,
        embedder: Embedder,
        shortlister: Shortlister,
        editor: Editor,
        camera: Camera,
    ) -> None:
        self._session_factory = session_factory
        self._collectors = collectors
        self._publishers = publishers
        self._extractor = extractor
        self._embedder = embedder
        self._shortlister = shortlister
        self._editor = editor
        self._camera = camera

    def run(self, section_slug: str, run_at: datetime) -> RunRecord:
        """Chạy một Kỳ cho Chuyên mục `section_slug` tại `run_at`.

        Ném RunInProgressError khi một tiến trình khác đang làm một Kỳ của Chuyên mục này.
        """
        if run_at.tzinfo is None:
            raise ValueError("run_at phải có múi giờ")
        with self._session_factory() as session:
            section = _section(session, section_slug)
            with self._exclusive(section):
                since = _since(session, section, run_at)
                run = Run(section=section, run_at=run_at)
                session.add(run)
                # Kỳ được lưu trước khi làm gì khác, để lỗi nào cũng để lại một Kỳ có kết quả.
                session.commit()
                return self._finish(session, run, since)

    def resume(self, section_slug: str) -> RunRecord | None:
        """Chạy tiếp Kỳ gần nhất của Chuyên mục nếu nó bị gián đoạn giữa chừng.

        Biên tập làm tiếp từ bước đang dở chứ không làm lại từ đầu. Trả về None khi Kỳ gần nhất
        đã có kết quả, tức là không có gì để chạy tiếp.
        """
        with self._session_factory() as session:
            section = _section(session, section_slug)
            with self._exclusive(section):
                run = latest_run(session, section.id)
                if run is None or run.outcome is not None:
                    return None
                return self._finish(session, run, _since(session, section, run.run_at))

    def retry(self, section_slug: str) -> RunRecord | None:
        """Chạy lại Kỳ gần nhất của Chuyên mục nếu nó hỏng, như một lần thử nữa của chính Kỳ ấy.

        Những bước đã xong được dùng lại: Bản tin đã dựng không bị viết lại, và Kênh đăng đã nhận
        phần nào của Bản tin thì không nhận lại phần đó. Trả về None khi Kỳ gần nhất không hỏng.
        """
        with self._session_factory() as session:
            section = _section(session, section_slug)
            with self._exclusive(section):
                run = latest_run(session, section.id)
                if run is None or run.outcome is not RunOutcome.FAILED:
                    return None
                run.attempts += 1
                run.outcome = run.reason = run.retry_at = None
                session.commit()
                return self._finish(session, run, _since(session, section, run.run_at))

    def abandon(self, section_slug: str, reason: str) -> RunRecord | None:
        """Kết thúc Kỳ gần nhất của Chuyên mục là hỏng, với lí do `reason`, nếu nó bị gián đoạn
        giữa chừng; dùng khi đã quá muộn để chạy tiếp. Trả về None khi Kỳ gần nhất đã có kết quả.
        """
        with self._session_factory() as session:
            section = _section(session, section_slug)
            with self._exclusive(section):
                run = latest_run(session, section.id)
                if run is None or run.outcome is not None:
                    return None
                run.outcome, run.reason = RunOutcome.FAILED, reason
                session.commit()
                return _record(run)

    def collect(self, now: datetime) -> None:
        """Thu thập Bài gốc mới của mọi Nguồn thuộc một Chuyên mục chưa tạm dừng.

        Lỗi được ghi lại ở từng Nguồn, không lan ra ngoài.
        """
        with self._session_factory() as session:
            in_use = (
                select(section_sources.c.source_id)
                .join(Section, Section.id == section_sources.c.section_id)
                .where(Section.is_paused.is_(False))
            )
            sources = session.scalars(
                select(Source).where(Source.id.in_(in_use)).order_by(Source.id)
            ).all()
            for source in sources:
                self._collect(session, source, now - COLLECT_WINDOW, now)
                session.commit()

    @contextmanager
    def _exclusive(self, section: Section) -> Iterator[None]:
        """Giữ khoá của Chuyên mục trong lúc làm một Kỳ, để hai tiến trình, như Lịch và một lệnh
        chạy tay, không cùng làm và cùng phát một Kỳ.

        Khoá nằm trên một kết nối riêng, vì phiên làm việc trả kết nối về sau mỗi lần commit.
        Tiến trình chết thì kết nối đóng và Postgres tự nhả khoá.
        """
        engine = self._session_factory.kw["bind"]
        with engine.connect() as connection:
            locked = connection.scalar(select(func.pg_try_advisory_lock(RUN_LOCK, section.id)))
            connection.commit()
            if not locked:
                raise RunInProgressError(
                    f"Một tiến trình khác đang chạy Kỳ của Chuyên mục {section.slug}"
                )
            try:
                yield
            finally:
                connection.execute(select(func.pg_advisory_unlock(RUN_LOCK, section.id)))
                connection.commit()

    def _finish(self, session: Session, run: Run, since: datetime) -> RunRecord:
        """Làm Bản tin cho một Kỳ đã lưu và ghi kết quả vào nó."""
        try:
            run.outcome, run.reason = self._make_bulletin(session, run, since)
        except Exception as error:
            session.rollback()
            log.exception("Kỳ của Chuyên mục %s gặp lỗi không lường trước", run.section.slug)
            run.outcome = RunOutcome.FAILED
            run.reason = f"Lỗi không lường trước: {str(error).splitlines()[0]}"
        session.commit()
        return _record(run)

    def _make_bulletin(
        self, session: Session, run: Run, since: datetime
    ) -> tuple[RunOutcome, str | None]:
        """Thu thập, gom Tin, sơ tuyển, để Biên tập dựng Bản tin và Kiểm chứng xét nó, chụp ảnh rồi
        phát; trả về kết quả của Kỳ kèm lí do.

        Mọi bước đều làm lại được trên cùng một Kỳ, để Kỳ bị gián đoạn chạy tiếp được.
        """
        section = run.section
        if not section.sources:
            return RunOutcome.FAILED, "Chuyên mục chưa có Nguồn nào"
        if run.editor_guideline is None:
            run.editor_guideline = session.scalar(
                select(Guideline).where(
                    Guideline.role == Role.EDITOR,
                    Guideline.section_id == section.id,
                    Guideline.is_active,
                )
            )
        if run.editor_guideline is None:
            return RunOutcome.FAILED, "Chuyên mục chưa có Hướng dẫn cho Biên tập"
        if run.verifier_guideline is None:
            run.verifier_guideline = session.scalar(
                select(Guideline).where(
                    Guideline.role == Role.VERIFIER,
                    Guideline.section_id.is_(None),
                    Guideline.is_active,
                )
            )
        if run.verifier_guideline is None:
            return RunOutcome.FAILED, "Chưa có Hướng dẫn cho Kiểm chứng"
        # Kỳ dùng các Bài gốc Lịch đã thu thập trong ngày, cộng một lượt thu thập ngay trước khi gom
        # Tin. Đã có ứng viên thì không thu thập nữa: Bài gốc lấy về lúc ấy được ghi là xuất hiện
        # trước giờ của Kỳ, nên không vào Kỳ này mà cũng không vào Kỳ sau.
        collecting = run.bulletin is None and not run.candidates
        collected = [
            self._collect(session, source, since, run.run_at)
            for source in (section.sources if collecting else ())
        ]
        session.commit()
        # Xét trước khi gọi Agent, để không tốn lời gọi LLM cho Bản tin không có nơi phát.
        if not section.channels:
            return RunOutcome.FAILED, "Chuyên mục chưa có Kênh đăng nào"

        if run.bulletin is None:
            # Ứng viên được lưu một lần; Kỳ chạy tiếp dùng lại đúng các ứng viên Biên tập đã thấy.
            if not run.candidates:
                articles = _run_articles(session, section, since, run.run_at)
                if not articles and not any(collected):
                    # Hỏng chứ không phải "không phát": thử lại sau có thể lấy được.
                    return RunOutcome.FAILED, "Không thu thập được Nguồn nào"
                try:
                    clusters = clustering.cluster(
                        session, self._embedder, section.id, articles, run.run_at
                    )
                except Exception as error:
                    session.rollback()
                    log.exception("Gom Tin của Chuyên mục %s gặp lỗi", section.slug)
                    return RunOutcome.FAILED, f"Gom Tin gặp lỗi: {str(error).splitlines()[0]}"
                # Lưu vector nhúng vừa tạo; không giữ giao dịch mở trong lúc chấm điểm.
                session.commit()
                try:
                    ranked = self._shortlister.rank(
                        run.editor_guideline.content, clusters, run.run_at, section.shortlist_size
                    )
                except ShortlistError as error:
                    return RunOutcome.FAILED, str(error)
                run.candidates = [
                    Candidate(
                        position=position,
                        articles=list(candidate.cluster.articles),
                        published_story_id=candidate.cluster.published_story_id,
                        score=candidate.score,
                        score_components=candidate.components,
                        shortlisted=candidate.shortlisted,
                    )
                    for position, candidate in enumerate(ranked, start=1)
                ]
                session.commit()
            if not run.candidates:
                return RunOutcome.NOT_PUBLISHED, "Không có Bài gốc mới"
            if not run.shortlist:
                return RunOutcome.NOT_PUBLISHED, "Không ứng viên Tin nào trong phạm vi Chuyên mục"
            assignment = Assignment(
                section=section.name,
                run_at=run.run_at,
                guideline=run.editor_guideline.content,
                verifier_guideline=run.verifier_guideline.content,
                max_stories=section.max_stories,
                candidates=[_for_editor(candidate, section) for candidate in run.shortlist],
            )
            # Biên tập làm việc lâu; không giữ giao dịch nào mở trong lúc đó.
            session.commit()
            # Mỗi lần chạy Kỳ một lượt Biên tập riêng: lượt đã kết thúc với lỗi thì làm tiếp chỉ
            # trả lại đúng lỗi ấy. Kỳ bị gián đoạn thì chạy tiếp trong cùng lượt.
            thread_id = f"run-{run.id}-editor" + (f"-{run.attempts}" if run.attempts > 1 else "")
            try:
                written = self._editor.work(thread_id, assignment, self._read_article)
            except (EditorError, VerifierError) as error:
                return RunOutcome.FAILED, str(error)
            except Exception as error:
                log.exception("Biên tập của Chuyên mục %s gặp lỗi", section.slug)
                return RunOutcome.FAILED, f"Biên tập gặp lỗi: {str(error).splitlines()[0]}"
            candidate_of = {
                article.id: candidate
                for candidate in run.shortlist
                for article in candidate.articles
            }
            run.bulletin = Bulletin(
                stories=[
                    Story(
                        position=position,
                        title=story.title,
                        summary=story.summary,
                        reason=story.reason,
                        candidate=candidate_of[story.article_id],
                        primary_article_id=story.article_id,
                        drop_reason=story.drop_reason,
                        verifications=[
                            Verification(
                                attempt=attempt,
                                title=draft.title,
                                summary=draft.summary,
                                passed=draft.passed,
                                reason=draft.reason,
                            )
                            for attempt, draft in enumerate(story.drafts, start=1)
                        ],
                    )
                    for position, story in enumerate(written, start=1)
                ]
            )
            # Bản tin được lưu trước khi phát, để Kỳ hỏng vẫn cho thấy nó định gửi gì.
            session.commit()

        story_count = len(_published_stories(run.bulletin))
        if story_count < MIN_STORIES:
            return RunOutcome.FAILED, (
                f"Chỉ {story_count} Tin qua Kiểm chứng, dưới mức tối thiểu {MIN_STORIES}; "
                "Bản tin không được phát"
            )
        self._capture_images(session, _published_stories(run.bulletin))
        publish_errors = self._publish(session, run.bulletin)
        delivered = any(delivery.delivered for delivery in run.bulletin.deliveries)
        return (RunOutcome.PUBLISHED if delivered else RunOutcome.FAILED), "; ".join(
            publish_errors
        ) or None

    def _collect(self, session: Session, source: Source, since: datetime, now: datetime) -> bool:
        """Lấy và lưu Bài gốc mới của một Nguồn; trả về có lấy được hay không.

        Lỗi được ghi lại ở Nguồn, không lan ra ngoài.
        """
        source.last_fetched_at = now
        try:
            new_articles = self._collectors[source.kind].collect(source.url, since)
            with session.begin_nested():
                _save_articles(session, source, new_articles, now)
        except Exception as error:
            log.exception("Không thu thập được Nguồn %s", source.name)
            source.last_error = str(error)
            return False
        source.last_error = None
        return True

    def _capture_images(self, session: Session, stories: Sequence[Story]) -> None:
        """Lấy ảnh cho các Tin chưa có, mỗi Tin một lần; Kỳ chạy tiếp dùng lại ảnh đã lấy.

        Tin không lấy được ảnh vẫn được phát, không ảnh.
        """
        for story in stories:
            if story.image is not None:
                continue
            url = story.primary_article.url
            # Chụp ảnh lâu; không giữ giao dịch nào mở trong lúc đó.
            session.commit()
            try:
                capture = self._camera.capture(url)
            except Exception as error:
                log.exception("Chụp ảnh %s gặp lỗi", url)
                first_line = (str(error).splitlines() or [type(error).__name__])[0]
                capture = Capture(ImageKind.NONE, None, (f"Chụp ảnh gặp lỗi: {first_line}",))
            story.image = StoryImage(
                kind=capture.kind,
                data=capture.data,
                fallback_reason="\n".join(capture.failures) or None,
            )
            session.commit()

    def _read_article(self, article_id: int) -> str:
        """Toàn văn của một Bài gốc; lần đầu thì lấy về và lưu lại."""
        with self._session_factory() as session:
            article = session.get_one(Article, article_id)
            if article.full_text is None:
                article.full_text = self._extractor.extract(article.url)
                session.commit()
            return article.full_text

    def _publish(self, session: Session, bulletin: Bulletin) -> list[str]:
        """Phát tới từng Kênh đăng chưa nhận trọn Bản tin; trả về lỗi của những Kênh đăng không
        phát được.

        Kênh đăng đã nhận trọn thì bỏ qua, đã nhận một phần thì chỉ nhận phần còn lại, để không
        Kênh đăng nào nhận Bản tin hai lần, kể cả khi thử lại hay chạy tiếp sau khi bị gián đoạn.
        """
        content = _content(bulletin)
        deliveries = {delivery.channel_id: delivery for delivery in bulletin.deliveries}
        errors = []
        for channel in bulletin.run.section.channels:
            delivery = deliveries.get(channel.id)
            if delivery is None:
                delivery = Delivery(channel=channel, parts_sent=0, delivered=False)
                bulletin.deliveries.append(delivery)
            if delivery.delivered:
                continue
            error = self._deliver(session, channel, delivery, content)
            if error is not None:
                errors.append(f"Kênh đăng {channel.name} lỗi: {error}")
        return errors

    def _deliver(
        self, session: Session, channel: Channel, delivery: Delivery, content: BulletinContent
    ) -> str | None:
        """Phát phần còn lại của Bản tin tới một Kênh đăng; trả về lỗi nếu không phát trọn."""

        def sent() -> None:
            delivery.parts_sent += 1
            session.commit()

        # Phát lâu; không giữ giao dịch nào mở trong lúc đó.
        session.commit()
        try:
            self._publishers[channel.kind].publish(
                channel.address, content, skip=delivery.parts_sent, on_sent=sent
            )
        except Exception as error:
            log.exception("Không phát được tới Kênh đăng %s", channel.name)
            delivery.error = str(error)
        else:
            delivery.delivered, delivery.error = True, None
        session.commit()
        return delivery.error

    def history(self, section_slug: str) -> list[RunRecord]:
        """Các Kỳ đã lưu của Chuyên mục, mới nhất trước."""
        with self._session_factory() as session:
            section = _section(session, section_slug)
            runs = session.scalars(
                select(Run)
                .where(Run.section_id == section.id)
                .order_by(Run.run_at.desc(), Run.id.desc())
            )
            return [_record(run) for run in runs]


def latest_run(session: Session, section_id: int) -> Run | None:
    """Kỳ gần nhất của Chuyên mục."""
    return session.scalar(
        select(Run)
        .where(Run.section_id == section_id)
        .order_by(Run.run_at.desc(), Run.id.desc())
        .limit(1)
    )


def can_retry(run: Run) -> bool:
    """Chạy lại Kỳ hỏng này có thể ra kết quả khác không.

    Bản tin đã dựng mà dưới mức tối thiểu thì không: chạy lại dùng đúng Bản tin ấy.
    """
    return run.bulletin is None or len(_published_stories(run.bulletin)) >= MIN_STORIES


def _section(session: Session, slug: str) -> Section:
    section = session.scalar(select(Section).where(Section.slug == slug))
    if section is None:
        raise LookupError(f"Không có Chuyên mục nào có mã {slug!r}")
    return section


def _content(bulletin: Bulletin) -> BulletinContent:
    return BulletinContent(
        section=bulletin.run.section.name,
        run_at=bulletin.run.run_at,
        stories=tuple(
            StoryContent(
                story.title,
                story.summary,
                story.primary_article.url,
                is_update=story.update_of is not None,
                image=story.image.data if story.image else None,
            )
            for story in _published_stories(bulletin)
        ),
    )


def _published_stories(bulletin: Bulletin) -> list[Story]:
    """Các Tin đã qua Kiểm chứng, theo thứ tự Biên tập nộp."""
    return [story for story in bulletin.stories if story.drop_reason is None]


def _record(run: Run) -> RunRecord:
    return RunRecord(
        run_at=run.run_at,
        outcome=run.outcome,
        reason=run.reason,
        bulletin=_content(run.bulletin) if run.bulletin else None,
        editor_guideline_version=(run.editor_guideline.version if run.editor_guideline else None),
        verifier_guideline_version=(
            run.verifier_guideline.version if run.verifier_guideline else None
        ),
        attempts=run.attempts,
    )


def _since(session: Session, section: Section, run_at: datetime) -> datetime:
    """Mốc bắt đầu của Kỳ: Bản tin trước của cùng Chuyên mục, lần đầu là 24 giờ gần nhất."""
    previous_bulletin = session.scalar(
        select(func.max(Run.run_at)).where(
            Run.section_id == section.id, Run.outcome == RunOutcome.PUBLISHED
        )
    )
    return previous_bulletin or run_at - FIRST_RUN_WINDOW


def _save_articles(
    session: Session, source: Source, new_articles: Sequence[NewArticle], now: datetime
) -> None:
    """Lưu các Bài gốc chưa có và ghi nhận chúng đã được thấy ở `source`."""
    if not new_articles:
        return
    normalized = {article.url: normalize_url(article.url) for article in new_articles}
    session.execute(
        insert(Article)
        .values(
            [
                {
                    "normalized_url": normalized[article.url],
                    "url": article.url,
                    "title": article.title,
                    "description": article.description,
                    # Nguồn ghi giờ xuất bản ở tương lai thì coi như vừa xuất hiện.
                    "appeared_at": min(article.published_at or now, now),
                    "collected_at": now,
                }
                for article in new_articles
            ]
        )
        .on_conflict_do_nothing(index_elements=[Article.normalized_url])
    )
    seen_at_source = select(Article.id, literal(source.id)).where(
        Article.normalized_url.in_(normalized.values())
    )
    session.execute(
        insert(article_sources)
        .from_select(["article_id", "source_id"], seen_at_source)
        .on_conflict_do_nothing()
    )


def _run_articles(
    session: Session, section: Section, since: datetime, run_at: datetime
) -> list[Article]:
    """Bài gốc từ Nguồn của Chuyên mục xuất hiện trong khoảng (since, run_at], mới nhất trước."""
    of_section = (
        select(article_sources.c.article_id)
        .join(section_sources, section_sources.c.source_id == article_sources.c.source_id)
        .where(section_sources.c.section_id == section.id)
    )
    return list(
        session.scalars(
            select(Article)
            .where(
                Article.id.in_(of_section),
                Article.appeared_at > since,
                Article.appeared_at <= run_at,
            )
            .order_by(Article.appeared_at.desc(), Article.id)
            .limit(MAX_ARTICLES)
        )
    )


def _for_editor(candidate: Candidate, section: Section) -> editor.Candidate:
    """Ứng viên Tin như Biên tập thấy."""
    story = candidate.published_story
    return editor.Candidate(
        articles=tuple(
            editor.CandidateArticle(
                id=article.id,
                title=article.title,
                # Bài gốc có thể được thấy ở cả Nguồn của Chuyên mục khác.
                source=next(source.name for source in article.sources if source in section.sources),
                url=article.url,
                appeared_at=article.appeared_at,
                description=article.description,
            )
            for article in candidate.articles
        ),
        published_story=(
            editor.PublishedStory(story.bulletin.run.run_at, story.title, story.summary)
            if story
            else None
        ),
    )

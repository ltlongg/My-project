"""Lịch: chạy Kỳ của từng Chuyên mục đúng giờ phát, thử lại Kỳ hỏng, thu thập Bài gốc định kỳ, và
nhắn riêng cho chủ hệ thống khi một Kỳ hỏng hẳn hoặc không phát.

Mọi trạng thái của Lịch nằm trong cơ sở dữ liệu, trừ lúc thu thập gần nhất: khởi động lại thì Lịch
nhìn các Kỳ đã lưu mà làm tiếp, và chỉ xét Kỳ gần nhất của mỗi Chuyên mục, nên không chạy bù hàng
loạt các Kỳ đã lỡ.
"""

import logging
from collections.abc import Callable
from datetime import datetime, time, timedelta
from functools import partial
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from siftly.models import Run, RunOutcome, Section
from siftly.notifications import Notifier
from siftly.runner import RunInProgressError, Runner, can_retry, latest_run

log = logging.getLogger(__name__)

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
COLLECT_EVERY = timedelta(hours=1)
RETRY_DELAY = timedelta(minutes=30)
MAX_RETRIES = 3
# Quá giờ phát chừng này thì Kỳ không được bắt đầu, chạy tiếp hay thử lại nữa: đủ cho ba lần thử
# lại, mà không phát Bản tin buổi sáng vào buổi chiều khi dịch vụ chạy lại sau một sự cố dài.
DEADLINE = timedelta(hours=3)


class Scheduler:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        runner: Runner,
        notifier: Notifier,
        clock: Callable[[], datetime],
    ) -> None:
        self._session_factory = session_factory
        self._runner = runner
        self._notifier = notifier
        self._clock = clock
        self._collected_at: datetime | None = None

    def tick(self) -> None:
        """Làm mọi việc đã tới giờ. Gọi đều đặn, chẳng hạn mỗi phút.

        Chuyên mục đang tạm dừng bị bỏ qua hoàn toàn: không chạy Kỳ mới, không thử lại, không nhắn.
        """
        now = self._clock()
        if self._collected_at is None or now - self._collected_at >= COLLECT_EVERY:
            self._runner.collect(now)
            self._collected_at = now
        with self._session_factory() as session:
            slugs = session.scalars(
                select(Section.slug).where(Section.is_paused.is_(False)).order_by(Section.id)
            ).all()
        for slug in slugs:
            # Một Chuyên mục gặp sự cố không chặn các Chuyên mục còn lại.
            try:
                self._advance(slug)
                self._settle(slug)
            except RunInProgressError:
                log.info("Kỳ của Chuyên mục %s đang chạy ở nơi khác", slug)
            except Exception:
                log.exception("Lịch của Chuyên mục %s gặp lỗi", slug)

    def _advance(self, slug: str) -> None:
        """Chạy tiếp, thử lại hoặc bắt đầu Kỳ của Chuyên mục nếu đã tới lúc."""
        now = self._clock()
        with self._session_factory() as session:
            section = session.scalars(select(Section).where(Section.slug == slug)).one()
            latest = latest_run(session, section.id)
            slot = _latest_slot(section.publish_time, now)
            if latest is not None and latest.outcome is None:
                too_late = now > latest.run_at + DEADLINE
                step = self._abandon if too_late else self._runner.resume
            elif latest is not None and latest.retry_at is not None:
                if latest.retry_at > now:
                    return
                if now > latest.run_at + DEADLINE:
                    # Bỏ lần thử lại đã lỡ khi dịch vụ không chạy; bước sau nhắn cho chủ hệ thống.
                    latest.retry_at = None
                    session.commit()
                    return
                step = self._runner.retry
            elif (latest is None or latest.run_at < slot) and now - slot <= DEADLINE:
                step = partial(self._runner.run, run_at=slot)
            else:
                return
        # Chạy Kỳ mất nhiều phút; không giữ phiên nào mở trong lúc đó.
        step(slug)

    def _abandon(self, slug: str) -> None:
        self._runner.abandon(slug, "Kỳ bị gián đoạn giữa chừng và đã quá hạn để chạy tiếp")

    def _settle(self, slug: str) -> None:
        """Hẹn thử lại Kỳ gần nhất nếu nó hỏng và còn lượt; hỏng hẳn hoặc không phát thì nhắn cho
        chủ hệ thống, một lần."""
        with self._session_factory() as session:
            section = session.scalars(select(Section).where(Section.slug == slug)).one()
            run = latest_run(session, section.id)
            if (
                run is None
                or run.outcome not in (RunOutcome.FAILED, RunOutcome.NOT_PUBLISHED)
                or run.retry_at is not None
                or run.alerted_at is not None
            ):
                return
            now = self._clock()
            if (
                run.outcome is RunOutcome.FAILED
                and run.attempts <= MAX_RETRIES
                and can_retry(run)
                and now + RETRY_DELAY <= run.run_at + DEADLINE
            ):
                run.retry_at = now + RETRY_DELAY
            else:
                try:
                    self._notifier.notify(_alert(run))
                except Exception:
                    # Lượt sau nhắn lại.
                    log.exception("Không nhắn được cho chủ hệ thống về Kỳ %s", run.id)
                    return
                run.alerted_at = now
            session.commit()


def _latest_slot(publish_time: time, now: datetime) -> datetime:
    """Giờ phát gần nhất không muộn hơn `now`, theo giờ Việt Nam."""
    local = now.astimezone(VIETNAM_TZ)
    slot = datetime.combine(local.date(), publish_time, VIETNAM_TZ)
    return slot if slot <= local else slot - timedelta(days=1)


def _alert(run: Run) -> str:
    """Tin nhắn riêng về một Kỳ hỏng hẳn hoặc không phát: Chuyên mục, giờ phát và lí do."""
    when = run.run_at.astimezone(VIETNAM_TZ).strftime("%H:%M ngày %d/%m/%Y")
    headline = f"Bản tin {run.section.name} {when} không được phát"
    if run.outcome is RunOutcome.FAILED:
        headline += f": Kỳ hỏng sau {run.attempts} lần chạy" if run.attempts > 1 else ": Kỳ hỏng"
    return f"{headline}.\nLí do: {run.reason}"

"""Gom Tin: gom các Bài gốc cùng nói về một sự kiện thành ứng viên Tin, và đối chiếu ứng viên với
các Tin đã phát của cùng Chuyên mục.

Đây là bước cố định, không phải Agent (ADR 0001). Độ giống nghĩa là cosine giữa các vector nhúng
của Bài gốc, lưu và so trong Postgres bằng pgvector.
"""

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Float, select
from sqlalchemy.orm import Session, aliased

from siftly.embeddings import Embedder
from siftly.models import Article, Bulletin, Run, RunOutcome, Story, candidate_articles

log = logging.getLogger(__name__)

# Hai Bài gốc giống nhau từ mức này trở lên thì coi là cùng một sự kiện. Chọn bằng cách đo trên
# RSS thật với BAAI/bge-m3; xem docs/clustering.md trước khi đổi.
SAME_EVENT_THRESHOLD = 0.78
# Ứng viên chỉ được đối chiếu với các Tin đã phát trong khoảng này. Chuyện cũ hơn mà xuất hiện lại
# thường là một sự kiện mới cùng chủ đề (ví dụ đời điện thoại năm sau), không phải tin trùng.
PUBLISHED_LOOKBACK = timedelta(days=7)


@dataclass(frozen=True)
class ArticleCluster:
    """Một ứng viên Tin: các Bài gốc cùng nói về một sự kiện, xuất hiện sớm nhất trước."""

    articles: tuple[Article, ...]
    # Tin đã phát của cùng Chuyên mục mà cụm này giống nhất; None là chuyện chưa phát.
    published_story_id: int | None


def cluster(
    session: Session,
    embedder: Embedder,
    section_id: int,
    articles: Sequence[Article],
    run_at: datetime,
) -> list[ArticleCluster]:
    """Gom `articles` thành các ứng viên Tin, ứng viên có Bài gốc mới nhất đứng trước.

    Bài gốc nào chưa có vector của model hiện tại thì được nhúng và lưu lại. Ném lỗi khi không
    nhúng được.
    """
    if not articles:
        return []
    ids = [article.id for article in articles]
    published = session.execute(
        select(Story.id, candidate_articles.c.article_id, Run.run_at)
        .join(Bulletin, Bulletin.id == Story.bulletin_id)
        .join(Run, Run.id == Bulletin.run_id)
        .join(candidate_articles, candidate_articles.c.candidate_id == Story.candidate_id)
        .where(
            Run.section_id == section_id,
            # Tin của Kỳ không phát hay hỏng chưa tới người đọc nào.
            Run.outcome == RunOutcome.PUBLISHED,
            Run.run_at >= run_at - PUBLISHED_LOOKBACK,
            Run.run_at < run_at,
            Story.drop_reason.is_(None),
        )
    ).all()
    _embed_missing(session, embedder, {*ids, *(row.article_id for row in published)})

    stories_with_article = defaultdict(list)
    for row in published:
        stories_with_article[row.article_id].append((row.run_at, row.id))
    # Với mỗi Bài gốc của Kỳ: Tin đã phát giống nó nhất, hoà thì Tin phát gần đây hơn.
    closest_story: dict[int, tuple[float, datetime, int]] = {}
    for article_id, published_article_id, similarity in _similar_pairs(
        session, ids, list(stories_with_article)
    ):
        for published_at, story_id in stories_with_article[published_article_id]:
            closest_story[article_id] = max(
                closest_story.get(article_id, (-1.0, published_at, 0)),
                (similarity, published_at, story_id),
            )

    by_id = {article.id: article for article in articles}
    clusters = []
    for group in _complete_linkage(ids, _similar_pairs(session, ids, ids)):
        closest = max((closest_story[i] for i in group if i in closest_story), default=None)
        clusters.append(
            ArticleCluster(
                tuple(sorted((by_id[i] for i in group), key=lambda a: (a.appeared_at, a.id))),
                closest[2] if closest else None,
            )
        )
    # Mới nhất trước, như thứ tự Bài gốc trước khi có Gom Tin.
    clusters.sort(
        key=lambda c: (max(a.appeared_at for a in c.articles), -c.articles[0].id), reverse=True
    )
    log.info("Gom %s Bài gốc thành %s ứng viên Tin", len(articles), len(clusters))
    return clusters


def embedding_text(article: Article) -> str:
    """Phần của Bài gốc được nhúng để so độ giống nghĩa: tiêu đề, và mô tả nếu có.

    Chỉ tiêu đề thì hai bài khác ngôn ngữ về cùng một sự kiện thường không đủ giống (xem
    docs/clustering.md).
    """
    return "\n".join(filter(None, (article.title, article.description)))


def _embed_missing(session: Session, embedder: Embedder, ids: set[int]) -> None:
    """Nhúng và lưu vector cho các Bài gốc trong `ids` chưa có vector của model hiện tại."""
    missing = list(
        session.scalars(
            select(Article)
            .where(
                Article.id.in_(ids),
                Article.embedding_model.is_distinct_from(embedder.model),
            )
            .order_by(Article.id)
        )
    )
    if not missing:
        return
    vectors = embedder.embed([embedding_text(article) for article in missing])
    for article, vector in zip(missing, vectors, strict=True):
        article.embedding, article.embedding_model = vector, embedder.model
    session.flush()


def _similar_pairs(
    session: Session, ids_a: Sequence[int], ids_b: Sequence[int]
) -> list[tuple[int, int, float]]:
    """Các cặp (Bài gốc trong `ids_a`, Bài gốc khác trong `ids_b`) giống nhau từ ngưỡng trở lên,
    kèm độ giống."""
    if not ids_a or not ids_b:
        return []
    a, b = aliased(Article), aliased(Article)
    distance = a.embedding.op("<=>", return_type=Float)(b.embedding)
    rows = session.execute(
        select(a.id, b.id, 1 - distance).where(
            a.id.in_(ids_a),
            b.id.in_(ids_b),
            a.id != b.id,
            distance <= 1 - SAME_EVENT_THRESHOLD,
        )
    )
    return [(id_1, id_2, float(similarity)) for id_1, id_2, similarity in rows]


def _complete_linkage(
    ids: Sequence[int], pairs: Sequence[tuple[int, int, float]]
) -> list[frozenset[int]]:
    """Gom theo kiểu liên kết đầy đủ: hai cụm chỉ nhập làm một khi mọi cặp Bài gốc giữa chúng đều
    đủ giống. Nhờ vậy A giống B, B giống C mà A không giống C thì A và C không chung cụm.

    Cặp giống nhất được xét trước. Trả về các cụm theo thứ tự Bài gốc đầu tiên của chúng trong
    `ids`.
    """
    similar = {frozenset((i1, i2)) for i1, i2, _ in pairs}
    group_of: dict[int, frozenset[int]] = {i: frozenset((i,)) for i in ids}
    for i1, i2, _ in sorted(pairs, key=lambda p: (-p[2], p[0], p[1])):
        g1, g2 = group_of[i1], group_of[i2]
        if g1 is g2 or not all(frozenset((x, y)) in similar for x in g1 for y in g2):
            continue
        merged = g1 | g2
        for i in merged:
            group_of[i] = merged
    seen: set[frozenset[int]] = set()
    groups = []
    for i in ids:
        if group_of[i] not in seen:
            seen.add(group_of[i])
            groups.append(group_of[i])
    return groups

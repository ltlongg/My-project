import { CircleAlertIcon, ClockIcon, FileTextIcon, NewspaperIcon, TagIcon } from 'lucide-react'

import { formatAgo, formatTime } from '@/lib/format'
import { kindLabel, type Kind } from '@/lib/kinds'
import type { Source } from '@/lib/sources'

// Tình trạng của Nguồn: loại, Chuyên mục, lần lấy gần nhất, số Bài gốc gần đây, lỗi gần nhất.
export function SourceHealth({
  source,
  kinds,
  names,
}: {
  source: Source
  kinds?: Kind[]
  names?: string
}) {
  return (
    <div className="flex flex-col gap-3">
      <dl className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <TagIcon className="size-4" />
          <dt className="sr-only">Loại</dt>
          <dd>{kindLabel(kinds, source.kind)}</dd>
        </div>
        {names !== undefined && (
          <div className="flex min-w-0 items-center gap-1.5">
            <NewspaperIcon className="size-4 shrink-0" />
            <dt className="sr-only">Chuyên mục</dt>
            <dd className="truncate">{names || 'Chưa gắn vào Chuyên mục nào'}</dd>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <ClockIcon className="size-4" />
          <dt className="sr-only">Lần lấy gần nhất</dt>
          <dd>
            {source.last_fetched_at ? (
              <time dateTime={source.last_fetched_at} title={formatTime(source.last_fetched_at)}>
                Lấy {formatAgo(source.last_fetched_at)}
              </time>
            ) : (
              'Chưa lấy lần nào'
            )}
          </dd>
        </div>
        <div className="flex items-center gap-1.5">
          <FileTextIcon className="size-4" />
          <dt className="sr-only">Bài gốc gần đây</dt>
          <dd>{source.recent_articles} Bài gốc trong 7 ngày qua</dd>
        </div>
      </dl>
      {source.last_error && (
        <p className="flex gap-1.5 text-sm text-destructive">
          <CircleAlertIcon className="mt-0.5 size-4 shrink-0" />
          <span className="min-w-0 break-words">Lần lấy gần nhất lỗi: {source.last_error}</span>
        </p>
      )}
    </div>
  )
}

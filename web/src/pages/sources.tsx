import { PlusIcon, RssIcon } from 'lucide-react'
import { Link } from 'react-router'

import { EnabledStatus, EnabledSwitch } from '@/components/enabled'
import { PageHeader } from '@/components/page'
import { SourceHealth } from '@/components/source-health'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { Kind } from '@/lib/kinds'
import { sectionNames, useSections, type Section } from '@/lib/sections'
import { useSourceKinds, useSources, useUpdateSource, type Source } from '@/lib/sources'

export function SourcesPage() {
  const sources = useSources()
  const kinds = useSourceKinds()
  const sections = useSections()

  return (
    <>
      <PageHeader
        title="Nguồn"
        description="Nơi hệ thống lấy Bài gốc về. Một Nguồn gắn được vào nhiều Chuyên mục."
        actions={
          <Button asChild size="lg">
            <Link to="/sources/new">
              <PlusIcon />
              Thêm Nguồn
            </Link>
          </Button>
        }
      />
      {sources.isPending && (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-40 rounded-xl" />
          <Skeleton className="h-40 rounded-xl" />
        </div>
      )}
      {sources.isError && (
        <Alert variant="destructive">
          <AlertTitle>Không tải được danh sách Nguồn</AlertTitle>
          <AlertDescription>{sources.error.message}</AlertDescription>
        </Alert>
      )}
      {sources.isSuccess && sources.data.length === 0 && <EmptyState />}
      {sources.isSuccess && (
        <div className="flex flex-col gap-4">
          {sources.data.map((source) => (
            <SourceCard
              key={source.id}
              source={source}
              kinds={kinds.data}
              sections={sections.data}
            />
          ))}
        </div>
      )}
    </>
  )
}

function SourceCard({
  source,
  kinds,
  sections,
}: {
  source: Source
  kinds?: Kind[]
  sections?: Section[]
}) {
  const update = useUpdateSource(source.id)
  const names = sectionNames(sections, source.section_ids)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-lg">
          <Link to={`/sources/${source.id}`} className="hover:underline">
            {source.name}
          </Link>
          <EnabledStatus enabled={source.is_enabled} />
          {source.last_error && <Badge variant="destructive">Lỗi</Badge>}
        </CardTitle>
        <CardDescription className="line-clamp-2 break-all">{source.url}</CardDescription>
        <CardAction>
          <Button asChild variant="outline">
            <Link to={`/sources/${source.id}`}>Sửa</Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <SourceHealth source={source} kinds={kinds} names={names} />
        <div className="flex justify-end">
          <EnabledSwitch
            id={`enabled-${source.id}`}
            name={source.name}
            enabled={source.is_enabled}
            pending={update.isPending}
            onChange={(enabled, done) => update.mutate({ is_enabled: enabled }, done)}
          />
        </div>
      </CardContent>
    </Card>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed px-6 py-12 text-center">
      <RssIcon className="mb-3 size-8 text-muted-foreground" />
      <p className="font-medium">Chưa có Nguồn nào</p>
      <p className="mt-1 mb-4 text-sm text-muted-foreground">
        Thêm một feed RSS, bấm thử để xem nó trả về gì, rồi gắn vào Chuyên mục.
      </p>
      <Button asChild>
        <Link to="/sources/new">
          <PlusIcon />
          Thêm Nguồn
        </Link>
      </Button>
    </div>
  )
}

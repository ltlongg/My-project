import { AtSignIcon, NewspaperIcon, PlusIcon, SendIcon, TagIcon } from 'lucide-react'
import { Link } from 'react-router'

import { EnabledStatus, EnabledSwitch } from '@/components/enabled'
import { PageHeader } from '@/components/page'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useChannelKinds, useChannels, useUpdateChannel, type Channel } from '@/lib/channels'
import { kindLabel, type Kind } from '@/lib/kinds'
import { sectionNames, useSections, type Section } from '@/lib/sections'

export function ChannelsPage() {
  const channels = useChannels()
  const kinds = useChannelKinds()
  const sections = useSections()

  return (
    <>
      <PageHeader
        title="Kênh đăng"
        description="Nơi Bản tin được phát tới. Mỗi Chuyên mục phát tới mọi Kênh đăng đang bật của nó."
        actions={
          <Button asChild size="lg">
            <Link to="/channels/new">
              <PlusIcon />
              Thêm Kênh đăng
            </Link>
          </Button>
        }
      />
      {channels.isPending && (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-32 rounded-xl" />
          <Skeleton className="h-32 rounded-xl" />
        </div>
      )}
      {channels.isError && (
        <Alert variant="destructive">
          <AlertTitle>Không tải được danh sách Kênh đăng</AlertTitle>
          <AlertDescription>{channels.error.message}</AlertDescription>
        </Alert>
      )}
      {channels.isSuccess && channels.data.length === 0 && <EmptyState />}
      {channels.isSuccess && (
        <div className="flex flex-col gap-4">
          {channels.data.map((channel) => (
            <ChannelCard
              key={channel.id}
              channel={channel}
              kinds={kinds.data}
              sections={sections.data}
            />
          ))}
        </div>
      )}
    </>
  )
}

function ChannelCard({
  channel,
  kinds,
  sections,
}: {
  channel: Channel
  kinds?: Kind[]
  sections?: Section[]
}) {
  const update = useUpdateChannel(channel.id)
  const names = sectionNames(sections, channel.section_ids)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-lg">
          <Link to={`/channels/${channel.id}`} className="hover:underline">
            {channel.name}
          </Link>
          <EnabledStatus enabled={channel.is_enabled} />
        </CardTitle>
        <CardAction>
          <Button asChild variant="outline">
            <Link to={`/channels/${channel.id}`}>Sửa</Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <dl className="flex min-w-0 flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <TagIcon className="size-4" />
            <dt className="sr-only">Loại</dt>
            <dd>{kindLabel(kinds, channel.kind)}</dd>
          </div>
          <div className="flex min-w-0 items-center gap-1.5">
            <AtSignIcon className="size-4 shrink-0" />
            <dt className="sr-only">Mã</dt>
            <dd className="truncate">
              <code>{channel.address}</code>
            </dd>
          </div>
          {names !== undefined && (
            <div className="flex min-w-0 items-center gap-1.5">
              <NewspaperIcon className="size-4 shrink-0" />
              <dt className="sr-only">Chuyên mục</dt>
              <dd className="truncate">{names || 'Chưa gắn vào Chuyên mục nào'}</dd>
            </div>
          )}
        </dl>
        <EnabledSwitch
          id={`enabled-${channel.id}`}
          name={channel.name}
          enabled={channel.is_enabled}
          pending={update.isPending}
          onChange={(enabled, done) => update.mutate({ is_enabled: enabled }, done)}
        />
      </CardContent>
    </Card>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed px-6 py-12 text-center">
      <SendIcon className="mb-3 size-8 text-muted-foreground" />
      <p className="font-medium">Chưa có Kênh đăng nào</p>
      <p className="mt-1 mb-4 text-sm text-muted-foreground">
        Thêm bot vào một nhóm Telegram, rồi khai nhóm đó ở đây và gửi một tin nhắn thử.
      </p>
      <Button asChild>
        <Link to="/channels/new">
          <PlusIcon />
          Thêm Kênh đăng
        </Link>
      </Button>
    </div>
  )
}

import { ClockIcon, ListOrderedIcon, NewspaperIcon, PlusIcon } from 'lucide-react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { PageHeader } from '@/components/page'
import { SectionStatus } from '@/components/section-status'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { useSections, useUpdateSection, type Section } from '@/lib/sections'

export function SectionsPage() {
  const sections = useSections()

  return (
    <>
      <PageHeader
        title="Chuyên mục"
        description="Mỗi Chuyên mục là một dòng Bản tin với phạm vi và giờ phát riêng."
        actions={
          <Button asChild size="lg">
            <Link to="/sections/new">
              <PlusIcon />
              Tạo Chuyên mục
            </Link>
          </Button>
        }
      />
      {sections.isPending && (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-36 rounded-xl" />
          <Skeleton className="h-36 rounded-xl" />
        </div>
      )}
      {sections.isError && (
        <Alert variant="destructive">
          <AlertTitle>Không tải được danh sách Chuyên mục</AlertTitle>
          <AlertDescription>{sections.error.message}</AlertDescription>
        </Alert>
      )}
      {sections.isSuccess && sections.data.length === 0 && <EmptyState />}
      {sections.isSuccess && (
        <div className="flex flex-col gap-4">
          {sections.data.map((section) => (
            <SectionCard key={section.id} section={section} />
          ))}
        </div>
      )}
    </>
  )
}

function SectionCard({ section }: { section: Section }) {
  const update = useUpdateSection(section.id)
  const switchId = `running-${section.id}`

  function setRunning(running: boolean) {
    update.mutate(
      { is_paused: !running },
      {
        onSuccess: () =>
          toast.success(
            running ? `Đã bật lại ${section.name}` : `Đã tạm dừng ${section.name}`,
          ),
        onError: (error) => toast.error(error.message),
      },
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-lg">
          <Link to={`/sections/${section.id}`} className="hover:underline">
            {section.name}
          </Link>
          <SectionStatus paused={section.is_paused} />
        </CardTitle>
        <CardDescription className="line-clamp-2">{section.scope || 'Chưa có mô tả phạm vi.'}</CardDescription>
        <CardAction>
          <Button asChild variant="outline">
            <Link to={`/sections/${section.id}`}>Sửa</Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <dl className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <ClockIcon className="size-4" />
            <dt className="sr-only">Giờ phát</dt>
            <dd>Phát lúc {section.publish_time}</dd>
          </div>
          <div className="flex items-center gap-1.5">
            <ListOrderedIcon className="size-4" />
            <dt className="sr-only">Số Tin</dt>
            <dd>Tối đa {section.max_stories} Tin</dd>
          </div>
        </dl>
        <div className="flex items-center gap-2">
          <Switch
            id={switchId}
            checked={!section.is_paused}
            disabled={update.isPending}
            onCheckedChange={setRunning}
          />
          <Label htmlFor={switchId} className="font-normal">
            {section.is_paused ? 'Đang tạm dừng' : 'Đang chạy'}
          </Label>
        </div>
      </CardContent>
    </Card>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed px-6 py-12 text-center">
      <NewspaperIcon className="mb-3 size-8 text-muted-foreground" />
      <p className="font-medium">Chưa có Chuyên mục nào</p>
      <p className="mt-1 mb-4 text-sm text-muted-foreground">
        Tạo Chuyên mục đầu tiên, hoặc chạy <code>siftly init</code> để có sẵn Chuyên mục công nghệ.
      </p>
      <Button asChild>
        <Link to="/sections/new">
          <PlusIcon />
          Tạo Chuyên mục
        </Link>
      </Button>
    </div>
  )
}

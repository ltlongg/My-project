import { ChevronLeftIcon, PlusIcon } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import { Field, PageHeader } from '@/components/page'
import { EnabledStatus } from '@/components/enabled'
import { SectionStatus } from '@/components/section-status'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/lib/api'
import { useChannels } from '@/lib/channels'
import {
  MAX_STORIES,
  MIN_STORIES,
  useCreateSection,
  useSection,
  useUpdateSection,
  type Section,
  type SectionFields,
} from '@/lib/sections'
import { useSources } from '@/lib/sources'

const BLANK: SectionFields = { name: '', scope: '', publish_time: '08:00', max_stories: 7 }

function BackLink() {
  return (
    <Link
      to="/sections"
      className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ChevronLeftIcon className="size-4" />
      Chuyên mục
    </Link>
  )
}

export function NewSectionPage() {
  const create = useCreateSection()
  const navigate = useNavigate()

  return (
    <>
      <PageHeader
        back={<BackLink />}
        title="Tạo Chuyên mục"
        description="Chuyên mục mới ở trạng thái tạm dừng; bật nó khi đã có Nguồn và Kênh đăng."
      />
      <SectionForm
        initial={BLANK}
        submitLabel="Tạo Chuyên mục"
        pending={create.isPending}
        error={create.error}
        onSubmit={(fields) =>
          create.mutate(fields, {
            onSuccess: (section) => {
              toast.success(`Đã tạo ${section.name}`)
              navigate(`/sections/${section.id}`, { replace: true })
            },
          })
        }
      />
    </>
  )
}

export function EditSectionPage() {
  const id = Number(useParams().id)
  const section = useSection(id)

  if (section.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    )
  }
  if (section.isError) {
    return (
      <>
        <BackLink />
        <Alert variant="destructive">
          <AlertTitle>Không mở được Chuyên mục</AlertTitle>
          <AlertDescription>{section.error.message}</AlertDescription>
        </Alert>
      </>
    )
  }
  // `key` dựng lại biểu mẫu khi chuyển sang Chuyên mục khác.
  return <EditSection key={section.data.id} section={section.data} />
}

function EditSection({ section }: { section: Section }) {
  const update = useUpdateSection(section.id)
  const pause = useUpdateSection(section.id)

  function setRunning(running: boolean) {
    pause.mutate(
      { is_paused: !running },
      {
        onSuccess: () => toast.success(running ? 'Đã bật lại Chuyên mục' : 'Đã tạm dừng Chuyên mục'),
        onError: (error) => toast.error(error.message),
      },
    )
  }

  return (
    <>
      <PageHeader
        back={<BackLink />}
        title={
          <span className="flex flex-wrap items-center gap-2">
            {section.name}
            <SectionStatus paused={section.is_paused} />
          </span>
        }
        description={
          <>
            Mã <code className="rounded bg-muted px-1 py-0.5 text-foreground">{section.slug}</code>,
            dùng ở dòng lệnh <code>siftly run {section.slug}</code>.
          </>
        }
      />
      <div className="flex flex-col gap-6">
        <SectionForm
          initial={section}
          submitLabel="Lưu thay đổi"
          pending={update.isPending}
          error={update.error}
          onSubmit={(fields) =>
            update.mutate(fields, { onSuccess: () => toast.success('Đã lưu. Có hiệu lực từ Kỳ kế tiếp.') })
          }
        />
        <Attached section={section} />
        <Card>
          <CardHeader>
            <CardTitle>Tạm dừng</CardTitle>
            <CardDescription>
              Khi tạm dừng, Lịch không chạy Kỳ nào cho Chuyên mục này. Thiết lập, Nguồn và Kênh
              đăng vẫn giữ nguyên.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex items-center gap-3">
            <Switch
              id="running"
              checked={!section.is_paused}
              disabled={pause.isPending}
              onCheckedChange={setRunning}
            />
            <Label htmlFor="running" className="font-normal">
              {section.is_paused ? 'Đang tạm dừng' : 'Đang chạy'}
            </Label>
          </CardContent>
        </Card>
      </div>
    </>
  )
}

// Nguồn và Kênh đăng đã gắn vào Chuyên mục; gắn và gỡ ở trang của từng Nguồn, Kênh đăng.
function Attached({ section }: { section: Section }) {
  const sources = useSources()
  const channels = useChannels()
  const groups = [
    {
      title: 'Nguồn',
      add: 'Thêm Nguồn',
      path: '/sources',
      none: 'Chưa có Nguồn nào. Kỳ không có gì để thu thập.',
      items: sources.data,
      error: sources.error,
    },
    {
      title: 'Kênh đăng',
      add: 'Thêm Kênh đăng',
      path: '/channels',
      none: 'Chưa có Kênh đăng nào. Bản tin không có nơi để phát.',
      items: channels.data,
      error: channels.error,
    },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Nguồn và Kênh đăng</CardTitle>
        <CardDescription>
          Kỳ chỉ dùng những cái đang bật. Gắn thêm hay gỡ ra ở trang của từng Nguồn và Kênh đăng.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 sm:grid-cols-2">
        {groups.map((group) => {
          const attached = group.items?.filter((item) => item.section_ids.includes(section.id))
          return (
            <div key={group.title} className="flex min-w-0 flex-col gap-2">
              <h3 className="text-sm font-medium">{group.title}</h3>
              {group.error && <p className="text-sm text-destructive">{group.error.message}</p>}
              {!attached && !group.error && <Skeleton className="h-16 rounded-lg" />}
              {attached?.length === 0 && (
                <p className="text-sm text-muted-foreground">{group.none}</p>
              )}
              {attached && attached.length > 0 && (
                <ul className="flex flex-col divide-y rounded-lg border">
                  {attached.map((item) => (
                    <li key={item.id} className="flex items-center gap-2 px-3 py-2.5 text-sm">
                      <Link
                        to={`${group.path}/${item.id}`}
                        className="min-w-0 flex-1 truncate hover:underline"
                      >
                        {item.name}
                      </Link>
                      <EnabledStatus enabled={item.is_enabled} />
                    </li>
                  ))}
                </ul>
              )}
              <Button asChild variant="outline" className="self-start">
                <Link to={`${group.path}/new?section=${section.id}`}>
                  <PlusIcon />
                  {group.add}
                </Link>
              </Button>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

function SectionForm({
  initial,
  submitLabel,
  pending,
  error,
  onSubmit,
}: {
  initial: SectionFields
  submitLabel: string
  pending: boolean
  error: Error | null
  onSubmit: (fields: SectionFields) => void
}) {
  const [name, setName] = useState(initial.name)
  const [scope, setScope] = useState(initial.scope)
  const [publishTime, setPublishTime] = useState(initial.publish_time)
  const [maxStories, setMaxStories] = useState(String(initial.max_stories))
  const fields = error instanceof ApiError ? error.fields : {}
  const unchanged =
    name === initial.name &&
    scope === initial.scope &&
    publishTime === initial.publish_time &&
    maxStories === String(initial.max_stories)

  function submit(event: FormEvent) {
    event.preventDefault()
    onSubmit({ name, scope, publish_time: publishTime, max_stories: Number(maxStories) })
  }

  function invalid(field: string) {
    return fields[field]
      ? { 'aria-invalid': true, 'aria-describedby': `${field}-error` }
      : {}
  }

  return (
    <Card>
      <form onSubmit={submit}>
        <CardContent className="flex flex-col gap-5">
          {error && !(error instanceof ApiError && Object.keys(fields).length > 0) && (
            <Alert variant="destructive">
              <AlertDescription>{error.message}</AlertDescription>
            </Alert>
          )}
          <Field id="name" label="Tên" error={fields.name} hint="Hiện ở tin nhắn mở đầu mỗi Bản tin.">
            <Input
              id="name"
              required
              maxLength={80}
              placeholder="Ví dụ: Thời sự"
              value={name}
              onChange={(event) => setName(event.target.value)}
              {...invalid('name')}
            />
          </Field>
          <Field
            id="scope"
            label="Mô tả phạm vi"
            error={fields.scope}
            hint="Sơ tuyển và Biên tập đọc mô tả này để biết Tin nào thuộc Chuyên mục. Nêu cả những gì không muốn nhận."
          >
            <Textarea
              id="scope"
              required
              rows={4}
              maxLength={2000}
              placeholder="Ví dụ: Tin trong nước và thế giới về chính sách, kinh tế vĩ mô và các sự kiện lớn. Không nhận tin giải trí."
              value={scope}
              onChange={(event) => setScope(event.target.value)}
              {...invalid('scope')}
            />
          </Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field
              id="publish_time"
              label="Giờ phát"
              error={fields.publish_time}
              hint="Giờ Việt Nam, mỗi ngày một Bản tin."
            >
              <Input
                id="publish_time"
                type="time"
                required
                value={publishTime}
                onChange={(event) => setPublishTime(event.target.value)}
                {...invalid('publish_time')}
              />
            </Field>
            <Field
              id="max_stories"
              label="Số Tin mỗi Bản tin"
              error={fields.max_stories}
              hint={`Tối đa, từ ${MIN_STORIES} đến ${MAX_STORIES}. Dưới ${MIN_STORIES} Tin qua Kiểm chứng thì không phát.`}
            >
              <Input
                id="max_stories"
                type="number"
                inputMode="numeric"
                required
                min={MIN_STORIES}
                max={MAX_STORIES}
                value={maxStories}
                onChange={(event) => setMaxStories(event.target.value)}
                {...invalid('max_stories')}
              />
            </Field>
          </div>
          <div className="flex flex-col-reverse gap-2 border-t pt-5 sm:flex-row sm:justify-end">
            <Button asChild variant="outline" size="lg">
              <Link to="/sections">Huỷ</Link>
            </Button>
            <Button type="submit" size="lg" disabled={pending || unchanged}>
              {pending ? 'Đang lưu…' : submitLabel}
            </Button>
          </div>
        </CardContent>
      </form>
    </Card>
  )
}

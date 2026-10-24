import { ChevronLeftIcon, CircleCheckIcon, FlaskConicalIcon } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { toast } from 'sonner'

import { EnabledStatus, EnabledSwitch } from '@/components/enabled'
import { KindSelect } from '@/components/kind-select'
import { Field, PageHeader } from '@/components/page'
import { SectionPicker } from '@/components/section-picker'
import { SourceHealth } from '@/components/source-health'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api'
import { formatAgo, formatTime } from '@/lib/format'
import { kindLabel, type Kind } from '@/lib/kinds'
import {
  useCreateSource,
  useSource,
  useSourceKinds,
  useTrySource,
  useUpdateSource,
  type Source,
  type SourceFields,
  type SourceTrial,
} from '@/lib/sources'

function BackLink() {
  return (
    <Link
      to="/sources"
      className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ChevronLeftIcon className="size-4" />
      Nguồn
    </Link>
  )
}

function Loading() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-10 w-48" />
      <Skeleton className="h-96 rounded-xl" />
    </div>
  )
}

export function NewSourcePage() {
  const create = useCreateSource()
  const kinds = useSourceKinds()
  const navigate = useNavigate()
  // Mở từ trang của một Chuyên mục thì Nguồn mới gắn sẵn vào Chuyên mục đó.
  const section = Number(useSearchParams()[0].get('section'))

  if (kinds.isPending) return <Loading />
  if (kinds.isError) {
    return (
      <>
        <BackLink />
        <Alert variant="destructive">
          <AlertTitle>Không tải được các loại Nguồn</AlertTitle>
          <AlertDescription>{kinds.error.message}</AlertDescription>
        </Alert>
      </>
    )
  }
  return (
    <>
      <PageHeader
        back={<BackLink />}
        title="Thêm Nguồn"
        description="Bấm lấy thử để chắc là đúng Nguồn trước khi lưu."
      />
      <SourceForm
        kinds={kinds.data}
        initial={{
          kind: kinds.data[0]?.kind ?? '',
          name: '',
          url: '',
          section_ids: section ? [section] : [],
        }}
        submitLabel="Thêm Nguồn"
        pending={create.isPending}
        error={create.error}
        onSubmit={(fields) =>
          create.mutate(fields, {
            onSuccess: (source) => {
              toast.success(`Đã thêm ${source.name}`)
              navigate('/sources', { replace: true })
            },
          })
        }
      />
    </>
  )
}

export function EditSourcePage() {
  const id = Number(useParams().id)
  const source = useSource(id)
  const kinds = useSourceKinds()

  if (source.isPending || kinds.isPending) return <Loading />
  if (source.isError || kinds.isError) {
    return (
      <>
        <BackLink />
        <Alert variant="destructive">
          <AlertTitle>Không mở được Nguồn</AlertTitle>
          <AlertDescription>{(source.error ?? kinds.error)?.message}</AlertDescription>
        </Alert>
      </>
    )
  }
  // `key` dựng lại biểu mẫu khi chuyển sang Nguồn khác.
  return <EditSource key={source.data.id} source={source.data} kinds={kinds.data} />
}

function EditSource({ source, kinds }: { source: Source; kinds: Kind[] }) {
  const update = useUpdateSource(source.id)
  const toggle = useUpdateSource(source.id)

  return (
    <>
      <PageHeader
        back={<BackLink />}
        title={
          <span className="flex flex-wrap items-center gap-2">
            {source.name}
            <EnabledStatus enabled={source.is_enabled} />
          </span>
        }
        description={`Nguồn loại ${kindLabel(kinds, source.kind)}.`}
      />
      <div className="flex flex-col gap-6">
        <SourceForm
          kinds={kinds}
          kindLocked
          initial={source}
          submitLabel="Lưu thay đổi"
          pending={update.isPending}
          error={update.error}
          onSubmit={({ name, url, section_ids }) =>
            update.mutate(
              { name, url, section_ids },
              { onSuccess: () => toast.success('Đã lưu. Có hiệu lực từ lần thu thập kế tiếp.') },
            )
          }
        />
        <Card>
          <CardHeader>
            <CardTitle>Tình trạng</CardTitle>
            <CardDescription>
              Lịch thu thập mỗi giờ, và một lần ngay trước mỗi Kỳ, các Nguồn đang bật của Chuyên mục
              đang chạy.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SourceHealth source={source} kinds={kinds} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Tắt Nguồn</CardTitle>
            <CardDescription>
              Nguồn đang tắt không được thu thập và không góp Bài gốc cho Kỳ nào. Thiết lập và các
              Chuyên mục đã gắn vẫn giữ nguyên.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <EnabledSwitch
              id="enabled"
              name={source.name}
              enabled={source.is_enabled}
              pending={toggle.isPending}
              onChange={(enabled, done) => toggle.mutate({ is_enabled: enabled }, done)}
            />
          </CardContent>
        </Card>
      </div>
    </>
  )
}

type FormValues = SourceFields & { kind: string }

function SourceForm({
  kinds,
  kindLocked = false,
  initial,
  submitLabel,
  pending,
  error,
  onSubmit,
}: {
  kinds: Kind[]
  kindLocked?: boolean
  initial: FormValues
  submitLabel: string
  pending: boolean
  error: Error | null
  onSubmit: (fields: FormValues) => void
}) {
  const [kind, setKind] = useState(initial.kind)
  const [name, setName] = useState(initial.name)
  const [url, setUrl] = useState(initial.url)
  const [sectionIds, setSectionIds] = useState(initial.section_ids)
  const trial = useTrySource()
  // Kết quả lấy thử chỉ còn đúng khi loại và địa chỉ chưa đổi kể từ lúc bấm.
  const [triedFor, setTriedFor] = useState<string | null>(null)
  const current = `${kind} ${url.trim()}`
  const info = kinds.find((item) => item.kind === kind)
  const fields = {
    ...(trial.error instanceof ApiError && triedFor === current ? trial.error.fields : {}),
    ...(error instanceof ApiError ? error.fields : {}),
  }
  const unchanged =
    name === initial.name &&
    url === initial.url &&
    sectionIds.join() === initial.section_ids.join()

  function submit(event: FormEvent) {
    event.preventDefault()
    onSubmit({ kind, name, url, section_ids: sectionIds })
  }

  function tryIt() {
    setTriedFor(current)
    trial.mutate({ kind, url })
  }

  function invalid(field: string) {
    return fields[field] ? { 'aria-invalid': true, 'aria-describedby': `${field}-error` } : {}
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
          <Field
            id="kind"
            label="Loại"
            error={fields.kind}
            hint={kindLocked ? 'Loại không đổi được sau khi thêm.' : undefined}
          >
            <KindSelect
              id="kind"
              kinds={kinds}
              value={kind}
              onChange={setKind}
              disabled={kindLocked}
            />
          </Field>
          <Field id="name" label="Tên" error={fields.name} hint="Biên tập thấy tên này cạnh mỗi Bài gốc.">
            <Input
              id="name"
              required
              maxLength={80}
              placeholder="Ví dụ: VnExpress Khoa học công nghệ"
              value={name}
              onChange={(event) => setName(event.target.value)}
              {...invalid('name')}
            />
          </Field>
          <Field
            id="url"
            label={info?.address_label ?? 'Địa chỉ'}
            error={fields.url}
            hint={info?.hint}
          >
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                id="url"
                required
                type="url"
                inputMode="url"
                maxLength={2000}
                placeholder={info?.placeholder}
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                {...invalid('url')}
              />
              <Button
                type="button"
                variant="outline"
                className="shrink-0"
                disabled={!url.trim() || trial.isPending}
                onClick={tryIt}
              >
                <FlaskConicalIcon />
                {trial.isPending ? 'Đang lấy…' : 'Lấy thử'}
              </Button>
            </div>
          </Field>
          {trial.isSuccess && triedFor === current && <TrialView result={trial.data} />}
          {trial.error && !(trial.error instanceof ApiError && trial.error.status === 422) && (
            <Alert variant="destructive">
              <AlertDescription>{trial.error.message}</AlertDescription>
            </Alert>
          )}
          <SectionPicker
            label="Chuyên mục"
            hint="Bài gốc của Nguồn góp ứng viên cho mọi Chuyên mục được đánh dấu, và chỉ lưu một lần."
            value={sectionIds}
            onChange={setSectionIds}
            error={fields.section_ids}
          />
          <div className="flex flex-col-reverse gap-2 border-t pt-5 sm:flex-row sm:justify-end">
            <Button asChild variant="outline" size="lg">
              <Link to="/sources">Huỷ</Link>
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

// Kết quả lấy thử: vài Bài gốc mới nhất, hoặc vì sao không lấy được.
function TrialView({ result }: { result: SourceTrial }) {
  if (result.error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Không lấy được Nguồn</AlertTitle>
        <AlertDescription className="break-words">{result.error}</AlertDescription>
      </Alert>
    )
  }
  if (result.total === 0) {
    return (
      <Alert>
        <AlertTitle>Nguồn trả lời nhưng chưa có Bài gốc nào</AlertTitle>
        <AlertDescription>Kiểm tra lại địa chỉ, hoặc thử lại sau khi Nguồn có bài mới.</AlertDescription>
      </Alert>
    )
  }
  return (
    <div className="rounded-lg border bg-muted/40 p-4">
      <p className="mb-3 flex items-center gap-1.5 text-sm font-medium text-success">
        <CircleCheckIcon className="size-4 shrink-0" />
        Lấy được {result.total} Bài gốc
        {result.total > result.articles.length && `, đây là ${result.articles.length} bài mới nhất`}
      </p>
      <ol className="flex flex-col gap-3">
        {result.articles.map((article) => (
          <li key={article.url} className="min-w-0 text-sm">
            <a
              href={article.url}
              target="_blank"
              rel="noreferrer"
              className="font-medium break-words hover:underline"
            >
              {article.title}
            </a>
            <p className="text-muted-foreground">
              {article.published_at ? (
                <time dateTime={article.published_at} title={formatTime(article.published_at)}>
                  {formatAgo(article.published_at)}
                </time>
              ) : (
                'Không ghi giờ xuất bản'
              )}
            </p>
            {article.description && (
              <p className="mt-0.5 line-clamp-2 text-muted-foreground">{article.description}</p>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}

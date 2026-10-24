import { ChevronLeftIcon, CircleCheckIcon, SendIcon } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { toast } from 'sonner'

import { EnabledStatus, EnabledSwitch } from '@/components/enabled'
import { KindSelect } from '@/components/kind-select'
import { Field, PageHeader } from '@/components/page'
import { SectionPicker } from '@/components/section-picker'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api'
import {
  useChannel,
  useChannelKinds,
  useCreateChannel,
  useTryChannel,
  useUpdateChannel,
  type Channel,
  type ChannelFields,
} from '@/lib/channels'
import { kindLabel, type Kind } from '@/lib/kinds'

function BackLink() {
  return (
    <Link
      to="/channels"
      className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ChevronLeftIcon className="size-4" />
      Kênh đăng
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

export function NewChannelPage() {
  const create = useCreateChannel()
  const kinds = useChannelKinds()
  const navigate = useNavigate()
  // Mở từ trang của một Chuyên mục thì Kênh đăng mới gắn sẵn vào Chuyên mục đó.
  const section = Number(useSearchParams()[0].get('section'))

  if (kinds.isPending) return <Loading />
  if (kinds.isError) {
    return (
      <>
        <BackLink />
        <Alert variant="destructive">
          <AlertTitle>Không tải được các loại Kênh đăng</AlertTitle>
          <AlertDescription>{kinds.error.message}</AlertDescription>
        </Alert>
      </>
    )
  }
  return (
    <>
      <PageHeader
        back={<BackLink />}
        title="Thêm Kênh đăng"
        description="Gửi một tin nhắn thử để chắc bot đã đăng được ở đó."
      />
      <ChannelForm
        kinds={kinds.data}
        initial={{
          kind: kinds.data[0]?.kind ?? '',
          name: '',
          address: '',
          section_ids: section ? [section] : [],
        }}
        submitLabel="Thêm Kênh đăng"
        pending={create.isPending}
        error={create.error}
        onSubmit={(fields) =>
          create.mutate(fields, {
            onSuccess: (channel) => {
              toast.success(`Đã thêm ${channel.name}`)
              navigate('/channels', { replace: true })
            },
          })
        }
      />
    </>
  )
}

export function EditChannelPage() {
  const id = Number(useParams().id)
  const channel = useChannel(id)
  const kinds = useChannelKinds()

  if (channel.isPending || kinds.isPending) return <Loading />
  if (channel.isError || kinds.isError) {
    return (
      <>
        <BackLink />
        <Alert variant="destructive">
          <AlertTitle>Không mở được Kênh đăng</AlertTitle>
          <AlertDescription>{(channel.error ?? kinds.error)?.message}</AlertDescription>
        </Alert>
      </>
    )
  }
  // `key` dựng lại biểu mẫu khi chuyển sang Kênh đăng khác.
  return <EditChannel key={channel.data.id} channel={channel.data} kinds={kinds.data} />
}

function EditChannel({ channel, kinds }: { channel: Channel; kinds: Kind[] }) {
  const update = useUpdateChannel(channel.id)
  const toggle = useUpdateChannel(channel.id)

  return (
    <>
      <PageHeader
        back={<BackLink />}
        title={
          <span className="flex flex-wrap items-center gap-2">
            {channel.name}
            <EnabledStatus enabled={channel.is_enabled} />
          </span>
        }
        description={`Kênh đăng loại ${kindLabel(kinds, channel.kind)}.`}
      />
      <div className="flex flex-col gap-6">
        <ChannelForm
          kinds={kinds}
          kindLocked
          initial={channel}
          submitLabel="Lưu thay đổi"
          pending={update.isPending}
          error={update.error}
          onSubmit={({ name, address, section_ids }) =>
            update.mutate(
              { name, address, section_ids },
              { onSuccess: () => toast.success('Đã lưu. Có hiệu lực từ Bản tin kế tiếp.') },
            )
          }
        />
        <Card>
          <CardHeader>
            <CardTitle>Tắt Kênh đăng</CardTitle>
            <CardDescription>
              Kênh đăng đang tắt không nhận Bản tin nào. Thiết lập và các Chuyên mục đã gắn vẫn giữ
              nguyên.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <EnabledSwitch
              id="enabled"
              name={channel.name}
              enabled={channel.is_enabled}
              pending={toggle.isPending}
              onChange={(enabled, done) => toggle.mutate({ is_enabled: enabled }, done)}
            />
          </CardContent>
        </Card>
      </div>
    </>
  )
}

type FormValues = ChannelFields & { kind: string }

function ChannelForm({
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
  const [address, setAddress] = useState(initial.address)
  const [sectionIds, setSectionIds] = useState(initial.section_ids)
  const trial = useTryChannel()
  // Kết quả gửi thử chỉ còn đúng khi loại và mã chưa đổi kể từ lúc bấm.
  const [triedFor, setTriedFor] = useState<string | null>(null)
  const current = `${kind} ${address.trim()}`
  const info = kinds.find((item) => item.kind === kind)
  const fields = {
    ...(trial.error instanceof ApiError && triedFor === current ? trial.error.fields : {}),
    ...(error instanceof ApiError ? error.fields : {}),
  }
  const unchanged =
    name === initial.name &&
    address === initial.address &&
    sectionIds.join() === initial.section_ids.join()

  function submit(event: FormEvent) {
    event.preventDefault()
    onSubmit({ kind, name, address, section_ids: sectionIds })
  }

  function tryIt() {
    setTriedFor(current)
    trial.mutate({ kind, address })
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
          <Field id="name" label="Tên" error={fields.name} hint="Chỉ để bạn nhận ra; người đọc không thấy.">
            <Input
              id="name"
              required
              maxLength={80}
              placeholder="Ví dụ: Nhóm gia đình"
              value={name}
              onChange={(event) => setName(event.target.value)}
              {...invalid('name')}
            />
          </Field>
          <Field
            id="address"
            label={info?.address_label ?? 'Địa chỉ'}
            error={fields.address}
            hint={info?.hint}
          >
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                id="address"
                required
                maxLength={200}
                autoComplete="off"
                placeholder={info?.placeholder}
                value={address}
                onChange={(event) => setAddress(event.target.value)}
                {...invalid('address')}
              />
              <Button
                type="button"
                variant="outline"
                className="shrink-0"
                disabled={!address.trim() || trial.isPending}
                onClick={tryIt}
              >
                <SendIcon />
                {trial.isPending ? 'Đang gửi…' : 'Gửi tin nhắn thử'}
              </Button>
            </div>
          </Field>
          {trial.isSuccess && triedFor === current && (
            trial.data.error ? (
              <Alert variant="destructive">
                <AlertTitle>Không gửi được</AlertTitle>
                <AlertDescription className="break-words">{trial.data.error}</AlertDescription>
              </Alert>
            ) : (
              <p className="flex items-center gap-1.5 rounded-lg border bg-muted/40 p-4 text-sm font-medium text-success">
                <CircleCheckIcon className="size-4 shrink-0" />
                Đã gửi. Mở cuộc trò chuyện để xem tin nhắn thử đã tới chưa.
              </p>
            )
          )}
          {trial.error && !(trial.error instanceof ApiError && trial.error.status === 422) && (
            <Alert variant="destructive">
              <AlertDescription>{trial.error.message}</AlertDescription>
            </Alert>
          )}
          <SectionPicker
            label="Chuyên mục"
            hint="Kênh đăng nhận Bản tin của mọi Chuyên mục được đánh dấu."
            value={sectionIds}
            onChange={setSectionIds}
            error={fields.section_ids}
          />
          <div className="flex flex-col-reverse gap-2 border-t pt-5 sm:flex-row sm:justify-end">
            <Button asChild variant="outline" size="lg">
              <Link to="/channels">Huỷ</Link>
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

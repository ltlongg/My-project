import { Link } from 'react-router'

import { SectionStatus } from '@/components/section-status'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { useSections } from '@/lib/sections'

// Gắn một Nguồn hay Kênh đăng vào một hay nhiều Chuyên mục: mỗi Chuyên mục một ô đánh dấu.
export function SectionPicker({
  label,
  hint,
  value,
  onChange,
  error,
}: {
  label: string
  hint: string
  value: number[]
  onChange: (ids: number[]) => void
  error?: string
}) {
  const sections = useSections()

  function toggle(id: number, checked: boolean) {
    onChange(checked ? [...value, id].sort((a, b) => a - b) : value.filter((item) => item !== id))
  }

  return (
    <fieldset
      className="flex flex-col gap-2"
      aria-invalid={error ? true : undefined}
      aria-describedby={error ? 'section_ids-error' : undefined}
    >
      <legend className="mb-2 text-sm leading-none font-medium">{label}</legend>
      {sections.isPending && <Skeleton className="h-20 rounded-lg" />}
      {sections.isError && <p className="text-sm text-destructive">{sections.error.message}</p>}
      {sections.isSuccess && sections.data.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Chưa có Chuyên mục nào.{' '}
          <Link to="/sections/new" className="text-foreground underline underline-offset-4">
            Tạo Chuyên mục
          </Link>{' '}
          trước, rồi quay lại gắn.
        </p>
      )}
      {sections.isSuccess && sections.data.length > 0 && (
        <div className="flex flex-col divide-y rounded-lg border">
          {sections.data.map((section) => {
            const id = `section-${section.id}`
            return (
              <div key={section.id} className="flex items-center gap-3 px-3 py-2.5">
                <Checkbox
                  id={id}
                  checked={value.includes(section.id)}
                  onCheckedChange={(checked) => toggle(section.id, checked === true)}
                />
                <Label htmlFor={id} className="min-w-0 flex-1 font-normal">
                  <span className="truncate">{section.name}</span>
                </Label>
                <SectionStatus paused={section.is_paused} />
              </div>
            )
          })}
        </div>
      )}
      {error ? (
        <p id="section_ids-error" className="text-sm text-destructive">
          {error}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">{hint}</p>
      )}
    </fieldset>
  )
}

const TIME_ZONE = 'Asia/Ho_Chi_Minh'

const absolute = new Intl.DateTimeFormat('vi-VN', {
  timeZone: TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})
const relative = new Intl.RelativeTimeFormat('vi', { numeric: 'auto' })
const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['minute', 60],
  ['hour', 24],
  ['day', 30],
]

// Giờ Việt Nam, như "08:15 24/10/2026".
export function formatTime(iso: string) {
  return absolute.format(new Date(iso))
}

// Cách đây bao lâu, như "5 phút trước"; quá 30 ngày thì ghi ngày giờ.
export function formatAgo(iso: string, now = Date.now()) {
  let amount = (new Date(iso).getTime() - now) / 60_000
  if (Math.abs(amount) < 1) return 'vừa xong'
  for (const [unit, size] of STEPS) {
    if (Math.abs(amount) < size) return relative.format(Math.round(amount), unit)
    amount /= size
  }
  return formatTime(iso)
}

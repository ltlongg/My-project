// Gọi API trang quản lí. Mọi lỗi thành ApiError mang lời nhắn tiếng Việt của máy chủ.

export class ApiError extends Error {
  readonly status: number
  // Lời nhắn theo từng trường khi dữ liệu gửi lên chưa hợp lệ (mã 422).
  readonly fields: Record<string, string>

  constructor(status: number, message: string, fields: Record<string, string> = {}) {
    super(message)
    this.status = status
    this.fields = fields
  }
}

// Gọi khi máy chủ trả 401 giữa chừng: phiên đã hết hạn hoặc bị đăng xuất ở nơi khác.
let onUnauthorized: () => void = () => {}

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method: options.method ?? 'GET',
      headers: options.body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: 'same-origin',
    })
  } catch {
    throw new ApiError(0, 'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.')
  }
  if (response.status === 204) return undefined as T
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    // Trang đăng nhập và khung trang tự xử lí 401 của chính chúng.
    if (response.status === 401 && path !== '/login' && path !== '/session') onUnauthorized()
    throw new ApiError(
      response.status,
      typeof payload.detail === 'string' ? payload.detail : 'Máy chủ gặp lỗi. Thử lại sau.',
      payload.fields ?? {},
    )
  }
  return payload as T
}

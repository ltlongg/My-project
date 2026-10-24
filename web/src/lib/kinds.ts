// Một loại Nguồn hay Kênh đăng như máy chủ mô tả. Màn hình thêm mới dựng ô địa chỉ từ đây, nên
// loại mới chỉ cần khai ở máy chủ.
export type Kind = {
  kind: string
  label: string
  address_label: string
  placeholder: string
  hint: string
}

export function kindLabel(kinds: Kind[] | undefined, kind: string) {
  return kinds?.find((item) => item.kind === kind)?.label ?? kind
}

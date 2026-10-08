"""Bộ thử endpoint LLM, test bằng một endpoint giả trả lời theo kịch bản; không gọi mạng."""

import json
import threading
import time
from collections import Counter
from typing import Any

import httpx
import pytest

from bulletin.thu_llm import EndpointLLM, thu_model, thu_nhieu_model, thu_nhung

DIA_CHI = "http://llm.example/v1"
KHOA = "sk-thu"
MODEL = "nha/model-thu"


def _stream(*manh: dict[str, Any]) -> httpx.Response:
    than = "".join(f"data: {json.dumps(m)}\n\n" for m in manh) + "data: [DONE]\n\n"
    return httpx.Response(200, content=than, headers={"content-type": "text/event-stream"})


def _delta(delta: dict[str, Any], ket_thuc: str | None = None) -> dict[str, Any]:
    return {"choices": [{"index": 0, "delta": delta, "finish_reason": ket_thuc}]}


class EndpointGia:
    """Đứng thay endpoint LLM: một model ngoan, làm đúng mọi phép thử, trừ khi test bảo khác."""

    def __init__(self) -> None:
        self.bo_qua_cong_cu = False
        self.bia_thay_vi_doc = False
        self.tra_van_xuoi_thay_json = False
        self.tu_choi_response_format = False
        # Số giây endpoint từ chối mọi lời gọi tới model sau một lần từ chối; 0 là không khoá.
        self.khoa_model_sau_khi_tu_choi = 0
        self.dang_khoa = False
        self.khong_stream_kem_done = False
        self.tra_loi_tieng_anh = False
        self.loi: httpx.Response | None = None
        self.khoa_da_nhan: set[str] = set()
        self.client = httpx.Client(transport=httpx.MockTransport(self._tra_loi))

    @property
    def endpoint(self) -> EndpointLLM:
        return EndpointLLM(self.client, DIA_CHI, KHOA)

    def _tra_loi(self, yeu_cau: httpx.Request) -> httpx.Response:
        self.khoa_da_nhan.add(yeu_cau.headers.get("authorization", ""))
        than = json.loads(yeu_cau.content)
        if yeu_cau.url.path.endswith("/embeddings"):
            if self.loi:
                return self.loi
            return httpx.Response(200, json={"data": [{"embedding": [0.1] * 1536}]})
        if self.loi:
            return self.loi
        if self.dang_khoa or ("response_format" in than and self.tu_choi_response_format):
            than_loi = {"error": {"message": "response_format lạ"}}
            if not self.khoa_model_sau_khi_tu_choi:
                return httpx.Response(400, json=than_loi)
            self.dang_khoa = True
            cho = {"retry-after": str(self.khoa_model_sau_khi_tu_choi)}
            return httpx.Response(400, json=than_loi, headers=cho)

        cong_cu = self._goi_cong_cu(than)
        noi_dung = None if cong_cu else self._noi_dung(than)
        if not than.get("stream"):
            thong_diep = {"role": "assistant", "content": noi_dung, "tool_calls": cong_cu}
            du_lieu = json.dumps({"choices": [{"message": thong_diep, "finish_reason": "stop"}]})
            if self.khong_stream_kem_done:
                du_lieu += "data: [DONE]\n\n"
            return httpx.Response(200, content=du_lieu)
        if cong_cu:
            [goi] = cong_cu
            tham_so = goi["function"]["arguments"]
            dau = {**goi, "index": 0, "function": {**goi["function"], "arguments": ""}}
            return _stream(
                _delta({"role": "assistant", "content": ""}),
                _delta({"tool_calls": [dau]}),
                # Tham số tới thành nhiều mảnh, như endpoint thật.
                _delta({"tool_calls": [{"index": 0, "function": {"arguments": tham_so[:3]}}]}),
                _delta({"tool_calls": [{"index": 0, "function": {"arguments": tham_so[3:]}}]}),
                _delta({}, "tool_calls"),
            )
        assert noi_dung is not None
        giua = len(noi_dung) // 2
        return _stream(
            _delta({"content": noi_dung[:giua]}), _delta({"content": noi_dung[giua:]}, "stop")
        )

    def _goi_cong_cu(self, than: dict[str, Any]) -> list[dict[str, Any]] | None:
        ten_cong_cu = {c["function"]["name"] for c in than.get("tools", [])}
        if not ten_cong_cu or self.bo_qua_cong_cu:
            return None

        def goi(ten: str, **tham_so: object) -> list[dict[str, Any]]:
            ham = {"name": ten, "arguments": json.dumps(tham_so)}
            return [{"id": f"call_{ten}", "type": "function", "function": ham}]

        da_goi = [
            g["function"]["name"]
            for tin in than["messages"]
            if tin["role"] == "assistant"
            for g in tin.get("tool_calls") or []
        ]
        if "tim_bai_goc" not in ten_cong_cu:
            return None if da_goi else goi("doc_bai_goc", ma=4172)
        if not da_goi:
            return goi("tim_bai_goc", tu_khoa="pin thể rắn")
        if da_goi == ["tim_bai_goc"] and not self.bia_thay_vi_doc:
            ket_qua_tim = json.loads(than["messages"][-1]["content"])
            [ma] = [bai["ma"] for bai in ket_qua_tim if "thể rắn" in bai["tieu_de"]]
            return goi("doc_bai_goc", ma=ma)
        return None

    def _noi_dung(self, than: dict[str, Any]) -> str:
        cuoi = than["messages"][-1]
        if cuoi["role"] == "tool":
            if self.bia_thay_vi_doc:
                return "Mật độ năng lượng khoảng 500 Wh/kg."
            # Nhắc lại đúng con số có trong kết quả của công cụ.
            [so] = [tu for tu in cuoi["content"].split() if tu.isdigit() and len(tu) == 3]
            return f"Bài nêu mật độ năng lượng {so} Wh/kg."
        de_bai = str(cuoi["content"])
        if "JSON" in de_bai:
            if self.tra_van_xuoi_thay_json:
                return "Bài này đáng chọn, tôi cho 8 điểm."
            return json.dumps(
                {"tieu_de": "Pin thể rắn", "tom_tat": "Một câu.", "diem": 8, "nen_chon": True}
            )
        if "Nvidia" in de_bai:
            if self.tra_loi_tieng_anh:
                return "Nvidia says Rubin GPUs will be made by TSMC and cut costs by 30%."
            return (
                "Nvidia cho biết dòng GPU Rubin thế hệ tiếp theo sẽ do TSMC sản xuất trên tiến "
                "trình 2 nanomet. Hãng nói chip mới giảm 30% chi phí suy luận so với Blackwell."
            )
        return "xin chào"


def dat(endpoint_gia: EndpointGia) -> dict[str, bool | None]:
    ket_qua = thu_model(endpoint_gia.endpoint, MODEL)
    return {ten: phep.dat for ten, phep in ket_qua.phep_thu.items()}


def test_model_lam_dung_moi_thu_thi_moi_phep_thu_deu_dat() -> None:
    endpoint_gia = EndpointGia()

    assert dat(endpoint_gia) == {
        "goi_thuong": True,
        "khong_stream": True,
        "cong_cu_mot_luot": True,
        "cong_cu_nhieu_luot": True,
        "json_schema": True,
        "json_theo_prompt": True,
        "tieng_viet": True,
    }
    assert endpoint_gia.khoa_da_nhan == {f"Bearer {KHOA}"}


def test_model_tra_loi_bang_chu_thay_vi_goi_cong_cu_thi_hai_phep_thu_cong_cu_khong_dat() -> None:
    endpoint_gia = EndpointGia()
    endpoint_gia.bo_qua_cong_cu = True

    ket_qua = dat(endpoint_gia)

    assert (ket_qua["cong_cu_mot_luot"], ket_qua["cong_cu_nhieu_luot"]) == (False, False)
    assert ket_qua["goi_thuong"] is True
    assert ket_qua["tieng_viet"] is True


def test_model_tra_loi_ma_khong_doc_bai_goc_thi_cong_cu_nhieu_luot_khong_dat() -> None:
    endpoint_gia = EndpointGia()
    endpoint_gia.bia_thay_vi_doc = True

    ket_qua = thu_model(endpoint_gia.endpoint, MODEL).phep_thu

    assert ket_qua["cong_cu_mot_luot"].dat is True
    assert ket_qua["cong_cu_nhieu_luot"].dat is False
    assert "doc_bai_goc" in ket_qua["cong_cu_nhieu_luot"].ghi_chu


def test_van_xuoi_thay_cho_json_thi_ket_qua_co_cau_truc_khong_dat() -> None:
    endpoint_gia = EndpointGia()
    endpoint_gia.tra_van_xuoi_thay_json = True

    ket_qua = dat(endpoint_gia)

    assert (ket_qua["json_schema"], ket_qua["json_theo_prompt"]) == (False, False)


def test_endpoint_tu_choi_response_format_thi_chi_json_schema_khong_dat() -> None:
    endpoint_gia = EndpointGia()
    endpoint_gia.tu_choi_response_format = True

    ket_qua = thu_model(endpoint_gia.endpoint, MODEL).phep_thu

    assert ket_qua["json_schema"].dat is False
    assert "response_format lạ" in ket_qua["json_schema"].ghi_chu
    assert ket_qua["json_theo_prompt"].dat is True


def test_endpoint_khoa_model_sau_khi_tu_choi_thi_bo_thu_cho_het_han_roi_moi_thu_tiep() -> None:
    endpoint_gia = EndpointGia()
    endpoint_gia.tu_choi_response_format = True
    endpoint_gia.khoa_model_sau_khi_tu_choi = 30
    da_cho: list[float] = []

    def ngu(giay: float) -> None:
        da_cho.append(giay)
        endpoint_gia.dang_khoa = False

    ket_qua = thu_model(endpoint_gia.endpoint, MODEL, ngu=ngu).phep_thu

    assert ket_qua["json_schema"].dat is False
    # Không chờ thì hai phép thử sau cũng bị từ chối oan vì model đang bị khoá.
    assert (ket_qua["json_theo_prompt"].dat, ket_qua["tieng_viet"].dat) == (True, True)
    assert da_cho == [31]


def test_than_phan_hoi_khong_stream_kem_done_thi_khong_stream_khong_dat() -> None:
    endpoint_gia = EndpointGia()
    endpoint_gia.khong_stream_kem_done = True

    ket_qua = dat(endpoint_gia)

    assert ket_qua["khong_stream"] is False
    assert ket_qua["goi_thuong"] is True


def test_tom_tat_van_bang_tieng_anh_thi_tieng_viet_khong_dat() -> None:
    endpoint_gia = EndpointGia()
    endpoint_gia.tra_loi_tieng_anh = True

    assert dat(endpoint_gia)["tieng_viet"] is False


def test_model_bi_endpoint_tu_choi_thi_ghi_lai_li_do_va_bo_qua_cac_phep_thu_con_lai() -> None:
    endpoint_gia = EndpointGia()
    endpoint_gia.loi = httpx.Response(
        400,
        json={"error": {"message": "model không dùng được với tài khoản này"}},
        headers={"retry-after": "28"},
    )

    da_cho: list[float] = []

    ket_qua = thu_model(endpoint_gia.endpoint, MODEL, ngu=da_cho.append).phep_thu

    assert ket_qua["goi_thuong"].dat is False
    assert ket_qua["goi_thuong"].ghi_chu == (
        "HTTP 400: model không dùng được với tài khoản này (retry-after: 28)"
    )
    # Chờ hết hạn khoá, để model kế tiếp cùng model gốc không bị từ chối oan.
    assert da_cho == [29]
    assert {ten: phep.dat for ten, phep in ket_qua.items() if ten != "goi_thuong"} == {
        "khong_stream": None,
        "cong_cu_mot_luot": None,
        "cong_cu_nhieu_luot": None,
        "json_schema": None,
        "json_theo_prompt": None,
        "tieng_viet": None,
    }


def test_endpoint_tao_duoc_vector_nhung_thi_bao_so_chieu() -> None:
    ket_qua = thu_nhung(EndpointGia().endpoint, "text-embedding-3-small")

    assert ket_qua.dat is True
    assert ket_qua.ghi_chu == "1536 chiều"


def test_endpoint_khong_tao_duoc_vector_nhung_thi_bao_li_do() -> None:
    endpoint_gia = EndpointGia()
    endpoint_gia.loi = httpx.Response(
        400, json={"error": {"message": "No credentials for provider: openai"}}
    )

    ket_qua = thu_nhung(endpoint_gia.endpoint, "text-embedding-3-small")

    assert ket_qua.dat is False
    assert ket_qua.ghi_chu == "HTTP 400: No credentials for provider: openai"


def test_loi_ket_noi_duoc_bao_la_khong_dat_chu_khong_lam_sap_bo_thu() -> None:
    def mat_mang(yeu_cau: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("không tới được", request=yeu_cau)

    endpoint = EndpointLLM(httpx.Client(transport=httpx.MockTransport(mat_mang)), DIA_CHI, KHOA)

    ket_qua = thu_model(endpoint, MODEL).phep_thu

    assert ket_qua["goi_thuong"].dat is False
    assert ket_qua["goi_thuong"].ghi_chu == "Không kết nối được (ConnectError)"


def test_thu_nhieu_model_giu_thu_tu_va_khong_goi_cung_luc_hai_model_cung_nha_cung_cap() -> None:
    khoa = threading.Lock()
    dang_goi: Counter[str] = Counter()
    nhieu_nhat: Counter[str] = Counter()
    endpoint_gia = EndpointGia()

    def tra_loi(yeu_cau: httpx.Request) -> httpx.Response:
        nha = json.loads(yeu_cau.content)["model"].split("/")[0]
        with khoa:
            dang_goi[nha] += 1
            nhieu_nhat[nha] = max(nhieu_nhat[nha], dang_goi[nha])
        time.sleep(0.002)
        with khoa:
            dang_goi[nha] -= 1
        return endpoint_gia._tra_loi(yeu_cau)

    endpoint = EndpointLLM(httpx.Client(transport=httpx.MockTransport(tra_loi)), DIA_CHI, KHOA)
    cac_model = ["a/mot", "b/mot", "a/hai", "b/hai"]

    ket_qua = thu_nhieu_model(endpoint, cac_model)

    assert [kq.model for kq in ket_qua] == cac_model
    assert all(kq.phep_thu["tieng_viet"].dat for kq in ket_qua)
    assert nhieu_nhat == {"a": 1, "b": 1}


@pytest.mark.parametrize("dia_chi", [DIA_CHI, DIA_CHI + "/"])
def test_liet_ke_model_cua_endpoint(dia_chi: str) -> None:
    def tra_loi(yeu_cau: httpx.Request) -> httpx.Response:
        assert str(yeu_cau.url) == "http://llm.example/v1/models"
        return httpx.Response(200, json={"data": [{"id": "b/hai"}, {"id": "a/mot"}]})

    endpoint = EndpointLLM(httpx.Client(transport=httpx.MockTransport(tra_loi)), dia_chi, KHOA)

    assert endpoint.cac_model() == ["a/mot", "b/hai"]

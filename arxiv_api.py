import os
import sys
import threading
import time
import types

import arxiv
from arxiv import HTTPError


def _patch_session_timeout(client: arxiv.Client, timeout: float) -> None:
    """arxiv 库默认不设 timeout，网络异常时会一直阻塞。"""
    sess = client._session
    _orig = sess.request

    def request(self, method, url, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = timeout
        return _orig(method, url, **kwargs)

    sess.request = types.MethodType(request, sess)


class ArxivApi:
    """
    封装 arXiv 官方 API。必须复用同一个 arxiv.Client，其 delay_seconds 才会在多次调用之间生效；
    若每次请求都 new Client()，则不会节流，容易触发 export.arxiv.org 的 HTTP 429。

    环境变量：ARXIV_API_DELAY_SECONDS、ARXIV_API_NUM_RETRIES、ARXIV_HTTP_TIMEOUT（秒，默认 90）。
    """

    def __init__(self, delay_seconds: float | None = None, num_retries: int | None = None):
        if delay_seconds is None:
            env = os.environ.get("ARXIV_API_DELAY_SECONDS")
            delay_seconds = float(env) if env not in (None, "") else 3.0
        if num_retries is None:
            env = os.environ.get("ARXIV_API_NUM_RETRIES")
            num_retries = int(env) if env not in (None, "") else 3
        self._client = arxiv.Client(delay_seconds=delay_seconds, num_retries=num_retries)
        http_timeout = float(os.environ.get("ARXIV_HTTP_TIMEOUT", "90"))
        _patch_session_timeout(self._client, http_timeout)
        self._lock = threading.Lock()

    def _first_result(self, arxiv_id: str):
        search = arxiv.Search(id_list=[arxiv_id])
        # 库内已对单次请求做 num_retries；此处仅在外层仍 429 时少量退避，并打印说明避免「像卡住」
        delays = (0.0, 12.0, 30.0)
        last_err: HTTPError | None = None
        for d in delays:
            if d:
                print(
                    f"  arXiv API 限流 (HTTP 429)，{d:.0f}s 后重试 id={arxiv_id} …",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(d)
            try:
                with self._lock:
                    return next(self._client.results(search), None)
            except HTTPError as e:
                if e.status != 429:
                    raise
                last_err = e
        assert last_err is not None
        raise last_err

    def get_result(self, arxiv_id: str):
        """单次 API 查询返回完整 Result，便于一次请求读取多个字段。"""
        result = self._first_result(arxiv_id)
        if result is None:
            raise ValueError(f"Could not find paper with arxiv_id: {arxiv_id}")
        return result

    def get_abstarct(self, arxiv_id: str):
        return self.get_result(arxiv_id).summary

    def get_pdf_url(self, arxiv_id: str):
        return self.get_result(arxiv_id).pdf_url

    def get_title(self, arxiv_id: str):
        return self.get_result(arxiv_id).title

    def download_pdf(self, arxiv_id: str, output_path: str):
        paper = self._first_result(arxiv_id)
        if paper is None:
            raise ValueError(f"Could not find paper with arxiv_id: {arxiv_id}")
        dir_path = os.path.dirname(output_path)
        os.makedirs(dir_path, exist_ok=True)
        paper.download_pdf(filename=output_path)

    def get_author_names(self, arxiv_id: str):
        return [author.name for author in self.get_result(arxiv_id).authors]

    def get_comment(self, arxiv_id: str):
        """arXiv Atom 中的 arxiv:comment（录用/会议等），可能为空字符串"""
        result = self.get_result(arxiv_id)
        c = getattr(result, "comment", None)
        if c is None:
            return ""
        return c.strip() if isinstance(c, str) else str(c).strip()


if __name__ == "__main__":

    arxiv_api = ArxivApi()
    #print(arxiv_api.get_abstarct("2505.23716"))
    #print(arxiv_api.get_pdf_url("2512.14692v1"))
    #print(arxiv_api.get_title("2505.23716"))
    #arxiv_api.download_pdf("2512.14692v1", "./arxiv_papers/test.pdf")
    print(arxiv_api.get_author_names("2512.14692v1"))

import os
import arxiv
class ArxivApi:

    def __init__(self):
        pass

    def get_result(self, arxiv_id: str):
        """单次 API 查询返回完整 Result，便于一次请求读取多个字段。"""
        client = arxiv.Client()
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(client.results(search), None)
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
        paper = next(arxiv.Search(id_list=[arxiv_id]).results())
        dir_path = os.path.dirname(output_path)
        os.makedirs(dir_path, exist_ok=True)
        paper.download_pdf( filename=output_path)

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
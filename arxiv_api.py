import os
import arxiv
class ArxivApi:

    def __init__(self):
        pass

    def get_abstarct(self, arxiv_id: str):
        client = arxiv.Client()
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(client.results(search), None)
        if result is None:
            raise ValueError(f"Could not find paper with arxiv_id: {arxiv_id}")
        return result.summary

    def get_pdf_url(self, arxiv_id: str):
        client = arxiv.Client()
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(client.results(search), None)
        if result is None:
            raise ValueError(f"Could not find paper with arxiv_id: {arxiv_id}")
        return result.pdf_url

    def get_title(self, arxiv_id: str):
        client = arxiv.Client()
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(client.results(search), None)
        if result is None:
            raise ValueError(f"Could not find paper with arxiv_id: {arxiv_id}")
        return result.title

    def download_pdf(self, arxiv_id: str, output_path: str):
        paper = next(arxiv.Search(id_list=[arxiv_id]).results())
        dir_path = os.path.dirname(output_path)
        os.makedirs(dir_path, exist_ok=True)
        paper.download_pdf( filename=output_path)

    def get_author_names(self, arxiv_id: str):
        client = arxiv.Client()
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(client.results(search), None)
        if result is None:
            raise ValueError(f"Could not find paper with arxiv_id: {arxiv_id}")
        return [author.name for author in result.authors]



if __name__ == "__main__":

    arxiv_api = ArxivApi()
    #print(arxiv_api.get_abstarct("2505.23716"))
    #print(arxiv_api.get_pdf_url("2512.14692v1"))
    #print(arxiv_api.get_title("2505.23716"))
    #arxiv_api.download_pdf("2512.14692v1", "./arxiv_papers/test.pdf")
    print(arxiv_api.get_author_names("2512.14692v1"))
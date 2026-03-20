import os
import requests
from typing import Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from ai_api import AiApi
from database import Database
from arxiv_api import ArxivApi
from pdf_convertor import PdfConvertor
from venue_from_comment import extract_venue_tag_from_comment

class Completer:
    def __init__(self, path, database: Database):
        """
        Cache structure
        .
        |--paper_id (对于 arXiv: paper_id = arxiv_id, 保持兼容)
          |--paper.pdf
        """
        self._path = path
        self._database: Database = database
        self._arxiv_api = ArxivApi()
        self._ai_api = AiApi()
        os.makedirs(os.path.dirname(self._path) if os.path.dirname(self._path) else '.', exist_ok=True)

    def _arxiv_metadata_need_api(self, paper_info: dict) -> bool:
        """
        是否需调用 arXiv API 拉取「记录元数据」：摘要、作者、标题、arxiv:comment。
        任一项按下面规则视为缺失则返回 True（一次请求可写回全部字段）。不含 venue/LLM。
        """
        arxiv_id = paper_info.get("arxiv_id")
        if not arxiv_id:
            return False
        if not paper_info.get("abstract"):
            return True
        if not paper_info.get("author_names"):
            return True
        if not paper_info.get("full_name"):
            return True
        ac = paper_info.get("arxiv_comments")
        if ac is None:
            return True
        if ac == "" and not paper_info.get("is_comment_used"):
            return True
        return False

    @staticmethod
    def _paper_info_apply_arxiv_metadata(paper_info: dict, meta: dict) -> None:
        paper_info["abstract"] = meta["abstract"]
        paper_info["author_names"] = meta["author_names"]
        paper_info["full_name"] = meta["full_name"]
        paper_info["arxiv_comments"] = meta["arxiv_comments"]

    def _fetch_arxiv_metadata_row_for_batch(
        self, paper_id: str, paper_info: dict
    ) -> Optional[dict]:
        """
        若需 API，则请求一次并就地更新 paper_info；返回 update_paper_info 用的一行 dict，失败返回 None。
        """
        if not self._arxiv_metadata_need_api(paper_info):
            return None
        arxiv_id = paper_info["arxiv_id"]
        try:
            print(
                f"Fetching arXiv metadata (abstract/authors/title/comment) for {arxiv_id}",
                flush=True,
            )
            meta = self._arxiv_api.fetch_record_metadata(arxiv_id)
            self._paper_info_apply_arxiv_metadata(paper_info, meta)
            return {
                "paper_id": paper_id,
                "arxiv_id": arxiv_id,
                "abstract": meta["abstract"],
                "author_names": meta["author_names"],
                "full_name": meta["full_name"],
                "arxiv_comments": meta["arxiv_comments"],
            }
        except Exception as e:
            print(f"✗ arXiv 元数据拉取失败 {paper_id}: {e}")
            return None

    def _ensure_arxiv_metadata_from_api(
        self,
        paper_id: str,
        paper_info: dict,
        updates: Optional[dict] = None,
    ) -> bool:
        """
        与 _fetch_arxiv_metadata_row_for_batch 相同触发条件；成功返回 True。
        updates 非 None 时把一行追加到 updates['paper_info_updates']，否则直接写库。
        """
        row = self._fetch_arxiv_metadata_row_for_batch(paper_id, paper_info)
        if row is None:
            return not self._arxiv_metadata_need_api(paper_info)
        if updates is not None:
            updates["paper_info_updates"].append(row)
        else:
            self._database.update_paper_info([row])
        return True

    def _batch_fetch_arxiv_metadata_for_paper_ids(
        self, paper_ids: List[str]
    ) -> List[dict]:
        """
        本组内合并 id_list 请求：对仍需 API 的论文一次（或按块）拉取元数据，
        返回 update_paper_info 用的行列表；失败或跳过的论文不产生行。
        """
        rows: List[dict] = []
        need_ids: List[str] = []
        infos: Dict[str, Optional[dict]] = {}
        for pid in paper_ids:
            pi = self._database.get_paper_info(paper_id=pid)
            infos[pid] = pi
            if pi and self._arxiv_metadata_need_api(pi):
                need_ids.append(pid)
        if not need_ids:
            return rows
        aids = [infos[pid]["arxiv_id"] for pid in need_ids]
        metas = self._arxiv_api.fetch_record_metadata_batch(aids)
        for pid in need_ids:
            aid = infos[pid]["arxiv_id"]
            meta = metas.get(aid)
            if not meta:
                print(f"✗ arXiv 批量元数据未命中 {pid} ({aid})", flush=True)
                continue
            self._paper_info_apply_arxiv_metadata(infos[pid], meta)
            rows.append(
                {
                    "paper_id": pid,
                    "arxiv_id": aid,
                    "abstract": meta["abstract"],
                    "author_names": meta["author_names"],
                    "full_name": meta["full_name"],
                    "arxiv_comments": meta["arxiv_comments"],
                }
            )
        return rows

    def _get_paper_ids_need_arxiv_metadata(self) -> List[str]:
        out: List[str] = []
        for paper_id in self._database.get_paper_ids():
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            if paper_info and self._arxiv_metadata_need_api(paper_info):
                out.append(paper_id)
        return out

    def _process_arxiv_comment_venue(
        self,
        paper_id: str,
        paper_info: dict,
        use_llm_for_venue: bool = True,
        *,
        phase: str,
    ):
        """
        arXiv comment 落库/结案 与 顶会（venue）解析；不在此函数内调用 arXiv API。
        phase=arxiv_comment 前应由调用方先执行 _ensure_arxiv_metadata_from_api /
        _fetch_arxiv_metadata_row_for_batch（一次 API 写入摘要/作者/标题/arxiv:comment）。
        会就地更新 paper_info 中的 arxiv_comments（随 LLM 或结案分支）。
        is_comment_used 表示「venue/comment 解析流程已结束」，单独一条 update，与 arxiv_comments 不同条：
        - 仅写入/更新 arxiv_comments（含仅拉取、或 LLM 未就绪/失败）时不写 is_comment_used。
        - LLM 成功跑完 extract 后写 is_comment_used；comment 经 API 确认为空时写 is_comment_used（无可解析内容）。
        返回 (paper_info_rows, tag_names)。

        phase（两步独立，勿混为同一概念）:
        - arxiv_comment: 不调 LLM；据已写入的 arxiv_comments 做持久化/结案（comment 步）。
        - venue: 仅用库内已有 comment 做顶会解析（LLM）；arxiv_comments 为 NULL 时跳过。

        use_llm_for_venue: 仅在 phase=venue 时生效；未配置或调用失败时只写 comment，不写 is_comment_used（有正文时可下次重试）。
        """
        if phase not in ("arxiv_comment", "venue"):
            phase = "arxiv_comment"

        arxiv_id = paper_info.get("arxiv_id")
        if not arxiv_id:
            return [], []

        upd_fields = {}
        tag_names = []

        if phase == "venue":
            if paper_info.get("is_comment_used"):
                return [], []
            if paper_info.get("arxiv_comments") is None:
                return [], []
        elif phase == "arxiv_comment":
            # arxiv:comment 与摘要/作者/标题同属一次 arXiv API 元数据拉取，由调用方先执行
            # _ensure_arxiv_metadata_from_api / _fetch_arxiv_metadata_row_for_batch，此处不再单独请求 API。
            pass

        if paper_info.get("is_comment_used"):
            if upd_fields:
                return [{"paper_id": paper_id, "arxiv_id": arxiv_id, **upd_fields}], []
            return [], []

        comment = paper_info.get("arxiv_comments") or ""
        stripped = (comment or "").strip()

        use_llm = (
            phase == "venue"
            and use_llm_for_venue
            and self._ai_api.is_llm_configured()
        )

        def _rows_comment_only():
            """仅持久化本次拉取的 arxiv_comments，不写 is_comment_used。"""
            if not upd_fields:
                return []
            return [{"paper_id": paper_id, "arxiv_id": arxiv_id, **upd_fields}]

        def _rows_after_venue_done():
            """LLM 已成功解析（或无需解析）：先写 arxiv_comments，再单独写 is_comment_used。"""
            ac = upd_fields["arxiv_comments"] if "arxiv_comments" in upd_fields else comment
            paper_info["arxiv_comments"] = ac
            paper_info["is_comment_used"] = True
            return [
                {
                    "paper_id": paper_id,
                    "arxiv_id": arxiv_id,
                    "arxiv_comments": ac,
                },
                {
                    "paper_id": paper_id,
                    "arxiv_id": arxiv_id,
                    "is_comment_used": True,
                },
            ]

        def _row_is_comment_used_only():
            paper_info["is_comment_used"] = True
            return [
                {
                    "paper_id": paper_id,
                    "arxiv_id": arxiv_id,
                    "is_comment_used": True,
                }
            ]

        # 无正文：只持久化本次拉取的 comment；is_comment_used 仅表示「venue 侧已结案」
        if not stripped:
            rows = _rows_comment_only()
            if use_llm:
                rows.extend(_row_is_comment_used_only())
            elif upd_fields:
                # 本轮回已从 API 得到空串：无可解析 venue，避免队列死循环
                rows.extend(_row_is_comment_used_only())
            elif phase == "venue":
                # 库内已有空 comment，仅结案
                rows.extend(_row_is_comment_used_only())
            elif phase == "arxiv_comment":
                # 元数据已在调用方一次 API 写入 arxiv_comments（可能为空）；此处不再带 upd_fields
                rows.extend(_row_is_comment_used_only())
            return rows, tag_names

        if not use_llm:
            return _rows_comment_only(), tag_names

        try:
            tag = extract_venue_tag_from_comment(comment, self._ai_api)
        except Exception as e:
            print(f"✗ LLM 顶会解析失败 {paper_id}: {e}")
            return _rows_comment_only(), tag_names

        rows = _rows_after_venue_done()
        if tag:
            tag_names.append(tag)
        return rows, tag_names

    def _apply_arxiv_comment_venue(
        self,
        paper_id: str,
        paper_info: dict,
        use_llm_for_venue: bool = True,
        *,
        phase: str,
    ):
        """写入数据库并打标签（用于非 batch 路径）；phase 须为 arxiv_comment 或 venue。"""
        rows, tags = self._process_arxiv_comment_venue(
            paper_id,
            paper_info,
            use_llm_for_venue=use_llm_for_venue,
            phase=phase,
        )
        if rows:
            self._database.update_paper_info(rows)
        for t in tags:
            self._database.add_tag_to_paper(paper_id, t)

    def _get_paper_ids_has_download_pdf(self) -> List[str]:
        """
        Scan cache directory and get all paper ids that have downloaded PDF
        """
        paper_ids = []
        if not os.path.exists(self._path):
            return paper_ids
        for paper_id in os.listdir(self._path):
            if os.path.exists(os.path.join(self._path, paper_id, "paper.pdf")):
                paper_ids.append(paper_id)
        return paper_ids

    def _get_paper_ids_need_to_download_pdf(self) -> List[str]:
        """
        Get all paper ids that need to download PDF
        """
        paper_ids_has_download = self._get_paper_ids_has_download_pdf()
        # 获取所有论文 ID
        all_paper_ids = self._database.get_paper_ids()
        return list(set(all_paper_ids) - set(paper_ids_has_download))

    def _get_paper_ids_has_convert_pdf_to_txt(self) -> List[str]:
        """
        Scan cache directory and get all paper ids that have converted PDF to TXT
        """
        paper_ids = []
        if not os.path.exists(self._path):
            return paper_ids
        for paper_id in os.listdir(self._path):
            if os.path.exists(os.path.join(self._path, paper_id, "paper.txt")):
                paper_ids.append(paper_id)
        return paper_ids
    
    def _get_paper_ids_need_to_convert_pdf_to_txt(self) -> List[str]:
        """
        Get all paper ids that need to convert pdf to txt
        """
        paper_ids_has_convert = self._get_paper_ids_has_convert_pdf_to_txt()
        # 获取所有论文 ID
        all_paper_ids = self._database.get_paper_ids()
        return list(set(all_paper_ids) - set(paper_ids_has_convert))

    def complete(self, max_workers=5):
        """
        完成所有任务
        
        Args:
            max_workers: PDF 下载的最大并发线程数（默认 5）
        """
        # 1. 下载 PDF（所有论文）- 使用多线程并行下载
        paper_ids = self._get_paper_ids_need_to_download_pdf()
        print(f"Downloading {len(paper_ids)} papers (using {max_workers} threads)")
        
        if paper_ids:
            # 准备下载任务
            download_tasks = []
            for paper_id in paper_ids:
                try:
                    paper_info = self._database.get_paper_info(paper_id=paper_id)
                    if not paper_info:
                        print(f"Warning: Paper info not found for {paper_id}, skipping")
                        continue
                    arxiv_id = paper_info.get("arxiv_id")
                    download_tasks.append((paper_id, arxiv_id))
                except Exception as e:
                    print(f"Error preparing download task for {paper_id}: {e}")
                    continue
            
            # 使用线程池并行下载
            success_count = 0
            error_count = 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有下载任务
                future_to_paper_id = {
                    executor.submit(self._download_pdf, paper_id, arxiv_id): paper_id
                    for paper_id, arxiv_id in download_tasks
                }
                
                # 使用 tqdm 显示进度
                with tqdm(total=len(download_tasks), desc="Downloading PDFs", unit="paper") as pbar:
                    # 处理完成的任务
                    for future in as_completed(future_to_paper_id):
                        paper_id = future_to_paper_id[future]
                        try:
                            future.result()  # 获取结果，如果有异常会抛出
                            success_count += 1
                            pbar.set_postfix({"success": success_count, "error": error_count})
                        except Exception as e:
                            error_count += 1
                            pbar.set_postfix({"success": success_count, "error": error_count})
                            print(f"\n✗ Error downloading {paper_id}: {e}")
                            import traceback
                            traceback.print_exc()
                        finally:
                            pbar.update(1)
            
            print(f"\nPDF download completed: {success_count} succeeded, {error_count} failed")

        # 2. arXiv 元数据（摘要/作者/标题/arxiv:comment）每篇至多一次 API
        meta_paper_ids = self._get_paper_ids_need_arxiv_metadata()
        print(f"Fetching arXiv metadata for {len(meta_paper_ids)} papers")
        for paper_id in meta_paper_ids:
            try:
                paper_info = self._database.get_paper_info(paper_id=paper_id)
                if paper_info:
                    self._ensure_arxiv_metadata_from_api(paper_id, paper_info, updates=None)
            except Exception as e:
                print(f"Error fetching arXiv metadata for {paper_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # 3. 转换 PDF 到 TXT（所有论文）
        paper_ids = self._get_paper_ids_need_to_convert_pdf_to_txt()
        print(f"Converting {len(paper_ids)} pdfs to txt")
        for paper_id in paper_ids:
            try:
                self._convert_pdf_to_txt(paper_id)
            except Exception as e:
                print(f"Error converting {paper_id}: {e}")
                import traceback
                traceback.print_exc()

        # 5. 获取标题（arXiv 从 API，非 arXiv 从 PDF）
        paper_ids = self._get_paper_ids_need_full_name()
        print(f"Fetching {len(paper_ids)} titles")
        for paper_id in paper_ids:
            try:
                self._fetch_full_name_by_paper_id(paper_id)
            except Exception as e:
                print(f"Error fetching full name for {paper_id}: {e}")
                import traceback
                traceback.print_exc()

        paper_ids = self._get_paper_ids_need_ai_attributes()
        print(f"Fetching {len(paper_ids)} ai attributes")
        for paper_id in paper_ids:
            try:
                self._fetch_ai_attributes_by_paper_id(paper_id)
            except Exception as e:
                print(f"Error fetching ai attributes for {paper_id}: {e}")
                import traceback
                traceback.print_exc()


    def _get_paper_ids_need_ai_attributes(self) -> List[str]:
        """
        一下任意属性缺失：
        - abstract
        - full_name 
        - summary
        - alias
        """
        all_paper_ids = self._database.get_paper_ids()
        paper_ids_need = []
        for paper_id in all_paper_ids:
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            missing_fields = []
            
            # 检查各项字段
            if not paper_info.get("abstract"):
                missing_fields.append("abstract")
            if not paper_info.get("summary"):
                missing_fields.append("summary")
            if not paper_info.get("alias"):
                missing_fields.append("alias")
            if not paper_info.get("full_name"):
                missing_fields.append("full_name")
            
            # 如果有缺少的字段，打印详细信息
            if missing_fields:
                print(f"Paper ID: {paper_id}")
                print(f"  缺少字段: {', '.join(missing_fields)}")
                print(f"  当前信息: abstract={bool(paper_info.get('abstract'))}, "
                      f"summary={bool(paper_info.get('summary'))}, "
                      f"alias={bool(paper_info.get('alias'))}, "
                      f"full_name={bool(paper_info.get('full_name'))}, ")
                paper_ids_need.append(paper_id)
        return paper_ids_need
    
    def _fetch_ai_attributes_by_paper_id(self, paper_id: str):
        """
        从 PDF 文本生成 AI 属性
        """
        print(f"Fetching ai attributes for {paper_id}")
        paper_info = self._database.get_paper_info(paper_id=paper_id)
        if not paper_info:
            print(f"Paper info not found for {paper_id}")
            return

        txt_path = os.path.join(self._path, paper_id, "paper.txt")
        if not os.path.exists(txt_path):
            print(f"PDF text not found for {paper_id}, skipping ai attributes")
            return
        
        paper_text = open(txt_path, 'r', encoding='utf-8').read()
        result = self._ai_api.quyer_paper_info(paper_text)
        if result:
            self._database.update_paper_info([{
                "paper_id": paper_id,
                "arxiv_id": paper_info.get("arxiv_id"),
                "abstract": result.get("abstract"),
                "summary": result.get("summary"),
                "full_name": result.get("title"),
                "alias": result.get("alias"),
                "company_names": result.get("company_names"),
                "university_names": result.get("university_names"),
            }])

    
    def _get_paper_ids_need_full_name(self) -> List[str]:
        """获取需要标题的论文 ID"""
        all_papers = self._database.get_all_papers_with_details()
        paper_ids_need = []
        for paper in all_papers:
            if not paper.get("full_name"):
                paper_ids_need.append(paper["paper_id"])
        return paper_ids_need
    
    def _fetch_full_name_by_paper_id(self, paper_id: str):
        """
        获取论文标题：有 arxiv_id 时与其它元数据共用一次 arXiv API；非 arXiv 暂无实现。
        """
        paper_info = self._database.get_paper_info(paper_id=paper_id)
        if not paper_info:
            print(f"Paper info not found for {paper_id}")
            return
        if paper_info.get("arxiv_id"):
            self._ensure_arxiv_metadata_from_api(paper_id, paper_info, updates=None)

    def _convert_pdf_to_txt(self, paper_id: str):
        """
        Convert pdf to txt
        """
        print(f"Converting {paper_id} to txt")
        pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
        txt_path = os.path.join(self._path, paper_id, "paper.txt")
        pdf_convertor = PdfConvertor(pdf_path)
        txt = pdf_convertor.convert_to_text()
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(txt)

    def _download_pdf(self, paper_id: str, arxiv_id: str = None):
        """
        Download pdf from arxiv or other source
        
        Args:
            paper_id: 论文 ID（用于缓存目录）
            arxiv_id: arXiv ID（如果有，用于下载）
        """
        print(f"Downloading pdf for {paper_id}")
        # Create directory for this paper_id if it doesn't exist
        paper_dir = os.path.join(self._path, paper_id)
        os.makedirs(paper_dir, exist_ok=True)
        
        pdf_path = os.path.join(paper_dir, "paper.pdf")
        
        if arxiv_id:
            # Download PDF directly from arxiv
            #pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            self._arxiv_api.download_pdf(arxiv_id, pdf_path)
        else:
            # 非 arXiv 论文，需要从 paper_url 获取
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            if not paper_info:
                raise ValueError(f"Paper info not found for paper_id: {paper_id}")
            pdf_url = paper_info.get("paper_url")
            if not pdf_url:
                raise ValueError(f"Paper URL not found for paper_id: {paper_id}")
        
            response = requests.get(pdf_url, stream=True)
            response.raise_for_status()
            
            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

    def _download_abstract(self, arxiv_id: str):
        """与其它 arXiv 元数据共用一次 API。"""
        paper_info = self._database.get_paper_info(arxiv_id=arxiv_id)
        if not paper_info:
            raise ValueError(f"Paper info not found for arxiv_id: {arxiv_id}")
        self._ensure_arxiv_metadata_from_api(paper_info["paper_id"], paper_info, updates=None)

    def _fetch_author_names(self, arxiv_id: str):
        """与其它 arXiv 元数据共用一次 API。"""
        paper_info = self._database.get_paper_info(arxiv_id=arxiv_id)
        if not paper_info:
            raise ValueError(f"Paper info not found for arxiv_id: {arxiv_id}")
        self._ensure_arxiv_metadata_from_api(paper_info["paper_id"], paper_info, updates=None)
    
    def _get_paper_ids_need_complete(self) -> List[str]:
        """
        查找所有需要 complete 的 paper
        PDF 只是一个缓存，如果数据库中所有属性都完整，就不需要下载 PDF
        
        检查以下条件：
        1. 需要下载摘要（arXiv 论文，不需要 PDF）
        2. 需要获取作者信息（arXiv 论文，不需要 PDF）
        3. 需要获取标题（arXiv 论文不需要 PDF，非 arXiv 论文可能需要 PDF）
        4. 需要获取 AI 属性（需要 PDF 转换的 TXT）
        """
        all_paper_ids = self._database.get_paper_ids()
        paper_ids_need = []
        
        for paper_id in all_paper_ids:
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            if not paper_info:
                continue
            
            arxiv_id = paper_info.get("arxiv_id")
            
            # 检查缺失的属性
            missing_abstract = not paper_info.get("abstract")
            missing_authors = not paper_info.get("author_names")
            missing_full_name = not paper_info.get("full_name")
            missing_summary = not paper_info.get("summary")
            missing_alias = not paper_info.get("alias")
            
            # 检查是否需要下载摘要（arXiv 论文，不需要 PDF）
            need_abstract = arxiv_id and missing_abstract
            
            # 检查是否需要获取作者信息（arXiv 论文，不需要 PDF）
            need_authors = arxiv_id and missing_authors

            # arXiv：comment 未落库或 venue 未结案（两步可分开跑，待补全集合仍用同一条件）
            need_arxiv_comment_or_venue = arxiv_id and (
                paper_info.get("arxiv_comments") is None
                or not paper_info.get("is_comment_used")
            )
            
            # 检查是否需要获取标题
            # arXiv 论文可以从 API 获取，不需要 PDF
            # 非 arXiv 论文可能需要从 PDF 获取
            need_full_name = missing_full_name
            
            # 检查是否需要获取 AI 属性（需要 PDF 转换的 TXT）
            # 如果缺少 abstract、summary、alias、full_name 中的任何一个，可能需要 AI 属性
            need_ai_attributes = missing_abstract or missing_summary or missing_alias or missing_full_name
            
            # 检查是否需要 PDF
            # PDF 只在需要 AI 属性时下载（因为 AI 属性需要 PDF 转换的 TXT）
            # 如果数据库中所有属性都完整，就不需要下载 PDF
            pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
            txt_path = os.path.join(self._path, paper_id, "paper.txt")
            
            # 如果需要 AI 属性，需要 PDF 和 TXT
            need_pdf = need_ai_attributes and (not os.path.exists(pdf_path) or not os.path.exists(txt_path))
            
            # 如果任何一个步骤需要完成，则添加到列表
            if (
                need_abstract
                or need_authors
                or need_arxiv_comment_or_venue
                or need_full_name
                or need_ai_attributes
                or need_pdf
            ):
                paper_ids_need.append(paper_id)
        
        return paper_ids_need

    def _get_paper_ids_need_venue_from_comment(self) -> List[str]:
        """需要从已有 arxiv_comments 解析顶会 / 结案的论文（不拉取 API；comment 为 NULL 的不入队）"""
        out: List[str] = []
        for paper_id in self._database.get_paper_ids():
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            if not paper_info or not paper_info.get("arxiv_id"):
                continue
            if paper_info.get("is_comment_used"):
                continue
            ac = paper_info.get("arxiv_comments")
            if ac is None:
                continue
            out.append(paper_id)
        return out

    def _get_paper_ids_need_pdf_to_txt(self) -> List[str]:
        """本地已有 paper.pdf、尚无 paper.txt 的论文（用于原子步骤 pdf_to_txt）"""
        out: List[str] = []
        for paper_id in self._database.get_paper_ids():
            pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
            txt_path = os.path.join(self._path, paper_id, "paper.txt")
            if os.path.isfile(pdf_path) and not os.path.isfile(txt_path):
                out.append(paper_id)
        return out

    def _paper_ids_sorted_by_date_desc(self) -> List[str]:
        """全库 paper_id：先有 arxiv 的按 arxiv_id 再 date；无 arxiv 的靠后按 date（与 paper_list_sort_key 一致）。"""
        from database import paper_list_sort_key

        all_ids = self._database.get_paper_ids()
        if not all_ids:
            return []
        batch = self._database.get_papers_info_batch(all_ids)
        return sorted(
            all_ids,
            key=lambda pid: paper_list_sort_key(batch.get(pid) or {"paper_id": pid}),
            reverse=True,
        )

    def _apply_newest_date_limit(
        self, paper_ids_need: List[str], newest_limit: Optional[int]
    ) -> List[str]:
        """
        仅在「按日期倒序的全库前 newest_limit 篇」与 paper_ids_need 的交集中保留论文，
        顺序与日期倒序一致。newest_limit 为 None 或 <=0 时不限制。
        """
        if not paper_ids_need:
            return []
        if newest_limit is None or newest_limit <= 0:
            return list(paper_ids_need)
        pool = self._paper_ids_sorted_by_date_desc()[:newest_limit]
        need_set = set(paper_ids_need)
        return [pid for pid in pool if pid in need_set]

    def _complete_single_paper_internal_batch_comment_phase(
        self, paper_id: str, *, phase: str
    ):
        """批量路径：仅 arxiv_comment（含按需一次 API）或仅 venue（不调 API）"""
        updates = {
            "paper_info_updates": [],
            "abstract_updates": [],
            "tag_updates": [],
        }
        try:
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            if not paper_info:
                print(f"错误: 论文信息未找到: {paper_id}")
                return updates
            if not paper_info.get("arxiv_id"):
                return updates
            if phase == "arxiv_comment":
                if self._arxiv_metadata_need_api(paper_info):
                    row = self._fetch_arxiv_metadata_row_for_batch(paper_id, paper_info)
                    if row:
                        updates["paper_info_updates"].append(row)
                    else:
                        return updates
            pi_rows, tag_names = self._process_arxiv_comment_venue(
                paper_id,
                paper_info,
                use_llm_for_venue=True,
                phase=phase,
            )
            if pi_rows:
                updates["paper_info_updates"].extend(pi_rows)
            for t in tag_names:
                updates["tag_updates"].append((paper_id, t))
        except Exception as e:
            import traceback

            print(f"\n❌ arXiv comment/venue 处理 {paper_id} 时出错: {e}")
            traceback.print_exc()
        return updates
    
    def _fetch_ai_attributes_data(self, paper_id: str, paper_info: dict):
        """
        获取 AI 属性数据（不写入数据库）
        
        Returns:
            dict with AI attributes data or None if failed
        """
        try:
            print(f"Fetching ai attributes for {paper_id}")
            txt_path = os.path.join(self._path, paper_id, "paper.txt")
            if not os.path.exists(txt_path):
                print(f"PDF text not found for {paper_id}, skipping ai attributes")
                return None
            
            paper_text = open(txt_path, 'r', encoding='utf-8').read()
            result = self._ai_api.quyer_paper_info(paper_text)
            if result:
                return {
                    "paper_id": paper_id,
                    "arxiv_id": paper_info.get("arxiv_id"),
                    "abstract": result.get("abstract"),
                    "summary": result.get("summary"),
                    "full_name": result.get("title"),
                    "alias": result.get("alias"),
                    "company_names": result.get("company_names"),
                    "university_names": result.get("university_names"),
                }
        except Exception as e:
            print(f"✗ AI 属性获取失败 {paper_id}: {e}")
            return None
        return None

    def _complete_single_paper_internal(self, paper_id: str):
        """
        对单个论文执行完整的补全操作（内部方法，不捕获输出）
        如果某个过程已经完成了可以跳过
        PDF 只是一个缓存，如果数据库中所有属性都完整，就不需要下载 PDF
        
        Args:
            paper_id: 要处理的论文 ID
        """
        try:
            # 获取论文信息
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            if not paper_info:
                print(f"错误: 论文信息未找到: {paper_id}")
                return
            
            arxiv_id = paper_info.get("arxiv_id")
            
            # 1. arXiv 元数据（摘要/作者/标题/arxiv:comment）一次 API；venue 解析仍单独走 LLM
            if arxiv_id:
                try:
                    self._ensure_arxiv_metadata_from_api(paper_id, paper_info, updates=None)
                    paper_info = self._database.get_paper_info(paper_id=paper_id)
                except Exception as e:
                    print(f"✗ arXiv 元数据失败 {paper_id}: {e}")
            
            # 2. arXiv：comment 步与 venue 步顺序执行（不再在此处单独打 arXiv API）
            if arxiv_id:
                try:
                    paper_info = self._database.get_paper_info(paper_id=paper_id)
                    self._apply_arxiv_comment_venue(
                        paper_id, paper_info, phase="arxiv_comment"
                    )
                    paper_info = self._database.get_paper_info(paper_id=paper_id)
                    self._apply_arxiv_comment_venue(paper_id, paper_info, phase="venue")
                except Exception as e:
                    print(f"✗ arXiv comment/venue 处理失败 {paper_id}: {e}")
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            
            # 3. 检查是否需要 AI 属性
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            missing_fields = []
            if not paper_info.get("abstract"):
                missing_fields.append("abstract")
            if not paper_info.get("summary"):
                missing_fields.append("summary")
            if not paper_info.get("alias"):
                missing_fields.append("alias")
            if not paper_info.get("full_name"):
                missing_fields.append("full_name")
            
            need_ai_attributes = len(missing_fields) > 0
            
            # 5. 下载 PDF（只在需要时）
            # PDF 只在需要 AI 属性时下载（因为 AI 属性需要 PDF 转换的 TXT）
            # 如果数据库中所有属性都完整，就不需要下载 PDF
            pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
            txt_path = os.path.join(self._path, paper_id, "paper.txt")
            
            if need_ai_attributes and not os.path.exists(pdf_path):
                # 需要 AI 属性，必须要有 PDF
                try:
                    self._download_pdf(paper_id, arxiv_id)
                except Exception as e:
                    print(f"✗ PDF 下载失败 {paper_id}: {e}")
            
            # 6. 转换 PDF 到 TXT（如果需要 AI 属性）
            pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
            txt_path = os.path.join(self._path, paper_id, "paper.txt")
            if need_ai_attributes and os.path.exists(pdf_path) and not os.path.exists(txt_path):
                try:
                    self._convert_pdf_to_txt(paper_id)
                except Exception as e:
                    print(f"✗ PDF 转换失败 {paper_id}: {e}")
            
            # 7. 获取 AI 属性（如果需要）
            if need_ai_attributes:
                # 重新获取论文信息
                paper_info = self._database.get_paper_info(paper_id=paper_id)
                missing_fields = []
                if not paper_info.get("abstract"):
                    missing_fields.append("abstract")
                if not paper_info.get("summary"):
                    missing_fields.append("summary")
                if not paper_info.get("alias"):
                    missing_fields.append("alias")
                if not paper_info.get("full_name"):
                    missing_fields.append("full_name")
                
                if missing_fields:
                    try:
                        self._fetch_ai_attributes_by_paper_id(paper_id)
                    except Exception as e:
                        print(f"✗ AI 属性获取失败 {paper_id}: {e}")
                    
        except Exception as e:
            import traceback
            print(f"\n❌ 处理论文 {paper_id} 时出错: {e}")
            traceback.print_exc()

    def _complete_single_paper_internal_batch(self, paper_id: str):
        """
        对单个论文执行完整的补全操作（批量版本，返回更新数据而不写入数据库）
        如果某个过程已经完成了可以跳过
        PDF 只是一个缓存，如果数据库中所有属性都完整，就不需要下载 PDF
        
        Args:
            paper_id: 要处理的论文 ID
            
        Returns:
            dict: 包含所有更新数据的字典，格式：
            {
                "paper_info_updates": [...],  # update_paper_info 格式的数据列表
                "abstract_updates": [...],    # [(arxiv_id, abstract), ...] 格式的数据列表
                "tag_updates": [...],         # [(paper_id, tag_name), ...]
            }
        """
        updates = {
            "paper_info_updates": [],
            "abstract_updates": [],
            "tag_updates": [],
        }
        
        try:
            # 获取论文信息
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            if not paper_info:
                print(f"错误: 论文信息未找到: {paper_id}")
                return updates
            
            arxiv_id = paper_info.get("arxiv_id")
            
            # 1. arXiv 元数据（摘要/作者/标题/arxiv:comment）一次 API
            if arxiv_id:
                row = self._fetch_arxiv_metadata_row_for_batch(paper_id, paper_info)
                if row:
                    updates["paper_info_updates"].append(row)
            
            # 2. arXiv：comment 步与 venue 步（不再单独打 arXiv API；paper_info 已由上文就地更新）
            if arxiv_id:
                try:
                    pi_rows, tag_names = self._process_arxiv_comment_venue(
                        paper_id, paper_info, phase="arxiv_comment"
                    )
                    if pi_rows:
                        updates["paper_info_updates"].extend(pi_rows)
                    for t in tag_names:
                        updates["tag_updates"].append((paper_id, t))
                    pi_rows2, tag_names2 = self._process_arxiv_comment_venue(
                        paper_id, paper_info, phase="venue"
                    )
                    if pi_rows2:
                        updates["paper_info_updates"].extend(pi_rows2)
                    for t in tag_names2:
                        updates["tag_updates"].append((paper_id, t))
                except Exception as e:
                    print(f"✗ arXiv comment/venue 处理失败 {paper_id}: {e}")
            
            # 3. 检查是否需要 AI 属性
            missing_fields = []
            if not paper_info.get("abstract"):
                missing_fields.append("abstract")
            if not paper_info.get("summary"):
                missing_fields.append("summary")
            if not paper_info.get("alias"):
                missing_fields.append("alias")
            if not paper_info.get("full_name"):
                missing_fields.append("full_name")
            
            need_ai_attributes = len(missing_fields) > 0
            
            # 5. 下载 PDF（只在需要时）
            # PDF 只在需要 AI 属性时下载（因为 AI 属性需要 PDF 转换的 TXT）
            # 如果数据库中所有属性都完整，就不需要下载 PDF
            pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
            txt_path = os.path.join(self._path, paper_id, "paper.txt")
            
            if need_ai_attributes and not os.path.exists(pdf_path):
                # 需要 AI 属性，必须要有 PDF
                try:
                    self._download_pdf(paper_id, arxiv_id)
                except Exception as e:
                    print(f"✗ PDF 下载失败 {paper_id}: {e}")
            
            # 6. 转换 PDF 到 TXT（如果需要 AI 属性）
            pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
            txt_path = os.path.join(self._path, paper_id, "paper.txt")
            if need_ai_attributes and os.path.exists(pdf_path) and not os.path.exists(txt_path):
                try:
                    self._convert_pdf_to_txt(paper_id)
                except Exception as e:
                    print(f"✗ PDF 转换失败 {paper_id}: {e}")
            
            # 7. 获取 AI 属性（如果需要）
            if need_ai_attributes:
                # 检查是否还有缺失的字段
                missing_fields = []
                if not paper_info.get("abstract"):
                    missing_fields.append("abstract")
                if not paper_info.get("summary"):
                    missing_fields.append("summary")
                if not paper_info.get("alias"):
                    missing_fields.append("alias")
                if not paper_info.get("full_name"):
                    missing_fields.append("full_name")
                
                if missing_fields:
                    ai_data = self._fetch_ai_attributes_data(paper_id, paper_info)
                    if ai_data:
                        # 合并到 paper_info_updates，只包含非 None 的字段
                        update_dict = {"paper_id": paper_id, "arxiv_id": paper_info.get("arxiv_id")}
                        if ai_data.get("abstract"):
                            update_dict["abstract"] = ai_data["abstract"]
                        if ai_data.get("summary"):
                            update_dict["summary"] = ai_data["summary"]
                        if ai_data.get("full_name"):
                            update_dict["full_name"] = ai_data["full_name"]
                        if ai_data.get("alias"):
                            update_dict["alias"] = ai_data["alias"]
                        if ai_data.get("company_names"):
                            update_dict["company_names"] = ai_data["company_names"]
                        if ai_data.get("university_names"):
                            update_dict["university_names"] = ai_data["university_names"]
                        
                        if len(update_dict) > 2:  # 除了 paper_id 和 arxiv_id 还有其他字段
                            updates["paper_info_updates"].append(update_dict)
                    
        except Exception as e:
            import traceback
            print(f"\n❌ 处理论文 {paper_id} 时出错: {e}")
            traceback.print_exc()
        
        return updates

    def _complete_single_paper_internal_batch_atomic(self, paper_id: str, step: str):
        """
        单步补全（批量路径）：只执行 step，返回与其它 batch 相同的 updates 结构。
        step: download_pdf | pdf_to_txt | abstract | authors | full_name | ai
        """
        updates = {
            "paper_info_updates": [],
            "abstract_updates": [],
            "tag_updates": [],
        }
        try:
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            if not paper_info:
                print(f"错误: 论文信息未找到: {paper_id}")
                return updates
            arxiv_id = paper_info.get("arxiv_id")

            if step == "download_pdf":
                self._download_pdf(paper_id, arxiv_id)
                return updates

            if step == "pdf_to_txt":
                pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
                if not os.path.isfile(pdf_path):
                    print(f"跳过 {paper_id}: 无 paper.pdf")
                    return updates
                self._convert_pdf_to_txt(paper_id)
                return updates

            if step == "arxiv_metadata":
                if not arxiv_id:
                    return updates
                row = self._fetch_arxiv_metadata_row_for_batch(paper_id, paper_info)
                if row:
                    updates["paper_info_updates"].append(row)
                return updates

            if step in ("abstract", "authors", "full_name"):
                if not arxiv_id:
                    if step == "full_name":
                        print(f"跳过 {paper_id}: 无 arxiv_id")
                    return updates
                if not self._arxiv_metadata_need_api(paper_info):
                    return updates
                row = self._fetch_arxiv_metadata_row_for_batch(paper_id, paper_info)
                if row:
                    updates["paper_info_updates"].append(row)
                return updates

            if step == "ai":
                ai_data = self._fetch_ai_attributes_data(paper_id, paper_info)
                if ai_data:
                    update_dict = {
                        "paper_id": paper_id,
                        "arxiv_id": paper_info.get("arxiv_id"),
                    }
                    if ai_data.get("abstract"):
                        update_dict["abstract"] = ai_data["abstract"]
                    if ai_data.get("summary"):
                        update_dict["summary"] = ai_data["summary"]
                    if ai_data.get("full_name"):
                        update_dict["full_name"] = ai_data["full_name"]
                    if ai_data.get("alias"):
                        update_dict["alias"] = ai_data["alias"]
                    if ai_data.get("company_names"):
                        update_dict["company_names"] = ai_data["company_names"]
                    if ai_data.get("university_names"):
                        update_dict["university_names"] = ai_data["university_names"]
                    if len(update_dict) > 2:
                        updates["paper_info_updates"].append(update_dict)
                return updates

            print(f"未知原子步骤: {step}")
        except Exception as e:
            import traceback

            print(f"\n❌ 原子步骤 {step} 处理 {paper_id} 时出错: {e}")
            traceback.print_exc()
        return updates

    def _atomic_batch_fn(self, step: str) -> Callable[[str], dict]:
        def _fn(paper_id: str):
            return self._complete_single_paper_internal_batch_atomic(paper_id, step)

        return _fn

    def complete_new(
        self,
        max_workers=10,
        group_size=10,
        only_mode: Optional[str] = None,
        newest_date_limit: Optional[int] = 200,
    ):
        """
        新的 complete 方法：先查找所有需要 complete 的 paper，然后用多线程，
        每个线程做完整的下载补全等操作（如果某个过程已经完成了可以跳过）。
        先分组，每一组并发补全，补全后批量写入数据库。

        Args:
            max_workers: 每组并发线程数（默认 5）
            group_size: 每组处理的论文数量（默认 20）
            only_mode: None 为全量补全；否则为原子步骤，见 --only 帮助。
            newest_date_limit: 仅处理全库按 date 倒序的前 N 篇与「待补全」的交集；默认 200。
                为 None 或 <=0 时不按日期窗口限制（与旧行为一致）。
        """
        # 1. 查找所有需要 complete 的 paper
        if only_mode == "venue":
            paper_ids = self._get_paper_ids_need_venue_from_comment()
            print(f"全库待解析顶会标签（venue）: {len(paper_ids)} 篇")

            def batch_fn(pid: str):
                return self._complete_single_paper_internal_batch_comment_phase(
                    pid, phase="venue"
                )

        elif only_mode == "download_pdf":
            paper_ids = self._get_paper_ids_need_to_download_pdf()
            print(f"全库待下载 PDF: {len(paper_ids)} 篇")
            batch_fn = self._atomic_batch_fn("download_pdf")

        elif only_mode == "pdf_to_txt":
            paper_ids = self._get_paper_ids_need_pdf_to_txt()
            print(f"全库待 PDF→TXT（已有 PDF、尚无 TXT）: {len(paper_ids)} 篇")
            batch_fn = self._atomic_batch_fn("pdf_to_txt")

        elif only_mode == "abstract":
            paper_ids = list(self._database.get_arxiv_ids_having_no_abstarct())
            print(f"全库待拉取摘要（arXiv API）: {len(paper_ids)} 篇")
            batch_fn = self._atomic_batch_fn("abstract")

        elif only_mode == "authors":
            paper_ids = list(self._database.get_arxiv_ids_having_no_authors())
            print(f"全库待拉取作者（arXiv API）: {len(paper_ids)} 篇")
            batch_fn = self._atomic_batch_fn("authors")

        elif only_mode == "full_name":
            paper_ids = self._get_paper_ids_need_full_name()
            print(f"全库待补全标题（arXiv 走 API）: {len(paper_ids)} 篇")
            batch_fn = self._atomic_batch_fn("full_name")

        elif only_mode == "ai":
            paper_ids = self._get_paper_ids_need_ai_attributes()
            print(f"全库待 AI 属性（需 paper.txt）: {len(paper_ids)} 篇")
            batch_fn = self._atomic_batch_fn("ai")

        elif only_mode == "arxiv_metadata":
            paper_ids = self._get_paper_ids_need_arxiv_metadata()
            print(
                f"全库待 arXiv 元数据+comment 步（摘要/作者/标题/arxiv:comment，按组 id_list 批量查询）: {len(paper_ids)} 篇"
            )
            batch_fn = self._atomic_batch_fn("arxiv_metadata")

        else:
            paper_ids = self._get_paper_ids_need_complete()
            print(f"全库待补全: {len(paper_ids)} 篇")
            batch_fn = self._complete_single_paper_internal_batch

        if newest_date_limit is not None and newest_date_limit > 0:
            before = len(paper_ids)
            paper_ids = self._apply_newest_date_limit(paper_ids, newest_date_limit)
            print(
                f"按日期倒序仅考虑最新 {newest_date_limit} 篇，与待补全交集: {len(paper_ids)} 篇"
                f"（全库待补全 {before} 篇）"
            )

        if not paper_ids:
            empty_msgs = {
                "venue": "没有需要解析 venue 的论文（若启用了日期窗口，可能该窗口内无待补全项）",
                "download_pdf": "没有需要下载 PDF 的论文",
                "pdf_to_txt": "没有需要 PDF→TXT 的论文（需先有 paper.pdf）",
                "abstract": "没有需要拉取摘要的 arXiv 论文",
                "authors": "没有需要拉取作者的 arXiv 论文",
                "full_name": "没有需要补全标题的论文",
                "ai": "没有需要补全 AI 属性的论文",
                "arxiv_metadata": "没有需要拉取 arXiv 元数据的论文",
            }
            msg = empty_msgs.get(
                only_mode, "没有需要补全的论文"
            )
            print(msg)
            return

        # 2. 分组
        groups = []
        for i in range(0, len(paper_ids), group_size):
            groups.append(paper_ids[i:i + group_size])
        
        print(f"分为 {len(groups)} 组，每组最多 {group_size} 篇论文，每组并发 {max_workers} 个线程")
        metadata_only_modes = ("arxiv_metadata", "abstract", "authors", "full_name")
        if only_mode in (
            "arxiv_metadata",
            "abstract",
            "authors",
            "full_name",
        ):
            print(
                "提示: 元数据已按组用 arXiv id_list 合并请求；仍受 Client 节流与 429 退避影响。",
                flush=True,
            )

        # 3. 每组并发处理
        total_success = 0
        total_error = 0
        
        for group_idx, group in enumerate(groups, 1):
            print(f"\n处理第 {group_idx}/{len(groups)} 组 ({len(group)} 篇论文)...")
            
            group_success = 0
            group_error = 0
            
            # 收集本组的所有更新数据
            group_paper_info_updates = []
            group_abstract_updates = []
            group_tag_updates = []

            if only_mode in metadata_only_modes:
                meta_rows: List[dict] = []
                try:
                    meta_rows = self._batch_fetch_arxiv_metadata_for_paper_ids(group)
                    if meta_rows:
                        self._database.update_paper_info(meta_rows)
                    group_success = len(group)
                    total_success += len(group)
                    print(
                        f"第 {group_idx} 组 arXiv 元数据批量拉取: 已写入 {len(meta_rows)} 篇",
                        flush=True,
                    )
                except Exception as e:
                    group_error = len(group)
                    total_error += len(group)
                    print(f"\n✗ 第 {group_idx} 组批量元数据失败: {e}")
                    import traceback

                    traceback.print_exc()
                if only_mode == "arxiv_metadata":
                    for pid in group:
                        pi = self._database.get_paper_info(paper_id=pid)
                        if not pi or not pi.get("arxiv_id"):
                            continue
                        try:
                            pi_rows, tag_names = self._process_arxiv_comment_venue(
                                pid,
                                pi,
                                use_llm_for_venue=True,
                                phase="arxiv_comment",
                            )
                            group_paper_info_updates.extend(pi_rows)
                            for t in tag_names:
                                group_tag_updates.append((pid, t))
                        except Exception as e:
                            print(f"\n✗ arXiv comment 步 {pid}: {e}")
                            import traceback

                            traceback.print_exc()
                if group_paper_info_updates or group_abstract_updates or group_tag_updates:
                    try:
                        if group_abstract_updates:
                            self._database.update_paper_abstract(group_abstract_updates)
                        if group_paper_info_updates:
                            self._database.update_paper_info(group_paper_info_updates)
                        for pid, tag_name in group_tag_updates:
                            self._database.add_tag_to_paper(pid, tag_name)
                        print(
                            f"第 {group_idx} 组完成: {group_success} 成功, {group_error} 失败, 已批量写入数据库"
                        )
                    except Exception as e:
                        print(f"✗ 第 {group_idx} 组数据库写入失败: {e}")
                        import traceback

                        traceback.print_exc()
                else:
                    print(
                        f"第 {group_idx} 组完成: {group_success} 成功, {group_error} 失败, 无数据需要写入"
                    )
                continue

            if only_mode is None:
                try:
                    pre_rows = self._batch_fetch_arxiv_metadata_for_paper_ids(group)
                    if pre_rows:
                        self._database.update_paper_info(pre_rows)
                except Exception as e:
                    print(f"\n✗ 第 {group_idx} 组预取 arXiv 元数据失败: {e}")
                    import traceback

                    traceback.print_exc()
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_paper_id = {
                    executor.submit(batch_fn, paper_id): paper_id
                    for paper_id in group
                }
                
                # 使用 tqdm 显示进度
                with tqdm(total=len(group), desc=f"组 {group_idx}", unit="paper") as pbar:
                    # 处理完成的任务
                    for future in as_completed(future_to_paper_id):
                        paper_id = future_to_paper_id[future]
                        try:
                            updates = future.result()  # 获取结果，如果有异常会抛出
                            
                            # 收集更新数据
                            if updates["paper_info_updates"]:
                                group_paper_info_updates.extend(updates["paper_info_updates"])
                            if updates["abstract_updates"]:
                                group_abstract_updates.extend(updates["abstract_updates"])
                            if updates.get("tag_updates"):
                                group_tag_updates.extend(updates["tag_updates"])
                            
                            group_success += 1
                            total_success += 1
                            pbar.set_postfix({"success": group_success, "error": group_error})
                        except Exception as e:
                            group_error += 1
                            total_error += 1
                            pbar.set_postfix({"success": group_success, "error": group_error})
                            print(f"\n✗ 处理失败 {paper_id}: {e}")
                        finally:
                            pbar.update(1)
            
            # 每组处理完后，批量写入数据库（标签在主线程写入，避免多线程锁竞争）
            if group_paper_info_updates or group_abstract_updates or group_tag_updates:
                try:
                    if group_abstract_updates:
                        self._database.update_paper_abstract(group_abstract_updates)
                    if group_paper_info_updates:
                        self._database.update_paper_info(group_paper_info_updates)
                    for pid, tag_name in group_tag_updates:
                        self._database.add_tag_to_paper(pid, tag_name)
                    print(f"第 {group_idx} 组完成: {group_success} 成功, {group_error} 失败, 已批量写入数据库")
                except Exception as e:
                    print(f"✗ 第 {group_idx} 组数据库写入失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"第 {group_idx} 组完成: {group_success} 成功, {group_error} 失败, 无数据需要写入")
        
        print(f"\n所有补全任务完成: 总计 {total_success} 成功, {total_error} 失败")

    def complete_single_paper(self, paper_id: str, only_mode: Optional[str] = None) -> str:
        """
        对单个论文执行 complete 操作（只处理指定的 paper_id）
        
        Args:
            paper_id: 要处理的论文 ID
            only_mode: None 为常规全量步骤；否则为原子步骤（与 CLI --only 一致）
        
        Returns:
            str: 处理日志
        """
        import io
        from contextlib import redirect_stdout
        
        # 捕获输出
        output_buffer = io.StringIO()
        
        try:
            with redirect_stdout(output_buffer):
                print(f"开始处理论文: {paper_id}")
                
                # 获取论文信息
                paper_info = self._database.get_paper_info(paper_id=paper_id)
                if not paper_info:
                    print(f"错误: 论文信息未找到: {paper_id}")
                    return output_buffer.getvalue()
                
                arxiv_id = paper_info.get("arxiv_id")

                if only_mode == "arxiv_metadata":
                    if not arxiv_id:
                        print("非 arXiv 论文，跳过")
                        return output_buffer.getvalue()
                    print(
                        "模式: arXiv API 写入摘要/作者/标题/arxiv:comment，随后 comment 步结案（不调 LLM）"
                    )
                    try:
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                        if self._arxiv_metadata_need_api(paper_info):
                            self._ensure_arxiv_metadata_from_api(paper_id, paper_info, None)
                            print("✓ 元数据已更新")
                        else:
                            print("四类字段均已齐备，跳过 API")
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                        self._apply_arxiv_comment_venue(
                            paper_id,
                            paper_info,
                            use_llm_for_venue=True,
                            phase="arxiv_comment",
                        )
                        print("✓ comment 步完成")
                    except Exception as e:
                        print(f"✗ 失败: {e}")
                    print(f"\n✅ 论文 {paper_id} arXiv 元数据步骤结束")
                    return output_buffer.getvalue()

                if only_mode == "venue":
                    if not arxiv_id:
                        print("非 arXiv 论文，跳过 venue")
                        return output_buffer.getvalue()
                    print("模式: 仅顶会标签（基于已有 arxiv_comments，使用 LLM）")
                    try:
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                        self._apply_arxiv_comment_venue(
                            paper_id, paper_info, use_llm_for_venue=True, phase="venue"
                        )
                        print("✓ venue 处理完成")
                    except Exception as e:
                        print(f"✗ venue 处理失败: {e}")
                    print(f"\n✅ 论文 {paper_id} venue 步骤结束")
                    return output_buffer.getvalue()

                if only_mode == "download_pdf":
                    print("模式: 仅下载 PDF 到缓存目录")
                    try:
                        self._download_pdf(paper_id, arxiv_id)
                        print("✓ PDF 下载完成")
                    except Exception as e:
                        print(f"✗ PDF 下载失败: {e}")
                    print(f"\n✅ 论文 {paper_id} PDF 步骤结束")
                    return output_buffer.getvalue()

                if only_mode == "pdf_to_txt":
                    print("模式: 仅 PDF→TXT")
                    pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
                    if not os.path.isfile(pdf_path):
                        print("无 paper.pdf，跳过")
                    else:
                        try:
                            self._convert_pdf_to_txt(paper_id)
                            print("✓ 转换完成")
                        except Exception as e:
                            print(f"✗ 转换失败: {e}")
                    print(f"\n✅ 论文 {paper_id} PDF→TXT 步骤结束")
                    return output_buffer.getvalue()

                if only_mode == "abstract":
                    if not arxiv_id:
                        print("非 arXiv 论文，跳过摘要")
                        return output_buffer.getvalue()
                    print("模式: 与其它元数据共用一次 arXiv API（任缺一则拉取并写回四类字段）")
                    try:
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                        if self._arxiv_metadata_need_api(paper_info):
                            self._ensure_arxiv_metadata_from_api(paper_id, paper_info, None)
                            print("✓ 已拉取")
                        else:
                            print("无需拉取")
                    except Exception as e:
                        print(f"✗ 失败: {e}")
                    print(f"\n✅ 论文 {paper_id} 摘要步骤结束")
                    return output_buffer.getvalue()

                if only_mode == "authors":
                    if not arxiv_id:
                        print("非 arXiv 论文，跳过作者")
                        return output_buffer.getvalue()
                    print("模式: 与其它元数据共用一次 arXiv API")
                    try:
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                        if self._arxiv_metadata_need_api(paper_info):
                            self._ensure_arxiv_metadata_from_api(paper_id, paper_info, None)
                            print("✓ 已拉取")
                        else:
                            print("无需拉取")
                    except Exception as e:
                        print(f"✗ 失败: {e}")
                    print(f"\n✅ 论文 {paper_id} 作者步骤结束")
                    return output_buffer.getvalue()

                if only_mode == "full_name":
                    print("模式: 仅补全标题（arXiv 走 API；与全量逻辑一致）")
                    try:
                        self._fetch_full_name_by_paper_id(paper_id)
                        print("✓ 标题步骤结束")
                    except Exception as e:
                        print(f"✗ 标题失败: {e}")
                    print(f"\n✅ 论文 {paper_id} 标题步骤结束")
                    return output_buffer.getvalue()

                if only_mode == "ai":
                    print("模式: 仅 AI 属性（需 paper.txt）")
                    try:
                        self._fetch_ai_attributes_by_paper_id(paper_id)
                        print("✓ AI 属性步骤结束")
                    except Exception as e:
                        print(f"✗ AI 属性失败: {e}")
                    print(f"\n✅ 论文 {paper_id} AI 属性步骤结束")
                    return output_buffer.getvalue()

                # 1. 下载 PDF（如果需要）
                pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
                if not os.path.exists(pdf_path):
                    print(f"[1/6] 下载 PDF...")
                    try:
                        self._download_pdf(paper_id, arxiv_id)
                        print(f"✓ PDF 下载完成")
                    except Exception as e:
                        print(f"✗ PDF 下载失败: {e}")
                else:
                    print(f"[1/6] PDF 已存在，跳过下载")
                
                paper_info = self._database.get_paper_info(paper_id=paper_id)
                arxiv_id = paper_info.get("arxiv_id")
                
                # 2–4. arXiv：一次 API 元数据 → comment 步 → venue 步（不混为单一 phase）
                if arxiv_id:
                    print(f"[2/6] arXiv API 元数据（摘要/作者/标题/arxiv:comment）...")
                    try:
                        self._ensure_arxiv_metadata_from_api(paper_id, paper_info, None)
                        print(f"✓ 元数据完成")
                    except Exception as e:
                        print(f"✗ 元数据失败: {e}")
                    print(f"[3/6] arXiv comment（落库/结案，无 LLM）...")
                    try:
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                        self._apply_arxiv_comment_venue(
                            paper_id, paper_info, phase="arxiv_comment"
                        )
                        print(f"✓ arxiv_comment 完成")
                    except Exception as e:
                        print(f"✗ arxiv_comment 失败: {e}")
                    print(f"[4/6] arXiv venue（LLM）...")
                    try:
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                        self._apply_arxiv_comment_venue(paper_id, paper_info, phase="venue")
                        print(f"✓ venue 完成")
                    except Exception as e:
                        print(f"✗ venue 失败: {e}")
                else:
                    print(
                        f"[2/6][3/6][4/6] 非 arXiv 论文，跳过元数据、arxiv_comment 与 venue"
                    )
                
                # 5. 转换 PDF 到 TXT（如果需要）
                txt_path = os.path.join(self._path, paper_id, "paper.txt")
                if os.path.exists(pdf_path) and not os.path.exists(txt_path):
                    print(f"[5/6] 转换 PDF 到 TXT...")
                    try:
                        self._convert_pdf_to_txt(paper_id)
                        print(f"✓ PDF 转换完成")
                    except Exception as e:
                        print(f"✗ PDF 转换失败: {e}")
                elif not os.path.exists(pdf_path):
                    print(f"[5/6] PDF 不存在，跳过转换")
                else:
                    print(f"[5/6] TXT 已存在，跳过转换")
                
                # 6. 获取 AI 属性（如果需要）
                paper_info = self._database.get_paper_info(paper_id=paper_id)
                missing_fields = []
                if not paper_info.get("abstract"):
                    missing_fields.append("abstract")
                if not paper_info.get("summary"):
                    missing_fields.append("summary")
                if not paper_info.get("alias"):
                    missing_fields.append("alias")
                if not paper_info.get("full_name"):
                    missing_fields.append("full_name")
                
                if missing_fields:
                    print(f"[6/6] 获取 AI 属性（缺少: {', '.join(missing_fields)}）...")
                    try:
                        self._fetch_ai_attributes_by_paper_id(paper_id)
                        print(f"✓ AI 属性获取完成")
                    except Exception as e:
                        print(f"✗ AI 属性获取失败: {e}")
                else:
                    print(f"[6/6] AI 属性完整，跳过获取")
                
                print(f"\n✅ 论文 {paper_id} 处理完成")
                
        except Exception as e:
            import traceback
            print(f"\n❌ 处理论文 {paper_id} 时出错: {e}")
            traceback.print_exc()
        
        return output_buffer.getvalue()
    

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    _ONLY_MODES = (
        "arxiv_metadata",
        "venue",
        "download_pdf",
        "pdf_to_txt",
        "abstract",
        "authors",
        "full_name",
        "ai",
    )

    parser = argparse.ArgumentParser(
        description="PaperMap 论文补全（completer）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
原子步骤 (--only)，便于分步执行（与全量路径中的对应段一致）：
  arxiv_metadata  批量 id_list 拉元数据并写库，再对每篇做 comment 步结案（不调 LLM）；随后可 --only venue
  download_pdf    仅下载 PDF 到缓存
  pdf_to_txt      仅转换：已有 paper.pdf → paper.txt
  abstract        与 arxiv_metadata 相同四类字段触发条件（仅批量拉元数据，不做 comment 步）
  authors         同上
  full_name       同上（有 arxiv_id 时）
  ai              仅 LLM 抽取 AI 属性（需 paper.txt）
  venue           仅用库内 arxiv_comments 调 LLM 打 venue 标签（须先有元数据/comment）
  省略 --only 时按「待补全」列表跑全量合并补全（全量内仍顺序执行 comment 与 venue 两步）。""",
    )
    parser.add_argument(
        "--only",
        choices=_ONLY_MODES,
        default=None,
        metavar="STEP",
        help="只跑一个原子步骤；见下方 epilog。与 --paper-id 联用可单篇调试",
    )
    parser.add_argument(
        "--paper-id",
        default=None,
        metavar="ID",
        help="只处理该 paper_id；省略则按库内待补全列表批量处理",
    )
    parser.add_argument("--group-size", type=int, default=30)
    parser.add_argument("--max-workers", type=int, default=20)
    parser.add_argument(
        "--newest-limit",
        type=int,
        default=200,
        metavar="N",
        help="只处理全库按 date 倒序的前 N 篇与待补全列表的交集；0 表示不限制（默认 200）",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="数据库路径（默认 ./data/database.db）",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="缓存目录（默认 ./cache）",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    db_path = str(args.db) if args.db else str(root / "data" / "database.db")
    cache_path = str(args.cache) if args.cache else str(root / "cache")

    cache_manager = Completer(cache_path, Database(db_path))

    if args.paper_id:
        log = cache_manager.complete_single_paper(args.paper_id, only_mode=args.only)
        print(log)
    else:
        nl = None if args.newest_limit <= 0 else args.newest_limit
        cache_manager.complete_new(
            group_size=args.group_size,
            max_workers=args.max_workers,
            only_mode=args.only,
            newest_date_limit=nl,
        )

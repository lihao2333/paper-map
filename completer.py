import os
import requests
from typing import List, Optional
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

    def _process_arxiv_comment_venue(
        self, paper_id: str, paper_info: dict, use_llm_for_venue: bool = True
    ):
        """
        拉取 arXiv comment（若尚未拉过）、解析顶会并返回待写入数据。
        会就地更新 paper_info 中的 arxiv_comments；is_comment_used 仅在无需 LLM、或 LLM 已成功调用后写入。
        返回 (paper_info_rows, tag_names)，paper_info_rows 为 0 或 1 条 update_paper_info 记录。

        use_llm_for_venue: 是否用 LLM 解析 venue；未配置 API、未启用 LLM 或调用失败时不写 is_comment_used，便于之后重试。
        """
        arxiv_id = paper_info.get("arxiv_id")
        if not arxiv_id:
            return [], []

        upd_fields = {}
        tag_names = []

        if paper_info.get("arxiv_comments") is None:
            try:
                print(f"Fetching arXiv comment for {arxiv_id}")
                c = self._arxiv_api.get_comment(arxiv_id)
                upd_fields["arxiv_comments"] = c
                paper_info["arxiv_comments"] = c
            except Exception as e:
                print(f"✗ arXiv comment 获取失败 {paper_id}: {e}")
                return [], []

        if paper_info.get("is_comment_used"):
            if upd_fields:
                return [{"paper_id": paper_id, "arxiv_id": arxiv_id, **upd_fields}], []
            return [], []

        comment = paper_info.get("arxiv_comments") or ""
        stripped = (comment or "").strip()

        def _row():
            if not upd_fields:
                return [], []
            return [{"paper_id": paper_id, "arxiv_id": arxiv_id, **upd_fields}], tag_names

        # 无文本则无需调用模型，直接标记已处理以免队列死循环
        if not stripped:
            upd_fields["is_comment_used"] = True
            paper_info["is_comment_used"] = True
            return _row()

        if not use_llm_for_venue or not self._ai_api.is_llm_configured():
            return _row()

        try:
            tag = extract_venue_tag_from_comment(comment, self._ai_api)
        except Exception as e:
            print(f"✗ LLM 顶会解析失败 {paper_id}: {e}")
            return _row()

        upd_fields["is_comment_used"] = True
        paper_info["is_comment_used"] = True
        if tag:
            tag_names.append(tag)
        return _row()

    def _apply_arxiv_comment_venue(
        self, paper_id: str, paper_info: dict, use_llm_for_venue: bool = True
    ):
        """写入数据库并打标签（用于非 batch 路径）"""
        rows, tags = self._process_arxiv_comment_venue(
            paper_id, paper_info, use_llm_for_venue=use_llm_for_venue
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

        # 2. 下载摘要（只处理 arXiv 论文）
        arxiv_ids = self._database.get_arxiv_ids_having_no_abstarct()
        print(f"Downloading {len(arxiv_ids)} abstracts (arXiv papers only)")
        for arxiv_id in arxiv_ids:
            try:
                self._download_abstract(arxiv_id)
            except Exception as e:
                print(f"Error downloading abstract for {arxiv_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # 2.5. 获取作者信息（只处理 arXiv 论文）
        arxiv_ids = self._database.get_arxiv_ids_having_no_authors()
        print(f"Fetching {len(arxiv_ids)} author names (arXiv papers only)")
        for arxiv_id in arxiv_ids:
            try:
                self._fetch_author_names(arxiv_id)
            except Exception as e:
                print(f"Error fetching author names for {arxiv_id}: {e}")
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
        获取论文标题（arXiv 从 API，非 arXiv 从 PDF）
        """
        print(f"Fetching full name for {paper_id}")
        paper_info = self._database.get_paper_info(paper_id=paper_id)
        if not paper_info:
            print(f"Paper info not found for {paper_id}")
            return
        
        arxiv_id = paper_info.get("arxiv_id")
        if arxiv_id:
            # arXiv 论文，从 API 获取
            full_name = self._arxiv_api.get_title(arxiv_id)
        
            self._database.update_paper_info([{
                "paper_id": paper_id,
                "arxiv_id": arxiv_id,
                "full_name": full_name,
            }])

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
        """
        Download abstract from arxiv using arxiv API and insert to database
        """
        print(f"Downloading abstract for {arxiv_id}")
        abstract = self._arxiv_api.get_abstarct(arxiv_id)   
        self._database.update_paper_abstract([(arxiv_id, abstract)])

    def _fetch_author_names(self, arxiv_id: str):
        """
        Fetch author names from arxiv using arxiv API and insert to database
        """
        print(f"Fetching author names for {arxiv_id}")
        author_names = self._arxiv_api.get_author_names(arxiv_id)
        
        # 获取 paper_id
        paper_info = self._database.get_paper_info(arxiv_id=arxiv_id)
        if not paper_info:
            raise ValueError(f"Paper info not found for arxiv_id: {arxiv_id}")
        paper_id = paper_info["paper_id"]
        
        # 更新作者信息
        self._database.update_paper_info([{
            "paper_id": paper_id,
            "arxiv_id": arxiv_id,
            "author_names": author_names
        }])
    
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

            # arXiv comment / 顶会标签：未拉取 comment 或未做解析标记
            need_comment_venue = arxiv_id and (
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
                or need_comment_venue
                or need_full_name
                or need_ai_attributes
                or need_pdf
            ):
                paper_ids_need.append(paper_id)
        
        return paper_ids_need

    def _get_paper_ids_need_arxiv_comment_only(self) -> List[str]:
        """仅需要拉取 / 解析 arXiv comment 的论文（有 arxiv_id，且未存 comment 或未标记已解析）"""
        out: List[str] = []
        for paper_id in self._database.get_paper_ids():
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            if not paper_info:
                continue
            arxiv_id = paper_info.get("arxiv_id")
            if not arxiv_id:
                continue
            if paper_info.get("arxiv_comments") is None or not paper_info.get(
                "is_comment_used"
            ):
                out.append(paper_id)
        return out

    def _paper_ids_sorted_by_date_desc(self) -> List[str]:
        """全库 paper_id 按 date（yyyyMM）降序；无 date 或非法值排在最后，同日期按 paper_id 升序。"""
        all_ids = self._database.get_paper_ids()
        if not all_ids:
            return []
        batch = self._database.get_papers_info_batch(all_ids)

        def sort_key(pid: str):
            info = batch.get(pid) or {}
            d = info.get("date")
            if d is not None and str(d).strip():
                s = str(d).strip()
                if s.isdigit():
                    return (int(s), pid)
            return (-1, pid)

        return sorted(all_ids, key=sort_key, reverse=True)

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

    def _complete_single_paper_internal_batch_arxiv_comment_only(self, paper_id: str):
        """批量路径：仅 arXiv comment / 顶会标签，返回结构与 _complete_single_paper_internal_batch 一致"""
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
            pi_rows, tag_names = self._process_arxiv_comment_venue(
                paper_id, paper_info, use_llm_for_venue=True
            )
            if pi_rows:
                updates["paper_info_updates"].extend(pi_rows)
            for t in tag_names:
                updates["tag_updates"].append((paper_id, t))
        except Exception as e:
            import traceback

            print(f"\n❌ arXiv comment 处理 {paper_id} 时出错: {e}")
            traceback.print_exc()
        return updates
    
    def _fetch_abstract_data(self, arxiv_id: str, paper_id: str):
        """
        获取摘要数据（不写入数据库）
        
        Returns:
            dict with abstract data or None if failed
        """
        try:
            print(f"Downloading abstract for {arxiv_id}")
            abstract = self._arxiv_api.get_abstarct(arxiv_id)
            return {"paper_id": paper_id, "arxiv_id": arxiv_id, "abstract": abstract}
        except Exception as e:
            print(f"✗ 摘要下载失败 {paper_id}: {e}")
            return None
    
    def _fetch_author_names_data(self, arxiv_id: str, paper_id: str):
        """
        获取作者信息数据（不写入数据库）
        
        Returns:
            dict with author_names data or None if failed
        """
        try:
            print(f"Fetching author names for {arxiv_id}")
            author_names = self._arxiv_api.get_author_names(arxiv_id)
            return {"paper_id": paper_id, "arxiv_id": arxiv_id, "author_names": author_names}
        except Exception as e:
            print(f"✗ 作者信息获取失败 {paper_id}: {e}")
            return None
    
    def _fetch_full_name_data(self, paper_id: str, arxiv_id: str = None):
        """
        获取标题数据（不写入数据库）
        
        Returns:
            dict with full_name data or None if failed
        """
        try:
            print(f"Fetching full name for {paper_id}")
            if arxiv_id:
                full_name = self._arxiv_api.get_title(arxiv_id)
                return {"paper_id": paper_id, "arxiv_id": arxiv_id, "full_name": full_name}
        except Exception as e:
            print(f"✗ 标题获取失败 {paper_id}: {e}")
            return None
        return None
    
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
            
            # 1. 下载摘要（arXiv 论文，不需要 PDF）
            if arxiv_id:
                if not paper_info.get("abstract"):
                    try:
                        self._download_abstract(arxiv_id)
                        # 重新获取论文信息，因为摘要已更新
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                    except Exception as e:
                        print(f"✗ 摘要下载失败 {paper_id}: {e}")
            
            # 2. 获取作者信息（arXiv 论文，不需要 PDF）
            if arxiv_id:
                if not paper_info.get("author_names"):
                    try:
                        self._fetch_author_names(arxiv_id)
                        # 重新获取论文信息，因为作者信息已更新
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                    except Exception as e:
                        print(f"✗ 作者信息获取失败 {paper_id}: {e}")
            
            # 2.5 arXiv comment / 顶会标签
            if arxiv_id:
                try:
                    paper_info = self._database.get_paper_info(paper_id=paper_id)
                    self._apply_arxiv_comment_venue(paper_id, paper_info)
                except Exception as e:
                    print(f"✗ arXiv comment/venue 处理失败 {paper_id}: {e}")
            
            # 3. 获取标题（arXiv 论文不需要 PDF，非 arXiv 论文可能需要 PDF）
            paper_info = self._database.get_paper_info(paper_id=paper_id)
            if not paper_info.get("full_name"):
                # arXiv 论文可以从 API 获取，不需要 PDF
                if arxiv_id:
                    try:
                        self._fetch_full_name_by_paper_id(paper_id)
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                    except Exception as e:
                        print(f"✗ 标题获取失败 {paper_id}: {e}")
                # 非 arXiv 论文可能需要从 PDF 获取，但先尝试其他方法
                # 如果后续需要 AI 属性，会下载 PDF
            
            # 4. 检查是否需要 AI 属性
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
            
            # 1. 下载摘要（arXiv 论文，不需要 PDF）
            if arxiv_id:
                if not paper_info.get("abstract"):
                    abstract_data = self._fetch_abstract_data(arxiv_id, paper_id)
                    if abstract_data:
                        updates["abstract_updates"].append((arxiv_id, abstract_data["abstract"]))
                        # 更新本地 paper_info，避免重复获取
                        paper_info["abstract"] = abstract_data["abstract"]
            
            # 2. 获取作者信息（arXiv 论文，不需要 PDF）
            if arxiv_id:
                if not paper_info.get("author_names"):
                    author_data = self._fetch_author_names_data(arxiv_id, paper_id)
                    if author_data:
                        updates["paper_info_updates"].append({
                            "paper_id": paper_id,
                            "arxiv_id": arxiv_id,
                            "author_names": author_data["author_names"]
                        })
                        # 更新本地 paper_info
                        paper_info["author_names"] = author_data["author_names"]
            
            # 2.5 arXiv comment / 顶会标签
            if arxiv_id:
                try:
                    pi_rows, tag_names = self._process_arxiv_comment_venue(paper_id, paper_info)
                    if pi_rows:
                        updates["paper_info_updates"].extend(pi_rows)
                    for t in tag_names:
                        updates["tag_updates"].append((paper_id, t))
                except Exception as e:
                    print(f"✗ arXiv comment/venue 处理失败 {paper_id}: {e}")
            
            # 3. 获取标题（arXiv 论文不需要 PDF，非 arXiv 论文可能需要 PDF）
            if not paper_info.get("full_name"):
                # arXiv 论文可以从 API 获取，不需要 PDF
                if arxiv_id:
                    full_name_data = self._fetch_full_name_data(paper_id, arxiv_id)
                    if full_name_data:
                        updates["paper_info_updates"].append({
                            "paper_id": paper_id,
                            "arxiv_id": arxiv_id,
                            "full_name": full_name_data["full_name"]
                        })
                        # 更新本地 paper_info
                        paper_info["full_name"] = full_name_data["full_name"]
                # 非 arXiv 论文可能需要从 PDF 获取，但先尝试其他方法
                # 如果后续需要 AI 属性，会下载 PDF
            
            # 4. 检查是否需要 AI 属性
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

    def complete_new(
        self,
        max_workers=10,
        group_size=10,
        only_arxiv_comment: bool = False,
        newest_date_limit: Optional[int] = 200,
    ):
        """
        新的 complete 方法：先查找所有需要 complete 的 paper，然后用多线程，
        每个线程做完整的下载补全等操作（如果某个过程已经完成了可以跳过）。
        先分组，每一组并发补全，补全后批量写入数据库。

        Args:
            max_workers: 每组并发线程数（默认 5）
            group_size: 每组处理的论文数量（默认 20）
            only_arxiv_comment: 为 True 时只拉取 / 解析 arXiv comment 与顶会标签，不跑其它补全步骤
            newest_date_limit: 仅处理全库按 date 倒序的前 N 篇与「待补全」的交集；默认 200。
                为 None 或 <=0 时不按日期窗口限制（与旧行为一致）。
        """
        # 1. 查找所有需要 complete 的 paper
        if only_arxiv_comment:
            paper_ids = self._get_paper_ids_need_arxiv_comment_only()
            print(f"全库待补全 arXiv comment: {len(paper_ids)} 篇")
            batch_fn = self._complete_single_paper_internal_batch_arxiv_comment_only
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
            print(
                "没有需要补全的论文"
                if not only_arxiv_comment
                else "没有需要补全 arXiv comment 的论文（若启用了日期窗口，可能该窗口内无待补全项）"
            )
            return

        # 2. 分组
        groups = []
        for i in range(0, len(paper_ids), group_size):
            groups.append(paper_ids[i:i + group_size])
        
        print(f"分为 {len(groups)} 组，每组最多 {group_size} 篇论文，每组并发 {max_workers} 个线程")
        
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

    def complete_single_paper(self, paper_id: str, only_arxiv_comment: bool = False) -> str:
        """
        对单个论文执行 complete 操作（只处理指定的 paper_id）
        
        Args:
            paper_id: 要处理的论文 ID
            only_arxiv_comment: 为 True 时只拉取 / 解析 arXiv comment 与顶会标签
        
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

                if only_arxiv_comment:
                    if not arxiv_id:
                        print("非 arXiv 论文，跳过 arXiv comment")
                        return output_buffer.getvalue()
                    print("模式: 仅 arXiv comment / 顶会标签")
                    try:
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                        self._apply_arxiv_comment_venue(
                            paper_id, paper_info, use_llm_for_venue=True
                        )
                        print("✓ arXiv comment 处理完成")
                    except Exception as e:
                        print(f"✗ arXiv comment/venue 处理失败: {e}")
                    print(f"\n✅ 论文 {paper_id} comment 处理完成")
                    return output_buffer.getvalue()
                
                # 1. 下载 PDF（如果需要）
                pdf_path = os.path.join(self._path, paper_id, "paper.pdf")
                if not os.path.exists(pdf_path):
                    print(f"[1/7] 下载 PDF...")
                    try:
                        self._download_pdf(paper_id, arxiv_id)
                        print(f"✓ PDF 下载完成")
                    except Exception as e:
                        print(f"✗ PDF 下载失败: {e}")
                else:
                    print(f"[1/7] PDF 已存在，跳过下载")
                
                # 2. 下载摘要（arXiv 论文，如果需要）
                if arxiv_id:
                    if not paper_info.get("abstract"):
                        print(f"[2/7] 下载摘要...")
                        try:
                            self._download_abstract(arxiv_id)
                            print(f"✓ 摘要下载完成")
                        except Exception as e:
                            print(f"✗ 摘要下载失败: {e}")
                    else:
                        print(f"[2/7] 摘要已存在，跳过下载")
                else:
                    print(f"[2/7] 非 arXiv 论文，跳过摘要下载")
                
                # 3. 获取作者信息（arXiv 论文，如果需要）
                if arxiv_id:
                    if not paper_info.get("author_names"):
                        print(f"[3/7] 获取作者信息...")
                        try:
                            self._fetch_author_names(arxiv_id)
                            print(f"✓ 作者信息获取完成")
                        except Exception as e:
                            print(f"✗ 作者信息获取失败: {e}")
                    else:
                        print(f"[3/7] 作者信息已存在，跳过获取")
                else:
                    print(f"[3/7] 非 arXiv 论文，跳过作者信息获取")
                
                # 4. arXiv comment / 顶会标签
                if arxiv_id:
                    print(f"[4/7] arXiv comment / 顶会标签...")
                    try:
                        paper_info = self._database.get_paper_info(paper_id=paper_id)
                        self._apply_arxiv_comment_venue(paper_id, paper_info)
                        print(f"✓ arXiv comment 处理完成")
                    except Exception as e:
                        print(f"✗ arXiv comment/venue 处理失败: {e}")
                else:
                    print(f"[4/7] 非 arXiv 论文，跳过 comment")
                
                # 5. 转换 PDF 到 TXT（如果需要）
                txt_path = os.path.join(self._path, paper_id, "paper.txt")
                if os.path.exists(pdf_path) and not os.path.exists(txt_path):
                    print(f"[5/7] 转换 PDF 到 TXT...")
                    try:
                        self._convert_pdf_to_txt(paper_id)
                        print(f"✓ PDF 转换完成")
                    except Exception as e:
                        print(f"✗ PDF 转换失败: {e}")
                elif not os.path.exists(pdf_path):
                    print(f"[5/7] PDF 不存在，跳过转换")
                else:
                    print(f"[5/7] TXT 已存在，跳过转换")
                
                # 6. 获取标题（如果需要）
                paper_info = self._database.get_paper_info(paper_id=paper_id)
                if not paper_info.get("full_name"):
                    print(f"[6/7] 获取标题...")
                    try:
                        self._fetch_full_name_by_paper_id(paper_id)
                        print(f"✓ 标题获取完成")
                    except Exception as e:
                        print(f"✗ 标题获取失败: {e}")
                else:
                    print(f"[6/7] 标题已存在，跳过获取")
                
                # 7. 获取 AI 属性（如果需要）
                # 重新获取论文信息，因为前面的步骤可能更新了信息
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
                    print(f"[7/7] 获取 AI 属性（缺少: {', '.join(missing_fields)}）...")
                    try:
                        self._fetch_ai_attributes_by_paper_id(paper_id)
                        print(f"✓ AI 属性获取完成")
                    except Exception as e:
                        print(f"✗ AI 属性获取失败: {e}")
                else:
                    print(f"[7/7] AI 属性完整，跳过获取")
                
                print(f"\n✅ 论文 {paper_id} 处理完成")
                
        except Exception as e:
            import traceback
            print(f"\n❌ 处理论文 {paper_id} 时出错: {e}")
            traceback.print_exc()
        
        return output_buffer.getvalue()
    

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="PaperMap 论文补全（completer）")
    parser.add_argument(
        "--only",
        choices=("arxiv_comment", "venue"),
        default=None,
        help="仅执行指定步骤（不跑 PDF/摘要/AI 等）。arxiv_comment 与 venue 等价：拉取 arXiv comment（若尚无）+ 解析顶会并打 venue.<简称> 标签（不含年份）",
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
    only_comment = args.only in ("arxiv_comment", "venue")

    if args.paper_id:
        log = cache_manager.complete_single_paper(
            args.paper_id, only_arxiv_comment=only_comment
        )
        print(log)
    else:
        nl = None if args.newest_limit <= 0 else args.newest_limit
        cache_manager.complete_new(
            group_size=args.group_size,
            max_workers=args.max_workers,
            only_arxiv_comment=only_comment,
            newest_date_limit=nl,
        )

import logging
import requests
import time
import re
import xml.etree.ElementTree as ET
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

mcp = FastMCP("PubmedEnhanced")

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def make_request_with_retry(url, params, max_retries=3, wait_time=1.0):
    """发送带重试机制的请求"""
    for i in range(max_retries):
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            if i < max_retries - 1:
                time.sleep(wait_time)
                wait_time *= 2
            else:
                raise

@mcp.tool()
async def search_pubmed(keywords: List[str] = [], journal: Optional[str] = None, num_results: int = 10, sort_by: str = "relevance") -> Dict[str, Any]:
    """
    使用指定的关键词和可选的期刊名搜索 PubMed 数据库。
    
    此函数允许用户通过提供关键词和可选的期刊名来搜索 PubMed 数据库。
    它以格式化的字典形式返回指定数量的结果。
    
    参数:
    - keywords (List[str]): 在 PubMed 中搜索的关键词，没有字段限制。
    - journal (Optional[str]): 用于将搜索限制到特定期刊的期刊名。
    - num_results (int): 返回的最大结果数。默认为 10。
    - sort_by (str): 结果的排序顺序。选项："relevance" (默认), "date_desc" (最新), "date_asc" (最旧)。
    
    返回:
    - Dict[str, Any]: 包含成功状态、包含 PubMed ID、链接、摘要的结果列表以及找到的总结果数的字典。
    """
    try:
        query_parts = []
        
        if keywords:
            keyword_query = " OR ".join([keyword for keyword in keywords])
            query_parts.append(f"({keyword_query})")
        
        if journal:
            query_parts.append(f"{journal}[Journal]")
        
        query = " AND ".join(query_parts) if query_parts else ""
        
        if not query:
            return {
                "success": False,
                "error": "未提供搜索参数。请指定关键词或期刊。",
                "results": []
            }
        
        logger.info(f"Search query: {query}")
        
        sort_param = ""
        if sort_by == "date_desc":
            sort_param = "pub date"
        elif sort_by == "date_asc":
            sort_param = "pub date"
        
        search_url = f"{BASE_URL}/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": num_results,
            "retmode": "json"
        }
        
        if sort_param:
            search_params["sort"] = sort_param
            
        search_response = make_request_with_retry(search_url, search_params)
        search_data = search_response.json()
        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        
        if sort_by == "date_asc" and sort_param:
            pmids.reverse()
            
        formatted_results = await format_paper_details(pmids)
        
        return {
            "success": True,
            "results": formatted_results,
            "total_results": int(search_data.get("esearchresult", {}).get("count", "0"))
        }
        
    except Exception as e:
        logger.error(f"Error in search_pubmed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "results": []
        }

@mcp.tool()
async def get_mesh_terms(search_word: str) -> Dict[str, Any]:
    """
    获取与搜索词相关的 MeSH（医学主题词）术语。
    
    此函数查询 PubMed MeSH 数据库，以查找与提供的搜索词相匹配的相关医学术语。
    对于寻找标准化医学术语非常有用。
    
    参数:
    - search_word (str): 在 MeSH 数据库中搜索的词或短语。
    
    返回:
    - Dict[str, Any]: 包含成功状态和 MeSH 术语列表的字典。
    """
    try:
        search_url = f"{BASE_URL}/esearch.fcgi"
        search_params = {
            "db": "mesh",
            "term": search_word,
            "retmode": "xml"
        }
        
        search_response = make_request_with_retry(search_url, search_params)
        
        try:
            tree = ET.fromstring(search_response.text)
            mesh_ids = [id_elem.text for id_elem in tree.findall(".//Id")]
        except ET.ParseError as e:
            logger.error(f"XML Parse Error in search response: {str(e)}")
            raise
        
        if not mesh_ids:
            logger.info(f"No MeSH IDs found for term: {search_word}")
            return {
                "success": True,
                "mesh_terms": []
            }

        fetch_url = f"{BASE_URL}/efetch.fcgi"
        fetch_params = {
            "db": "mesh",
            "id": ",".join(mesh_ids),
            "retmode": "text"
        }
        
        fetch_response = make_request_with_retry(fetch_url, fetch_params)
        mesh_terms = parse_mesh_text_response(fetch_response.text)
        logger.debug(f"Parsed MeSH terms: {mesh_terms}")
        
        return {
            "success": True,
            "mesh_terms": mesh_terms
        }
        
    except Exception as e:
        logger.error(f"Error in get_mesh_terms: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "mesh_terms": []
        }

@mcp.tool()
async def get_pubmed_count(search_terms: List[str]) -> Dict[str, Any]:
    """
    获取多个搜索词的 PubMed 结果数量。
    
    此函数查询 PubMed 并返回每个提供的搜索词的结果数量。
    对于比较不同医学术语或概念在文献中的流行度很有用。
    
    参数:
    - search_terms (List[str]): 要在 PubMed 中查询的搜索词列表。
    
    返回:
    - Dict[str, Any]: 包含成功状态和每个搜索词的数量的字典。
    """
    try:
        if not search_terms:
            return {
                "success": False,
                "error": "未提供搜索词",
                "counts": {}
            }
            
        base_url = f"{BASE_URL}/esearch.fcgi"
        counts = {}
        
        for term in search_terms:
            params = {
                "db": "pubmed",
                "term": term,
                "retmode": "xml"
            }
            
            response = make_request_with_retry(base_url, params)
            counts[term] = extract_count_from_xml(response.text)
            
        return {
            "success": True,
            "counts": counts
        }
        
    except Exception as e:
        logger.error(f"Error in get_pubmed_count: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "counts": {}
        }

@mcp.tool()
async def format_paper_details(pubmed_ids: List[str]) -> List[Dict[str, Any]]:
    """
    获取并格式化多个 PubMed 文章的详细信息。
    
    此函数检索一系列 PubMed ID 的详细信息，并将其格式化为
    包含文章信息的字典列表。
    
    参数:
    - pubmed_ids (List[str]): 要获取详细信息的 PubMed ID 列表。
    
    返回:
    - List[Dict[str, Any]]: 字典列表，每个字典包含一篇 PubMed 文章的详细信息。
    """
    try:
        if not pubmed_ids:
            return []
            
        fetch_url = f"{BASE_URL}/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pubmed_ids),
            "retmode": "xml"
        }
        
        fetch_response = make_request_with_retry(fetch_url, fetch_params)
        return parse_article_details(fetch_response.content)
    except Exception as e:
        logger.error(f"Error in format_paper_details: {str(e)}")
        return []

def parse_article_details(xml_content) -> List[Dict[str, Any]]:
    """解析 XML 内容以提取文章详细信息"""
    root = ET.fromstring(xml_content)
    articles = root.findall(".//PubmedArticle")
    results = []
    
    for article in articles:
        title = article.findtext(".//ArticleTitle", default="N/A")
        
        abstract_sections = article.findall(".//Abstract/AbstractText")
        if abstract_sections:
            abstract_parts = []
            for section in abstract_sections:
                label = section.get("Label", "")
                text = section.text or ""
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)
        else:
            abstract = article.findtext(".//Abstract/AbstractText", default="N/A")
        
        journal = article.findtext(".//Journal/Title", default="N/A")
        volume = article.findtext(".//Journal/JournalIssue/Volume", default="N/A")
        issue = article.findtext(".//Journal/JournalIssue/Issue", default="N/A")
        pages = article.findtext(".//Pagination/MedlinePgn", default="N/A")
        
        doi_elem = article.find(".//ELocationID[@EIdType='doi']")
        doi = doi_elem.text if doi_elem is not None else "N/A"
        
        year = article.findtext(".//PubDate/Year", default="")
        month = article.findtext(".//PubDate/Month", default="")
        day = article.findtext(".//PubDate/Day", default="")
        
        pubdate_parts = [part for part in [year, month, day] if part]
        pubdate = "-".join(pubdate_parts) if pubdate_parts else "N/A"
        
        authors = []
        for author in article.findall(".//Author"):
            lastname = author.findtext("LastName", default="")
            forename = author.findtext("ForeName", default="")
            initials = author.findtext("Initials", default="")
            
            if lastname and forename:
                authors.append(f"{lastname} {forename}")
            elif lastname and initials:
                authors.append(f"{lastname} {initials}")
            elif lastname:
                authors.append(lastname)
        
        keywords = []
        for keyword in article.findall(".//MeshHeading/DescriptorName"):
            if keyword.text:
                keywords.append(keyword.text)
        
        pmid = article.findtext(".//PMID", default="N/A")
                
        results.append({
            "pubmed_id": pmid,
            "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "title": title,
            "authors": authors,
            "source": journal,
            "volume": volume,
            "issue": issue,
            "pages": pages,
            "doi": doi,
            "pubdate": pubdate,
            "abstract": abstract,
            "keywords": keywords[:10] if keywords else []
        })
    
    return results

def parse_mesh_text_response(text):
    """解析 MeSH API 的文本响应以提取术语"""
    entries = []
    current_entry = ""
    pattern = r'^\d+: (.+?)(?=\n|$)'
    
    for line in text.split('\n'):
        if re.match(r'^\d+:', line):
            if current_entry:
                match = re.search(pattern, current_entry)
                if match:
                    entries.append(match.group(1).strip())
            current_entry = line
        else:
            current_entry += "\n" + line
    
    if current_entry:
        match = re.search(pattern, current_entry)
        if match:
            entries.append(match.group(1).strip())
    
    return entries

def extract_count_from_xml(xml_text):
    """从 XML 响应中提取计数值"""
    tree = ET.fromstring(xml_text)
    count_element = tree.find("Count")
    if count_element is not None:
        return int(count_element.text)
    else:
        raise ValueError("Count element not found in the XML response")

@mcp.tool()
async def pico_search(p_terms: List[str] = [], i_terms: List[str] = [], c_terms: List[str] = [], o_terms: List[str] = []) -> Dict[str, Any]:
    """
    使用 PICO（人群、干预、对照、结果）和同义词进行 PubMed 搜索。
    
    此函数接收每个 PICO 元素的术语列表，在每个元素内部用 OR 组合它们，
    然后在元素之间执行各种 AND 组合。返回搜索查询和结果数量。
    
    参数:
    - p_terms (List[str]): 人群术语/同义词（建议至少 2 个）
    - i_terms (List[str]): 干预术语/同义词（建议至少 2 个）
    - c_terms (List[str]): 对照术语/同义词（可选，如果提供建议至少 2 个）
    - o_terms (List[str]): 结果术语/同义词（可选，如果提供建议至少 2 个）
    
    返回:
    - Dict[str, Any]: 一个字典，包含单个元素搜索和组合搜索的查询和结果数量。
    """
    try:
        if len(p_terms) < 1 or len(i_terms) < 1:
            return {
                "success": False,
                "error": "至少需要 P (人群) 和 I (干预) 术语，并建议提供多个同义词。",
                "results": {}
            }
            
        results = {}
        
        async def process_element(element_name: str, terms: List[str]) -> Tuple[str, int]:
            if not terms:
                return "", 0
                
            element_query = " OR ".join([f"({term})" for term in terms])
            full_query = f"({element_query})"
            
            count_result = await get_pubmed_count([full_query])
            count = count_result.get("counts", {}).get(full_query, 0)
            
            return full_query, count
        
        p_query, p_count = await process

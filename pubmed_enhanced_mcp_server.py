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
    """Send a request with a retry mechanism."""
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
    Search the PubMed database using specified keywords and optional journal name.
    
    This function allows users to search the PubMed database by providing keywords
    and an optional journal name. It returns a specified number of
    results in a formatted dictionary.
    
    Parameters:
    - keywords (List[str]): Keywords to search for in PubMed without field restrictions.
    - journal (Optional[str]): Journal name to limit the search to a specific journal.
    - num_results (int): Maximum number of results to return. Default is 10.
    - sort_by (str): Sort order for results. Options: "relevance" (default), "date_desc" (newest first), "date_asc" (oldest first).
    
    Returns:
    - Dict[str, Any]: A dictionary containing the success status, a list of results with PubMed IDs,
      links, abstracts, and the total number of results found.
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
                "error": "No search parameters provided. Please specify keywords or journal.",
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
    Get MeSH (Medical Subject Headings) terms related to a search word.
    
    This function queries the PubMed MeSH database to find relevant medical terminology
    that matches the provided search term. Useful for finding standardized medical terms.
    
    Parameters:
    - search_word (str): The word or phrase to search for in the MeSH database.
    
    Returns:
    - Dict[str, Any]: A dictionary containing success status and a list of MeSH terms.
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
    Get the number of PubMed results for multiple search terms.
    
    This function queries PubMed and returns the count of results for each provided search term.
    Useful for comparing the prevalence of different medical terms or concepts in the literature.
    
    Parameters:
    - search_terms (List[str]): List of search terms to query in PubMed.
    
    Returns:
    - Dict[str, Any]: A dictionary containing success status and counts for each search term.
    """
    try:
        if not search_terms:
            return {
                "success": False,
                "error": "No search terms provided",
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
    Fetch and format details of multiple PubMed articles.
    
    This function retrieves details for a list of PubMed IDs and formats them
    into a list of dictionaries containing article information.
    
    Parameters:
    - pubmed_ids (List[str]): A list of PubMed IDs to fetch details for.
    
    Returns:
    - List[Dict[str, Any]]: A list of dictionaries, each containing details of a PubMed article.
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
    """Parse XML content to extract article details"""
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
    """Parse the text response from MeSH API to extract terms"""
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
    """Extract count value from XML response"""
    tree = ET.fromstring(xml_text)
    count_element = tree.find("Count")
    if count_element is not None:
        return int(count_element.text)
    else:
        raise ValueError("Count element not found in the XML response")

@mcp.tool()
async def pico_search(p_terms: List[str] = [], i_terms: List[str] = [], c_terms: List[str] = [], o_terms: List[str] = []) -> Dict[str, Any]:
    """
    Perform PICO (Population, Intervention, Comparison, Outcome) based PubMed search with synonyms.
    
    This function takes lists of terms for each PICO element, combines them with OR within each element,
    and then performs various AND combinations between elements. Returns search queries and result counts.
    
    Parameters:
    - p_terms (List[str]): Population terms/synonyms (at least 2 recommended)
    - i_terms (List[str]): Intervention terms/synonyms (at least 2 recommended)
    - c_terms (List[str]): Comparison terms/synonyms (optional, at least 2 recommended if provided)
    - o_terms (List[str]): Outcome terms/synonyms (optional, at least 2 recommended if provided)
    
    Returns:
    - Dict[str, Any]: A dictionary containing individual element searches and combination searches with queries and result counts
    """
    try:
        if len(p_terms) < 1 or len(i_terms) < 1:
            return {
                "success": False,
                "error": "At least P (Population) and I (Intervention) terms are required with multiple synonyms recommended.",
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
        
        p_query, p_count = await process_element("Population", p_terms)
        i_query, i_count = await process_element("Intervention", i_terms)
        c_query, c_count = await process_element("Comparison", c_terms)
        o_query, o_count = await process_element("Outcome", o_terms)
        
        results["individual"] = {
            "P": {"query": p_query, "count": p_count},
            "I": {"query": i_query, "count": i_count}
        }
        
        if c_terms:
            results["individual"]["C"] = {"query": c_query, "count": c_count}
        
        if o_terms:
            results["individual"]["O"] = {"query": o_query, "count": o_count}
        
        combinations = {}
        
        pi_query = f"{p_query} AND {i_query}"
        pi_count_result = await get_pubmed_count([pi_query])
        combinations["P_AND_I"] = {
            "query": pi_query,
            "count": pi_count_result.get("counts", {}).get(pi_query, 0)
        }
        
        if c_terms:
            pic_query = f"{p_query} AND {i_query} AND {c_query}"
            pic_count_result = await get_pubmed_count([pic_query])
            combinations["P_AND_I_AND_C"] = {
                "query": pic_query,
                "count": pic_count_result.get("counts", {}).get(pic_query, 0)
            }
        
        if o_terms:
            pio_query = f"{p_query} AND {i_query} AND {o_query}"
            pio_count_result = await get_pubmed_count([pio_query])
            combinations["P_AND_I_AND_O"] = {
                "query": pio_query,
                "count": pio_count_result.get("counts", {}).get(pio_query, 0)
            }
        
        if c_terms and o_terms:
            pico_query = f"{p_query} AND {i_query} AND {c_query} AND {o_query}"
            pico_count_result = await get_pubmed_count([pico_query])
            combinations["P_AND_I_AND_C_AND_O"] = {
                "query": pico_query,
                "count": pico_count_result.get("counts", {}).get(pico_query, 0)
            }
        
        results["combinations"] = combinations
        
        return {
            "success": True,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in pico_search: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "results": {}
        }

if __name__ == "__main__":
    mcp.run()

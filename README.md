# PubMed Enhanced Search MCP Server

[![smithery badge](https://smithery.ai/badge/@leescot/pubmed-mcp-smithery)](https://smithery.ai/server/@leescot/pubmed-mcp-smithery)

A Model Content Protocol server that provides enhanced tools to search and retrieve academic papers from PubMed database, with additional features such as MeSH term lookup, publication count statistics, and PICO-based evidence search.

## Features

- Search PubMed by keywords with optional journal filter
- Support for sorting results by relevance or date (newest/oldest first)
- Get MeSH (Medical Subject Headings) terms related to a search word
- Get publication counts for multiple search terms (useful for comparing prevalence)
- Retrieve detailed paper information including abstract, DOI, authors, and keywords
- Perform structured PICO-based searches with support for synonyms and combination queries

## Installing

### Prerequisites

- Python 3.6+
- pip

### Installation

1. Clone this repository:

   ```
   git clone https://github.com/leescot/pubmed-mcp-smithery
   cd pubmed-mcp-smithery
   ```

2. Install dependencies:
   ```
   pip install fastmcp requests
   ```

## Usage

### Running locally

Start the server:

```
python pubmed_enhanced_mcp_server.py
```

For development mode with auto-reloading:

```
mcp dev pubmed_enhanced_mcp_server.py
```

### Adding to Claude Desktop

Edit your Claude Desktop configuration file (_CLAUDE_DIRECTORY/claude_desktop_config.json_) to add the server:

```json
"pubmed-enhanced": {
    "command": "python",
    "args": [
        "/path/pubmed-mcp-smithery/pubmed_enhanced_mcp_server.py"
    ]
}
```

## MCP Functions

The server provides these main functions:

1. `search_pubmed` - Search PubMed for articles matching keywords with optional journal filtering

   ```python
   # Example
   results = await search_pubmed(
       keywords=["diabetes", "insulin resistance"],
       journal="Nature Medicine",
       num_results=5,
       sort_by="date_desc"
   )
   ```

2. `get_mesh_terms` - Look up MeSH terms related to a medical concept

   ```python
   # Example
   mesh_terms = await get_mesh_terms("diabetes")
   ```

3. `get_pubmed_count` - Get the count of publications for multiple search terms

   ```python
   # Example
   counts = await get_pubmed_count(["diabetes", "obesity", "hypertension"])
   ```

4. `format_paper_details` - Get detailed information about specific papers by PMID

   ```python
   # Example
   paper_details = await format_paper_details(["12345678", "87654321"])
   ```

5. `pico_search` - Perform structured PICO (Population, Intervention, Comparison, Outcome) searches with synonyms
   ```python
   # Example
   pico_results = await pico_search(
       p_terms=["diabetes", "type 2 diabetes", "T2DM"],
       i_terms=["metformin", "glucophage"],
       c_terms=["sulfonylurea", "glipizide"],
       o_terms=["HbA1c reduction", "glycemic control"]
   )
   ```

## PICO Search Functionality

The PICO search tool helps researchers conduct evidence-based literature searches by:

1. Allowing multiple synonym terms for each PICO element
2. Combining terms within each element using OR operators
3. Performing AND combinations between elements (P AND I, P AND I AND C, etc.)
4. Returning both search queries and publication counts for each combination

This approach helps refine research questions and identify the most relevant literature.

## Rate Limiting

The server implements automatic retry mechanism with backoff delays to handle potential rate limiting by NCBI's E-utilities service.

## License

This project is licensed under the BSD 3-Clause License - see the LICENSE file for details.

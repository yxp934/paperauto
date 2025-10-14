"""
Paper content loader - extracts text from various sources (PDF, HTML, ArXiv API)
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PaperLoader:
    """Load paper content from various sources"""
    
    def __init__(self):
        pass
    
    def load_from_paper_object(self, paper: Dict) -> Dict[str, str]:
        """
        Load paper content from a paper object (from fetch_papers)
        
        Args:
            paper: Dict with keys like title, abstract, description, arxiv_id
            
        Returns:
            Dict with 'title', 'abstract', 'full_text', 'arxiv_id'
        """
        title = paper.get('title', '')
        abstract = paper.get('description', '') or paper.get('abstract', '')
        arxiv_id = paper.get('id', '') or paper.get('arxiv_id', '') or 'unknown'
        
        # For now, we use abstract as full_text (PDF parsing can be added later)
        # In production, you'd fetch PDF and extract full text here
        full_text = f"{title}\n\n{abstract}"
        
        return {
            'title': title,
            'abstract': abstract,
            'full_text': full_text,
            'arxiv_id': arxiv_id,
            'authors': paper.get('authors', []),
        }
    
    def load_from_arxiv_id(self, arxiv_id: str) -> Optional[Dict[str, str]]:
        """
        Load paper from ArXiv ID (future: fetch PDF and parse)
        
        For now, returns None (not implemented)
        """
        logger.warning(f"load_from_arxiv_id not yet implemented for {arxiv_id}")
        return None


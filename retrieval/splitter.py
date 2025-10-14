"""
Text splitter for chunking paper content
"""
import re
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter


class PaperTextSplitter:
    """Split paper text into chunks for embedding"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        """
        Args:
            chunk_size: Target size of each chunk (in characters)
            chunk_overlap: Overlap between chunks
        """
        # Use RecursiveCharacterTextSplitter with Chinese-friendly separators
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",  # Paragraph breaks
                "\n",    # Line breaks
                "。",    # Chinese period
                "！",    # Chinese exclamation
                "？",    # Chinese question
                "；",    # Chinese semicolon
                ".",     # English period
                "!",
                "?",
                ";",
                " ",     # Space
                "",      # Character-level fallback
            ],
            length_function=len,
        )
    
    def split_text(self, text: str) -> List[str]:
        """
        Split text into chunks
        
        Args:
            text: Full text to split
            
        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []
        
        chunks = self.splitter.split_text(text)
        return [c.strip() for c in chunks if c.strip()]
    
    def split_paper(self, paper_content: dict) -> List[dict]:
        """
        Split paper into chunks with metadata
        
        Args:
            paper_content: Dict from PaperLoader with title, abstract, full_text, arxiv_id
            
        Returns:
            List of dicts with 'text', 'metadata'
        """
        full_text = paper_content.get('full_text', '')
        chunks_text = self.split_text(full_text)
        
        chunks = []
        for i, chunk_text in enumerate(chunks_text):
            chunks.append({
                'text': chunk_text,
                'metadata': {
                    'arxiv_id': paper_content.get('arxiv_id', 'unknown'),
                    'title': paper_content.get('title', ''),
                    'chunk_index': i,
                    'total_chunks': len(chunks_text),
                }
            })
        
        return chunks


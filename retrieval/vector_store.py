"""
Vector store using local Chroma for paper content retrieval
Uses Chroma's default embedding function (all-MiniLM-L6-v2) to avoid protobuf conflicts
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class PaperVectorStore:
    """Local Chroma vector store for paper content"""

    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Initialize Chroma vector store

        Args:
            persist_directory: Local directory to persist Chroma data
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize Chroma client with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )

        # Collection name
        self.collection_name = "papers"

        # Get or create collection (use Chroma's default embedding function)
        try:
            self.collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"Loaded existing collection '{self.collection_name}' with {self.collection.count()} documents")
        except Exception:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Paper content chunks for retrieval"}
            )
            logger.info(f"Created new collection '{self.collection_name}'")
    
    def add_paper(self, paper_id: str, chunks: List[Dict]):
        """
        Add paper chunks to vector store

        Args:
            paper_id: Unique paper identifier (e.g., arxiv_id)
            chunks: List of dicts with 'text' and 'metadata'
        """
        if not chunks:
            logger.warning(f"No chunks to add for paper {paper_id}")
            return

        # Prepare data for Chroma
        texts = [chunk['text'] for chunk in chunks]
        metadatas = [chunk['metadata'] for chunk in chunks]
        ids = [f"{paper_id}_chunk_{i}" for i in range(len(chunks))]

        # Add to collection (Chroma will auto-generate embeddings)
        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )

        logger.info(f"Added {len(chunks)} chunks for paper {paper_id} to vector store")
    
    def query(self, query_text: str, n_results: int = 5, filter_paper_id: Optional[str] = None) -> List[Dict]:
        """
        Query vector store for relevant chunks

        Args:
            query_text: Query string
            n_results: Number of results to return
            filter_paper_id: Optional paper_id to filter results

        Returns:
            List of dicts with 'text', 'metadata', 'distance'
        """
        # Build where clause for filtering
        where = None
        if filter_paper_id:
            where = {"arxiv_id": filter_paper_id}

        # Query collection (Chroma will auto-generate query embedding)
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where
        )

        # Format results
        formatted_results = []
        if results and results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                formatted_results.append({
                    'text': doc,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results['distances'] else 0.0
                })

        return formatted_results
    
    def delete_paper(self, paper_id: str):
        """
        Delete all chunks for a paper
        
        Args:
            paper_id: Paper identifier
        """
        # Get all IDs for this paper
        results = self.collection.get(where={"arxiv_id": paper_id})
        if results and results['ids']:
            self.collection.delete(ids=results['ids'])
            logger.info(f"Deleted {len(results['ids'])} chunks for paper {paper_id}")
    
    def reset(self):
        """Reset (clear) the entire collection"""
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Paper content chunks for retrieval"}
        )
        logger.info(f"Reset collection '{self.collection_name}'")


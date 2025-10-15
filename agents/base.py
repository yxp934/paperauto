"""
Base agent class with LLM integration and token counting
"""
import os
import json
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tiktoken

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all agents with LLM and token counting"""
    
    def __init__(self, name: str):
        self.name = name
        self.llm_client = None  # Will be injected
        self.token_counter = TokenCounter()
        self.total_tokens = 0
        self.total_cost = 0.0
    
    def load_prompt(self, prompt_file: str) -> Dict[str, str]:
        """Load prompt template from YAML file"""
        prompt_path = Path("prompts") / prompt_file
        if not prompt_path.exists():
            logger.error(f"Prompt file not found: {prompt_path}")
            return {"system": "", "user": ""}
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def call_llm(self, messages: List[Dict], temperature: float = 0.3, max_tokens: int = 4096) -> Tuple[str, int, int]:
        """
        Call LLM and count tokens
        
        Returns:
            (response_text, prompt_tokens, completion_tokens)
        """
        if not self.llm_client:
            raise ValueError("LLM client not set")
        
        # Count prompt tokens
        prompt_tokens = self.token_counter.count_messages(messages)
        
        # Call LLM
        response = self.llm_client.chat_completion(messages, temperature, max_tokens)
        if not response:
            logger.error(f"[{self.name}] LLM returned empty text")
        else:
            try:
                logger.info(f"[{self.name}] Raw LLM response (first 400): {response[:400]}")
            except Exception:
                pass

        # Count completion tokens
        completion_tokens = self.token_counter.count_text(response)

        # Update totals
        total = prompt_tokens + completion_tokens
        self.total_tokens += total

        # Estimate cost (rough estimate, adjust based on actual model)
        cost = self._estimate_cost(prompt_tokens, completion_tokens)
        self.total_cost += cost

        logger.info(f"[{self.name}] LLM call: {prompt_tokens} prompt + {completion_tokens} completion = {total} tokens (${cost:.4f})")

        return response, prompt_tokens, completion_tokens

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimate cost based on token counts
        
        Rough pricing (adjust based on actual model):
        - GPT-4o-mini: $0.15/1M input, $0.60/1M output
        - Gemini 1.5 Flash: $0.075/1M input, $0.30/1M output
        """
        # Use conservative estimate (GPT-4o-mini pricing)
        input_cost = (prompt_tokens / 1_000_000) * 0.15
        output_cost = (completion_tokens / 1_000_000) * 0.60
        return input_cost + output_cost
    
    def extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from LLM response with robust cleaning and brace scanning."""
        if not text:
            return None

        import re

        # Normalize and clean invisible/control characters
        cleaned = text
        # Strip BOM and zero-width spaces / non-breaking spaces
        cleaned = cleaned.lstrip("\ufeff").replace("\u200b", "").replace("\u200c", "").replace("\xa0", " ")
        # Remove common markdown code fences
        cleaned = re.sub(r"^```(?:json)?\s*\n", "", cleaned, flags=re.IGNORECASE|re.MULTILINE)
        cleaned = re.sub(r"\n```\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()

        # 1) Try direct parse on fully cleaned text
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # 2) Regex patterns to locate JSON object blocks
        patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{[^\n]*\}\s*$)',  # same-line { ... }
            r'(\{.*?\})',
        ]
        for pattern in patterns:
            m = re.search(pattern, cleaned, re.DOTALL)
            if m:
                frag = m.group(1)
                try:
                    return json.loads(frag)
                except Exception:
                    # try trailing comma fix
                    try:
                        frag2 = re.sub(r',\s*([}\]])', r'\1', frag)
                        return json.loads(frag2)
                    except Exception:
                        continue

        # 3) Brace stack scanning for the first balanced top-level JSON object
        def scan_first_object(s: str) -> Optional[str]:
            depth = 0
            start_idx = -1
            in_str = False
            esc = False
            for i, ch in enumerate(s):
                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                else:
                    if ch == '"':
                        in_str = True
                        continue
                    if ch == '{':
                        if depth == 0:
                            start_idx = i
                        depth += 1
                    elif ch == '}':
                        if depth > 0:
                            depth -= 1
                            if depth == 0 and start_idx != -1:
                                return s[start_idx:i+1]
            return None

        candidate = scan_first_object(cleaned)
        if candidate:
            try:
                return json.loads(candidate)
            except Exception:
                try:
                    candidate2 = re.sub(r',\s*([}\]])', r'\1', candidate)
                    return json.loads(candidate2)
                except Exception:
                    pass

        # 4) Last resort: slice from first { to last } and attempt fix
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1 and end > start:
            span = cleaned[start:end+1]
            span = re.sub(r',\s*([}\]])', r'\1', span)
            try:
                return json.loads(span)
            except Exception:
                pass

        logger.warning(f"[{self.name}] Failed to extract JSON from response")
        return None


class TokenCounter:
    """Token counter using tiktoken"""
    
    def __init__(self, model: str = "gpt-4"):
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except Exception:
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_text(self, text: str) -> int:
        """Count tokens in text"""
        if not text:
            return 0
        return len(self.encoding.encode(text))
    
    def count_messages(self, messages: List[Dict]) -> int:
        """Count tokens in message list"""
        total = 0
        for msg in messages:
            content = msg.get('content', '')
            total += self.count_text(content)
            total += 4  # Overhead per message
        return total


"""
A2A Workflow Coordinator - orchestrates multi-agent paper-to-video generation
"""
import logging
from typing import Dict, List, Callable, Optional
from agents.orchestrator import OrchestratorAgent
from agents.script_agent import ScriptAgent
from agents.slide_agent import SlideAgent
from agents.qa_agent import QAAgent
from retrieval.loader import PaperLoader
from retrieval.splitter import PaperTextSplitter
from retrieval.vector_store import PaperVectorStore

logger = logging.getLogger(__name__)


class A2AWorkflow:
    """Workflow coordinator for A2A multi-agent system"""
    
    def __init__(self, llm_client, log_callback: Optional[Callable] = None):
        """
        Initialize workflow with agents
        
        Args:
            llm_client: LLM client instance
            log_callback: Optional callback for logging (func(dict))
        """
        self.llm_client = llm_client
        self.log_callback = log_callback or (lambda x: None)
        
        # Initialize retrieval components
        self.paper_loader = PaperLoader()
        self.text_splitter = PaperTextSplitter()
        self.vector_store = PaperVectorStore()
        
        # Initialize agents (each creates its own LLMClient with appropriate agent_type)
        self.orchestrator = OrchestratorAgent(log_callback=log_callback)  # Uses AGENT_MODEL
        self.script_agent = ScriptAgent(retriever=self.vector_store, log_callback=log_callback)  # Uses SCRIPT_MODEL
        self.slide_agent = SlideAgent(log_callback=log_callback)  # Uses AGENT_MODEL
        self.qa_agent = QAAgent()
        
        # State tracking
        self.state = {
            'paper': None,
            'sections': None,
            'scripts': None,
            'slides': None,
            'qa_report': None,
            'total_tokens': 0,
            'total_cost': 0.0
        }
    
    def run(self, paper: Dict, max_qa_retries: int = 2) -> Dict:
        """
        Run complete workflow
        
        Args:
            paper: Paper dict {title, abstract, arxiv_id, authors}
            max_qa_retries: Maximum QA retry attempts
            
        Returns:
            {
                "sections": [...],
                "scripts": [...],
                "slides": [...],
                "qa_report": {...},
                "meta": {token counts, costs}
            }
        """
        self._log("workflow", "Starting A2A workflow")
        
        # Step 1: Load and index paper
        self._log("workflow", "Step 1: Loading and indexing paper")
        paper_content = self.paper_loader.load_from_paper_object(paper)
        chunks = self.text_splitter.split_paper(paper_content)
        self.vector_store.add_paper(paper_content['arxiv_id'], chunks)
        self._log("workflow", f"Indexed {len(chunks)} chunks")
        
        self.state['paper'] = paper
        
        # Step 2: Orchestrator - analyze structure
        self._log("orchestrator", "Step 2: Analyzing paper structure")
        orchestrator_result = self.orchestrator.analyze_paper(paper)
        sections = orchestrator_result['sections']
        self._update_tokens(orchestrator_result['meta'])
        self._log("orchestrator", f"Generated {len(sections)} sections")
        
        self.state['sections'] = sections
        
        # Step 3-6: Generate scripts and slides with QA loop
        for attempt in range(max_qa_retries + 1):
            self._log("workflow", f"Generation attempt {attempt + 1}/{max_qa_retries + 1}")
            
            # Step 3: Script Agent - generate scripts
            self._log("script_agent", "Step 3: Generating scripts")
            scripts = []
            for i, section in enumerate(sections):
                self._log("script_agent", f"Generating script {i+1}/{len(sections)}: {section['title']}")
                script = self.script_agent.generate_script(section, paper)
                scripts.append(script)
                self._update_tokens(script.get('meta', {}))
                self._log("script_agent", f"Script {i+1} generated: {len(script.get('narration_parts', []))} parts")
            
            self.state['scripts'] = scripts
            
            # Step 4: Slide Agent - generate slides
            self._log("slide_agent", "Step 4: Generating slides")
            slides = []
            for i, script in enumerate(scripts):
                self._log("slide_agent", f"Generating slide {i+1}/{len(scripts)}: {script['title']}")
                slide = self.slide_agent.generate_slide_plan(script, paper, slide_index=i+1)
                slides.append(slide)
                self._update_tokens(slide.get('meta', {}))
                self._log("slide_agent", f"Slide {i+1} generated with image: {slide.get('image_path', 'N/A')}")
            
            self.state['slides'] = slides
            
            # Step 5: QA Agent - quality check
            self._log("qa_agent", "Step 5: Running quality checks")
            qa_report = self.qa_agent.generate_quality_report(scripts, slides)
            self.state['qa_report'] = qa_report
            
            self._log("qa_agent", f"QA Result: {'PASSED' if qa_report['overall_passed'] else 'FAILED'}")
            self._log("qa_agent", f"Stats: {qa_report['stats']}")
            
            if qa_report['overall_passed']:
                self._log("workflow", "Quality checks passed, workflow complete")
                break
            else:
                self._log("qa_agent", f"Quality issues found: {len(qa_report['scripts_issues']) + len(qa_report['slides_issues'])}")
                for issue in qa_report['scripts_issues']:
                    self._log("qa_agent", f"  - {issue}")
                for issue in qa_report['slides_issues']:
                    self._log("qa_agent", f"  - {issue}")
                
                if attempt < max_qa_retries:
                    self._log("workflow", f"Retrying generation (attempt {attempt + 2})")
                else:
                    self._log("workflow", "Max retries reached, proceeding with current results")
        
        # Aggregate token usage
        self.state['total_tokens'] += self.orchestrator.total_tokens
        self.state['total_tokens'] += self.script_agent.total_tokens
        self.state['total_tokens'] += self.slide_agent.total_tokens
        
        self.state['total_cost'] += self.orchestrator.total_cost
        self.state['total_cost'] += self.script_agent.total_cost
        self.state['total_cost'] += self.slide_agent.total_cost
        
        self._log("workflow", f"Workflow complete. Total tokens: {self.state['total_tokens']}, Total cost: ${self.state['total_cost']:.4f}")
        
        return {
            'sections': self.state['sections'],
            'scripts': self.state['scripts'],
            'slides': self.state['slides'],
            'qa_report': self.state['qa_report'],
            'meta': {
                'total_tokens': self.state['total_tokens'],
                'total_cost': self.state['total_cost'],
                'orchestrator_tokens': self.orchestrator.total_tokens,
                'script_agent_tokens': self.script_agent.total_tokens,
                'slide_agent_tokens': self.slide_agent.total_tokens,
            }
        }
    
    def _update_tokens(self, meta: Dict):
        """Update token counts from agent meta"""
        tokens = meta.get('total_tokens', 0)
        self.state['total_tokens'] += tokens
    
    def _log(self, agent: str, message: str):
        """Send log message via callback"""
        self.log_callback({
            'type': 'log',
            'agent': agent,
            'message': message
        })


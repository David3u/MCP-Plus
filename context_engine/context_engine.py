import os
import pathspec
import logging
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
from .prompts import (
    CONTEXT_ENGINE_SYSTEM_PROMPT, 
    FILE_SELECTION_PROMPT,
    COMPREHENSIVE_ANALYSIS_PROMPT
)

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("ContextEngine")

class ContextEngine:
    def __init__(self):
        logger.info("Initializing ContextEngine...")
        
        # Get API key from environment variable
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is not set. "
                "Please set it in your .env file or environment."
            )
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        
        # Get model from environment variable with fallback
        self.model = os.getenv("CONTEXT_MODEL", "google/gemini-2.5-flash-lite")
        self.system_prompt = CONTEXT_ENGINE_SYSTEM_PROMPT
        logger.info(f"Using model: {self.model}")

    def get_ignore_spec(self, root_dir: str):
        gitignore_path = os.path.join(root_dir, '.gitignore')
        patterns = [
            '.git/', 
            'node_modules/', 
            'venv/', 
            '__pycache__/', 
            '.next/',
            '.DS_Store',
            '*.pyc',
            '.env',
            '.env.local',
            'dist/',
            'build/',
            '.cache/',
        ]
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                patterns.extend(f.readlines())
            logger.debug(f"Loaded .gitignore from {gitignore_path}")
        return pathspec.PathSpec.from_lines('gitwildmatch', patterns)

    def scan_files(self, root_dir: str) -> List[str]:
        logger.info(f"Scanning files in: {root_dir}")
        spec = self.get_ignore_spec(root_dir)
        files = []
        for root, dirs, filenames in os.walk(root_dir):
            rel_root = os.path.relpath(root, root_dir)
            if rel_root == ".":
                rel_root = ""
            
            dirs[:] = [d for d in dirs if not spec.match_file(os.path.join(rel_root, d + '/'))]
            
            for f in filenames:
                rel_path = os.path.join(rel_root, f)
                if not spec.match_file(rel_path):
                    files.append(rel_path)
        
        logger.info(f"Found {len(files)} files")
        return sorted(files)

    def add_line_numbers(self, content: str, interval: int = 50) -> str:
        """Add line numbers at regular intervals for better code citation."""
        lines = content.split('\n')
        result = []
        
        for i, line in enumerate(lines, start=1):
            # Add line number marker every N lines
            if i % interval == 0:
                result.append(f"[Line {i}]")
            result.append(line)
        
        return '\n'.join(result)

    def get_file_content(self, root_dir: str, rel_path: str, max_lines: int = 5000, add_line_nums: bool = True) -> str:
        """Read file content with optional line numbers."""
        try:
            full_path = os.path.join(root_dir, rel_path)
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            if len(lines) > max_lines:
                logger.debug(f"Truncating {rel_path} from {len(lines)} to {max_lines} lines")
                content = "".join(lines[:max_lines])
                content += f"\n\n... [TRUNCATED: {len(lines) - max_lines} more lines] ..."
            else:
                content = "".join(lines)
            
            # Add line numbers at intervals
            if add_line_nums:
                content = self.add_line_numbers(content)
            
            return content
        except UnicodeDecodeError:
            logger.warning(f"Binary file skipped: {rel_path}")
            return "[Binary file - skipped]"
        except Exception as e:
            logger.error(f"Error reading {rel_path}: {e}")
            return f"[Error reading file: {str(e)}]"

    def select_relevant_files(self, question: str, all_files: List[str], max_files: int = 50) -> List[str]:
        """Use LLM to intelligently select the most relevant files."""
        logger.info(f"Using LLM to select top {max_files} relevant files from {len(all_files)} total files...")
        
        file_list_str = "\n".join(all_files)
        prompt = FILE_SELECTION_PROMPT.format(
            question=question,
            file_list=file_list_str
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse response
        selected_files = []
        response_text = response.choices[0].message.content or ""
        
        for line in response_text.split('\n'):
            line = line.strip()
            # Remove markdown formatting, bullets, numbers
            line = line.lstrip('*- 0123456789.').strip()
            line = line.strip('`')
            
            # Only include if it's a valid file from our list
            if line and line in all_files:
                selected_files.append(line)
                if len(selected_files) >= max_files:
                    break
        
        logger.info(f"Selected {len(selected_files)} files for analysis")
        return selected_files

    def get_codebase_context(self, question: str, root_dir: str) -> str:
        """
        Main entry point: analyze codebase with intelligent file selection.
        
        Args:
            question: The question to answer about the codebase
            root_dir: Root directory of the codebase
            
        Returns:
            Comprehensive answer
        """
        logger.info(f"=== Starting context retrieval ===" )
        logger.info(f"Question: {question}")
        logger.info(f"Root dir: {root_dir}")
        
        # 1. Scan all files
        all_files = self.scan_files(root_dir)
        file_list_str = "\n".join(all_files)
        
        # 2. Use LLM to select most relevant files
        selected_files = self.select_relevant_files(question, all_files, max_files=50)
        
        # 3. Read selected file contents with line numbers
        logger.info(f"Reading content from {len(selected_files)} selected files...")
        file_contents_parts = []
        for file_path in selected_files:
            content = self.get_file_content(root_dir, file_path, add_line_nums=True)
            file_contents_parts.append(f"=== FILE: {file_path} ===\n{content}\n")
        
        file_contents_str = "\n".join(file_contents_parts)
        
        # 4. Build comprehensive prompt
        prompt = COMPREHENSIVE_ANALYSIS_PROMPT.format(
            question=question,
            file_list=file_list_str,
            file_contents=file_contents_str
        )
        
        # 5. Single LLM call for comprehensive analysis
        logger.info("Calling LLM for comprehensive analysis...")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        
        initial_result = response.choices[0].message.content or "No response generated."
        
        logger.info(f"=== Context retrieval complete ===")
        return initial_result

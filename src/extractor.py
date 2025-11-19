"""AI-based information extraction from transcripts."""

import logging
from typing import Dict, List, Optional

from anthropic import Anthropic
from openai import OpenAI

from .utils import retry_with_backoff

logger = logging.getLogger(__name__)


class TranscriptExtractor:
    """Extracts key information from transcripts using AI."""

    # Rough character budget per chunk to keep prompts within context limits
    MAX_CHARS_PER_CHUNK = 8000

    EXTRACTION_PROMPT = """You are analyzing a transcript from a YouTube video. Your task is to extract the most relevant and important information.

Please analyze the following transcript and provide:

1. **Executive Summary** (2-3 sentences): A high-level overview of the main topic and conclusion
2. **Key Points** (bullet points): The main ideas and arguments presented
3. **Important Quotes** (with timestamps if available): Notable or impactful statements
4. **Main Topics** (bullet points): The key themes discussed
5. **Actionable Insights** (numbered list): Practical takeaways or recommendations

Format your response in clean, well-structured Markdown.

Video Metadata:
- Title: {title}
- Author: {author}
- Duration: {duration}

Transcript:
{transcript}
"""

    CHUNK_SUMMARY_PROMPT = """You are analyzing PART {index} of {total} from a longer video transcript.

Summarize this part concisely in Markdown with:
- Short section title
- 5–10 bullet point key ideas
- Any especially important quotes (with timestamps if present)

Transcript part:
{transcript_part}
"""

    FINAL_SUMMARY_PROMPT = """You are given high-level summaries of multiple parts of a longer video transcript.

Using ONLY the information below, produce a single, coherent Markdown summary for the entire video with:
1. **Executive Summary** (2-3 sentences)
2. **Key Points** (bullet points)
3. **Important Quotes** (with timestamps if available)
4. **Main Topics** (bullet points)
5. **Actionable Insights** (numbered list)

Video Metadata:
- Title: {title}
- Author: {author}
- Duration: {duration}

Part summaries:
{part_summaries}
"""

    def __init__(self, llm_type: str = "claude", api_key: Optional[str] = None):
        """
        Initialize the extractor.

        Args:
            llm_type: Type of LLM to use ('claude' or 'gpt')
            api_key: API key for the chosen LLM
        """
        self.llm_type = llm_type.lower()
        self.api_key = api_key

        if self.llm_type == "claude":
            self.client = Anthropic(api_key=api_key)
        elif self.llm_type == "gpt":
            self.client = OpenAI(api_key=api_key)
        else:
            raise ValueError(f"Unsupported LLM type: {llm_type}. Use 'claude' or 'gpt'")

    def extract(self, transcript: str, metadata: Dict) -> str:
        """
        Extract key information from transcript using AI.

        Args:
            transcript: The full transcript text
            metadata: Video metadata dictionary

        Returns:
            Extracted information as formatted markdown

        Raises:
            Exception: If extraction fails
        """
        from .utils import format_duration

        title = metadata.get("title", "Unknown")
        author = metadata.get("author", "Unknown")
        duration_str = format_duration(metadata.get("duration", 0))

        # Simple path for shorter transcripts: single extraction call
        if len(transcript) <= self.MAX_CHARS_PER_CHUNK:
            prompt = self.EXTRACTION_PROMPT.format(
                title=title,
                author=author,
                duration=duration_str,
                transcript=transcript,
            )
            if self.llm_type == "claude":
                return self._extract_with_claude(prompt)
            else:
                return self._extract_with_gpt(prompt)

        # For long transcripts, do a hierarchical summarization:
        # 1) summarize each chunk, 2) summarize across chunk summaries.
        logger.info("Transcript is long; using chunked hierarchical extraction...")
        chunks = self._split_transcript(transcript)

        part_summaries: List[str] = []
        total_parts = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            logger.info("Summarizing transcript chunk %d/%d...", idx, total_parts)
            part_prompt = self.CHUNK_SUMMARY_PROMPT.format(
                index=idx,
                total=total_parts,
                transcript_part=chunk,
            )
            if self.llm_type == "claude":
                summary_part = self._extract_with_claude(part_prompt)
            else:
                summary_part = self._extract_with_gpt(part_prompt)
            part_summaries.append(summary_part.strip())

        combined_prompt = self.FINAL_SUMMARY_PROMPT.format(
            title=title,
            author=author,
            duration=duration_str,
            part_summaries="\n\n".join(part_summaries),
        )

        logger.info("Combining chunk summaries into final extraction...")
        if self.llm_type == "claude":
            return self._extract_with_claude(combined_prompt)
        else:
            return self._extract_with_gpt(combined_prompt)

    def _split_transcript(self, transcript: str) -> List[str]:
        """
        Split a long transcript into roughly MAX_CHARS_PER_CHUNK chunks,
        preferring to break on paragraph boundaries.
        """
        if not transcript:
            return [""]

        paragraphs = transcript.split("\n\n")
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph would exceed the limit, start a new chunk
            if current and current_len + len(para) + 2 > self.MAX_CHARS_PER_CHUNK:
                chunks.append("\n\n".join(current))
                current = [para]
                current_len = len(para)
            else:
                current.append(para)
                current_len += len(para) + 2  # account for spacing

        if current:
            chunks.append("\n\n".join(current))

        return chunks

    def _extract_with_claude(self, prompt: str) -> str:
        """
        Extract using Claude API.

        Args:
            prompt: The extraction prompt

        Returns:
            Extracted information

        Raises:
            Exception: If API call fails
        """
        try:
            logger.info("Extracting key information with Claude...")

            def call_claude():
                response = self.client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=4000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                return response.content[0].text

            result = retry_with_backoff(
                call_claude,
                max_retries=3,
                exceptions=(Exception,)
            )

            logger.info("Extraction with Claude complete")
            return result

        except Exception as e:
            raise Exception(f"Claude extraction failed: {str(e)}")

    def _extract_with_gpt(self, prompt: str) -> str:
        """
        Extract using GPT API.

        Args:
            prompt: The extraction prompt

        Returns:
            Extracted information

        Raises:
            Exception: If API call fails
        """
        try:
            logger.info("Extracting key information with GPT...")

            def call_gpt():
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{
                        "role": "system",
                        "content": "You are a helpful assistant that extracts key information from video transcripts."
                    }, {
                        "role": "user",
                        "content": prompt
                    }],
                    max_tokens=4000,
                    temperature=0.3,
                )
                return response.choices[0].message.content

            result = retry_with_backoff(
                call_gpt,
                max_retries=3,
                exceptions=(Exception,)
            )

            logger.info("Extraction with GPT complete")
            return result

        except Exception as e:
            raise Exception(f"GPT extraction failed: {str(e)}")

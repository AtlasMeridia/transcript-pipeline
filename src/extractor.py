"""AI-based information extraction from transcripts."""

from typing import Dict, Optional
from anthropic import Anthropic
from openai import OpenAI
from .utils import retry_with_backoff


class TranscriptExtractor:
    """Extracts key information from transcripts using AI."""

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

        # Prepare the prompt
        prompt = self.EXTRACTION_PROMPT.format(
            title=metadata.get('title', 'Unknown'),
            author=metadata.get('author', 'Unknown'),
            duration=format_duration(metadata.get('duration', 0)),
            transcript=transcript
        )

        # Extract using the appropriate LLM
        if self.llm_type == "claude":
            return self._extract_with_claude(prompt)
        else:
            return self._extract_with_gpt(prompt)

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
            print("Extracting key information with Claude...")

            def call_claude():
                response = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
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

            print("Extraction complete")
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
            print("Extracting key information with GPT...")

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

            print("Extraction complete")
            return result

        except Exception as e:
            raise Exception(f"GPT extraction failed: {str(e)}")

import math
from typing import List

def chunk_text(text: str, max_words: int = 200) -> List[str]:
    """
    Split text into chunks of up to max_words words each.
    Returns a list of text chunks.
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i+max_words])
        chunks.append(chunk)
    return chunks


def summarize_chunk(chunk: str) -> str:
    """
    Placeholder summarizer. Replace with a real LLM or summarizer as needed.
    For now, just returns the first 2 sentences or 50 words.
    """
    import re
    sentences = re.split(r'(?<=[.!?]) +', chunk)
    if len(sentences) > 1:
        return " ".join(sentences[:2])
    else:
        # fallback: first 50 words
        return " ".join(chunk.split()[:50])


def summarize_chunks(chunks: List[str]) -> List[str]:
    """
    Summarize each chunk using summarize_chunk.
    Returns a list of summaries.
    """
    return [summarize_chunk(chunk) for chunk in chunks] 
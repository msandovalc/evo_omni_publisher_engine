# Helper function to extract a clean title from a long caption
def get_smart_title(text: str, max_length: int = 60) -> str:
    """
    Extracts a summary title from a caption based on the first line or sentence.
    """
    if not text:
        return "Untitled Post"

    # 1. Try to split by the first newline
    first_line = text.split('\n')[0].strip()

    # 2. Try to split by the first period within that line
    first_sentence = first_line.split('.')[0].strip()

    # 3. Use the sentence if it's meaningful, otherwise use a clean truncation
    title = first_sentence if first_sentence else first_line

    if len(title) > max_length:
        title = title[:max_length - 3].strip() + "..."

    return title or "Untitled TikTok"
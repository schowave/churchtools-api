def normalize_newlines(text: str) -> str:
    """
    Normalizes line breaks in a text.
    Replaces all types of line breaks (\r\n, \r) with \n.
    Also removes special Unicode characters that may sometimes appear in text fields.
    """
    if text is None:
        return ""
    # First replace \r\n with \n
    text = text.replace("\r\n", "\n")
    # Then replace single \r with \n
    text = text.replace("\r", "\n")
    # Remove special Unicode characters that may sometimes appear in text fields
    text = text.replace("\u2028", "\n")  # Line Separator
    text = text.replace("\u2029", "\n")  # Paragraph Separator
    return text

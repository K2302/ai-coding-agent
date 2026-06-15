"""
Shared tokenizer for BM25 indexing and search.

Extracted to its own module so Whoosh can properly unpickle
the tokenizer class regardless of which module opens the index.
"""

import re
from typing import Any

from whoosh.analysis import LowercaseFilter, Token, Tokenizer


class CamelCaseTokenizer(Tokenizer):
    """Tokenizer that splits identifiers on CamelCase boundaries and non-alphanumeric characters.

    Transforms ``ApplicantService`` → ``applicant service``,
    ``updateStatus`` → ``update status``, and
    ``/candidate/{id}`` → ``candidate id``.
    """

    def __call__(self, text: str, **kwargs: Any) -> Token:  # noqa: ANN401
        text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
        text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
        text = re.sub(r"[^A-Za-z0-9]", " ", text)
        for i, token in enumerate(text.split()):
            if token.strip():
                t = Token()
                t.original = t.text = token
                t.pos = i
                t.startchar = 0
                t.endchar = 0
                yield t


def camel_case_analyzer() -> "whoosh.analysis.Composable":
    """Return a composable analyzer that splits CamelCase and lowercases."""
    return CamelCaseTokenizer() | LowercaseFilter()
"""Calibre-compatible search query parser and evaluator.

Supports:
  - Field prefixes: tags:, title:, authors:, series:, formats:, rating:
  - Quoted values: tags:"Fic.Fantasy"
  - Exact match: tags:"=Fic.Fantasy" (= prefix inside quotes)
  - Boolean operators: and, or, not (case-insensitive)
  - Parentheses for grouping
  - Virtual library references: vl:"Library Name"
  - Bare text: searches across title, authors, tags, series
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from hermitage.database import Book


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class TokType(Enum):
    WORD = auto()
    QUOTED = auto()
    LPAREN = auto()
    RPAREN = auto()
    COLON = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    EOF = auto()


@dataclass(slots=True)
class Token:
    type: TokType
    value: str


def tokenize(query: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(query)

    while i < n:
        c = query[i]

        if c.isspace():
            i += 1
            continue

        if c == "(":
            tokens.append(Token(TokType.LPAREN, "("))
            i += 1
        elif c == ")":
            tokens.append(Token(TokType.RPAREN, ")"))
            i += 1
        elif c == ":":
            tokens.append(Token(TokType.COLON, ":"))
            i += 1
        elif c == '"':
            # Quoted string
            i += 1
            start = i
            while i < n and query[i] != '"':
                i += 1
            tokens.append(Token(TokType.QUOTED, query[start:i]))
            if i < n:
                i += 1  # skip closing quote
        else:
            # Unquoted word — read until whitespace or special char
            start = i
            while i < n and query[i] not in ' \t\n():"':
                i += 1
            word = query[start:i]
            low = word.lower()
            if low == "and":
                tokens.append(Token(TokType.AND, word))
            elif low == "or":
                tokens.append(Token(TokType.OR, word))
            elif low == "not":
                tokens.append(Token(TokType.NOT, word))
            else:
                tokens.append(Token(TokType.WORD, word))

    tokens.append(Token(TokType.EOF, ""))
    return tokens


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------

class Expr:
    """Base class for AST nodes."""


@dataclass(slots=True)
class FieldExpr(Expr):
    field: str       # e.g. "tags", "title", "vl"
    value: str       # the search term
    exact: bool      # True if prefixed with =


@dataclass(slots=True)
class BareExpr(Expr):
    value: str       # searches all fields


@dataclass(slots=True)
class AndExpr(Expr):
    left: Expr
    right: Expr


@dataclass(slots=True)
class OrExpr(Expr):
    left: Expr
    right: Expr


@dataclass(slots=True)
class NotExpr(Expr):
    child: Expr


# ---------------------------------------------------------------------------
# Recursive descent parser
# ---------------------------------------------------------------------------

class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, typ: TokType) -> Token:
        tok = self._advance()
        if tok.type != typ:
            raise ParseError(f"Expected {typ}, got {tok.type}")
        return tok

    def parse(self) -> Expr | None:
        if self._peek().type == TokType.EOF:
            return None
        expr = self._or_expr()
        return expr

    def _or_expr(self) -> Expr:
        left = self._and_expr()
        while self._peek().type == TokType.OR:
            self._advance()
            right = self._and_expr()
            left = OrExpr(left, right)
        return left

    def _and_expr(self) -> Expr:
        left = self._not_expr()
        while self._peek().type == TokType.AND:
            self._advance()
            right = self._not_expr()
            left = AndExpr(left, right)
        # Implicit AND: two primaries next to each other without an operator
        while self._peek().type in (
            TokType.WORD, TokType.QUOTED, TokType.LPAREN, TokType.NOT,
        ):
            right = self._not_expr()
            left = AndExpr(left, right)
        return left

    def _not_expr(self) -> Expr:
        if self._peek().type == TokType.NOT:
            self._advance()
            child = self._not_expr()
            return NotExpr(child)
        return self._primary()

    def _primary(self) -> Expr:
        tok = self._peek()

        if tok.type == TokType.LPAREN:
            self._advance()
            expr = self._or_expr()
            self._expect(TokType.RPAREN)
            return expr

        if tok.type == TokType.WORD:
            # Could be field:value or bare word
            self._advance()
            if self._peek().type == TokType.COLON:
                # Field expression
                self._advance()  # consume colon
                field = tok.value.lower()
                val_tok = self._advance()
                if val_tok.type == TokType.QUOTED:
                    value = val_tok.value
                elif val_tok.type == TokType.WORD:
                    value = val_tok.value
                else:
                    raise ParseError(f"Expected value after {field}:, got {val_tok.type}")
                exact = value.startswith("=")
                if exact:
                    value = value[1:]
                return FieldExpr(field, value, exact)
            else:
                # Bare word
                return BareExpr(tok.value)

        if tok.type == TokType.QUOTED:
            self._advance()
            return BareExpr(tok.value)

        raise ParseError(f"Unexpected token: {tok}")


def parse_query(query: str) -> Expr | None:
    """Parse a Calibre-style search query into an AST."""
    tokens = tokenize(query)
    return Parser(tokens).parse()


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def _field_values(book: Book, field: str) -> list[str]:
    """Get the searchable string values for a field on a Book."""
    if field == "title":
        return [book.title]
    elif field in ("author", "authors"):
        return book.authors
    elif field in ("tag", "tags"):
        return book.tags
    elif field == "series":
        return [book.series] if book.series else []
    elif field in ("format", "formats"):
        return book.formats
    elif field == "rating":
        if book.rating is not None:
            return [str(book.rating // 2)]
        return []
    elif field == "comment":
        return [book.comment] if book.comment else []
    return []


def _match_field(book: Book, field: str, value: str, exact: bool) -> bool:
    """Check if a book's field matches the given value."""
    vals = _field_values(book, field)
    value_lower = value.lower()

    # Hierarchical tag semantics — match cquarry: tags:Foo finds the exact tag
    # 'Foo' AND any descendant tag prefixed by 'Foo.'. This is the only field
    # that uses dot-separated hierarchy in Calibre, so the special case stays
    # narrow. Substring fallback is intentionally gone for tags — it produced
    # absurd matches (tags:Fic matching 'Sci-Fi' because of the substring).
    if field in ("tag", "tags") and not exact:
        prefix = value_lower + "."
        for v in vals:
            v_lower = v.strip().lower()
            if v_lower == value_lower or v_lower.startswith(prefix):
                return True
        return False

    for v in vals:
        v_lower = v.lower()
        if exact:
            if v_lower == value_lower:
                return True
        else:
            if value_lower in v_lower:
                return True
    return False


def _match_bare(book: Book, value: str) -> bool:
    """Check if a bare search term matches any searchable field."""
    value_lower = value.lower()
    for field in ("title", "authors", "tags", "series"):
        for v in _field_values(book, field):
            if value_lower in v.lower():
                return True
    return False


VirtualLibraryResolver = Callable[[str], Expr | None]


def evaluate(
    expr: Expr,
    book: Book,
    vl_resolver: VirtualLibraryResolver | None = None,
) -> bool:
    """Evaluate a parsed query against a book. Returns True if it matches."""
    if isinstance(expr, FieldExpr):
        if expr.field == "vl":
            if vl_resolver:
                vl_expr = vl_resolver(expr.value)
                if vl_expr is not None:
                    return evaluate(vl_expr, book, vl_resolver)
            return False
        return _match_field(book, expr.field, expr.value, expr.exact)
    elif isinstance(expr, BareExpr):
        return _match_bare(book, expr.value)
    elif isinstance(expr, AndExpr):
        return evaluate(expr.left, book, vl_resolver) and evaluate(
            expr.right, book, vl_resolver,
        )
    elif isinstance(expr, OrExpr):
        return evaluate(expr.left, book, vl_resolver) or evaluate(
            expr.right, book, vl_resolver,
        )
    elif isinstance(expr, NotExpr):
        return not evaluate(expr.child, book, vl_resolver)
    return False


def filter_books(
    query: str,
    books: list[Book],
    vl_resolver: VirtualLibraryResolver | None = None,
) -> list[Book]:
    """Parse a query and filter a list of books. Returns all books if query is empty."""
    query = query.strip()
    if not query:
        return books
    try:
        expr = parse_query(query)
    except ParseError:
        return books
    if expr is None:
        return books
    return [b for b in books if evaluate(expr, b, vl_resolver)]

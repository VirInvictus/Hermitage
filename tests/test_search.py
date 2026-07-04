"""Tests for the Calibre-compatible search parser and evaluator.

Pure-Python layer — no GTK, no database. Books are built directly from the
dataclass so every match rule is exercised against known metadata.
"""

import unittest

from hermitage.database import Book
from hermitage.search import (
    AndExpr,
    BareExpr,
    FieldExpr,
    NotExpr,
    OrExpr,
    ParseError,
    Parser,
    TokType,
    evaluate,
    filter_books,
    parse_query,
    tokenize,
)


def _book(**kw):
    defaults = dict(
        id=1,
        title="The Dispossessed",
        sort="Dispossessed, The",
        authors=["Ursula K. Le Guin"],
        path="Ursula K. Le Guin/The Dispossessed (1)",
        has_cover=False,
    )
    defaults.update(kw)
    return Book(**defaults)


# --------------------------------------------------------------------------- #
# tokenizer
# --------------------------------------------------------------------------- #
class TestTokenize(unittest.TestCase):
    def test_words_and_operators(self):
        toks = tokenize("dragons and magic or not epic")
        self.assertEqual(
            [t.type for t in toks],
            [
                TokType.WORD,
                TokType.AND,
                TokType.WORD,
                TokType.OR,
                TokType.NOT,
                TokType.WORD,
                TokType.EOF,
            ],
        )

    def test_quoted_and_field(self):
        toks = tokenize('tags:"Fic.Fantasy"')
        self.assertEqual(
            [t.type for t in toks],
            [TokType.WORD, TokType.COLON, TokType.QUOTED, TokType.EOF],
        )
        self.assertEqual(toks[2].value, "Fic.Fantasy")

    def test_unterminated_quote(self):
        toks = tokenize('"unclosed')
        self.assertEqual(toks[0].type, TokType.QUOTED)
        self.assertEqual(toks[0].value, "unclosed")


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
class TestParser(unittest.TestCase):
    def test_empty_query(self):
        self.assertIsNone(parse_query(""))
        self.assertIsNone(parse_query("   "))

    def test_field_expr(self):
        expr = parse_query("tags:Fantasy")
        self.assertIsInstance(expr, FieldExpr)
        self.assertEqual(
            (expr.field, expr.value, expr.exact), ("tags", "Fantasy", False)
        )

    def test_exact_prefix(self):
        expr = parse_query('tags:"=Fic.Fantasy"')
        self.assertTrue(expr.exact)
        self.assertEqual(expr.value, "Fic.Fantasy")

    def test_implicit_and(self):
        expr = parse_query("dragons magic")
        self.assertIsInstance(expr, AndExpr)
        self.assertIsInstance(expr.left, BareExpr)
        self.assertIsInstance(expr.right, BareExpr)

    def test_explicit_and_after_implicit(self):
        # Regression: "a b and c" used to silently drop "and c" because the
        # implicit-AND loop ran after the explicit one and parse() never
        # checked that all tokens were consumed.
        expr = parse_query("a b and c")
        values = []

        def _collect(e):
            if isinstance(e, AndExpr):
                _collect(e.left)
                _collect(e.right)
            elif isinstance(e, BareExpr):
                values.append(e.value)

        _collect(expr)
        self.assertEqual(values, ["a", "b", "c"])

    def test_implicit_and_after_explicit(self):
        expr = parse_query("a and b c")
        self.assertIsInstance(expr, AndExpr)

    def test_or_precedence(self):
        # AND binds tighter than OR: "a or b c" is a OR (b AND c)
        expr = parse_query("a or b c")
        self.assertIsInstance(expr, OrExpr)
        self.assertIsInstance(expr.right, AndExpr)

    def test_not(self):
        expr = parse_query("not tags:Fantasy")
        self.assertIsInstance(expr, NotExpr)
        self.assertIsInstance(expr.child, FieldExpr)

    def test_parens(self):
        expr = parse_query("(a or b) and c")
        self.assertIsInstance(expr, AndExpr)
        self.assertIsInstance(expr.left, OrExpr)

    def test_trailing_garbage_raises(self):
        with self.assertRaises(ParseError):
            parse_query("a )")

    def test_unbalanced_paren_raises(self):
        with self.assertRaises(ParseError):
            parse_query("(a or b")

    def test_missing_field_value_raises(self):
        with self.assertRaises(ParseError):
            parse_query("tags:)")

    def test_parser_is_reusable_via_tokens(self):
        toks = tokenize("title:foo")
        expr = Parser(toks).parse()
        self.assertIsInstance(expr, FieldExpr)


# --------------------------------------------------------------------------- #
# evaluator
# --------------------------------------------------------------------------- #
class TestEvaluate(unittest.TestCase):
    def setUp(self):
        self.book = _book(
            tags=["Fic.Fantasy.Grimdark", "Owned"],
            series="Hainish Cycle",
            rating=8,
            formats=["EPUB", "PDF"],
            comment="A classic of anarchist science fiction.",
        )

    def _matches(self, query):
        return evaluate(parse_query(query), self.book)

    def test_bare_matches_title_author_tags_series(self):
        self.assertTrue(self._matches("dispossessed"))
        self.assertTrue(self._matches("le guin"))
        self.assertTrue(self._matches("grimdark"))
        self.assertTrue(self._matches("hainish"))
        self.assertFalse(self._matches("tolkien"))

    def test_field_contains(self):
        self.assertTrue(self._matches("title:dispossessed"))
        self.assertTrue(self._matches('authors:"Le Guin"'))
        self.assertTrue(self._matches("formats:epub"))

    def test_field_exact(self):
        self.assertTrue(self._matches('title:"=The Dispossessed"'))
        self.assertFalse(self._matches('title:"=Dispossessed"'))

    def test_tag_hierarchy_prefix(self):
        # tags:Foo matches the exact tag and any Foo.* descendant, and
        # deliberately does NOT substring-match (tags:Fic vs "Sci-Fi").
        self.assertTrue(self._matches("tags:Fic"))
        self.assertTrue(self._matches('tags:"Fic.Fantasy"'))
        self.assertTrue(self._matches("tags:Owned"))
        self.assertFalse(self._matches("tags:Own"))
        self.assertFalse(self._matches("tags:Fantasy"))

    def test_tag_exact(self):
        self.assertTrue(self._matches('tags:"=Fic.Fantasy.Grimdark"'))
        self.assertFalse(self._matches('tags:"=Fic"'))

    def test_rating_is_five_star_scale(self):
        # Calibre stores 0-10; queries use the 5-star scale.
        self.assertTrue(self._matches("rating:4"))
        self.assertFalse(self._matches("rating:5"))

    def test_boolean_combinations(self):
        self.assertTrue(self._matches("tags:Fic and formats:pdf"))
        self.assertFalse(self._matches("tags:Fic and not formats:pdf"))
        self.assertTrue(self._matches("tolkien or series:hainish"))

    def test_vl_resolver(self):
        vl_expr = parse_query("tags:Fic")
        resolver = {"Fiction": vl_expr}.get
        self.assertTrue(evaluate(parse_query('vl:"Fiction"'), self.book, resolver))
        self.assertFalse(evaluate(parse_query('vl:"Nope"'), self.book, resolver))
        # No resolver wired: vl: matches nothing rather than crashing.
        self.assertFalse(evaluate(parse_query('vl:"Fiction"'), self.book, None))


# --------------------------------------------------------------------------- #
# filter_books
# --------------------------------------------------------------------------- #
class TestFilterBooks(unittest.TestCase):
    def setUp(self):
        self.books = [
            _book(id=1, title="A", tags=["Fic"]),
            _book(id=2, title="B", tags=["Non.Fic"]),
            _book(id=3, title="C", tags=[]),
        ]

    def test_empty_query_returns_all(self):
        self.assertEqual(filter_books("", self.books), self.books)

    def test_filters(self):
        got = filter_books("tags:Fic", self.books)
        self.assertEqual([b.id for b in got], [1])

    def test_parse_error_falls_back_to_all(self):
        self.assertEqual(filter_books("a )", self.books), self.books)


if __name__ == "__main__":
    unittest.main()

"""Tests for reportmanager.utils."""

from reportmanager.utils import preprocess_text


class TestPreprocessText:
    """Tests for preprocess_text function."""

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        assert preprocess_text("") == ""

    def test_none_value(self):
        """Test that None returns empty string."""
        assert preprocess_text(None) == ""

    def test_whitespace_only(self):
        """Test that whitespace-only string returns empty string."""
        assert preprocess_text("   ") == ""
        assert preprocess_text("\t\n") == ""

    def test_simple_text(self):
        """Test that simple text is returned unchanged."""
        assert preprocess_text("Hello world") == "Hello world"

    def test_leading_trailing_whitespace(self):
        """Test that leading and trailing whitespace is stripped."""
        assert preprocess_text("  Hello world  ") == "Hello world"
        assert preprocess_text("\tHello world\n") == "Hello world"

    def test_multiple_spaces_collapsed(self):
        """Test that multiple consecutive spaces are collapsed to single space."""
        assert preprocess_text("Hello    world") == "Hello world"
        assert preprocess_text("Hello  world  test") == "Hello world test"

    def test_newlines_and_tabs_collapsed(self):
        """Test that newlines and tabs are replaced with single space."""
        assert preprocess_text("Hello\nworld") == "Hello world"
        assert preprocess_text("Hello\tworld") == "Hello world"
        assert preprocess_text("Hello\n\n\nworld") == "Hello world"
        assert preprocess_text("Line1\nLine2\nLine3") == "Line1 Line2 Line3"

    def test_mixed_whitespace(self):
        """Test that mixed whitespace types are normalized."""
        assert preprocess_text("  Hello \n\t world  ") == "Hello world"
        assert (
            preprocess_text("Text\t\n  with   \nmixed\r\nspaces")
            == "Text with mixed spaces"
        )

    def test_html_entities_decoded(self):
        """Test that HTML entities are unescaped."""
        assert preprocess_text("&lt;div&gt;") == "<div>"
        assert preprocess_text("&amp;") == "&"
        assert preprocess_text("&quot;Hello&quot;") == '"Hello"'
        assert preprocess_text("&#39;apostrophe&#39;") == "'apostrophe'"

    def test_html_entities_with_whitespace(self):
        """Test that HTML entities are decoded and whitespace normalized."""
        assert preprocess_text("  &lt;div&gt;  ") == "<div>"
        assert preprocess_text("&amp;\n&amp;") == "& &"

    def test_real_world_comment(self):
        """Test with a realistic bug report comment."""
        input_text = """
        The page doesn't load properly.

        Steps to reproduce:
        1. Go to the site
        2. Click the button

        Expected: Page loads
        Actual:   &lt;error&gt; shown
        """
        expected = "The page doesn't load properly. Steps to reproduce: 1. Go to the site 2. Click the button Expected: Page loads Actual: <error> shown"  # noqa
        assert preprocess_text(input_text) == expected

    def test_combined_transformations(self):
        """Test multiple transformations applied together."""
        # HTML entities + whitespace normalization + trimming
        assert preprocess_text("  &lt;Hello   World&gt;\n\n") == "<Hello World>"

        # Multiple issues in one string
        input_text = "\t  The &amp; symbol   is\nescaped  "
        assert preprocess_text(input_text) == "The & symbol is escaped"

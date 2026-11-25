"""WordPress-safety helpers for building the pasted page.

Copied from the usage tool's build_embed.py (NFLData/ff_utilization) so this
repo stands alone. If a fix lands there, copy it here too.

The site edits posts where WordPress's wpautop and shortcode filters run over
<script>/<style> bodies, so the pasted block must:
  - have each <style>/<script> body collapsed to ONE line (no line breaks for
    wpautop to inject <p>/<br> into), which means no "//" line comments,
  - contain nothing that looks like a WordPress shortcode ("[table", "[embed"...)
    inside a <script>.
"""
import re

_BLOCK_RE = re.compile(r"(<style[^>]*>|<script[^>]*>)(.*?)(</style>|</script>)",
                       re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(^|[^:\"'])//")


def collapse_script_style_blocks(html):
    """Squash each <style>/<script> body to a single line."""
    def _collapse(match):
        open_tag, body, close_tag = match.groups()
        return open_tag + re.sub(r"\s+", " ", body).strip() + close_tag
    return _BLOCK_RE.sub(_collapse, html)


# Shortcode names registered on the live site (WordPress core, TablePress,
# AdRotate, s2Member). WordPress runs do_shortcode over the post, <script>
# bodies included, so JS like `TABLES[table]` was read as TablePress's [table]
# shortcode and broke the script on the live page. Rename such variables.
_SHORTCODE_NAMES = ("table", "caption", "wp_caption", "gallery", "embed",
                    "audio", "video", "playlist", "the_ad", "adrotate", "s2If",
                    "s2Get", "s2Member", "s2Key", "s2Stream", "s2Eot")
_SHORTCODE_RE = re.compile(r"\[\s*(" + "|".join(_SHORTCODE_NAMES) + r")(?![\w-])", re.I)


def assert_no_shortcode_brackets(html, name):
    for body in re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL):
        m = _SHORTCODE_RE.search(body)
        if m:
            raise AssertionError(
                f"{name}: '{body[m.start():m.start()+30]}' in <script> looks "
                f"like a WordPress shortcode ([{m.group(1)}]) -- WordPress will "
                f"replace it on the live page and break the script. Rename it.")


def assert_no_line_comments(html, name):
    """Collapsing turns newlines into spaces, so a surviving "//" comment would
    silently swallow the rest of the script. Block comments only. The guard
    character class keeps "https://" and "url(https://...)" from tripping it."""
    for body in re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL):
        for num, line in enumerate(body.splitlines(), 1):
            if _LINE_COMMENT_RE.search(line):
                raise AssertionError(
                    f"{name}: '//' line comment in <script> line {num} -- "
                    f"convert it to /* */ in component.html, or collapsing "
                    f"will eat the rest of the file:\n    {line.strip()[:90]}")


# cache:"no-cache" revalidates rather than pinning a ?v= in the URL, so a fresh
# upload is picked up with no code change and an unchanged file returns 304.
FETCH = ('fetch("{url}", {{cache:"no-cache"}}).then(function(r){{'
         'if(!r.ok){{throw new Error("HTTP "+r.status);}}return r.json();}})')

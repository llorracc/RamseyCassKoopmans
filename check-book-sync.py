#!/usr/bin/env python3
"""Report where this handout has drifted from its source, the book's chapter.

The chapter in intertemporal-choice/intertemporal-choice.github.io is the source: edits
start there and are carried into RamseyCassKoopmans.tex by hand (decision 4 of the
split-chapter-appendix skill in llorracc/workspace-course-choice). The chapter is
content/growth/RamseyCassKoopmans/index.md since book PR #83 (0d30dd3) and was
content/growth/RamseyCassKoopmans.md before; the script reads whichever the ref has.
This script only reports; it changes nothing. Adapted from llorracc/PerfForesightCRRA's.

    ./check-book-sync.py                  compare with the book's main branch on GitHub
    ./check-book-sync.py --ref REF        compare with a book branch or commit on GitHub
    ./check-book-sync.py --book-git DIR   read the book at --ref from a local clone (git show)
    ./check-book-sync.py --book-dir DIR   read the book from a local checkout's working tree

The numerical appendix is split off: the time-elimination method left both documents for the
notebook, of which the handout keeps an identical copy (the split-chapter-appendix skill's
decision 6). Each document keeps a paragraph that points to it.

It compares the title, the wording (headings, equations, footnotes, figure captions),
margin notes (the chapter's margin blocks against the handout's \\marginFootnote notes, which
print as footnotes, paired by their words so that a note on one side only is one difference),
equation labels, citations, external links, the
figure files, and the symbols the macros render. It ignores macro names that render the
same, quotation marks and emphasis, and does not compare the bibliography's entries.

It also checks the handout alone for raw letters: every letter in its math that names an
object must be written with its macro (rule D, Chris, 2026-11-15), and a raw letter passes
only if RAW_ALLOWED says what non-object it is (a date, Euler's e, a differential, a dummy
or a throwaway letter).

A difference that should stay goes in one of the ACCEPTED lists below, with its reason.
An entry that no longer matches anything is reported too, so the lists can't go stale.
The handout's symbols are read from the registry's KaTeX file, the published twin of the
LaTeX macros it loads, and from @local/RamseyCassKoopmans.sty.

Exit status: 0 nothing to resolve, 1 something to resolve, 2 the book could not be read.
"""
import argparse
import difflib
import hashlib
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = 'https://raw.githubusercontent.com/intertemporal-choice/intertemporal-choice.github.io/{ref}/{path}'
# The chapter's path, newest first: book PR #83 (0d30dd3) moved it into a folder of its own.
CHAPTERS = ('content/growth/RamseyCassKoopmans/index.md', 'content/growth/RamseyCassKoopmans.md')
START = 'followed much later by'  # the first words of the shared text
REGISTRY = '@resources/notation/econark-math.yml'
LOCAL_STY = os.path.join('@local', 'RamseyCassKoopmans.sty')

# A course macro the chapter writes, and the registry name the handout writes for the same object.
# Empty since book #104 (a7abe20): the chapter writes the registry's names throughout, under Chris's
# 2026-11-16 09:28:16 ruling, "I want to eliminate any bespoke definitions like \pGro and replace them
# with the equivalent from the registry". An entry the chapter no longer uses is reported.
BOOK_TO_HANDOUT = {}

# (book pattern, what the handout writes, why the difference is accepted)
ACCEPTED_REWRITES = []  # the chapter's \check{\kap} became \Steady{\kap} in book #102 (09ee17a)

# (the handout's words just before it, handout words, book words, why accepted)
# Words are as tokenized, with spaces between them.
ACCEPTED_TEXT = []  # 'handout' / 'chapter' went with book #114's intro (no "This handout follows ..." sentence)

# The book's links to labels in other chapters, and the address the handout gives each
# (Chris, 2026-11-14: link to the book's page).
CROSS_CHAPTER = {
    '#eq:PFCRRA-cgrow': 'https://intertemporal-choice.github.io/content/consumption/perfforesightcrra/#eq-pfcrra-cgrow',
    '#eq:PatWGroCond': 'https://intertemporal-choice.github.io/content/consumption/perfforesightcrra/#eq-patwgrocond',
    '#fact:eulerstheorem': 'https://intertemporal-choice.github.io/content/appendices/mathematical/mathfactslist/#fact-eulerstheorem',
    '#sec:HamiltonianVSDiscrete': 'https://intertemporal-choice.github.io/content/appendices/mathematical/hamiltonianvsdiscrete/',
    '#eq:uceqvk': 'https://intertemporal-choice.github.io/content/appendices/mathematical/hamiltonianvsdiscrete/#eq-uceqvk',
    '#eq:lamgrow': 'https://intertemporal-choice.github.io/content/appendices/mathematical/hamiltonianvsdiscrete/#eq-lamgrow',
    '#sec:Endogenous': 'https://intertemporal-choice.github.io/content/growth/endogenous/',
    '#sec:decentralizingrck': 'https://intertemporal-choice.github.io/content/growth/decentralizingrck/',
    '#sec:RCKWithGov': 'https://intertemporal-choice.github.io/content/growth/rckwithgov/',
}

# The notebook beside the chapter, of which the handout keeps an identical copy beside it
# (Chris, 2026-11-14, in cc:course-choice: "own copy of the notebook").
NOTEBOOK = 'RamseyCassKoopmans.ipynb'

# (book address, handout address, why accepted): links the handout points at its own copy.
OWN_COPY = "the handout's own copy of the notebook"
ACCEPTED_LINKS = [
    ('https://colab.research.google.com/github/intertemporal-choice/intertemporal-choice.github.io/blob/main/content/growth/RamseyCassKoopmans/RamseyCassKoopmans.ipynb',
     'https://colab.research.google.com/github/llorracc/RamseyCassKoopmans/blob/master/RamseyCassKoopmans.ipynb', OWN_COPY),
    ('https://mybinder.org/v2/gh/intertemporal-choice/intertemporal-choice.github.io/main?labpath=content/growth/RamseyCassKoopmans/RamseyCassKoopmans.ipynb',
     'https://mybinder.org/v2/gh/llorracc/RamseyCassKoopmans/master?labpath=RamseyCassKoopmans.ipynb', OWN_COPY),
]

# A symbol that prints differently in the handout and the chapter is a difference to resolve, never an
# accepted one: the side that departs from the registry changes. Chris, 2026-11-16 11:11:13 EST, of the
# chapter's italic u against the handout's upright \uFunc, which this list had accepted: "This is exactly
# the kind of thing that should be sync'd when we sync handout and chapter". The list stays only for a
# difference he rules should stay, with his words; it is empty.
ACCEPTED_SYMBOLS = {}

# Rule D (Chris, 2026-11-15, typed in cc:course-choice: "I want you to ensure that the handouts/chapters
# always use the macro for the object, rather than writing it in plain latex; e.g., there should never
# be simply "$C$" but instead "$\CLvl$" etc"). Every letter in the handout's math that names an object
# is written with its macro, the registry's or @local's. A raw letter, Latin or a Greek command such as
# \lambda, passes only where one of these patterns matches at it; each names what the letter is.
GREEK = ('alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa varkappa lambda mu nu '
         'xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega '
         'Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega ell').split()
RAW_ALLOWED = [
    (r't(?![A-Za-z])', 'the date'),
    (r'e(?=\s*\^)', "Euler's e"),
    (r'd(?=\s*(?:\^\{?\d\}?\s*)?(?:[A-Za-z]|\\[A-Za-z]))', 'the differential, as in dt or d^{2}c'),
    (r'\\tau(?![A-Za-z])', 'the dummy of integration in the transversality condition'),
]

# Letters the book's chapter still writes raw, where the handout writes the macro that prints the same
# letter (rule D): (the book's raw letter, the handout's macro). Read only inside the book's math.
# Empty since book #104 (a7abe20) wrote the chapter's raw c, k and \lambda as \cNrm, \kap and \vk.
RAW_IN_BOOK = {}

COMMENT = r'(?<!\\)%.*$'
BOOK_DIR = None  # a local checkout of the book, from --book-dir
BOOK_GIT = None  # a local clone of the book, from --book-git


def fetch(ref, path):
    """The bytes of a file in the book at ref, or None if it isn't there.

    With --book-git, files are read from that clone with git show; with --book-dir, a file that
    is in that checkout is read from it, and the rest come from GitHub."""
    if BOOK_GIT:
        run = subprocess.run(['git', '-C', BOOK_GIT, 'show', f'{ref}:{path}'], capture_output=True)
        return run.stdout if run.returncode == 0 else None
    if BOOK_DIR and os.path.exists(os.path.join(BOOK_DIR, path)):
        with open(os.path.join(BOOK_DIR, path), 'rb') as f:
            return f.read()
    url = RAW.format(ref=urllib.parse.quote(ref, safe=''), path=urllib.parse.quote(path, safe='/'))
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def need(ref, path):
    """The text of a file the check can't run without."""
    data = fetch(ref, path)
    if data is None:
        raise OSError(f'{path} is not there')
    return data.decode('utf8')


def read_macros(text):
    """A MyST math block, either  '\\name': 'definition'  or  "\\\\name": "definition"."""
    table = {}
    for line in text.split('\n'):
        m = re.match(r"""\s*(['"]?)(\\{1,2}[A-Za-z]+)\1\s*:\s*(.*)$""", line)
        if not m:
            continue
        value = m[3].split(' #')[0].strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in '\'"':
            quote, value = value[0], value[1:-1]
            if quote == '"':
                value = value.replace('\\\\', '\\')
        table[m[2].lstrip('\\')] = value
    return table


def expand(definition, table):
    """Replace macros with their definitions until none are left, then drop what doesn't print."""
    for _ in range(12):
        new = re.sub(r'\\([A-Za-z]+)', lambda m: table.get(m[1], m[0]), definition)
        if new == definition:
            break
        definition = new
    definition = re.sub(r'[\s{}]+', '', definition.replace('\\ensuremath', ''))
    return re.sub(r'(\\textbf|\\text)\\text(?![a-z])', r'\1', definition)  # text nested in text prints the same


def matching_brace(text, start):
    depth, i = 0, start
    while i < len(text):
        if text[i] == '\\':
            i += 2
            continue
        depth += (text[i] == '{') - (text[i] == '}')
        if depth == 0:
            return i
        i += 1
    raise ValueError('unbalanced braces after: ' + text[start:start + 60])


def unwrap(text, opener, before='', after=''):
    """Remove a command and its braces, keeping what they enclose."""
    pattern = re.compile(opener + r'\{')
    while True:
        m = pattern.search(text)
        if not m:
            return text
        close = matching_brace(text, m.end() - 1)
        text = text[:m.start()] + before + text[m.end():close] + after + text[close + 1:]


def take_margins(text):
    """The handout's versions of the book's margin notes, removed from the text and returned.

    \\marginFootnote{...} prints a book margin note as a footnote (Chris, 2026-11-14); the 2021 handout's
    instructor notes, \\opt{MarginNotes}{\\marginpar{\\tiny ...}}, printed only with that option."""
    notes = []
    while True:
        m = re.search(r'\\marginFootnote\{|\\opt\{MarginNotes\}\{', text)
        if not m:
            return text, notes
        close = matching_brace(text, m.end() - 1)
        inner = text[m.end():close].strip()
        inner = re.sub(r'^\\marginpar\{(.*)\}$', r'\1', inner, flags=re.S)
        notes.append(re.sub(r'^\\tiny\b', '', inner.strip()))
        text = text[:m.start()] + text[close + 1:]


def between(text, start, end):
    """The text from the first `start` up to the first `end` after it."""
    i = text.index(start)
    return text[i:text.index(end, i)]


def strip_label(x):
    return re.sub(r'^(?:eq|fig):(?:RCK-)?', '', x)


def handout_words(t):
    t = re.sub(COMMENT, '', t, flags=re.M)
    t = re.sub(r'\\(begin|end)\{itemize\}|\\item\b', '', t)
    t = re.sub(r'\\label\{[^}]*\}', '', t)
    t = re.sub(r'\\eqref\{([^}]*)\}', lambda m: 'EQ' + strip_label(m[1]), t)
    t = re.sub(r'[Ff]igure~\\ref\{([^}]*)\}', lambda m: 'FIGREF' + strip_label(m[1]), t)
    t = re.sub(r'\\cite([tp]?)\{([^}]*)\}', lambda m: ('CITEP' if m[1] == 'p' else 'CITET') + m[2], t)  # textual or parenthetical
    t = re.sub(r'\\includegraphics(\[[^\]]*\])?\{[^}]*\}', '', t)
    t = re.sub(r'\\(begin|end)\{figure\}', '', t)
    t = re.sub(r'\\(notag|medskip|pagebreak|centering|centerline|LARGE|Large|bf|small|par)\b', '', t)
    for opener in (r'\\hyperref\[[^\]]*\]', r'\\href\{[^}]*\}', r'\\textit', r'\\textbf', r'\\texttt',
                   r'\\caption', r'\\(?:sub)*section'):
        t = unwrap(t, opener)
    return tokens(unwrap(t, r'\\footnote', ' FOOT ', ' ENDFOOT '))


def book_rewrite(b, used):
    for pattern, replacement, _ in ACCEPTED_REWRITES:
        b, count = re.subn(pattern, replacement, b)
        used[pattern] = used.get(pattern, 0) + count
    return re.sub(r'\\([A-Za-z]+)', lambda m: '\\' + BOOK_TO_HANDOUT.get(m[1], m[1]), b)


def take_book_margins(md):
    """The chapter's margin blocks, removed from the text and returned."""
    notes = re.findall(r'^:::\{margin\}\n(.*?)\n:::$', md, flags=re.M | re.S)
    return re.sub(r'^:::\{margin\}\n.*?\n:::$', '', md, flags=re.M | re.S), notes


def raw_pattern(letter):
    """A raw letter, Latin or a Greek command, not inside a longer command name."""
    if letter.startswith('\\'):
        return re.escape(letter) + r'(?![A-Za-z])'
    return r'(?<![\\A-Za-z])' + re.escape(letter) + r'(?![A-Za-z])'


def book_math(s, raw_used):
    """The book's math, with the raw letters of RAW_IN_BOOK written as the handout's macros."""
    for letter, macro in RAW_IN_BOOK.items():
        s, n = re.subn(raw_pattern(letter), lambda m: '\\' + macro, s)
        raw_used[letter] = raw_used.get(letter, 0) + n
    return s


def book_words(b, raw_used):
    """A page's words, already rewritten into the handout's macro names."""
    b = re.sub(r'^- ', '', b, flags=re.M)  # list items, which the handout writes as \item
    footnotes = {}

    def keep(m):
        footnotes[m[1]] = m[2]
        return ''

    b = re.sub(r'^\[\^([\w-]+)\]:[ \n]((?:.*\n?)(?:(?:[ ]{4}.*|)\n)*)', keep, b, flags=re.M)
    b = re.sub(r'\[\^([\w-]+)\]', lambda m: ' FOOT ' + footnotes.get(m[1], 'MISSING') + ' ENDFOOT ', b)
    b = re.sub(r'^:::\{figure\}.*$|^:name:.*$|^:align:.*$|^:::$|^:label:.*$', '', b, flags=re.M)
    b = re.sub(r'```\{math\}(.*?)```', lambda m: book_math(m[1], raw_used), b, flags=re.S)
    b = b.replace('```', '')
    b = re.sub(r'\{math\}`([^`]*)`', lambda m: book_math(m[1], raw_used), b)
    b = re.sub(r'\{eq\}`([^`]*)`', lambda m: 'EQ' + strip_label(m[1]), b)
    b = re.sub(r'\{numref\}`([^`]*)`', lambda m: 'FIGREF' + strip_label(m[1]), b)
    b = re.sub(r'\{cite:([tp])\}`([^`]*)`', lambda m: 'CITE' + m[1].upper() + m[2], b)
    b = re.sub(r'^\([A-Za-z:-]+\)=$', '', b, flags=re.M)
    b = re.sub(r'^#+ ', '', b, flags=re.M)
    b = re.sub(r'\[([^\]]*)\]\((?:\\.|[^)\\])*\)', r'\1', b)
    return tokens(b)


def tokens(s):
    s = re.sub(r'\\(begin|end)\{(equation\*?|gathered|aligned)\}', '', s)
    s = s.replace('\\\n', ' ').replace('\\ ', ' ').replace('~', ' ').replace('``', '').replace("''", '')
    for mark in '"`*':
        s = s.replace(mark, '')
    s = s.replace('$', ' ').replace('&', ' ').replace('—', ' ').replace('−', '-')
    s = re.sub(r"(?<![A-Za-z])'|'(?![a-z])", '', s)
    s = s.replace('{', ' ').replace('}', ' ')
    return re.findall(r'\\[A-Za-z]+|\\\\|[A-Za-z]+|\d+(?:\.\d+)?|\S', s)


def compare_words(hand, book, accepted, problems, what='Wording'):
    """Report differing words that no entry of `accepted` explains; return the entries that matched."""
    matched = set()
    ops = difflib.SequenceMatcher(None, hand, book, autojunk=False).get_opcodes()
    for tag, i1, i2, j1, j2 in ops:
        if tag == 'equal':
            continue
        h, b = ' '.join(hand[i1:i2]), ' '.join(book[j1:j2])
        near = ' '.join(hand[max(0, i1 - 9):i1])
        for entry in accepted:
            if (h, b) == (entry[1], entry[2]) and near.endswith(entry[0]):
                matched.add(entry)
                break
        else:
            problems.append(f'{what}, after "... {near}":\n    book:    {b[:600]}\n    handout: {h[:600]}')
    return matched


def align_notes(hand, book, least=0.4):
    """Pair the handout's margin notes with the chapter's by their words, keeping both orders.

    Returns (i, j) pairs: j None for a note only in the handout, i None for one only in the book.
    Two notes pair only if difflib finds them at least `least` alike, so one note added or removed
    on either side is reported as that one note, and the notes after it still pair with their own."""
    def alike(a, b):
        return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()

    n, m = len(hand), len(book)
    best = [[0.0] * (m + 1) for _ in range(n + 1)]  # best[i][j]: the most likeness pairing hand[i:] with book[j:]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            r = alike(hand[i], book[j])
            best[i][j] = max(best[i + 1][j], best[i][j + 1], r + best[i + 1][j + 1] if r >= least else 0.0)
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        r = alike(hand[i], book[j])
        if r >= least and best[i][j] == r + best[i + 1][j + 1]:
            pairs.append((i, j))
            i, j = i + 1, j + 1
        elif best[i][j] == best[i + 1][j]:
            pairs.append((i, None))
            i += 1
        else:
            pairs.append((None, j))
            j += 1
    return pairs + [(k, None) for k in range(i, n)] + [(None, k) for k in range(j, m)]


def link_macros():
    """The addresses the handout names with macros in @local/dir-paths.tex, such as \\NotebookColab."""
    text = open(os.path.join(HERE, '@local', 'dir-paths.tex'), encoding='utf8').read()
    return dict(re.findall(r'^\\providecommand\{\\(\w+)\}\{([^}\\]*)\}', text, re.M))


def compare_marks(plain, md, problems, links_used):
    """Equation labels, citations and external links: `plain` is handout source, `md` the book page."""
    h_labels = {strip_label(x) for x in re.findall(r'\\label\{(eq:[^}]*)\}', plain)}
    b_labels = {strip_label(x) for x in re.findall(r'^\s*:label:\s*(eq:\S+)', md, re.M)}
    for x in sorted(b_labels - h_labels):
        problems.append(f'Equation label only in the book: {x}')
    for x in sorted(h_labels - b_labels):
        problems.append(f'Equation label only in the handout: {x}')

    h_cites = {k.strip() for g in re.findall(r'\\cite[tp]?\{([^}]*)\}', plain) for k in g.split(',')}
    b_cites = {k.strip() for g in re.findall(r'\{cite:[tp]\}`([^`]*)`', md) for k in g.split(',')}
    for k in sorted(b_cites ^ h_cites):
        problems.append(f'Citation only in the {"book" if k in b_cites else "handout"}: {k}')

    macros = link_macros()
    h_links = {}
    for url, text in re.findall(r'\\href\{([^}]*)\}\{([^}]*)\}', plain):
        url = re.sub(r'^\\(\w+)$', lambda m: macros.get(m[1], m[0]), url)
        # LaTeX escapes % and # in \href; either side may percent-encode a character such as an en dash
        h_links.setdefault(text, []).append(urllib.parse.unquote(url.replace('\\%', '%').replace('\\#', '#')))
    b_links = {}
    # the chapter's own targets: equation labels, and (label)= lines before headings
    own = set(re.findall(r'^\s*:label:\s*(\S+)', md, re.M)) | set(re.findall(r'^\(([^()\s]+)\)=$', md, re.M))
    for text, url in re.findall(r'\[([^\]]*)\]\(((?:\\.|[^)\\])*)\)', md):
        url = urllib.parse.unquote(re.sub(r'\\([()])', r'\1', url))
        if url.startswith('#'):
            if url[1:] in own:
                continue  # a link within the chapter; the handout's \hyperref isn't compared
            if url not in CROSS_CHAPTER:
                problems.append(f'Link "{text}" to {url} in another chapter: give its address in CROSS_CHAPTER')
                continue
            url = CROSS_CHAPTER[url]
        b_links.setdefault(text, []).append(url)
    for text in sorted(set(b_links) | set(h_links)):
        b_urls, h_urls = b_links.get(text, []), h_links.get(text, [])
        if not b_urls or not h_urls:
            problems.append(f'Link only in the {"handout" if not b_urls else "book"}: {text}')
            continue
        for b_url, h_url in zip(b_urls, h_urls):
            if b_url == h_url or (not b_url.startswith('http') and h_url.endswith('/' + b_url)):
                continue
            entry = next((e for e in ACCEPTED_LINKS if (e[0], e[1]) == (b_url, h_url)), None)
            if entry:
                links_used.add(entry)
            else:
                problems.append(f'Link "{text}":\n    book:    {b_url}\n    handout: {h_url}')
        if len(b_urls) != len(h_urls):
            problems.append(f'Link "{text}": {len(b_urls)} in the book, {len(h_urls)} in the handout')


def compare_title(tex, md, problems):
    h_title = re.search(r'\\begin\{verbatimwrite\}\{\\jobname\.title\}\s*(.*?)\s*\\end\{verbatimwrite\}', tex, re.S)[1]
    b_title = re.search(r'^# (.*)$', md, re.M)[1].strip()
    if h_title != b_title:
        problems.append(f'Title:\n    book:    {b_title}\n    handout: {h_title}')


def compare_figures(ref, chapter, md, problems):
    """Each figure the chapter shows, against the PNG of the same name in the handout's Figures/."""
    for path in re.findall(r'^:::\{figure\}\s*(\S+)', md, re.M):
        full = path.lstrip('/') if path.startswith('/') else os.path.normpath(os.path.join(os.path.dirname(chapter), path))
        name = os.path.basename(path)
        book = fetch(ref, full)
        local = os.path.join(HERE, 'Figures', name)
        if book is None:
            problems.append(f'Figure {full} is not in the book at this ref')
        elif not os.path.exists(local):
            problems.append(f'Figure {name} is in the book ({full}) but not in Figures/')
        elif hashlib.sha256(book).digest() != hashlib.sha256(open(local, 'rb').read()).digest():
            problems.append(f'Figure {name} differs from the book\'s {full}')


def one_argument_same(a, b):
    """Whether two expanded definitions print the same once applied to one argument: \\bar and
    \\bar{#1} (which expands to \\bar#1) both put a bar over it. KaTeX macros may leave the argument implicit."""
    def bare(d):
        return d[:-2] if d.endswith('#1') and d.count('#') == 1 else d
    return bare(a) == bare(b)


def compare_symbols(md, tex_body, book_table, hand_table, problems):
    differing = set()
    hand_used = set(re.findall(r'\\([A-Za-z]+)', tex_body))
    for c in sorted(set(re.findall(r'\\([A-Za-z]+)', md)) & set(book_table)):
        h = BOOK_TO_HANDOUT.get(c, c)
        if h not in hand_used:
            continue
        b_def, h_def = expand('\\' + c, book_table), expand('\\' + h, hand_table)
        if b_def == h_def or one_argument_same(b_def, h_def):
            continue
        if h in ACCEPTED_SYMBOLS:
            differing.add(h)
        else:
            problems.append(f'Prints differently: the chapter\'s \\{c} prints {b_def}, the handout\'s \\{h} prints {h_def}')
    for h in sorted(set(ACCEPTED_SYMBOLS) - differing):
        problems.append(f'No longer needed in ACCEPTED_SYMBOLS: \\{h} now agrees with the book, or is unused')
    return len(differing)


def check_raw_letters(plain, problems):
    """Rule D: report each raw letter in the handout's math that no RAW_ALLOWED entry explains.

    `plain` is the handout without its comments, so its line numbers are the file's. The math is
    the contents of equation environments and of $...$. Returns how many letters each entry explained."""
    start = plain.index('\\begin{document}')
    body = plain[start:]
    envs = re.compile(r'\\begin\{(equation\*?)\}(.*?)\\end\{\1\}', re.S)
    spans = [(m.start(2), m[2]) for m in envs.finditer(body)]
    outside = envs.sub(lambda m: ' ' * len(m[0]), body)
    spans += [(m.start(1), m[1]) for m in re.finditer(r'(?<!\\)\$(.+?)(?<!\\)\$', outside, re.S)]

    def blank(m):
        return ' ' * len(m[0])

    explained, found = {}, []
    for offset, span in spans:
        # Blank out what isn't a letter of the math: environment names, labels and text, then every
        # command except a Greek letter.
        masked = re.sub(r'\\(?:begin|end|label|text|textrm|mbox|operatorname)\{[^{}]*\}', blank, span)
        masked = re.sub(r'\\[A-Za-z]+', lambda m: m[0] if m[0][1:] in GREEK else blank(m), masked)
        masked = re.sub(r'\\[^A-Za-z]', blank, masked)
        for m in re.finditer(r'\\[A-Za-z]+|[A-Za-z]', masked):
            allowed = next((p for p, _ in RAW_ALLOWED if re.compile(p).match(span, m.start())), None)
            if allowed:
                explained[allowed] = explained.get(allowed, 0) + 1
                continue
            line = plain.count('\n', 0, start + offset + m.start()) + 1
            near = ' '.join(span[max(0, m.start() - 30):m.end() + 30].split())
            found.append((line, f'Raw letter {m[0]} on line {line} (rule D: write the object with its macro): ... {near} ...'))
    problems.extend(text for _, text in sorted(found))
    return explained


def book_macro_table(ref):
    table = read_macros(need(ref, REGISTRY))
    table.update(read_macros(need(ref, 'notation/course-local-math.yml')))
    return table


def main():
    global BOOK_DIR, BOOK_GIT
    parser = argparse.ArgumentParser(description='Report where the handout has drifted from the book.')
    parser.add_argument('--ref', default='main', help='book branch or commit (default: main)')
    parser.add_argument('--book-git', help='a local clone of the book, read at --ref with git show')
    parser.add_argument('--book-dir', help='a local checkout of the book; files it lacks are read from GitHub at --ref')
    parser.add_argument('--handout', default=os.path.join(HERE, 'RamseyCassKoopmans.tex'), help='handout source')
    args = parser.parse_args()
    BOOK_DIR, BOOK_GIT = args.book_dir, args.book_git
    book_name = args.book_dir or (f'{args.book_git} at {args.ref}' if args.book_git else f'book ref {args.ref}')

    tex = open(args.handout, encoding='utf8').read()
    plain = re.sub(COMMENT, '', tex, flags=re.M)
    try:
        for chapter in CHAPTERS:
            data = fetch(args.ref, chapter)
            if data is not None:
                md = data.decode('utf8')
                break
        else:
            raise OSError(f'no chapter at {" or ".join(CHAPTERS)}')
        book_table = book_macro_table(args.ref)
    except OSError as err:  # includes urllib's errors
        print(f'Could not read the book at {args.ref}: {err}', file=sys.stderr)
        return 2

    problems = []
    used, raw_used = {}, {}
    compare_title(tex, md, problems)

    # The handout's text: the body from START to the bibliography.
    hand_text, hand_margins = take_margins(between(tex, START, '\\bibliographystyle'))
    book_text, book_margins = take_book_margins(book_rewrite(md[md.index(START):], used))
    matched = compare_words(handout_words(hand_text), book_words(book_text, raw_used), ACCEPTED_TEXT, problems)
    hand_notes = [handout_words(n) for n in hand_margins]
    book_notes = [book_words(n, raw_used) for n in book_margins]
    for i, j in align_notes(hand_notes, book_notes):
        if j is None:
            problems.append(f'Margin note only in the handout: "{" ".join(hand_notes[i][:12])} ..."')
        elif i is None:
            problems.append(f'Margin note only in the book: "{" ".join(book_notes[j][:12])} ..."')
        else:
            compare_words(hand_notes[i], book_notes[j], [], problems,
                          what=f'Margin note "{" ".join(book_notes[j][:6])} ..."')
    for entry in ACCEPTED_TEXT:
        if entry not in matched:
            problems.append(f'No longer needed in ACCEPTED_TEXT: {entry[1]!r} / {entry[2]!r}')
    for pattern, _, _ in ACCEPTED_REWRITES:
        if not used.get(pattern):
            problems.append(f'No longer needed in ACCEPTED_REWRITES: {pattern}')
    for letter, macro in RAW_IN_BOOK.items():
        if not raw_used.get(letter):
            problems.append(f'No longer needed in RAW_IN_BOOK: the book no longer writes a raw {letter} (\\{macro})')
    book_macros = set(re.findall(r'\\([A-Za-z]+)', md))
    for course, registry in BOOK_TO_HANDOUT.items():
        if course not in book_macros:
            problems.append(f'No longer needed in BOOK_TO_HANDOUT: the chapter no longer writes \\{course} (\\{registry})')

    links_used = set()
    compare_marks(plain, md, problems, links_used)
    for entry in ACCEPTED_LINKS:
        if entry not in links_used:
            problems.append(f'No longer needed in ACCEPTED_LINKS: {entry[1]}')
    compare_figures(args.ref, chapter, md, problems)
    book_nb = fetch(args.ref, os.path.join(os.path.dirname(chapter), NOTEBOOK))
    if book_nb is None:
        problems.append(f'The notebook {NOTEBOOK} is not beside the chapter at this ref')
    elif not os.path.exists(os.path.join(HERE, NOTEBOOK)):
        problems.append(f'The notebook {NOTEBOOK} is beside the chapter but not beside the handout')
    elif hashlib.sha256(book_nb).digest() != hashlib.sha256(open(os.path.join(HERE, NOTEBOOK), 'rb').read()).digest():
        problems.append(f"The notebook {NOTEBOOK} differs from the book's: copy it again, with ditto")

    hand_table = read_macros(open(os.path.join(HERE, REGISTRY), encoding='utf8').read())
    sty = open(os.path.join(HERE, LOCAL_STY), encoding='utf8').read()
    hand_table.update(dict(re.findall(r'^\\providecommand\{\\(\w+)\}\{(.*)\}\s*%', sty, re.M)))
    n_sym = compare_symbols(md, plain[plain.index('\\begin{document}'):], book_table, hand_table, problems)

    explained = check_raw_letters(plain, problems)
    for pattern, why in RAW_ALLOWED:
        if not explained.get(pattern):
            problems.append(f'No longer needed in RAW_ALLOWED: {why} ({pattern})')

    print(f'Compared the handout with the chapter {chapter} in {book_name}.')
    print(f'Accepted: {len(matched)} wording differences, {n_sym} symbols that render differently, '
          f'{sum(raw_used.values())} raw letters in the book that the handout writes with macros.')
    print(f'Raw letters in the handout\'s math: {sum(explained.values())}, each a date, Euler\'s e, a differential, '
          'a dummy or a throwaway letter (RAW_ALLOWED).')
    if not problems:
        print('Nothing to resolve.')
        return 0
    print(f'\n{len(problems)} to resolve. The book is the source of the wording: carry its version into the handout.')
    print('A symbol that prints differently is resolved by the side that departs from the registry, usually the')
    print("book's course macros. Only a difference Chris rules should stay goes in an ACCEPTED list.\n")
    for p in problems:
        print('- ' + p)
    return 1


if __name__ == '__main__':
    sys.exit(main())

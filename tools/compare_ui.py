"""Compare a Django screen against the React screen it replaced.

The React component is rendered with react-dom/server and the Django page is
fetched from a running server; both are reduced to a skeleton of tag, classes,
id, href and visible text, and the two are diffed. It catches a dropped class,
a changed link, a missing element or altered copy — the things that would make
the interface differ from the original.

Attributes that only exist to attach behaviour (`data-*`) are ignored, because
the React version attached its handlers in JSX instead.

Usage (with `python manage.py runserver 127.0.0.1:8000` already running):

    node --version                      # Node is needed for the React side
    python tools/compare_ui.py landing
    python tools/compare_ui.py dashboard --workspace workspace.json

`landing` needs nothing else. `dashboard` needs a workspace JSON file, which is
what `GET /api/workspace` returns for a signed-in account:

    curl -s -c jar -X POST http://127.0.0.1:8000/api/auth/login \\
        -H "Content-Type: application/json" \\
        -d '{"email":"you@example.com","password":"..."}' |
        python -c "import json,sys;print(json.dumps(json.load(sys.stdin)['workspace']))" > workspace.json
"""
import argparse
import difflib
import html
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCREENS = {
    'landing': {
        'url': '/',
        'start': '<div class="landing"',
        'end': None,
        'entry': (
            "import { renderToStaticMarkup } from 'react-dom/server';\n"
            "import { MemoryRouter } from 'react-router-dom';\n"
            "import Landing from './src/Landing.jsx';\n"
            "process.stdout.write(renderToStaticMarkup(<MemoryRouter><Landing /></MemoryRouter>));\n"
        ),
    },
    'dashboard': {
        'url': '/portal',
        'start': '<div class="dashboard-v2">',
        'end': '</main>',
        'needs_workspace': True,
        'entry': (
            "import { readFileSync } from 'node:fs';\n"
            "import { renderToStaticMarkup } from 'react-dom/server';\n"
            "import { MemoryRouter } from 'react-router-dom';\n"
            "import Dashboard from './src/components/Dashboard.jsx';\n"
            "const data = JSON.parse(readFileSync(process.argv[2], 'utf8'));\n"
            "process.stdout.write(renderToStaticMarkup("
            "<MemoryRouter><Dashboard data={data} /></MemoryRouter>));\n"
        ),
    },
}


def render_react(screen, workspace):
    """Bundle and run the React component through react-dom/server.

    The bundle is written under .data/, which is already ignored by git, so the
    tool does not depend on the system temp directory being writable.
    """
    work = ROOT / '.data' / 'ui-compare'
    work.mkdir(parents=True, exist_ok=True)
    entry = ROOT / 'ssr-compare-entry.jsx'
    bundle = work / 'bundle.cjs'
    entry.write_text(screen['entry'], encoding='utf-8')
    try:
        subprocess.run(
            ['npx', 'esbuild', entry.name, '--bundle', '--platform=node', '--format=cjs',
             '--jsx=automatic', '--loader:.css=empty', f'--outfile={bundle}', '--log-level=error'],
            cwd=ROOT, check=True, shell=sys.platform == 'win32',
        )
        command = ['node', str(bundle)]
        if workspace:
            command.append(str(Path(workspace).resolve()))
        # Decode as UTF-8: the markup carries the interface's own typography.
        result = subprocess.run(
            command, capture_output=True, text=True, encoding='utf-8', check=True
        )
        return result.stdout
    finally:
        entry.unlink(missing_ok=True)


def fetch_django(base, screen, cookie):
    request = urllib.request.Request(base.rstrip('/') + screen['url'])
    if cookie:
        request.add_header('Cookie', cookie)
    with urllib.request.urlopen(request) as response:
        page = response.read().decode('utf-8')
    start = page.index(screen['start'])
    end = page.index(screen['end']) if screen['end'] else page.rindex('</div>') + 6
    return page[start:end]


def skeleton(markup):
    markup = re.sub(r'<!--.*?-->', '', markup, flags=re.S)
    markup = re.sub(r'\sdata-[\w-]+(="[^"]*")?', '', markup)
    tokens = []
    for tag, attrs, text in re.findall(r'<(\w+)([^>]*)>([^<]*)', markup):
        parts = [tag]
        for pattern, prefix in (('class', '.'), ('id', '#'), ('href', 'href='), ('value', 'value=')):
            found = re.search(rf'{pattern}="([^"]*)"', attrs)
            if not found:
                continue
            value = found.group(1)
            parts.append(prefix + ('.'.join(sorted(value.split())) if pattern == 'class' else value))
        body = re.sub(r'\s+', ' ', html.unescape(text)).strip()
        if body:
            parts.append(f'"{body}"')
        tokens.append(' '.join(parts))
    return tokens


def main():
    # The skeletons contain the interface's own typography, which a Windows
    # console will not encode by default.
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('screen', choices=sorted(SCREENS))
    parser.add_argument('--base', default='http://127.0.0.1:8000')
    parser.add_argument('--workspace', help='Workspace JSON file, required for screens that need data.')
    parser.add_argument('--cookie', help='Cookie header for a signed-in request, e.g. "soundbridge_session=...".')
    options = parser.parse_args()

    screen = SCREENS[options.screen]
    if screen.get('needs_workspace') and not options.workspace:
        parser.error(f'{options.screen} needs --workspace')

    react = skeleton(render_react(screen, options.workspace))
    django_page = skeleton(fetch_django(options.base, screen, options.cookie))
    differences = [
        line
        for line in difflib.unified_diff(react, django_page, 'react', 'django', lineterm='', n=0)
        if line[:1] in '+-' and not line.startswith(('+++', '---'))
    ]
    print(f'react {len(react)} elements, django {len(django_page)} elements, {len(differences)} differences')
    for line in differences:
        print(' ', line)
    return 1 if differences else 0


if __name__ == '__main__':
    raise SystemExit(main())

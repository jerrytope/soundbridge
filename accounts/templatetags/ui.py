"""Template tags standing in for the small shared React components.

`icon` reproduces src/components/Icon.jsx byte for byte in its output, so the
existing CSS (which styles `svg` inside these elements) applies unchanged.
`money` reproduces the currency formatting used across the React screens.
"""
from decimal import Decimal

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

PATHS = {
    'home': 'M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
    'search': 'm21 21-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
    'people': 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8m6 10v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
    'briefcase': 'M3 7h18v14H3ZM8 7V3h8v4M3 12l9 3 9-3M12 12v5',
    'spark': 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4m-2-2h4',
    'wallet': 'M3 5h16v4H3V5Zm0 4v11h18V9Zm14 5h4',
    'calendar': 'M4 5h16v16H4ZM8 2v6m8-6v6M4 11h16m-12 5 2 2 5-5',
    'chart': 'M4 3v18h17M8 16v-5m5 5V7m5 9V4',
    'settings': 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2',
    'arrow': 'M5 12h14m-5-5 5 5-5 5',
    'up': 'M6 18 18 6M6 6h12v12',
    'plus': 'M12 5v14M5 12h14',
    'music': 'M9 18V5l12-3v13M9 9l12-3M9 18a3 3 0 1 1-3-3h3m12 0a3 3 0 1 1-3-3h3',
    'menu': 'M4 6h16M4 12h16M4 18h16',
    'close': 'm6 6 12 12M6 18 18 6',
    'check': 'm5 12 4 4L19 6',
    'info': 'M12 11v6m0-10v.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
}

SYMBOLS = {'USD': '$', 'NGN': '₦', 'EUR': '€', 'GBP': '£'}


@register.simple_tag
def icon(name, size=20):
    path = PATHS.get(name, PATHS['spark'])
    return format_html(
        '<svg width="{}" height="{}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="{}"/></svg>',
        size, size, mark_safe(path),
    )


@register.filter
def money(amount, currency='USD'):
    """Match Intl.NumberFormat('en', {style:'currency'}) as the React screens used it."""
    if amount in (None, ''):
        return ''
    value = Decimal(str(amount))
    sign = '-' if value < 0 else ''
    return f'{sign}{SYMBOLS.get(currency, "")}{abs(value):,.2f}'


@register.filter
def thousands(value):
    try:
        return f'{int(value):,}'
    except (TypeError, ValueError):
        return value


@register.filter
def plain(value):
    """Print a decimal without trailing zeros, as JavaScript printed the number."""
    if value in (None, ''):
        return ''
    number = Decimal(str(value)).normalize()
    return format(number, 'f')


@register.filter
def initials(name):
    return (name or 'SB')[:2].upper()


@register.simple_tag(takes_context=True)
def active(context, path):
    """`aria-current` for the current nav item, matching NavLink behaviour."""
    return 'page' if context['request'].path == '/' + path else ''


@register.simple_tag
def agent_field(agent_id, field):
    """Look up one field of a specialist by id, as getAgent(id) did in the studio."""
    from aiteam.agents import get_agent

    agent = get_agent(agent_id)
    return agent.get(field, '') if agent else ''


@register.filter
def first_line(text):
    return (text or '').splitlines()[0] if text else ''


@register.filter
def length_of(value):
    return len(value or '')

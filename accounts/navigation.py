"""Sidebar navigation, ported verbatim from the `navigation` array and
`iconNames` list in src/main.jsx so the shell renders the same nine items in the
same order, with the same icons, labels and section captions.
"""

NAVIGATION = [
    {"path": "portal", "icon": "home", "label": "Overview", "caption": "YOUR NETWORK"},
    {"path": "discover", "icon": "search", "label": "Discover", "caption": ""},
    {
        "path": "collaborations",
        "icon": "people",
        "label": "Collaborations",
        "caption": "",
    },
    {"path": "connections", "icon": "people", "label": "Connections", "caption": ""},
    {
        "path": "notifications",
        "icon": "calendar",
        "label": "Notifications",
        "caption": "",
    },
    {
        "path": "opportunities",
        "icon": "briefcase",
        "label": "Opportunities",
        "caption": "",
    },
    {
        "path": "assistants",
        "icon": "spark",
        "label": "AI Team",
        "caption": "YOUR CREATIVE TOOLKIT",
    },
    {"path": "royalties", "icon": "wallet", "label": "Royalties", "caption": ""},
    {
        "path": "release-planner",
        "icon": "calendar",
        "label": "Release Planner",
        "caption": "",
    },
    {"path": "analytics", "icon": "chart", "label": "Analytics", "caption": ""},
    {"path": "music-search", "icon": "music", "label": "Music Search", "caption": ""},
]

# Pages reachable from the workspace search dialog, matching the React shell.
SEARCHABLE = NAVIGATION + [
    {"path": "royalty-calculator", "icon": "wallet", "label": "Royalty Calculator"},
    {"path": "royalty-upload", "icon": "wallet", "label": "Statement Upload"},
    {"path": "membership", "icon": "spark", "label": "Membership"},
    {"path": "settings", "icon": "settings", "label": "Settings & profile"},
]

"""Load the sample creator and opportunity directories.

The data is ported from src/creators.js and the `opportunities` list in
src/main.jsx so Discover and Opportunities render the same cards they render
today, now from the database. These are illustrative samples, not real
accounts or live listings, and both screens say so on the page.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from network.models import Creator, Opportunity

CREATORS = [
    (
        1,
        "Kairo Ade",
        "KA",
        "Producer",
        ["Afrobeats", "Amapiano"],
        "Nigeria",
        "Lagos",
        96,
        "Producer focused on rhythm-led African pop, artist development and collaborative recording sessions.",
    ),
    (
        2,
        "Ama Serwaa",
        "AS",
        "Songwriter",
        ["R&B", "Afrobeats"],
        "Ghana",
        "Accra",
        93,
        "Melody-first songwriter creating emotional records for independent artists and global audiences.",
    ),
    (
        3,
        "Thabo Mokoena",
        "TM",
        "Audio Engineer",
        ["Amapiano", "Hip-Hop"],
        "South Africa",
        "Johannesburg",
        91,
        "Mix and mastering engineer helping artists achieve clean, energetic and commercially competitive records.",
    ),
    (
        4,
        "Jordan Blake",
        "JB",
        "Artist",
        ["Alternative", "R&B"],
        "United Kingdom",
        "London",
        89,
        "Independent recording artist exploring alternative R&B, electronic textures and cross-cultural collaborations.",
    ),
    (
        5,
        "Nneka Okoro",
        "NO",
        "Music Manager",
        ["Afrobeats", "Pop"],
        "Nigeria",
        "Abuja",
        87,
        "Artist manager supporting release strategy, partnerships, career planning and sustainable audience growth.",
    ),
    (
        6,
        "Maya Robinson",
        "MR",
        "Videographer",
        ["Hip-Hop", "Pop"],
        "United States",
        "Atlanta",
        85,
        "Music filmmaker and visual director creating performance videos, campaign content and artist documentaries.",
    ),
    (
        7,
        "David Mensah",
        "DM",
        "Producer",
        ["Gospel", "Afrobeats"],
        "Ghana",
        "Kumasi",
        83,
        "Producer and instrumentalist creating uplifting contemporary gospel and Afrobeats records.",
    ),
    (
        8,
        "Zara Bello",
        "ZB",
        "Artist",
        ["Pop", "Afrobeats"],
        "Nigeria",
        "Lagos",
        81,
        "Pop artist interested in international collaborations, live performance and fresh African sounds.",
    ),
    (
        9,
        "Lerato Khumalo",
        "LK",
        "Songwriter",
        ["Amapiano", "Pop"],
        "South Africa",
        "Pretoria",
        79,
        "Topline songwriter developing memorable hooks and vocal ideas for dance and pop releases.",
    ),
]

OPPORTUNITIES = [
    (
        "sync",
        "Original music for an independent film",
        "Sync",
        "Remote",
        "Prepare a pitch with two atmospheric instrumental tracks and a short licensing overview.",
    ),
    (
        "writing",
        "Afrobeats songwriting session",
        "Collaboration",
        "Lagos",
        "Develop melodies and toplines for a collaborative writing session.",
    ),
    (
        "live",
        "Independent artist showcase",
        "Live",
        "Accra",
        "Prepare a short artist introduction, live footage and a proposed setlist.",
    ),
]


class Command(BaseCommand):
    help = "Load the sample creator and opportunity directories."

    def handle(self, *args, **options):
        if settings.PUBLIC_ORIGIN:
            raise CommandError("Demo seeding is disabled on public deployments.")
        for (
            external_id,
            name,
            initials,
            role,
            genres,
            country,
            city,
            match,
            bio,
        ) in CREATORS:
            Creator.objects.update_or_create(
                external_id=external_id,
                defaults={
                    "name": name,
                    "initials": initials,
                    "role": role,
                    "genres": genres,
                    "country": country,
                    "city": city,
                    "match_score": match,
                    "bio": bio,
                },
            )
        for slug, title, kind, city, description in OPPORTUNITIES:
            Opportunity.objects.update_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "type": kind,
                    "city": city,
                    "description": description,
                    "verification_state": Opportunity.UNVERIFIED,
                    "is_sample": True,
                },
            )
        self.stdout.write(
            f"Seeded {Creator.objects.count()} sample creators and {Opportunity.objects.count()} sample opportunities."
        )

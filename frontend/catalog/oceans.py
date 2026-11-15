"""Oceans tab configuration (kept separate from Atmosphere).
To add an ocean variable: add an Option to an existing Group, or a new Group
with its CMR short name and version. Nothing else needs to change."""
from .base import Group, Option

OCEANS = (
    Group(
        key="skin_temp", label="Skin temperature (marine regions)",
        short_name="M2TMNXOCN", version="5.12.4",
        product="MERRA-2 monthly mean ocean surface diagnostics",
        temporal="monthly", files_per_month=1,
        options=(
            Option("open_water", "Open water skin temperature", hints=("skin", "water")),
            Option("sea_ice", "Sea ice skin temperature", hints=("skin", "ice")),
        ),
        note="Sea ice skin temperature is only defined where sea ice exists, so many grid points are empty.",
    ),
)

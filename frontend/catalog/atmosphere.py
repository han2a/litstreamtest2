"""Atmosphere tab configuration (kept separate from Oceans)."""
from .base import Group, Option

_GV = "https://giovanni.gsfc.nasa.gov/giovanni/doc/glossary/Giovanni_Variable_Definitions_Glossary.html"
CONUS = (25.0, 53.0, -125.0, -67.0)      # NLDAS domain

AIRS_LEVELS = (1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150,
               100, 70, 50, 30, 20, 15, 10, 7, 5, 3, 2, 1.5, 1)

ATMOSPHERE = (
    Group(
        key="aerosol", label="Aerosols and atmospheric diagnostics",
        short_name="M2T1NXAER", version="5.12.4",
        product="MERRA-2 hourly time-averaged aerosol diagnostics",
        temporal="hourly", files_per_month=30.4,
        options=(Option("so2cmass", "SO2 Column Mass Density (ensemble), time average",
                        variable="SO2CMASS"),),
        source_url="https://disc.gsfc.nasa.gov/datacollection/M2T1NXAER_5.12.4.html",
        glossary_url=_GV + "#h.d7f0kiqvu3gj",
    ),
    Group(
        key="pressure", label="Atmospheric pressure",
        short_name="M2T1NXSLV", version="5.12.4",
        product="MERRA-2 hourly time-averaged single-level diagnostics",
        temporal="hourly", files_per_month=30.4,
        options=(Option("slp", "Sea Level Pressure, time average", variable="SLP"),),
        source_url="https://disc.gsfc.nasa.gov/datacollection/M2T1NXSLV_5.12.4.html",
        glossary_url=_GV + "#h.xf95hnwiztju",
    ),
    Group(
        key="geopotential", label="Geopotential height",
        short_name="M2TMNXSLV", version="5.12.4",
        product="MERRA-2 monthly mean, time-averaged single-level diagnostics",
        temporal="monthly", files_per_month=1,
        options=(
            Option("h1000", "Geopotential Height at 1000 hPa", variable="H1000"),
            Option("h850", "Geopotential Height at 850 hPa", variable="H850"),
            Option("h500", "Geopotential Height at 500 hPa", variable="H500"),
            Option("h250", "Geopotential Height at 250 hPa", variable="H250"),
        ),
        source_url="https://disc.gsfc.nasa.gov/datacollection/M2TMNXSLV_5.12.4.html",
        glossary_url=_GV + "#h.v30nm8airhl4",
    ),
    Group(
        key="air_temperature", label="Air temperature (AIRS)",
        short_name="AIRS3STD", version="006",
        product="Aqua AIRS Level 3 Daily Standard Physical Retrieval (AIRS-only)",
        temporal="daily", files_per_month=30.4,
        options=(
            Option("temp_day", "Air Temperature, daytime / ascending",
                   variable="Temperature_A"),
            # night variable name not given in the brief: matched against the
            # file's variable list (never assumed to exist).
            Option("temp_night", "Air Temperature, nighttime / descending",
                   hints=("Temperature_D",)),
        ),
        levels=AIRS_LEVELS, default_levels=(500,),
        note="Vertical coverage 1000 hPa to 1 hPa. The backend uses the nearest level in the file.",
        source_url="http://disc.gsfc.nasa.gov/datacollection/AIRS3STD_006.html",
        glossary_url=_GV + "#h.gy9u3l6adp3c",
    ),
    Group(
        key="wind10m", label="10-meter wind components",
        short_name="NLDAS_FORA0125_M", version="2.0",
        product="NLDAS Primary Forcing Data, monthly, 0.125 x 0.125 deg",
        temporal="monthly", files_per_month=1,
        options=(
            Option("wind_e", "Zonal Wind (10 m above ground)", hints=("zonal",)),
            Option("wind_n", "Meridional Wind (10 m above ground)", hints=("meridional",)),
            Option("wind_speed", "Wind speed (derived from both components)",
                   components=("wind_e", "wind_n"),
                   description="Computed by the backend as sqrt(u^2 + v^2). Direction is not computed."),
        ),
        note="NLDAS covers the contiguous US only.", coverage=CONUS,
        source_url="https://disc.gsfc.nasa.gov/datasets/NLDAS_FORA0125_M_2.0/summary",
        glossary_url=_GV + "#h.19w7bquxg627",
    ),
    Group(
        key="precip", label="Precipitation",
        short_name="NLDAS_FORA0125_H", version="2.0",
        product="NLDAS Primary Forcing Data, hourly, 0.125 x 0.125 deg",
        temporal="hourly", files_per_month=730.5,
        options=(Option("precip_total", "Total precipitation", hints=("precip",)),),
        note=("NLDAS covers the contiguous US only. The files are hourly, so the "
              "backend's 1500-file cap allows only about two months per product. "
              "Hourly values are averaged to monthly means (a mean rate, not a monthly total)."),
        coverage=CONUS,
    ),
)

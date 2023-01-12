#!/usr/bin/env python

import datetime as _dt
import os as _os
from pathlib import Path
import pandas as _pd

# Ensure that both source code and bundled data are correctly found
_original_wd = _os.getcwd()
_os.chdir(_os.path.dirname(_os.path.abspath(__file__)))

# Environment needs to be set up before importing the bidding infrastructure
_os.environ["LOCATION_LAT"] = "52.1051"
_os.environ["LOCATION_LON"] = "-3.6680"

from src.bidding import slimjab_bidder as _slimjab_bidder, util as _util
from src.onsite import onsite as _onsite
from src.pricing import pricing as _pricing
from src.solar import solar as _solar
from src.wind import wind as _wind

# Load our mocked/cached API data
_dayahead = _pd.read_csv(Path(__file__).absolute().parent.parent / "agile_snails_coding_challenge/dummy_data/market_index.csv")
_weather = _pd.read_csv(Path(__file__).absolute().parent.parent / "agile_snails_coding_challenge/dummy_data/weather_mock.csv")

_os.chdir(_original_wd)


def get_price_and_quantity(date: _dt.date) -> _pd.DataFrame:
    """Get the price and quantity bid for the day following `date`.

    Arguments:

    date (datetime.date): The date the bids would be placed; i.e. the
    day before the day for which the bids are prices for.

    Returns:

    result (pd.DataFrame): A Pandas DataFrame indexed by the ID of the hour,
    with columns for `volume` and `price`, where the latter is negative for
    importing and positive for exporting.
    """
    start = _dt.datetime.combine(date, _dt.time(23))
    times = [(start + _dt.timedelta(minutes=30) * i).isoformat() for i in range(48)]

    # Patch get_output_template to use the date we specify rather than "today"
    _slimjab_bidder.get_output_template = lambda: _util.get_output_template(
        dt=(start + _dt.timedelta(days=1)).date()
    )

    # Get needed data from the mocked APIs
    # Previously managed by Node Red
    forecast = _weather[
        (_weather.time > start.isoformat())
        & (_weather.time < (start + _dt.timedelta(hours=26)).isoformat())
    ].copy()
    bare_prices = (
        _dayahead[_dayahead.date == start.date().isoformat()]
        .sort_values(by=["period"])
        .price.to_numpy()
    )

    # Reformat imported data to match expected format for
    # pricing.predict_price_tomorrow
    current_price_df = _pd.DataFrame(
        {
            "date": [
                (start + _dt.timedelta(days=-2, hours=1)).isoformat() for _ in range(24)
            ],
            "period": list(range(24)),
            "price": bare_prices,
        }
    )

    # Pass data into the prediction routines
    # If errors occur, give up as likely some mocked data are missing
    # Previously managed by calls from Node Red into the server,
    # which call these functions
    try:
        consumed_onsite = _onsite.get_energy_demand(forecast, start_time=start)
        generated_solar = _solar.get_solar_prediction(forecast)
        generated_wind = _wind.get_wind_prediction(forecast)
        price_df = _pricing.predict_price_tomorrow(current_price_df)
    except Exception:
        raise ValueError(f"Unable to predict for {date}.")

    # Reformat predictions to match expected format for
    # slimjab_bidder.slimjab_bidder
    # Previously done by an SQL query
    net_export = (
        generated_wind.WindPower
        + generated_solar.SolarPower
        - consumed_onsite["Total demand"]
    ) * 1000
    power_df = _pd.DataFrame({"time": times, "NetPower": net_export})

    # Construct bid, previously done by call from Node Red into the server
    # If errors occur, give up as likely some mocked data are missing.
    try:
        result = _slimjab_bidder.slimjab_bidder(price=price_df, power=power_df)
    except:
        raise ValueError("Unable to predict for {date}.")

    # Reformat bid for simplicity of output
    result["quantity"] = result.volume * (-1) ** (result.type == "BUY")
    result.set_index("hour_ID", inplace=True)
    result = result.loc[:, ["quantity", "price"]]
    return result


if __name__ == "__main__":
    DATE = _dt.date(2022, 1, 2)
    print(get_price_and_quantity(DATE))

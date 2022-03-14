# -*- coding: utf-8 -*-
"""Functions to obtain forecast data from the Met Office API.

Based on SLIMjab
"""

import os
from requests import Response
from dotenv import load_dotenv
from datetime import datetime
import numpy as np
import requests
import pandas as pd

DATETIME_FORMAT = "%Y-%m-%dT%H:%MZ"


def get_forecast()->pd.DataFrame:
    load_dotenv(dotenv_path="composer/.env")
    METOFFICEAPI = os.environ.get("MET_API_KEY")
    METOFFICESECRET = os.environ.get("MET_SECRET_KEY")
    lat = os.environ.get("LOCATION_LAT")
    lon = os.environ.get("LOCATION_LON")
    noParamNames = True

    headers = {
        "X-IBM-Client-Id": METOFFICEAPI,
        "X-IBM-Client-Secret": METOFFICESECRET,
        "accept": "application/json"
    }

    url = "https://rgw.5878-e94b1c46.eu-gb.apiconnect.appdomain.cloud"
    url += "/metoffice/production/v0/forecasts/point/hourly"
    url +=  "?excludeParameterMetadata={}".format(noParamNames)
    url +=  "&includeLocationName=true"
    url +=  "&latitude={}&longitude={}".format(lat,lon)

    response = requests.get(url, headers=headers)

    assert response.status_code == 200  # check response is good

    forecast = response.json()
    forecast = forecast["features"][0]["properties"]["timeSeries"]

    return cut_frame(pd.DataFrame(forecast))

def cut_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Cut a dataframe on the DateTime column into intervals of 23:00 - 23:00.

    Cuts a given Pandas DataFrame via a string DateTime column into an interval
    of 23:00 - 23:00.

    Args:
        frame (pd.DataFrame): Pandas dataframe to be cut. Must contain a DataTime
            column.

    Returns: pd.DataFrame: Pandas dataframe cut into intervals of 23:00 - 23:00
    """
    hrs = []
    for i in range(len(frame["time"])):
        hrs.append(datetime.strptime(frame["time"][i], DATETIME_FORMAT).hour)
    idxs = np.where(np.asarray(hrs) == 23)[0]
    start = idxs[0]
    end = idxs[1] 
    return frame.truncate(start, end)

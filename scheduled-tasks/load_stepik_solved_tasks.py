#https://stepik.org/api/docs/#!/submissions/

import json
import os

from os.path import isdir, exists, join, getsize

import re
import requests
import sys
from requests.auth import HTTPBasicAuth
from itertools import count
from datetime import datetime
import dateutil.parser
from dateutil.tz import tzutc
from collections import namedtuple, defaultdict
from itertools import combinations
from tqdm import tqdm_notebook as tqdm
import lzma


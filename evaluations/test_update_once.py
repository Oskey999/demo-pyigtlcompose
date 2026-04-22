#!/usr/bin/env python3
"""Test the update_pending_rows function once without watch mode"""

import sys
sys.path.insert(0, '.')
from update import ResultsCSVUpdater

updater = ResultsCSVUpdater('./results.csv')
updater.ensure_csv_initialized()
updater.update_pending_rows()

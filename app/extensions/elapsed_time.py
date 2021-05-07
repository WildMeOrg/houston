# -*- coding: utf-8 -*-
# Simple timer class for measuring elapsed time in a debug friendly manner

import time


class ElapsedTime:
    def __init__(self):
        self._start_time = time.perf_counter()

    def elapsed(self):
        elapsed_time = time.perf_counter() - self._start_time
        return f'{elapsed_time:.2f}'

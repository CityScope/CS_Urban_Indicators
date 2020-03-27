#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 26 15:07:25 2020

@author: doorleyr
"""

from toolbox import Indicator
import random

class RandomIndicator(Indicator):
    def setup(self):
        pass
    
    def return_indicator(self, geogrid_data):
        result=[{'name': 'Social Wellbeing', 'value': random.random()},
                {'name': 'Environmental Impact', 'value': random.random()},
                {'name': 'Mobility Impact', 'value': random.random()},
                {'name': 'Economic Impact', 'value': random.random()},
                {'name': 'Innovation Potential', 'value': random.random()}]
        return result
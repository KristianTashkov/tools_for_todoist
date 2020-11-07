"""
Copyright (C) 2020-2020 Kristian Tashkov <kristian.tashkov@gmail.com>

This file is part of "Tools for Todoist".

"Tools for Todoist" is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

"Tools for Todoist" is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
more details.

You should have received a copy of the GNU General Public License along
with this program. If not, see <http://www.gnu.org/licenses/>.
"""
import re


def _parse_byday(byday):
    if byday is None:
        return ''

    def _parse_day(day):
        match = re.match(r'(\d)?([A-Z]{2})', day)
        count_map = {None: '', '1': 'first ', '2': 'second ', '3': 'third ', '4': 'fourth '}
        day_map = {
            'MO': 'Mon',
            'TU': 'Tue',
            'WE': 'Wed',
            'TH': 'Thu',
            'FR': 'Fri',
            'SA': 'Sat',
            'SU': 'Sun',
        }
        count, day = match.groups()
        return f'{count_map[count]}{day_map[day]}'

    return ', '.join([_parse_day(day) for day in byday.split(',')])


def _daily_rrule(components, ending_condition):
    count = int(components.get('INTERVAL', 1))
    if count == 1:
        recurrence_string = 'day'
    elif count == 2:
        recurrence_string = 'other day'
    else:
        recurrence_string = f'{count} days'
    return f'every {recurrence_string}{ending_condition}'


def _weekly_rrule(components, ending_condition, byday):
    count = int(components.get('INTERVAL', 1))
    if count == 1:
        recurrence_string = byday
    elif count == 2:
        recurrence_string = f'other {byday}'
    elif count == 3:
        recurrence_string = f'3rd {byday}'
    elif count <= 5:
        recurrence_string = f'{count}th {byday}'
    else:
        recurrence_string = f'{count} weeks'
    return f'every {recurrence_string}{ending_condition}'


def _monthly_rrule(components, ending_condition, byday):
    count = int(components.get('INTERVAL', 1))
    if count == 1 or (count > 1 and byday):
        recurrence_string = byday if byday else 'month'
    elif count == 2:
        recurrence_string = 'other month'
    elif count == 3:
        recurrence_string = '3rd month'
    else:
        recurrence_string = f'{count} months'
    return f'every {recurrence_string}{ending_condition}'


def _yearly_rrule(components, ending_condition):
    count = int(components.get('INTERVAL', 1))
    if count == 1:
        recurrence_string = 'year'
    else:
        recurrence_string = f'{count} years'
    return f'every {recurrence_string}{ending_condition}'


def rrule_to_string(rrule):
    components = rrule[len('RRULE:') :].split(';')
    components = [component.split('=') for component in components]
    components = {key: value for key, value in components}
    ending_condition = ''
    if int(components.get('COUNT', 0)) > 1:
        ending_condition = f' for {components["COUNT"]} times'
    elif components.get('UNTIL'):
        ending_condition = f' until {components["UNTIL"]}'
    byday = _parse_byday(components.get('BYDAY'))

    freq = components['FREQ']
    if freq == 'DAILY':
        return _daily_rrule(components, ending_condition)
    elif freq == 'WEEKLY':
        return _weekly_rrule(components, ending_condition, byday)
    elif freq == 'MONTHLY':
        return _monthly_rrule(components, ending_condition, byday)
    else:
        return _yearly_rrule(components, ending_condition)

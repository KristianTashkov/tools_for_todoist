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

import json
import logging
from datetime import datetime, timedelta, timezone

import requests
from dateutil.tz import gettz
from openai import OpenAI

from tools_for_todoist.storage import get_storage

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN_KEY = 'logging.telegram_bot_token'
TELEGRAM_CHAT_ID_KEY = 'logging.telegram_chat_id'
OPENAI_API_KEY = 'telegram_bot.openai_api_key'
OPENAI_MODEL = 'telegram_bot.openai_model'
BOT_MEMORY_KEY = 'telegram_bot.memory'

TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'list_tasks',
            'description': (
                'List active Todoist tasks. Can filter by project name, label, or whether '
                'they have a due date. Returns task id, content, due date, labels, and priority.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'project_name': {
                        'type': 'string',
                        'description': 'Filter by project name (exact match)',
                    },
                    'label': {
                        'type': 'string',
                        'description': 'Filter by label name',
                    },
                    'with_due_date_only': {
                        'type': 'boolean',
                        'description': 'If true, only return tasks that have a due date',
                    },
                    'include_completed': {
                        'type': 'boolean',
                        'description': (
                            'If true, include completed tasks. Useful for shopping lists '
                            'to find items that can be uncompleted instead of re-created.'
                        ),
                    },
                },
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'reschedule_task',
            'description': (
                'Reschedule a task to a new due date. For recurring tasks, this only changes '
                'the next occurrence date without modifying the recurrence rule. '
                'Use a date or datetime string (e.g. "2026-03-15", "2026-03-15T10:00:00").'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'task_id': {
                        'type': 'string',
                        'description': 'The ID of the task to reschedule',
                    },
                    'due_date': {
                        'type': 'string',
                        'description': (
                            'The new due date in ISO format. Use YYYY-MM-DD for all-day tasks '
                            'or YYYY-MM-DDTHH:MM:SS for tasks with a specific time. '
                            'Times should be in the user\'s timezone.'
                        ),
                    },
                },
                'required': ['task_id', 'due_date'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'complete_task',
            'description': 'Mark a task as completed.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'task_id': {
                        'type': 'string',
                        'description': 'The ID of the task to complete',
                    },
                },
                'required': ['task_id'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'uncomplete_task',
            'description': (
                'Uncomplete a previously completed task, making it active again. '
                'Use for shopping lists to reactivate items instead of creating duplicates.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'task_id': {
                        'type': 'string',
                        'description': 'The ID of the completed task to uncomplete',
                    },
                },
                'required': ['task_id'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'update_task_priority',
            'description': ('Update the priority of a task. Priority 1 is normal, 4 is urgent.'),
            'parameters': {
                'type': 'object',
                'properties': {
                    'task_id': {
                        'type': 'string',
                        'description': 'The ID of the task to update',
                    },
                    'priority': {
                        'type': 'integer',
                        'description': 'Priority level: 1 (normal) to 4 (urgent)',
                        'enum': [1, 2, 3, 4],
                    },
                },
                'required': ['task_id', 'priority'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'add_task',
            'description': 'Create a new task in Todoist.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'content': {
                        'type': 'string',
                        'description': 'The text/title of the task',
                    },
                    'project_name': {
                        'type': 'string',
                        'description': 'Project to add the task to. Defaults to Inbox.',
                    },
                    'section_name': {
                        'type': 'string',
                        'description': (
                            'Section within the project to add the task to. '
                            'Use list_sections to find available sections.'
                        ),
                    },
                    'due_string': {
                        'type': 'string',
                        'description': 'Natural language due date (e.g. "tomorrow at 10:00")',
                    },
                    'priority': {
                        'type': 'integer',
                        'description': 'Priority: 1 (normal) to 4 (urgent)',
                        'enum': [1, 2, 3, 4],
                    },
                    'labels': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'List of label names to assign',
                    },
                },
                'required': ['content'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'add_label_to_task',
            'description': 'Add a label to an existing task.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'task_id': {
                        'type': 'string',
                        'description': 'The ID of the task',
                    },
                    'label': {
                        'type': 'string',
                        'description': 'The label name to add',
                    },
                },
                'required': ['task_id', 'label'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'remove_label_from_task',
            'description': 'Remove a label from an existing task.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'task_id': {
                        'type': 'string',
                        'description': 'The ID of the task',
                    },
                    'label': {
                        'type': 'string',
                        'description': 'The label name to remove',
                    },
                },
                'required': ['task_id', 'label'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'save_memory',
            'description': (
                'Save a note to persistent long-term memory. Use this to remember user '
                'preferences, recurring instructions, important context, or anything the user '
                'asks you to remember. Each memory has a unique key (overwriting if it exists).'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'key': {
                        'type': 'string',
                        'description': (
                            'A short descriptive key for this memory '
                            '(e.g. "preferred_meeting_time", "project_priorities")'
                        ),
                    },
                    'value': {
                        'type': 'string',
                        'description': 'The content to remember',
                    },
                },
                'required': ['key', 'value'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'delete_memory',
            'description': 'Delete a specific entry from persistent long-term memory.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'key': {
                        'type': 'string',
                        'description': 'The key of the memory to delete',
                    },
                },
                'required': ['key'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'assign_task',
            'description': (
                'Assign a task to a collaborator by name, or unassign by passing null. '
                'Use list_collaborators first if you need to find the right person.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'task_id': {
                        'type': 'string',
                        'description': 'The ID of the task',
                    },
                    'person_name': {
                        'type': ['string', 'null'],
                        'description': (
                            'Name of the person to assign to (partial match supported), '
                            'or null to unassign'
                        ),
                    },
                },
                'required': ['task_id', 'person_name'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'list_collaborators',
            'description': 'List all collaborators (people) available for task assignment.',
            'parameters': {'type': 'object', 'properties': {}},
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'list_sections',
            'description': (
                'List sections in a project. Useful for grocery/shopping lists where '
                'items are organized by store section (e.g. Produce, Dairy, Frozen).'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'project_name': {
                        'type': 'string',
                        'description': 'Name of the project to list sections for',
                    },
                },
                'required': ['project_name'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'compact_history',
            'description': (
                'Replace the recent conversation history with a short summary. '
                'Call this when the user is moving on to a different topic and the full '
                'detail of previous exchanges is no longer needed. Write a concise summary '
                'that preserves any important context, decisions, or outcomes.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'summary': {
                        'type': 'string',
                        'description': (
                            'A concise summary of the conversation so far, preserving '
                            'key decisions, actions taken, and any context that may be '
                            'relevant later'
                        ),
                    },
                },
                'required': ['summary'],
            },
        },
    },
]

SYSTEM_PROMPT = """\
You are a helpful Todoist assistant running on a personal server. \
You help manage tasks: listing, rescheduling, completing, creating, and organizing them.

When the user asks about tasks, use the list_tasks tool first to find relevant tasks, \
then answer based on the results. When performing actions, confirm what you did.

Keep responses concise - this is a Telegram chat. Use short paragraphs, not long lists \
unless specifically asked. Use emoji sparingly for readability.

If a user refers to a task by name rather than ID, use list_tasks to find it first, \
then use the ID from the results.

The user's timezone is {user_timezone}. Task due dates in tool results may include a \
'timezone' field showing their original timezone. Always present times converted to the \
user's timezone. If a task's timezone differs from the user's, convert it and show the \
time in the user's timezone.

**Proactive updates:** You periodically receive automated update requests. When you get one:
- Use list_tasks with with_due_date_only=true to review tasks
- Highlight meetings (calendar label) and urgent (priority 1) items prominently
- For overdue tasks, be direct and firm
- Recurring tasks include a 'last_completed_at' field showing when they were last completed. \
Use this to detect procrastination: if a task's due date keeps being pushed forward but \
last_completed_at is far in the past (or missing), the user is likely procrastinating. \
Be gentle at first, firmer if the gap between last completion and current due date is large
- Keep updates brief and actionable

**Shopping lists:** When asked to add items to a shopping/grocery project:
1. First use list_tasks with include_completed=true for that project to check for existing \
completed items with the same name
2. If a matching completed item exists, use uncomplete_task to reactivate it instead of \
creating a duplicate
3. For new items, use list_sections to find the appropriate section and place items in the \
right section (e.g. milk → Dairy, apples → Produce)

**Sections:** Tasks can belong to sections within projects. When adding tasks to projects \
that use sections, always check list_sections first and assign the appropriate section.

You have persistent long-term memory. Use save_memory to remember user preferences, \
instructions, or anything important for future conversations. Use delete_memory to remove \
outdated entries. Use compact_history to replace recent conversation history with a short \
summary when the user changes topic — this keeps context manageable. Your current memories:
{memories}"""

PROACTIVE_UPDATE_HOURS = {8, 12, 16, 20, 23}


class TelegramBot:
    def __init__(self, todoist):
        self.todoist = todoist
        storage = get_storage()
        self._bot_token = storage.get_value(TELEGRAM_BOT_TOKEN_KEY)
        self._chat_id = storage.get_value(TELEGRAM_CHAT_ID_KEY)
        self._openai_api_key = storage.get_value(OPENAI_API_KEY)
        self._openai_model = storage.get_value(OPENAI_MODEL)
        self._update_offset = None
        self._openai_client = None
        self._conversation_history = []
        self._memory = storage.get_value(BOT_MEMORY_KEY, {})
        self._last_proactive_hour = None
        self._last_completed_cache = None
        self._last_completed_cache_time = None
        self._user_timezone = (
            todoist._initial_result.get('user', {}).get('tz_info', {}).get('timezone', 'UTC')
        )

        if self._bot_token and self._openai_api_key:
            self._openai_client = OpenAI(api_key=self._openai_api_key)
            logger.info('Telegram bot initialized.')
        else:
            logger.warning('Telegram bot not configured (missing bot token or OpenAI API key).')

    @property
    def is_configured(self):
        return self._openai_client is not None

    def _telegram_api(self, method, **kwargs):
        url = f'https://api.telegram.org/bot{self._bot_token}/{method}'
        response = requests.post(url, json=kwargs, timeout=5)
        response.raise_for_status()
        return response.json()

    def _send_message(self, text):
        # Telegram message limit is 4096 chars
        while text:
            chunk, text = text[:4096], text[4096:]
            self._telegram_api('sendMessage', chat_id=self._chat_id, text=chunk)

    def _get_updates(self):
        params = {'timeout': 0, 'limit': 10}
        if self._update_offset is not None:
            params['offset'] = self._update_offset
        try:
            result = self._telegram_api('getUpdates', **params)
            return result.get('result', [])
        except Exception as e:
            logger.warning(f'Telegram getUpdates failed: {e}')
            return []

    def _get_last_completed_lookup(self):
        now = datetime.now(timezone.utc)
        if (
            self._last_completed_cache is not None
            and self._last_completed_cache_time
            and (now - self._last_completed_cache_time).total_seconds() < 60
        ):
            return self._last_completed_cache
        lookup = {}
        for item in self.todoist._items.values():
            if not item.is_completed():
                continue
            raw = item.raw() or {}
            completed_at = raw.get('completed_at')
            if not completed_at:
                continue
            key = (item.content.lower().strip(), item.project_id)
            if key not in lookup or completed_at > lookup[key]:
                lookup[key] = completed_at
        self._last_completed_cache = lookup
        self._last_completed_cache_time = now
        return lookup

    def _task_to_dict(self, item):
        project = self.todoist._projects.get(item.project_id, {})
        result = {
            'id': item.id,
            'content': item.content,
            'project': project.get('name', 'Unknown'),
            'priority': item.priority,
            'labels': list(item.labels()),
        }
        if item.section_id:
            section = self.todoist._sections.get(item.section_id)
            if section:
                result['section'] = section['name']
        due_date = item.next_due_date()
        if due_date is not None:
            result['due_date'] = str(due_date)
        due_string = item.get_due_string()
        if due_string is not None:
            result['due_string'] = due_string
        if item._due and item._due.get('timezone'):
            result['timezone'] = item._due['timezone']
        if item.is_recurring():
            result['is_recurring'] = True
        raw = item.raw() or {}
        completed_at = raw.get('completed_at')
        if completed_at:
            result['completed_at'] = completed_at
        elif item.is_recurring() and not item.is_completed():
            lookup = self._get_last_completed_lookup()
            key = (item.content.lower().strip(), item.project_id)
            last_completed = lookup.get(key)
            if last_completed:
                result['last_completed_at'] = last_completed
        responsible_uid = raw.get('responsible_uid')
        if responsible_uid:
            collaborator = self.todoist._collaborators.get(responsible_uid, {})
            result['assigned_to'] = collaborator.get('full_name', responsible_uid)
        return result

    def _execute_tool(self, name, args):
        if name == 'list_tasks':
            return self._tool_list_tasks(**args)
        elif name == 'reschedule_task':
            return self._tool_reschedule_task(**args)
        elif name == 'complete_task':
            return self._tool_complete_task(**args)
        elif name == 'uncomplete_task':
            return self._tool_uncomplete_task(**args)
        elif name == 'update_task_priority':
            return self._tool_update_priority(**args)
        elif name == 'add_task':
            return self._tool_add_task(**args)
        elif name == 'add_label_to_task':
            return self._tool_add_label(**args)
        elif name == 'remove_label_from_task':
            return self._tool_remove_label(**args)
        elif name == 'save_memory':
            return self._tool_save_memory(**args)
        elif name == 'delete_memory':
            return self._tool_delete_memory(**args)
        elif name == 'assign_task':
            return self._tool_assign_task(**args)
        elif name == 'list_collaborators':
            return self._tool_list_collaborators()
        elif name == 'list_sections':
            return self._tool_list_sections(**args)
        elif name == 'compact_history':
            return self._tool_compact_history(**args)
        return {'error': f'Unknown tool: {name}'}

    def _tool_list_tasks(
        self, project_name=None, label=None, with_due_date_only=False, include_completed=False
    ):
        tasks = []
        for item in self.todoist._items.values():
            if item.is_completed() and not include_completed:
                continue
            if project_name is not None:
                project = self.todoist._projects.get(item.project_id, {})
                if project.get('name') != project_name:
                    continue
            if label is not None and label not in item.labels():
                continue
            if with_due_date_only and item.next_due_date() is None:
                continue
            task_dict = self._task_to_dict(item)
            if item.is_completed():
                task_dict['completed'] = True
            tasks.append(task_dict)
        return {'tasks': tasks, 'count': len(tasks)}

    def _tool_reschedule_task(self, task_id, due_date):
        item = self.todoist.get_item_by_id(task_id)
        if item is None:
            return {'error': f'Task {task_id} not found'}
        new_due = {'date': due_date}
        if item._due:
            if item._due.get('string'):
                new_due['string'] = item._due['string']
            if item._due.get('timezone'):
                new_due['timezone'] = item._due['timezone']
        self.todoist.update_item(item, due=new_due)
        return {'success': True, 'task': item.content, 'new_due_date': due_date}

    def _tool_complete_task(self, task_id):
        item = self.todoist.get_item_by_id(task_id)
        if item is None:
            return {'error': f'Task {task_id} not found'}
        item.archive()
        return {'success': True, 'task': item.content}

    def _tool_uncomplete_task(self, task_id):
        item = self.todoist.get_item_by_id(task_id)
        if item is None:
            return {'error': f'Task {task_id} not found'}
        if not item.is_completed():
            return {'error': f'Task "{item.content}" is not completed'}
        item.uncomplete()
        return {'success': True, 'task': item.content}

    def _tool_update_priority(self, task_id, priority):
        item = self.todoist.get_item_by_id(task_id)
        if item is None:
            return {'error': f'Task {task_id} not found'}
        self.todoist.update_item(item, priority=priority)
        return {'success': True, 'task': item.content, 'priority': priority}

    def _tool_add_task(
        self,
        content,
        project_name=None,
        section_name=None,
        due_string=None,
        priority=1,
        labels=None,
    ):
        from tools_for_todoist.models.item import TodoistItem

        project_id = None
        if project_name:
            project = self.todoist.get_project_by_name(project_name)
            if project:
                project_id = project['id']
        if project_id is None:
            project_id = self.todoist._initial_result['user']['inbox_project_id']

        section_id = None
        if section_name and project_id:
            section = self.todoist.get_section_by_name(project_id, section_name)
            if section:
                section_id = section['id']

        item = TodoistItem(self.todoist, content, project_id)
        item.section_id = section_id
        if due_string:
            item._due = {'string': due_string}
        item.priority = priority
        if labels:
            for label in labels:
                item.add_label(label)
        item.save()
        return {'success': True, 'task': content, 'id': item.id}

    def _tool_add_label(self, task_id, label):
        item = self.todoist.get_item_by_id(task_id)
        if item is None:
            return {'error': f'Task {task_id} not found'}
        item.add_label(label)
        item.save()
        return {'success': True, 'task': item.content, 'label': label}

    def _tool_remove_label(self, task_id, label):
        item = self.todoist.get_item_by_id(task_id)
        if item is None:
            return {'error': f'Task {task_id} not found'}
        item.remove_label(label)
        item.save()
        return {'success': True, 'task': item.content, 'label': label}

    def _find_collaborator_by_name(self, name):
        name_lower = name.lower()
        for collab in self.todoist._collaborators.values():
            if name_lower in collab.get('full_name', '').lower():
                return collab
        return None

    def _tool_assign_task(self, task_id, person_name):
        item = self.todoist.get_item_by_id(task_id)
        if item is None:
            return {'error': f'Task {task_id} not found'}
        if person_name is None:
            self.todoist.update_item(item, responsible_uid=None)
            return {'success': True, 'task': item.content, 'assigned_to': None}
        collaborator = self._find_collaborator_by_name(person_name)
        if collaborator is None:
            available = [c.get('full_name') for c in self.todoist._collaborators.values()]
            return {'error': f'No collaborator matching "{person_name}"', 'available': available}
        self.todoist.update_item(item, responsible_uid=collaborator['id'])
        return {
            'success': True,
            'task': item.content,
            'assigned_to': collaborator['full_name'],
        }

    def _tool_list_collaborators(self):
        collaborators = [
            {'id': c['id'], 'name': c.get('full_name', 'Unknown')}
            for c in self.todoist._collaborators.values()
        ]
        return {'collaborators': collaborators}

    def _tool_list_sections(self, project_name):
        project = self.todoist.get_project_by_name(project_name)
        if project is None:
            return {'error': f'Project "{project_name}" not found'}
        sections = self.todoist.get_sections_for_project(project['id'])
        return {
            'sections': [
                {'id': s['id'], 'name': s['name'], 'order': s.get('section_order', 0)}
                for s in sections
            ],
            'count': len(sections),
        }

    def _save_memory_to_storage(self):
        get_storage().set_value(BOT_MEMORY_KEY, self._memory)

    def _tool_save_memory(self, key, value):
        self._memory[key] = value
        self._save_memory_to_storage()
        logger.info(f'Telegram bot memory saved: {key}')
        return {'success': True, 'key': key}

    def _tool_delete_memory(self, key):
        if key not in self._memory:
            return {'error': f'Memory key "{key}" not found'}
        del self._memory[key]
        self._save_memory_to_storage()
        logger.info(f'Telegram bot memory deleted: {key}')
        return {'success': True, 'key': key}

    def _format_memories(self):
        if not self._memory:
            return '(none)'
        return '\n'.join(f'- {key}: {value}' for key, value in self._memory.items())

    def _tool_compact_history(self, summary):
        entry_count = len(self._conversation_history)
        self._conversation_history = [
            {
                'user': '(previous conversation summary)',
                'assistant': summary,
                'timestamp': datetime.now(timezone.utc),
            }
        ]
        logger.info(f'Telegram bot compacted {entry_count} history entries into summary')
        return {'success': True, 'compacted_entries': entry_count}

    def _prune_history(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        self._conversation_history = [
            entry for entry in self._conversation_history if entry['timestamp'] >= cutoff
        ]

    def _process_message(self, text):
        self._prune_history()

        messages = [
            {
                'role': 'system',
                'content': SYSTEM_PROMPT.format(
                    user_timezone=self._user_timezone,
                    memories=self._format_memories(),
                ),
            },
        ]
        for entry in self._conversation_history:
            messages.append({'role': 'user', 'content': entry['user']})
            messages.append({'role': 'assistant', 'content': entry['assistant']})
        messages.append({'role': 'user', 'content': text})

        try:
            for _iteration in range(100):
                response = self._openai_client.chat.completions.create(
                    model=self._openai_model,
                    messages=messages,
                    tools=TOOLS,
                )
                choice = response.choices[0]

                if choice.finish_reason == 'tool_calls':
                    messages.append(choice.message)
                    for tool_call in choice.message.tool_calls:
                        args = json.loads(tool_call.function.arguments)
                        logger.info(f'Telegram bot tool call: {tool_call.function.name}({args})')
                        result = self._execute_tool(tool_call.function.name, args)
                        messages.append(
                            {
                                'role': 'tool',
                                'tool_call_id': tool_call.id,
                                'content': json.dumps(result),
                            }
                        )
                    continue

                reply = choice.message.content or 'Done.'
                self._conversation_history.append(
                    {
                        'user': text,
                        'assistant': reply,
                        'timestamp': datetime.now(timezone.utc),
                    }
                )
                return reply

            return 'Sorry, I hit the maximum number of steps. Please try a simpler request.'
        except Exception as e:
            logger.exception(f'Telegram bot AI processing failed: {e}', exc_info=e)
            return f'Error processing your request: {e}'

    def _should_send_proactive_update(self):
        tz = gettz(self._user_timezone)
        now = datetime.now(tz)
        if now.minute < 55:
            return False
        if now.hour not in PROACTIVE_UPDATE_HOURS:
            return False
        check_key = (now.date(), now.hour)
        if self._last_proactive_hour == check_key:
            return False
        return True

    def _send_proactive_update(self, context='hourly'):
        tz = gettz(self._user_timezone)
        now = datetime.now(tz)
        self._last_proactive_hour = (now.date(), now.hour)

        prompt = (
            f'(Automated {context} update) '
            f"It's currently {now.strftime('%H:%M on %A, %B %d, %Y')}. "
            'Please give me a proactive status update. Review my tasks and tell me:\n'
            '1. Any overdue tasks that need immediate attention\n'
            '2. Upcoming meetings or important tasks in the next few hours\n'
            '3. Tasks I might be procrastinating on (check your memory for patterns)\n'
            '4. Any helpful reminders\n\n'
            'Be concise but firm about important things. Increase urgency for tasks '
            "you know I've been putting off.\n"
            'If this is a follow-up update, don\'t repeat information from the last '
            'update unless the situation has changed or it\'s urgent enough to re-emphasize. '
            'Focus on what\'s new or different since last time.'
        )

        logger.info(f'Sending proactive {context} update')
        response = self._process_message(prompt)
        self._send_message(response)

    def poll(self):
        if not self.is_configured:
            return False

        updates = self._get_updates()
        had_messages = False
        for update in updates:
            self._update_offset = update['update_id'] + 1
            message = update.get('message', {})
            chat_id = str(message.get('chat', {}).get('id', ''))
            text = message.get('text', '')

            if chat_id != str(self._chat_id) or not text:
                continue

            logger.info(f'Telegram bot received: {text[:100]}')
            had_messages = True
            response = self._process_message(text)
            self._send_message(response)

        if self._should_send_proactive_update():
            self._send_proactive_update()

        return had_messages

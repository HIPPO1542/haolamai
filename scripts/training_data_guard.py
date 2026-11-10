"""Fail before loading ML libraries if training inputs overlap held-out data."""
import hashlib
import json
from pathlib import Path
import re


def _prompt_fingerprints(path):
    fingerprints = set()
    count = 0
    with Path(path).open(encoding='utf-8-sig') as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get('prompt'), list) or not isinstance(row.get('completion'), list):
                raise ValueError(f'{path}:{line_number}: expected prompt/completion lists')
            if not row['prompt'] or not row['completion']:
                raise ValueError(f'{path}:{line_number}: empty messages')
            for message in row['prompt'] + row['completion']:
                if not isinstance(message, dict) or message.get('role') not in ('system', 'user', 'assistant') or not isinstance(message.get('content'), str) or not message['content'].strip():
                    raise ValueError(f'{path}:{line_number}: invalid message')
            if row['completion'][-1]['role'] != 'assistant':
                raise ValueError(f'{path}:{line_number}: missing assistant completion')
            user = ' '.join(message['content'] for message in row['prompt'] if message['role'] == 'user')
            if not user:
                raise ValueError(f'{path}:{line_number}: missing user prompt')
            canonical = re.sub(r'\s+', ' ', user).strip().casefold()
            fingerprints.add(hashlib.sha256(canonical.encode()).hexdigest())
            count += 1
    if not count:
        raise ValueError(f'{path}: empty dataset')
    return fingerprints


def validate_training_inputs(train, validation, heldout=None):
    train = Path(train).resolve()
    validation = Path(validation).resolve()
    if re.search(r'(?:^|[_\W])(test|eval|benchmark|validation|valid|dev)(?:[_\W]|$)', train.stem, re.I):
        raise ValueError('A held-out filename cannot be used for training')
    if train == validation:
        raise ValueError('Training and validation paths must be different')
    train_prompts = _prompt_fingerprints(train)
    validation_prompts = _prompt_fingerprints(validation)
    if train_prompts & validation_prompts:
        raise ValueError('Training and validation contain identical user prompts')
    heldout_paths = {train.parent/'test_external.jsonl', validation.parent/'test_external.jsonl'}
    if heldout:
        explicit_heldout = Path(heldout).resolve()
        if not explicit_heldout.is_file():
            raise ValueError('Explicit held-out dataset does not exist')
        heldout_paths.add(explicit_heldout)
    for path in heldout_paths:
        if path.is_file() and train_prompts & _prompt_fingerprints(path):
            raise ValueError(f'Training contains held-out prompts from {path.name}')

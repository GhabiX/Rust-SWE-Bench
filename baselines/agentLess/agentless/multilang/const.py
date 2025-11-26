import os

from agentless.multilang.example import (
    DIFF_RUST
)


def get_config(language):
    configs = {
        'rust': {
            'LANG_EXT': ['rs'],
            'DIFF_EXAMPLE': DIFF_RUST,
        }
    }
    if language not in configs:
        raise RuntimeError(f'Unknown language {language}')
    return configs[language]


LANGUAGE = os.environ.get('SWEBENCH_LANG', 'rust').lower()
STRUCTURE_KEYS = {'functions', 'classes', 'text'}
globals().update(get_config(LANGUAGE))
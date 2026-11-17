# -*- coding: utf-8 -*-
"""Extra saved-artifact checks using only the independent lexer, never build.py."""
import argparse
from pathlib import Path
from replay import lex, independent_records, differences, sha, read, write, SOURCE_SHA

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    assert not a.output.exists()
    a.output.mkdir(parents=True)
    examples_path = a.bundle / 'manual_examples.json'
    examples = read(examples_path)
    errors = []
    for i, item in enumerate(examples['examples']):
        display, slots = lex(item['raw'])
        errors.extend(differences({'display': display, 'slots': slots},
            {'display': item['display'], 'slots': item['slots']}, '/manual/' + str(i)))
    rows = independent_records()
    texts = {}
    for version in ('ZL', 'IT'):
        path = a.bundle / (version + '_lines.txt')
        lines = path.read_text().splitlines()
        assert '# source_sha256=' + SOURCE_SHA[version] in lines
        actual = [line.split('\t') for line in lines if not line.startswith('#')]
        expected = [[str(r['source_line']), r['locator'], r['locus_type'], r['display'], r['raw']]
            for r in rows if r['version'] == version]
        errors.extend(differences(expected, actual, '/txt/' + version))
        texts[version] = {'rows': len(expected), 'sha256': sha(path)}
    write(a.output / 'errors.json', errors)
    result = {'all_passed': not errors, 'author_manual_cases': len(examples['examples']),
        'author_examples_sha256': sha(examples_path), 'text_exports': texts,
        'independent_lexer_sha256': sha(Path(__file__).parent / 'replay.py'),
        'checker_sha256': sha(__file__), 'author_code_imported': False,
        'scope': 'Saved author toy examples and both complete TXT exports checked against an independent source parser.'}
    write(a.output / 'audit_report.json', result)
    assert not errors
    print(result)

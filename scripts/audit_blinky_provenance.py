#!/usr/bin/env python3
"""Verify attributed upstream files and individually reviewed Blinky deltas.

This is a reproducible content/provenance audit, not an authorship detector or a
legal clean-room certification. A review authorizes only its recorded final SHA
and actual pinned upstream bytes. Changed or missing evidence fails closed.
"""
import argparse
import collections
import csv
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CODE = {'.c', '.cpp', '.h', '.hpp', '.cc', '.in', '.cmake', '.py', '.ps1',
        '.bat', '.pica', '.inc', '.sh', '.glsl', '.hlsl', '.metal', '.mm', '.rc',
        '.patch', '.yml', '.yaml', '.rsf'}
SKIP = {'build-arm', 'build-3ds', 'build', 'dist', 'dist-wizard', 'work',
        'validation', '__pycache__', '.git', 'wizard-logs'}
CATEGORIES = {'A', 'B', 'C', 'D', 'B+A', 'B+D', 'C+A', 'C+D'}
PREFIXES = {'lus': 'third_party/libultraship/', 'mm': 'third_party/2ship/'}
PINS = {
    'alpha3': ('af3a7e80208e5eff755704d3ae5f5a25a6b7ed6e',
               '41602d1f75cc811d6d778352fc90105c0903af25c3c166ef61366de17c46eca9'),
    'lus': ('7f9b86a593c526fc42261d7fe197100cecf57178',
            '656ca95a03bc7f762b71bd76a26749f6ba2f734369a646f99fddaa996c9551c7'),
    'mm': ('6bfd6a35a0e0d8900273e61ce85cb038d4f4a528',
           '216b4792595fa3023e9ba2dae68754ce69286fabef3c2d00985353c497d45ae6'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def normalized(data):
    return digest(data.replace(b'\r\n', b'\n'))


def delta_digest(before, after):
    """Hash a canonical LF-normalized unified diff; raw bytes are pinned too."""
    def lines(data):
        return data.replace(b'\r\n', b'\n').decode('utf-8', errors='surrogateescape').splitlines(True)
    patch = ''.join(difflib.unified_diff(lines(before), lines(after),
                                       fromfile='upstream', tofile='reviewed', n=3))
    return digest(patch.encode('utf-8', errors='surrogateescape'))


def archive(path):
    """Read source bytes without extracting or executing archive contents."""
    result = {}
    with zipfile.ZipFile(path) as source:
        for entry in source.infolist():
            if entry.is_dir() or '/' not in entry.filename:
                continue
            name = entry.filename.split('/', 1)[1]
            if not safe_relative(name) or name in result:
                raise ValueError(f'unsafe or duplicate archive member: {name}')
            result[name] = source.read(entry)
    return result


def safe_relative(name):
    path = PurePosixPath(name)
    return bool(name) and '\\' not in name and ':' not in name and not path.is_absolute() and '..' not in path.parts


def source_files(root):
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in SKIP for part in relative.parts):
            continue
        name = relative.as_posix()
        if name.startswith('third_party/') and not name.startswith(tuple(PREFIXES.values())):
            continue
        if path.suffix.lower() in CODE or path.name == 'CMakeLists.txt':
            yield name, path


def upstream_for(name, archives):
    for reference, prefix in PREFIXES.items():
        if name.startswith(prefix):
            member = name[len(prefix):]
            return reference, member, archives[reference].get(member)
    return None, None, None


def verify_review(review, data, archives):
    """Return every failed condition; no path-only authorship allowlist exists."""
    errors = []
    name = review['file']
    category = review.get('category')
    if category not in CATEGORIES:
        errors.append('unsupported review category')
    if review.get('sha256') != digest(data):
        errors.append('final SHA-256 differs from reviewed bytes')
    if review.get('normalized_sha256') != normalized(data):
        errors.append('normalized final SHA-256 differs')
    if not review.get('evidence') or not review.get('authorship_scope'):
        errors.append('review explanation or attribution scope is missing')
    reference, member, expected_base = upstream_for(name, archives)
    base = review.get('upstream')
    if base is not None:
        if not isinstance(base, dict) or base.get('archive') != reference or base.get('file') != member:
            errors.append('upstream reference does not match the source path')
        elif expected_base is None:
            errors.append('upstream member does not exist in pinned archive')
        else:
            base_category = 'B' if reference == 'lus' else 'C'
            if category not in (base_category, base_category + '+A', base_category + '+D'):
                errors.append('upstream authors are not retained in category')
            if base.get('sha256') != digest(expected_base):
                errors.append('actual upstream SHA-256 differs from review')
            if base.get('normalized_sha256') != normalized(expected_base):
                errors.append('actual normalized upstream SHA-256 differs from review')
            if review.get('delta_sha256') != delta_digest(expected_base, data):
                errors.append('reviewed upstream delta SHA-256 differs')
            if category == base_category and normalized(expected_base) != normalized(data):
                errors.append('modified file cannot be classified as unchanged upstream')
    else:
        if category not in ('A', 'D'):
            errors.append('mixed/upstream attribution requires an upstream member')
        if expected_base is not None:
            errors.append('existing upstream member requires explicit base attribution')
    return errors


def run(args):
    manifest = json.loads(args.reviewed.read_text(encoding='utf-8'))
    retired = json.loads((ROOT / 'docs/BLINKY-RETIRED-FILES.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or manifest.get('whole_source_original') is not False:
        raise ValueError('unsupported review schema or invalid whole-source authorship claim')
    if manifest.get('cleanroom_certified') is not False:
        raise ValueError('content audit cannot certify legal clean-room provenance')
    for document in manifest.get('review_documents', []):
        name = document['file']
        if not safe_relative(name) or digest((ROOT / name).read_bytes()) != document['sha256']:
            raise ValueError(f'review evidence document missing or changed: {name}')
    paths = {'alpha3': args.alpha3, 'lus': args.lus_upstream, 'mm': args.mm_upstream}
    archives = {}
    for name, path in paths.items():
        commit, checksum = PINS[name]
        reference = manifest['references'].get(name, {})
        if digest(path.read_bytes()) != checksum:
            raise ValueError(f'{name}: archive does not match pinned SHA-256')
        if reference.get('commit') != commit or reference.get('archive_sha256') != checksum:
            raise ValueError(f'{name}: reviewed reference differs from pinned archive')
        archives[name] = archive(path)
    reviews = {}
    for item in manifest['files']:
        name = item['file']
        if not safe_relative(name) or name in reviews:
            raise ValueError(f'unsafe or duplicate review path: {name}')
        reviews[name] = item
    if len(retired) != len(set(retired)) or any(not safe_relative(name) for name in retired):
        raise ValueError('invalid retired file list')
    rows, failures, visited = [], [], set()
    alpha_hashes = collections.defaultdict(list)
    for name, data in archives['alpha3'].items():
        alpha_hashes[normalized(data)].append(name)
    for name, path in source_files(ROOT):
        visited.add(name)
        data = path.read_bytes()
        checksum = normalized(data)
        reference, _, base = upstream_for(name, archives)
        category = 'F'
        evidence = 'No individual review or unchanged official upstream match.'
        review_status = 'unreviewed'
        matches_alpha = alpha_hashes.get(checksum, [])
        if base is not None and normalized(base) == checksum:
            category = 'B' if reference == 'lus' else 'C'
            evidence = 'Matches actual pinned official upstream bytes after CRLF normalization; upstream authors retained.'
            review_status = 'verified-upstream'
        elif matches_alpha:
            category = 'E'
            evidence = 'Complete-file alpha.3 match without unchanged official upstream match; replacement/review required.'
        if name in reviews:
            review = reviews[name]
            errors = verify_review(review, data, archives)
            if review.get('category') == 'A' and matches_alpha:
                errors.append('claimed authored file equals a complete alpha.3 member')
            if errors:
                category = 'F'
                evidence = '; '.join(errors)
                review_status = 'stale-or-invalid-review'
                failures.append({'file': name, 'errors': errors})
            else:
                category = review['category']
                evidence = review['evidence']
                review_status = 'verified-review'
        if name in retired:
            category = 'F'
            evidence = 'File declared retired has reappeared.'
            review_status = 'retired-file-restored'
            failures.append({'file': name, 'errors': [evidence]})
        replacement = 'audit/rewrite' if category in ('E', 'F') else 'no'
        subsystem = ('audio' if 'audio' in name.lower() else 'graphics' if any(
            part in name.lower() for part in ('gfx', 'fast/', 'shader')) else 'input' if any(
            part in name.lower() for part in ('controller', 'input')) else 'game/resources' if
            name.startswith(PREFIXES['mm']) else 'platform/build')
        rows.append(dict(file=name, subsystem=subsystem, category=category, evidence=evidence,
                         replacement=replacement, priority='P1' if replacement != 'no' else 'preserve',
                         activity='test-only' if name.startswith('tests/') else 'source inventory; build membership not inferred',
                         sha256=digest(data), upstream_sha256=digest(base) if base is not None else '',
                         upstream_normalized_sha256=normalized(base) if base is not None else '',
                         alpha3_equal=bool(matches_alpha), review_status=review_status))
    for name in sorted(reviews.keys() - visited):
        failures.append({'file': name, 'errors': ['reviewed source is missing or outside the audited source scope']})
    restored = sorted(name for name in retired if (ROOT / name).exists())
    for name in restored:
        if name not in visited:
            failures.append({'file': name, 'errors': ['retired file has reappeared outside the source inventory']})
    counts = dict(sorted(collections.Counter(row['category'] for row in rows).items()))
    unresolved = [row['file'] for row in rows if row['category'] in ('E', 'F')]
    success = not failures and not unresolved and not restored
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'BLINKY-PROVENANCE-INVENTORY.csv').open('w', newline='', encoding='utf-8') as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]) if rows else ['file'])
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        'current_build': manifest['build'], 'provenance_review_complete': success,
        'native_adaptations_reviewed': success, 'whole_source_original': False,
        'cleanroom_certified': False, 'soh_removal_complete': False,
        'soh_removal_complete_scope': 'Absolute historical absence is not certified by content review; reviewed native work is recorded separately in provenance_review_complete.',
        'hardware_tested': False, 'hardware_tested_by_agent': False,
        'claim_boundary': 'Verified upstream attribution and individually reviewed native deltas in the stated scope; no whole-source authorship or absolute historical-origin certification.',
        'method': 'Pinned archive SHA-256; actual upstream raw/normalized SHA-256; final raw/normalized SHA-256 and canonical reviewed delta SHA-256. No path-only authorship allowlist or similarity-based attribution.',
        'scope': {'roots': ['local build/platform/tests sources', *PREFIXES.values()],
                  'extensions': sorted(CODE), 'special_filenames': ['CMakeLists.txt'],
                  'excluded_directories': sorted(SKIP),
                  'other_vendor_dependencies': 'Outside this inventory; retain their own upstream authors and licenses.',
                  'not_covered': 'Non-code assets, documentation and binary dependencies; whole source originality is not asserted.'},
        'categories': counts, 'source_files': len(rows), 'reviewed_files': len(reviews),
        'unresolved_files': unresolved, 'verification_errors': failures,
        'retired_files': sorted(name for name in retired if not (ROOT / name).exists()),
        'unexpectedly_restored_files': restored,
        'review_manifest_sha256': digest(args.reviewed.read_bytes()),
        'retired_manifest_sha256': digest((ROOT / 'docs/BLINKY-RETIRED-FILES.json').read_bytes()),
        'source_archives': {path.name: digest(path.read_bytes()) for path in paths.values()},
        'alpha3_commit': PINS['alpha3'][0], '2ship_reference': PINS['mm'][0], 'lus_reference': PINS['lus'][0],
        'local_git_history_present': (ROOT / '.git').exists(),
        'user_feedback': manifest.get('user_feedback', {
            'build': 'blinky-performance-06', 'result': 'Game renders on console; poor performance reported.',
            'photo_frame_ms': 967.5, 'photo_cpu_triangles_per_frame': 2081.3,
            'audio_home_lid_confirmed': False}),
        'previous_user_feedback': manifest.get('previous_user_feedback', []),
    }
    (args.output / 'BLINKY-PROVENANCE-SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'provenance_review_complete': success, 'categories': counts,
                      'source_files': len(rows), 'reviewed_files': len(reviews),
                      'retired_files': len(summary['retired_files']),
                      'unresolved_files': unresolved, 'verification_errors': failures}, indent=2))
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alpha3', type=Path, required=True)
    parser.add_argument('--lus-upstream', type=Path, required=True)
    parser.add_argument('--mm-upstream', type=Path, required=True)
    parser.add_argument('--reviewed', type=Path, default=ROOT / 'docs/BLINKY-REVIEWED-DELTAS.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs')
    try:
        return run(parser.parse_args())
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(f'Provenance audit failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

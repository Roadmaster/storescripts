#!/usr/bin/env python3
import argparse
import logging
import os
import sys

import humanize
import requests


RELEASED_REVISIONS = {
    ('core', 'amd64'): [
        4830,
        4917,
        4571,
        4486,
        4650,
        5742,
        5897,
        6034,
        6130,
    ],
}


def get_info(name):
    headers = {
        'Snap-Device-Series': '16',
    }
    url = 'https://api.snapcraft.io/v2/snaps/info/{}'.format(name)
    r = requests.get(url, headers=headers)
    return r.json()


def get_deltas(snap_id, architecture, source_revisions, candidate):
    headers = {
        'Content-Type': 'application/json',
        'Snap-Device-Series': '16',
        'Snap-Device-Architecture': architecture,
        'Snap-Accept-Delta-Format': 'xdelta',
    }
    url = 'https://api.snapcraft.io/v2/snaps/refresh'

    # Build a context with all source_revisions
    context = [{
        'snap-id': snap_id,
        'revision': src,
        'tracking-channel': candidate,
        'instance-key': str(src),
    } for src in source_revisions]

    # Request a refresh for the entire context.
    actions = [{
        'action': 'refresh',
        'snap-id': snap_id,
        'instance-key': c['instance-key']
    } for c in context]

    payload = {'context': context, 'actions': actions}
    r = requests.post(url, json=payload, headers=headers)
    return r.json()['results']


def main():
    parser = argparse.ArgumentParser(
        description='check snap delta availability'
    )
    parser.add_argument(
        '--version', action='version',
        version=' "{}"'.format(
            os.environ.get('SNAP_VERSION', 'devel')))
    parser.add_argument('-v', '--debug', action='store_true',
                        help='Prints request and response headers')
    parser.add_argument(
        '-a', '--architecture', default='amd64',
        choices=['amd64', 'arm64', 'armhf', 'i386', 'ppc64el', 's390x'])
    parser.add_argument(
        '-c', '--candidate', default='candidate', metavar='CHANNEL',
        help=('Promoted channel, defaults to "candidate", but can be any '
              'branch or track.'))
    parser.add_argument('name', metavar='SNAP_NAME')

    args = parser.parse_args()

    if args.debug:
        handler = requests.packages.urllib3.add_stderr_logger()
        handler.setFormatter(logging.Formatter('\033[1m%(message)s\033[0m'))

    # Figure out the `snap-id` and `stable_revision` for the context architecture.
    info = get_info(args.name)
    snap_id = info['snap-id']
    stable_revision = [
        c['revision'] for c in info['channel-map']
        if (c['channel']['name'] == 'stable' and
            c['channel']['architecture'] == args.architecture)][0]

    # Consider RELEASED revisions for the context (snap, arch).
    sources = RELEASED_REVISIONS.get(
        (args.name, args.architecture), []) + [stable_revision]

    results = get_deltas(snap_id, args.architecture, sources, args.candidate)
    candidate_revision = results[0]['snap']['revision']
    candidate_size = results[0]['snap']['download']['size']
    print('Snap:      {} ({})'.format(args.name, snap_id))
    print('Promoting: {}'.format(args.candidate))
    print('Candidate: {} ({})'.format(
        candidate_revision, humanize.naturalsize(candidate_size, gnu=True)))
    print('Deltas:')
    for r in results:
        src = r['instance-key']
        if r['snap']['download']['deltas']:
            delta_size = r['snap']['download']['deltas'][0]['size']
            note = '{} / saves {:.0f} %'.format(
                humanize.naturalsize(delta_size, gnu=True),
                (candidate_size - delta_size) / float(candidate_size) * 100,
            )
        else:
            note = 'not available'
        print('  {}: {}'.format(src, note))


if __name__ == '__main__':
    sys.exit(main())

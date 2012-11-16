# Copyright (C) 2012 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Common data/functions for the Chromium merging scripts.

"""

import os
import re
import subprocess
import sys


REPOSITORY_ROOT = os.path.join(os.environ['ANDROID_BUILD_TOP'],
                               'external/chromium_org')


# Whitelist of projects that need to be merged to build WebView. We don't need
# the other upstream repositories used to build the actual Chrome app.
THIRD_PARTY_PROJECTS_WITH_FLAT_HISTORY = [
    'third_party/WebKit',
]

THIRD_PARTY_PROJECTS_WITH_FULL_HISTORY = [
    'googleurl',
    'sdch/open-vcdiff',
    'testing/gtest',
    'third_party/angle',
    'third_party/freetype',
    'third_party/icu',
    'third_party/leveldatabase/src',
    'third_party/libjingle/source',
    'third_party/libphonenumber/src/phonenumbers',
    'third_party/libphonenumber/src/resources',
    'third_party/openssl',
    'third_party/ots',
    'third_party/skia/include',
    'third_party/skia/gyp',
    'third_party/skia/src',
    'third_party/smhasher/src',
    'third_party/v8-i18n',
    'tools/grit',
    'tools/gyp',
    'v8',
]


PROJECTS_WITH_FLAT_HISTORY = ['.'] + THIRD_PARTY_PROJECTS_WITH_FLAT_HISTORY
PROJECTS_WITH_FULL_HISTORY = THIRD_PARTY_PROJECTS_WITH_FULL_HISTORY

THIRD_PARTY_PROJECTS = (THIRD_PARTY_PROJECTS_WITH_FLAT_HISTORY +
                        THIRD_PARTY_PROJECTS_WITH_FULL_HISTORY)

ALL_PROJECTS = ['.'] + THIRD_PARTY_PROJECTS


# Directories to be removed when flattening history.
PRUNE_WHEN_FLATTENING = {
    'third_party/WebKit': [
        'LayoutTests',
    ],
}


assert all(p in PROJECTS_WITH_FLAT_HISTORY for p in PRUNE_WHEN_FLATTENING)


def GetCommandStdout(args, cwd=REPOSITORY_ROOT, ignore_errors=False):
  """Gets stdout from runnng the specified shell command.
  Args:
    args: The command and its arguments.
    cwd: The working directory to use. Defaults to REPOSITORY_ROOT.
    ignore_errors: Ignore the command's return code.
  Returns:
    stdout from running the command.
  """

  p = subprocess.Popen(args=args, cwd=cwd, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
  stdout, stderr = p.communicate()
  if p.returncode == 0 or ignore_errors:
    return stdout
  else:
    print >>sys.stderr, 'Running command %s failed:' % args
    print >>sys.stderr, stderr
    raise Exception('Command execution failed')


def CheckNoConflictsAndCommitMerge(commit_message, cwd=REPOSITORY_ROOT):
  """Prompts the user to resolve merge conflicts then once done, commits the
  merge using either the supplied commit message or a user-supplied override.
  Args:
    commit_message: The default commit message
  """

  status = GetCommandStdout(['git', 'status', '--porcelain'], cwd=cwd)
  conflicts_deleted_by_us = re.findall(r'^(?:DD|DU) ([^\n]+)$', status,
                                       flags=re.MULTILINE)
  if conflicts_deleted_by_us:
    print 'Keeping ours for the following locally deleted files.\n  %s' % \
        '\n  '.join(conflicts_deleted_by_us)
    GetCommandStdout(['git', 'rm', '-rf', '--ignore-unmatch'] +
                     conflicts_deleted_by_us, cwd=cwd)

  # If upstream renames a file we have deleted then it will conflict, but
  # we shouldn't just blindly delete these files as they may have been renamed
  # into a directory we don't delete. Let them get re-added; they will get
  # re-deleted if they are still in a directory we delete.
  conflicts_renamed_by_them = re.findall(r'^UA ([^\n]+)$', status,
                                         flags=re.MULTILINE)
  if conflicts_renamed_by_them:
    print 'Adding theirs for the following locally deleted files.\n  %s' % \
        '\n  '.join(conflicts_renamed_by_them)
    GetCommandStdout(['git', 'add', '-f'] + conflicts_renamed_by_them, cwd=cwd)

  while True:
    status = GetCommandStdout(['git', 'status', '--porcelain'], cwd=cwd)
    conflicts = re.findall(r'^((DD|AU|UD|UA|DU|AA|UU) [^\n]+)$', status,
                           flags=re.MULTILINE)
    if not conflicts:
      break
    conflicts_string = '\n'.join([x[0] for x in conflicts])
    new_commit_message = raw_input(
        ('The following conflicts exist and must be resolved.\n\n%s\n\nWhen '
         'done, enter a commit message or press enter to use the default '
         '(\'%s\').\n\n') % (conflicts_string, commit_message))
    if new_commit_message:
      commit_message = new_commit_message

  GetCommandStdout(['git', 'commit', '-m', commit_message], cwd=cwd)


def PushToServer(autopush, src, dest):
  """Push each merge branch to the server."""

  if not autopush:
    print 'Merge complete; push to server? [y|n]: ',
    answer = sys.stdin.readline()
    if not answer.lower().startswith('y'):
      return

  print 'Pushing to server ...'
  for path in ALL_PROJECTS:
    print path
    dest_dir = os.path.join(REPOSITORY_ROOT, path)
    GetCommandStdout(['git', 'push', 'goog', src + ':' + dest], cwd=dest_dir)

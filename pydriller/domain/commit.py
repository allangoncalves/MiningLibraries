# Copyright 2018 Davide Spadini
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import os
from datetime import datetime
from git import Repo, Diff, Git, Commit as GitCommit


logger = logging.getLogger(__name__)
from pydriller.domain.developer import Developer

NULL_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'


class ModificationType(object):
    ADD = 1,
    COPY = 2,
    RENAME = 3,
    DELETE = 4,
    MODIFY = 5


class Modification:
    def __init__(self, old_path, new_path,
                 change_type,
                 diff_text, sc):
        """
        Initialize a modification. A modification carries on information regarding
        the changed file. Normally, you shouldn't initialize a new one.
        """
        self.old_path = old_path
        self.new_path = new_path
        self.change_type = change_type
        self.diff = diff_text
        self.source_code = sc

    @property
    def added(self):
        """
        Return the total number of added lines in the file.

        :return: int lines_added
        """
        added = 0
        for line in self.diff.replace('\r', '').split("\n"):
            if line.startswith('+') and not line.startswith('+++'):
                added += 1
        return added

    @property
    def removed(self):
        """
        Return the total number of deleted lines in the file.

        :return: int lines_deleted
        """
        removed = 0
        for line in self.diff.replace('\r', '').split("\n"):
            if line.startswith('-') and not line.startswith('---'):
                removed += 1
        return removed

    @property
    def filename(self):
        """
        Return the filename. Given a path-like-string (e.g.
        "/Users/dspadini/pydriller/myfile.py") returns only the filename
        (e.g. "myfile.py")

        :return filename
        """
        if self.new_path is not None and self.new_path != "/dev/null":
            path = self.new_path
        else:
            path = self.old_path

        if os.sep not in path:
            return path

        filename = path.split(os.sep)
        return filename[-1]

    def __eq__(self, other):
        if not isinstance(other, Modification):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self.__dict__ == other.__dict__

    def __str__(self):
        return (
            'MODIFICATION\n' +
            'Old Path: {}\n'.format(self.old_path) +
            'New Path: {}\n'.format(self.new_path) +
            'Type: {}\n'.format(self.change_type.name) +
            'Diff: {}\n'.format(self.diff) +
            'Source code: {}\n'.format(self.source_code)
        )


class Commit:
    def __init__(self, commit, path, main_branch):
        """
        Create a commit object.
        """
        self._c_object = commit
        self._path = path
        self._main_branch = main_branch

    @property
    def hash(self):
        """
        Return the SHA of the commit.

        :return hash
        """
        return self._c_object.hexsha

    @property
    def author(self):
        """
        Return the author of the commit as a Developer object.

        :return: author
        """
        return Developer(self._c_object.author.name, self._c_object.author.email)

    @property
    def committer(self):
        """
        Return the committer of the commit as a Developer object.

        :return: committer
        """
        return Developer(self._c_object.committer.name, self._c_object.committer.email)

    @property
    def author_date(self):
        """
        Return the authored datetime.

        :return: datetime author_datetime
        """
        return self._c_object.authored_datetime

    @property
    def committer_date(self):
        """
        Return the committed datetime.

        :return: datetime committer_datetime
        """
        return self._c_object.committed_datetime

    @property
    def author_timezone(self):
        """
        Author timezone expressed in seconds from epoch.

        :return: int timezone
        """
        return self._c_object.author_tz_offset

    @property
    def committer_timezone(self):
        """
        Author timezone expressed in seconds from epoch.

        :return: int timezone
        """
        return self._c_object.committer_tz_offset

    @property
    def msg(self):
        """
        Return commit message.

        :return commit_message
        """
        return self._c_object.message.strip()

    @property
    def parents(self):
        """
        Return the list of parents SHAs.

        :return: List[str] parents
        """
        parents = []
        for p in self._c_object.parents:
            parents.append(p.hexsha)
        return parents

    @property
    def merge(self):
        """
        Return True if the commit is a merge, False otherwise.

        :return: bool merge
        """
        return len(self._c_object.parents) > 1

    @property
    def modifications(self):
        """
        Return a list of modified files.

        :return: List[Modification] modifications
        """
        repo = Repo(self._path)
        commit = self._c_object

        if len(self.parents) > 0:
            # the commit has a parent
            diff_index = self._c_object.parents[0].diff(commit, create_patch=True)
        else:
            # this is the first commit of the repo. Comparing it with git NULL TREE
            parent = repo.tree(NULL_TREE)
            diff_index = parent.diff(commit.tree, create_patch=True)

        return self._parse_diff(diff_index)

    def _parse_diff(self, diff_index):
        modifications_list = []
        for d in diff_index:
            old_path = d.a_path
            new_path = d.b_path
            change_type = self._from_change_to_modification_type(d)

            diff_text = ''
            sc = ''
            try:
                diff_text = d.diff.decode('utf-8')
                sc = d.b_blob.data_stream.read().decode('utf-8')
            except (UnicodeDecodeError, AttributeError, ValueError):
                logger.debug(
                    'Could not load source code or the diff of a file in commit {}'.format(self._c_object.hexsha))

            modifications_list.append(Modification(old_path, new_path, change_type, diff_text, sc))

        return modifications_list

    @property
    def in_main_branch(self):
        """
        Return True if the commit is in the main branch, False otherwise.

        :return: bool in_main_branch
        """
        return self._main_branch in self.branches

    @property
    def branches(self):
        """
        Return the set of branches that contain the commit.

        :return: set(str) branches
        """
        git = Git(self._path)
        branches = set()
        for branch in set(git.branch('--contains', self.hash).split('\n')):
            branches.add(branch.strip().replace('* ', ''))
        return branches

    def _from_change_to_modification_type(self, d):
        if d.new_file:
            return ModificationType.ADD
        elif d.deleted_file:
            return ModificationType.DELETE
        elif d.renamed_file:
            return ModificationType.RENAME
        elif d.a_blob and d.b_blob and d.a_blob != d.b_blob:
            return ModificationType.MODIFY

    def __eq__(self, other):
        if not isinstance(other, Commit):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self.__dict__ == other.__dict__

    def __str__(self):
        return ('Hash: {}'.format(self.hash) + '\n'
                'Author: {}'.format(self.author.name) + '\n'
                'Author email: {}'.format(self.author.email) + '\n'
                'Committer: {}'.format(self.committer.name) + '\n'
                'Committer email: {}'.format(self.committer.email) + '\n'
                'Author date: {}'.format(self.author_date.strftime("%Y-%m-%d %H:%M:%S")) + '\n'
                'Committer date: {}'.format(self.committer_date.strftime("%Y-%m-%d %H:%M:%S")) + '\n'
                'Message: {}'.format(self.msg) + '\n'
                'Parent: {}'.format("\n".join(map(str, self.parents))) + '\n'
                'Merge: {}'.format(self.merge) + '\n'
                'Modifications: \n{}'.format("\n".join(map(str, self.modifications))) + '\n'
                'Branches: \n{}'.format("\n".join(map(str, self.branches))) + '\n'
                'In main branch: {}'.format(self.in_main_branch)
                )
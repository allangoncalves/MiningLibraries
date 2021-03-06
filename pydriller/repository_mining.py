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

import pytz as pytz

from pydriller.domain.commit import Commit
from pydriller.git_repository import GitRepository
from datetime import datetime

logger = logging.getLogger(__name__)


class RepositoryMining:
    def __init__(self, path_to_repo,
                 single = None,
                 since = None, to = None,
                 from_commit = None, to_commit = None,
                 from_tag = None, to_tag = None,
                 reversed_order = False,
                 only_in_main_branch = False,
                 only_in_branches = None,
                 only_modifications_with_file_types = None,
                 only_no_merge = False):
        """
        Init a repository mining.

        :param str path_to_repo: absolute path to the repository you have to analyze
        :param str single: hash of a single commit to analyze
        :param datetime since: starting date
        :param datetime to: ending date
        :param str from_commit: starting commit (only if `since` is None)
        :param str to_commit: ending commit (only if `to` is None)
        :param str from_tag: starting the analysis from specified tag (only if `since` and `from_commit` are None)
        :param str to_tag: ending the analysis from specified tag (only if `to` and `to_commit` are None)
        :param bool reversed_order: whether the commits should be analyzed in reversed order
        :param bool only_in_main_branch: whether only commits in main branch should be analyzed
        :param List[str] only_in_branches: only commits in these branches will be analyzed
        :param List[str] only_modifications_with_file_types: only modifications with that file types will be analyzed
        :param bool only_no_merge: if True, merges will not be analyzed
        """
        self.git_repo = GitRepository(path_to_repo)
        self.single = single
        self.since = since
        self.to = to
        self.reversed_order = reversed_order
        self.only_in_main_branch = only_in_main_branch
        self.only_in_branches = only_in_branches
        self.only_modifications_with_file_types = only_modifications_with_file_types
        self.only_no_merge = only_no_merge

        self._check_filters(from_commit, from_tag, since, single, to, to_commit, to_tag)
        self._check_timezones()

    def _check_filters(self, from_commit, from_tag, since, single, to, to_commit, to_tag):
        if single is not None:
            if since is not None or to is not None or from_commit is not None or \
                   to_commit is not None or from_tag is not None or to_tag is not None:
                raise Exception('You can not specify a single commit with other filters')

        if from_commit is not None:
            if since is not None:
                raise Exception('You can not specify both <since date> and <from commit>')
            self.since = self.git_repo.get_commit(from_commit).author_date

        if to_commit is not None:
            if to is not None:
                raise Exception('You can not specify both <to date> and <to commit>')
            self.to = self.git_repo.get_commit(to_commit).author_date

        if from_tag is not None:
            if since is not None or from_commit is not None:
                raise Exception('You can not specify <since date> or <from commit> when using <from tag>')
            self.since = self.git_repo.get_commit_from_tag(from_tag).author_date

        if to_tag is not None:
            if to is not None or to_commit is not None:
                raise Exception('You can not specify <to date> or <to commit> when using <to tag>')
            self.to = self.git_repo.get_commit_from_tag(to_tag).author_date

    def traverse_commits(self):
        """
        Analyze all the specified commits (all of them by default), returning
        a generator of commits.
        """
        logger.info('Git repository in {}'.format(self.git_repo.path))
        all_cs = self._apply_filters_on_commits(self.git_repo.get_list_commits())

        if not self.reversed_order:
            all_cs.reverse()

        for commit in all_cs:
            logger.info('Commit #{} in {} from {}'
                         .format(commit.hash.encode('utf-8'), commit.author_date, commit.author.name.encode('utf-8')))

            if self._is_commit_filtered(commit):
                logger.info('Commit #{} filtered'.format(commit.hash.encode('utf-8')))
                continue

            yield commit

    def _is_commit_filtered(self, commit):
        if self.only_in_main_branch is True and commit.in_main_branch is False:
            logger.debug('Commit filtered for main branch')
            return True
        if self.only_in_branches is not None:
            logger.debug('Commit filtered for only in branches')
            if not self._commit_branch_in_branches(commit):
                return True
        if self.only_modifications_with_file_types is not None:
            logger.debug('Commit filtered for modification types')
            if not self._has_modification_with_file_type(commit):
                return True
        if self.only_no_merge is True and commit.merge is True:
            logger.debug('Commit filtered for no merge')
            return True
        return False

    def _commit_branch_in_branches(self, commit):
        for branch in commit.branches:
            if branch in self.only_in_branches:
                return True
        return False

    def _has_modification_with_file_type(self, commit):
        for mod in commit.modifications:
            if mod.filename.endswith(tuple(self.only_modifications_with_file_types)):
                return True
        return False

    def _apply_filters_on_commits(self, all_commits):
        res = []

        if self._all_filters_are_none():
            return all_commits

        for commit in all_commits:
            if self.single is not None and commit.hash == self.single:
                return [commit]
            if self.since is None or self.since <= commit.author_date:
                if self.to is None or commit.author_date <= self.to:
                    res.append(commit)
                    continue
        return res

    def _all_filters_are_none(self):
        return self.single is None and self.since is None and self.to is None

    def _check_timezones(self):
        if self.since is not None:
            if self.since.tzinfo is None or self.since.tzinfo.utcoffset(self.since) is None:
                self.since = self.since.replace(tzinfo=pytz.utc)
        if self.to is not None:
            if self.to.tzinfo is None or self.to.tzinfo.utcoffset(self.to) is None:
                self.to = self.to.replace(tzinfo=pytz.utc)

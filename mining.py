#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pydriller import RepositoryMining
from pydriller import GitRepository
from repos import repositories
import pandas as pd
import ast
import re
import logging
import requests
import json

logging.basicConfig(filename='errors.log',level=logging.ERROR)

class Visitor(ast.NodeVisitor):

    def __init__(self, modification, repository_name):
        self.repo = GitRepository('repositories/'+repository_name)
        self.modified_lines = [line for line, _ in self.repo.parse_diff(modification.diff)['added']]
        self.commit_message = ''
        self.except_found = False
    
    def visit_ExceptHandler(self, node):
        if len(node.body) == 1 and all(isinstance(x, ast.Pass) for x in node.body) and node.lineno in self.modified_lines:
            self.except_found = True

class Minner():

    def __init__(self, username, repository_name):
        self.username = username
        self.repository_name = repository_name
        self.header = {'Authorization': 'token f9aeefc6106b2022d58950abeade70da5a3e266d'}
        self.issues = []
        self.commits = []
        self.last_checked_file = ''
        
    def check_modifications(self, commit):
        commit_info = []
        issues = []
        for modification in commit.modifications:
            if modification.filename.endswith('.py') and self.last_checked_file != modification.filename:
                try:
                    root = ast.parse(modification.source_code)
                except (SyntaxError, ValueError) as e1:
                    logging.error('{}\n\t{}'.format(e1.msg, e1.text))
                    continue
                except IndentationError as e2:
                    logging.error(e2.print_file_and_line)
                    continue
                v = Visitor(modification, self.repository_name)
                v.visit(root)
                if v.except_found:
                    self.commits.append({'hash': commit.hash, 'message': commit.msg})
                    self.check_issues(commit)
                    logging.error('{}\n{}'.format(commit_info, issues))
            self.last_checked_file = modification.filename

    def check_issues(self, commit):
        issues = re.findall("#(\w+)", commit.msg)
        for issue in issues:
            request = requests.get('https://api.github.com/repos/{}/{}/issues/{}'.format(self.repository_name, self.repository_name, issue), headers=self.header)
            if request.ok:
                content = json.loads(request.content)
                print {'number': issue, 'commit': commit.hash, 'title': content['title']}
                self.issues.append({'number': issue, 'commit': commit.hash, 'title': content['title']})
    
    def duplicated_issue(self, number):
        return any(issue['number'] == number for issue in self.issues)
    
    def duplicated_commit(self, hash):
        return any(commit['number'] == number for commit in self.commits)

    def start_mining(self):
        for commit in RepositoryMining('repositories/'+self.repository_name, only_modifications_with_file_types=['.py']).traverse_commits():
            print ('Hash: {}'.format(commit.hash))
            self.check_modifications(commit)
            
    
    def to_json(self):
        with open('{}_commits'.format(self.repository_name), 'w') as f:
            json.dump(self.commits, f)
        with open('{}_issues'.format(self.repository_name), 'w') as f:
            json.dump(self.issues, f)

    def to_csv(self):
        df_commits = pd.DataFrame(self.commits)
        df_commits.to_csv('{}_commits.csv'.format(self.repository_name), index=False, sep=';', encoding='utf-8')

        df_issues = pd.DataFrame(self.issues)
        df_issues.to_csv('{}_issues.csv'.format(self.repository_name), index=False, sep=';', encoding='utf-8')


if __name__ == '__main__':
    for username, repository_name in repositories.iteritems():
        minner = Minner(username, repository_name)
        minner.start_mining()
        minner.to_csv()
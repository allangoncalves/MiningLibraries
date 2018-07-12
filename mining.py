#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ast
import re
import logging
from pydriller import RepositoryMining
from pydriller import GitRepository

REPO_NAME = 'repositories/pandas'

class Visitor(ast.NodeVisitor):

    def __init__(self, modification):
        repo = GitRepository(REPO_NAME)
        self.modified_lines = [line for line, _ in repo.parse_diff(modification.diff)['added']]
        self.commit_message = ''
        self.issues = None
        self.except_found = False
    
    def visit_ExceptHandler(self, node):
        if len(node.body) == 1 and all(isinstance(x, ast.Pass) for x in node.body) and node.lineno in self.modified_lines:
            self.except_found = True
            self.commit_message = commit.msg
            self.issues = re.findall("#(\w+)", commit.msg)

def create_logger(title, file_name, level=logging.INFO):
    logger = logging.getLogger(title)
    handler = logging.FileHandler(file_name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger

MSG_LOGGER = create_logger('Data', '{}_messages_and_issues.log'.format(REPO_NAME))

EXCEPTION_LOGGER = create_logger('Errors', '{}_errors.log'.format(REPO_NAME), logging.ERROR)

def check_modifications(commit):
    file_name = ''
    for modification in commit.modifications:
        if modification.filename.endswith('.py') and file_name != modification.filename:
            try:
                root = ast.parse(modification.source_code)
            except SyntaxError as e1:
                EXCEPTION_LOGGER.error('{}\n\t{}'.format(e1.msg, e1.text))
                continue
            except IndentationError as e2:
                EXCEPTION_LOGGER.error(e2.print_file_and_line)
                continue
            v = Visitor(modification)
            v.visit(root)
            if v.except_found:
                MSG_LOGGER.info({'Commit': commit.hash, 'File Name': modification.filename,'Message': v.commit_message, 'Issues': v.issues})
                return
        file_name = modification.filename


if __name__ == '__main__':
    for commit in RepositoryMining(REPO_NAME, only_modifications_with_file_types=['.py'], from_commit='70d2eb64cf53fb7ef95ec64b1eb02d61116e58a0').traverse_commits():
        print ('Hash: {}'.format(commit.hash))
        check_modifications(commit)
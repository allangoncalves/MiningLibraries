import ast
import re
import logging
from pydriller import RepositoryMining
from pydriller import GitRepository

REPO_NAME = 'sympy'

class Visitor(ast.NodeVisitor):

    def __init__(self, modification):
        repo = GitRepository(REPO_NAME)
        self.modified_lines = [line for line, _ in repo.parse_diff(modification.diff)['added']]
        self.commit_message = ''
        self.issues = None
    
    def visit_ExceptHandler(self, node):
        if node.lineno in self.modified_lines:
            self.commit_message = commit.msg
            self.issues = re.findall("#(\w+)", commit.msg)

def check_modifications(modifications):
    for modification in modifications:
        if modification.filename.endswith('.py'):
            try:
                root = ast.parse(modification.source_code)
            except SyntaxError as e1:
                logging.error('{}\n\t{}'.format(e1.msg, e1.text))
                continue
            except IndentationError as e2:
                logging.error(e2.print_file_and_line)
                continue
            v = Visitor(modification)
            v.visit(root)
            if v.issues:
                print('Issues to the commit: {}'.format(v.issues))
            elif v.commit_message:
                print('Commit message: {}'.format(v.commit_message))


if __name__ == '__main__':
    logging.basicConfig(filename='{}.log'.format(REPO_NAME), level=logging.ERROR)
    for commit in RepositoryMining(REPO_NAME, only_modifications_with_file_types=['.py']).traverse_commits():
        print ('Hash: {}'.format(commit.hash))
        check_modifications(commit.modifications)
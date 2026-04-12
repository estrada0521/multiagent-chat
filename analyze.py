import ast
import os
import sys

def analyze_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except Exception as e:
            return

    for node in ast.walk(tree):
        # Exception handling
        if isinstance(node, ast.ExceptHandler):
            if node.type is None or (isinstance(node.type, ast.Name) and node.type.id == 'Exception'):
                # check if there's any logging or raise
                has_log = False
                has_raise = False
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Raise):
                        has_raise = True
                    if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute) and stmt.func.attr in ('error', 'exception', 'warning'):
                        has_log = True
                    if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Name) and stmt.func.id == 'print':
                        has_log = True
                if not has_log and not has_raise:
                    print(f"{filepath}:{node.lineno}: Silent exception swallowing (bare except or except Exception without log/raise)")
                    
        # Type hints
        if isinstance(node, ast.FunctionDef):
            missing_args = [arg.arg for arg in node.args.args if arg.arg != 'self' and arg.arg != 'cls' and arg.annotation is None]
            if node.returns is None and node.name != '__init__':
                pass

        # Performance (e.g. string concatenation in loop)
        if isinstance(node, ast.For) or isinstance(node, ast.While):
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.AugAssign) and isinstance(stmt.op, ast.Add):
                    print(f"{filepath}:{stmt.lineno}: Potential performance issue: string concatenation (+ or +=) in a loop. Use ''.join() instead.")

        # Log safety (e.g. logging with f-string)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('debug', 'info', 'warning', 'error', 'critical', 'exception'):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in ('logger', 'logging'):
                    if node.args and isinstance(node.args[0], ast.JoinedStr):
                        print(f"{filepath}:{node.lineno}: Log safety / Style: Using f-string in log message ({node.func.attr}). Pass variables as arguments instead.")

for root, _, files in os.walk('.'):
    for f in files:
        if f.endswith('.py') or f in ('multiagent-public-edge', 'multiagent'):
            filepath = os.path.join(root, f)
            if 'lib/' in filepath or 'bin/' in filepath:
                analyze_file(filepath)

import ast


def parse_value(text):
    """Turn a value from the config file into a Python value: numbers, strings, lists, dicts, True/False/None."""
    return ast.literal_eval(text)

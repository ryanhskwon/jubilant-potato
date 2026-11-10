def parse_value(text):
    return eval(text, {"__builtins__": {}}, {"True": True, "False": False, "None": None})

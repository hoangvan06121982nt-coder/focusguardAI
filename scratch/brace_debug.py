with open("static/js/main.js", "r") as f:
    content = f.read()

stack = []
lines = content.split('\n')

def get_pos(idx):
    current = 0
    for i, line in enumerate(lines, 1):
        if current + len(line) + 1 > idx:
            return i, idx - current + 1
        current += len(line) + 1
    return len(lines), 1

mapping = {')': '(', '}': '{', ']': '['}
trace = []

for idx, char in enumerate(content):
    if char in '({[':
        stack.append((char, idx))
        trace.append(f"Push {char} at line {get_pos(idx)[0]}, col {get_pos(idx)[1]}")
    elif char in ')}]':
        expected = mapping[char]
        if not stack:
            line_no, col_no = get_pos(idx)
            trace.append(f"Extra closing '{char}' at line {line_no}, col {col_no}")
        else:
            top_char, top_idx = stack.pop()
            trace.append(f"Pop {top_char} (opened at line {get_pos(top_idx)[0]}, col {get_pos(top_idx)[1]}) matching '{char}' at line {get_pos(idx)[0]}, col {get_pos(idx)[1]}")
            if top_char != expected:
                line_no, col_no = get_pos(idx)
                orig_line, orig_col = get_pos(top_idx)
                print(f"Mismatched closing '{char}' at line {line_no}, col {col_no} (opened with '{top_char}' at line {orig_line}, col {orig_col})")
                print("Last 30 trace steps:")
                for step in trace[-30:]:
                    print(step)
                break

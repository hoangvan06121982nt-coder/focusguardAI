with open("static/js/main.js", "r") as f:
    lines = f.readlines()

stack = []
for i, line in enumerate(lines, 1):
    # Strip comments to avoid counting braces in comments
    clean_line = ""
    in_comment = False
    j = 0
    while j < len(line):
        if line[j:j+2] == '//':
            break
        elif line[j:j+2] == '/*':
            in_comment = True
            j += 2
            continue
        elif in_comment and line[j:j+2] == '*/':
            in_comment = False
            j += 2
            continue
        if not in_comment:
            clean_line += line[j]
        j += 1

    for col, char in enumerate(clean_line, 1):
        if char == '{':
            stack.append((i, col, line.strip()))
        elif char == '}':
            if stack:
                stack.pop()
            else:
                print(f"Line {i}: Extra closing brace found!")

# Print remaining unclosed braces and their contents
print(f"Total unclosed braces left: {len(stack)}")
for item in stack[-10:]:
    print(f"  Line {item[0]}, col {item[1]}: {item[2][:80]}")

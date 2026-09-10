"""Count status-500 lines with pure Python (10 passes, one process)."""
total = 0
for _ in range(10):
    with open("access.log", encoding="utf-8") as handle:
        for line in handle:
            if '" 500 ' in line:
                total += 1
print(total)

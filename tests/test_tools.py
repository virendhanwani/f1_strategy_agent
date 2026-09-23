from agents.tools import ALL_TOOLS

for t in ALL_TOOLS:
    print(t.name, "-", t.description.splitlines()[0])